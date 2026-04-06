"""
FastAPI application for the case adversarial analysis service.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .auth import verify_token
from .schemas import (
    AddMaterialRequest,
    AddMaterialResponse,
    CaseInfoResponse,
    CaseListEntry,
    CaseListQuery,
    CaseListResponse,
    CaseStatus,
    ConfirmRequest,
    CreateCaseRequest,
    CreateCaseResponse,
    DiffEntryResponse,
    ExtractionResponse,
    ScenarioDiffResponse,
    ScenarioRunRequest,
)
from .service import (
    _WORKSPACE_BASE,
    case_index,
    get_artifact,
    list_artifacts,
    run_analysis,
    run_extraction,
    scenario_service,
    store,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: rebuild case index from disk
    if _WORKSPACE_BASE is not None:
        n = case_index.scan_from_disk(_WORKSPACE_BASE)
        logger.info("案件索引重建完成，共 %d 条", n)
    yield
    # Shutdown: no cleanup needed


app = FastAPI(
    title="案件对抗分析系统",
    description="渐进式案件录入与 AI 对抗分析 API",
    version="1.0.0",
    dependencies=[Depends(verify_token)],
    lifespan=lifespan,
)

_STATIC_DIR = Path(__file__).parent / "static"


def _get_case_or_404(case_id: str):
    record = store.get(case_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"案件不存在: {case_id}")
    return record


def _require_status(record, *allowed: CaseStatus, detail: str = "当前状态不允许该操作"):
    if record.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{detail}（当前状态: {record.status.value}，"
                f"需要: {' / '.join(s.value for s in allowed)}）"
            ),
        )


@app.post("/api/cases/", response_model=CreateCaseResponse, status_code=201)
async def create_case(body: CreateCaseRequest) -> CreateCaseResponse:
    info: dict[str, Any] = {
        "case_type": body.case_type,
        "plaintiff": body.plaintiff.model_dump(),
        "defendant": body.defendant.model_dump(),
        "claims": [c.model_dump() for c in body.claims],
        "defenses": [d.model_dump() for d in body.defenses],
    }
    record = store.create(info)
    return CreateCaseResponse(case_id=record.case_id, status=record.status)


@app.get("/api/cases", response_model=CaseListResponse)
async def list_cases(q: CaseListQuery = Depends()) -> CaseListResponse:
    entries, total = case_index.query(
        status=q.status.value if q.status else None,
        case_type=q.case_type,
        from_date=q.from_date,
        to_date=q.to_date,
        page=q.page,
        page_size=q.page_size,
        sort=q.sort,
    )
    return CaseListResponse(
        items=[CaseListEntry.model_validate(e) for e in entries],
        total=total,
        page=q.page,
        page_size=q.page_size,
    )


@app.get("/api/cases/{case_id}", response_model=CaseInfoResponse)
async def get_case(case_id: str) -> CaseInfoResponse:
    record = _get_case_or_404(case_id)
    return CaseInfoResponse(
        case_id=record.case_id,
        status=record.status,
        info=record.info,
        progress=record.progress,
        error=record.error,
        has_extraction=record.extraction_data is not None,
        has_analysis=record.analysis_data is not None,
        run_id=record.run_id,
    )


@app.post("/api/cases/{case_id}/materials", response_model=AddMaterialResponse)
async def add_material_json(case_id: str, body: AddMaterialRequest) -> AddMaterialResponse:
    record = _get_case_or_404(case_id)
    _require_status(
        record,
        CaseStatus.created,
        CaseStatus.extracted,
        CaseStatus.confirmed,
        detail="只能在案件创建后或提取完成后添加材料",
    )

    role = body.role.lower()
    if role not in ("plaintiff", "defendant"):
        raise HTTPException(status_code=400, detail="role 必须是 plaintiff 或 defendant")

    material = {
        "source_id": body.source_id,
        "role": role,
        "doc_type": body.doc_type,
        "text": body.text,
    }
    record.materials[role].append(material)

    if record.status in (CaseStatus.extracted, CaseStatus.confirmed):
        record.status = CaseStatus.created
        record.extraction_data = None
        record.ev_index = None
        record.issue_tree = None

    return AddMaterialResponse(
        source_id=body.source_id,
        role=role,
        doc_type=body.doc_type,
        char_count=len(body.text),
    )


@app.post("/api/cases/{case_id}/materials/upload", response_model=AddMaterialResponse)
async def upload_material_file(
    case_id: str,
    file: UploadFile = File(...),
    role: str = Form(...),
    doc_type: str = Form("general"),
    source_id: str = Form(""),
) -> AddMaterialResponse:
    record = _get_case_or_404(case_id)
    _require_status(
        record,
        CaseStatus.created,
        CaseStatus.extracted,
        CaseStatus.confirmed,
        detail="只能在案件创建后或提取完成后添加材料",
    )

    role = role.lower()
    if role not in ("plaintiff", "defendant"):
        raise HTTPException(status_code=400, detail="role 必须是 plaintiff 或 defendant")

    raw = await file.read()
    filename = file.filename or "upload"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = (
            f"[上传文件: {filename}，共 {len(raw)} 字节。"
            "请在提取前确保引擎可处理该格式，或改用 JSON 接口粘贴文本。]"
        )

    sid = source_id or f"src-{filename[:20]}"
    record.materials[role].append(
        {
            "source_id": sid,
            "role": role,
            "doc_type": doc_type,
            "text": text,
        }
    )

    if record.status in (CaseStatus.extracted, CaseStatus.confirmed):
        record.status = CaseStatus.created
        record.extraction_data = None
        record.ev_index = None
        record.issue_tree = None

    return AddMaterialResponse(source_id=sid, role=role, doc_type=doc_type, char_count=len(text))


@app.post("/api/cases/{case_id}/extract", status_code=202)
async def trigger_extraction(case_id: str) -> dict:
    record = _get_case_or_404(case_id)
    if record.status != CaseStatus.extracting:
        _require_status(record, CaseStatus.created, detail="只能在案件创建后触发提取")

    total_mats = len(record.materials["plaintiff"]) + len(record.materials["defendant"])
    if total_mats == 0:
        raise HTTPException(status_code=400, detail="请先上传至少一份材料再触发提取")

    record, started = store.try_start_extraction(case_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"案件不存在: {case_id}")
    if not started and record.status != CaseStatus.extracting:
        _require_status(record, CaseStatus.created, detail="只能在案件创建后触发提取")
    if started:
        asyncio.create_task(run_extraction(record))
        message = "提取任务已启动"
    else:
        message = "提取任务正在进行中"
    return {"case_id": case_id, "status": CaseStatus.extracting.value, "message": message}


@app.get("/api/cases/{case_id}/extraction", response_model=ExtractionResponse)
async def get_extraction(case_id: str) -> ExtractionResponse:
    record = _get_case_or_404(case_id)
    if record.status == CaseStatus.extracting:
        raise HTTPException(status_code=202, detail="提取正在进行中，请稍后再试")
    if record.status == CaseStatus.failed:
        raise HTTPException(status_code=500, detail=f"提取失败: {record.error}")
    if record.extraction_data is None:
        raise HTTPException(status_code=400, detail="尚未执行提取，请先调用 POST /extract")

    return ExtractionResponse(
        status=record.status,
        evidence=record.extraction_data.get("evidence", []),
        issues=record.extraction_data.get("issues", []),
    )


@app.post("/api/cases/{case_id}/confirm", status_code=200)
async def confirm_extraction(case_id: str, body: ConfirmRequest) -> dict:
    record = _get_case_or_404(case_id)
    _require_status(
        record,
        CaseStatus.extracted,
        CaseStatus.confirmed,
        detail="只能在提取完成后确认",
    )

    if body.issues and record.issue_tree:
        edits = {item["issue_id"]: item for item in body.issues if "issue_id" in item}
        for issue in record.issue_tree.issues:
            if issue.issue_id in edits:
                edit = edits[issue.issue_id]
                if "title" in edit:
                    issue.title = edit["title"]
                if "description" in edit:
                    issue.description = edit["description"]
        if record.extraction_data:
            record.extraction_data["issues"] = [
                issue.model_dump(mode="json") for issue in record.issue_tree.issues
            ]

    record.status = CaseStatus.confirmed
    return {
        "case_id": case_id,
        "status": CaseStatus.confirmed.value,
        "message": "确认成功，可启动分析",
    }


@app.post("/api/cases/{case_id}/analyze", status_code=202)
async def trigger_analysis(case_id: str) -> dict:
    record = _get_case_or_404(case_id)
    if record.status != CaseStatus.analyzing:
        _require_status(
            record,
            CaseStatus.extracted,
            CaseStatus.confirmed,
            detail="请先完成提取（并可选地确认结果）再启动分析",
        )
    if record.ev_index is None or record.issue_tree is None:
        raise HTTPException(status_code=400, detail="提取数据不完整，请重新提取")

    record, started = store.try_start_analysis(case_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"案件不存在: {case_id}")
    if not started and record.status != CaseStatus.analyzing:
        _require_status(
            record,
            CaseStatus.extracted,
            CaseStatus.confirmed,
            detail="请先完成提取（并可选地确认结果）再启动分析",
        )
    if started:
        asyncio.create_task(run_analysis(record))
        message = "分析任务已启动"
    else:
        message = "分析任务正在进行中"
    return {"case_id": case_id, "status": CaseStatus.analyzing.value, "message": message}


@app.get("/api/cases/{case_id}/analysis")
async def stream_analysis(case_id: str):
    record = _get_case_or_404(case_id)

    async def event_stream():
        if record.status == CaseStatus.analyzed:
            payload = json.dumps(
                {"type": "done", "result": record.analysis_data}, ensure_ascii=False
            )
            yield f"data: {payload}\n\n"
            return

        if record.status == CaseStatus.failed:
            payload = json.dumps(
                {"type": "error", "message": record.error or "未知错误"},
                ensure_ascii=False,
            )
            yield f"data: {payload}\n\n"
            return

        if record.status != CaseStatus.analyzing:
            payload = json.dumps(
                {"type": "error", "message": "分析尚未启动，请先调用 POST /analyze"},
                ensure_ascii=False,
            )
            yield f"data: {payload}\n\n"
            return

        async for msg in record.iter_progress():
            if msg == "__ping__":
                yield f"data: {json.dumps({'type': 'ping'}, ensure_ascii=False)}\n\n"
            else:
                yield (
                    "data: "
                    f"{json.dumps({'type': 'progress', 'message': msg}, ensure_ascii=False)}\n\n"
                )

        if record.status == CaseStatus.analyzed:
            payload = json.dumps(
                {"type": "done", "result": record.analysis_data}, ensure_ascii=False
            )
            yield f"data: {payload}\n\n"
        else:
            payload = json.dumps(
                {"type": "error", "message": record.error or "分析异常终止"},
                ensure_ascii=False,
            )
            yield f"data: {payload}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/cases/{case_id}/progress")
async def stream_pipeline_progress(case_id: str):
    from engines.shared.progress_reporter import get_progress_queue

    queue = get_progress_queue(case_id)
    if queue is None:
        raise HTTPException(
            status_code=404,
            detail=f"No progress stream registered for case_id: {case_id}",
        )

    async def event_stream():
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'ping'}, ensure_ascii=False)}\n\n"
                continue
            if event is None:
                yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                break
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/cases/{case_id}/report")
async def download_report(case_id: str):
    record = _get_case_or_404(case_id)
    if record.status != CaseStatus.analyzed:
        raise HTTPException(status_code=400, detail="分析尚未完成，无法下载报告")
    if record.report_path is None or not record.report_path.exists():
        raise HTTPException(status_code=404, detail="报告文件不存在")

    return FileResponse(
        path=str(record.report_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"case_{case_id[-8:]}_report.docx",
    )


def _build_scenario_diff_response(result: dict) -> ScenarioDiffResponse:
    scenario = result["scenario"]
    diff_summary = scenario.get("diff_summary") or []
    diff_entries = [
        DiffEntryResponse(
            issue_id=entry["issue_id"],
            impact_description=entry["impact_description"],
            direction=(
                entry["direction"]
                if isinstance(entry["direction"], str)
                else str(entry["direction"])
            ),
        )
        for entry in diff_summary
        if isinstance(entry, dict)
    ]
    return ScenarioDiffResponse(
        scenario_id=scenario["scenario_id"],
        case_id=scenario["case_id"],
        baseline_run_id=scenario["baseline_run_id"],
        diff_entries=diff_entries,
        affected_issue_ids=scenario.get("affected_issue_ids", []),
        affected_evidence_ids=scenario.get("affected_evidence_ids", []),
        status=scenario["status"],
    )


@app.post("/api/scenarios/run", response_model=ScenarioDiffResponse, status_code=200)
async def run_scenario(body: ScenarioRunRequest) -> ScenarioDiffResponse:
    try:
        result = await scenario_service.run(
            run_id=body.run_id,
            change_set=[change.model_dump() for change in body.change_set],
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _build_scenario_diff_response(result)


@app.get("/api/scenarios/{scenario_id}", response_model=ScenarioDiffResponse)
async def get_scenario(scenario_id: str) -> ScenarioDiffResponse:
    result = scenario_service.get(scenario_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"scenario_id 不存在: {scenario_id}")
    return _build_scenario_diff_response(result)


@app.get("/api/cases/{case_id}/artifacts")
async def list_case_artifacts(case_id: str):
    record = store.get(case_id)
    if record is None:
        return JSONResponse(
            status_code=404,
            content={"error": f"案件不存在: {case_id}", "code": 404},
        )
    return {"case_id": case_id, "artifacts": list_artifacts(record)}


@app.get("/api/cases/{case_id}/artifacts/{artifact_name}")
async def get_case_artifact(case_id: str, artifact_name: str):
    record = store.get(case_id)
    if record is None:
        return JSONResponse(
            status_code=404,
            content={"error": f"案件不存在: {case_id}", "code": 404},
        )
    artifact = get_artifact(record, artifact_name)
    if artifact is None:
        return JSONResponse(
            status_code=404,
            content={"error": f"产物尚不可用: {artifact_name}", "code": 404},
        )
    return artifact


@app.get("/api/cases/{case_id}/report/markdown")
async def get_markdown_report(case_id: str):
    record = store.get(case_id)
    if record is None:
        return JSONResponse(
            status_code=404,
            content={"error": f"案件不存在: {case_id}", "code": 404},
        )
    if record.report_markdown is None:
        return JSONResponse(
            status_code=404,
            content={"error": "报告尚不可用，请先完成分析", "code": 404},
        )
    return Response(content=record.report_markdown, media_type="text/markdown")


@app.get("/")
async def serve_frontend():
    return FileResponse(str(_STATIC_DIR / "index.html"))


if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
