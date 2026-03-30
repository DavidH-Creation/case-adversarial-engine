"""
FastAPI 主应用 — 渐进式案件录入 Web 服务。
FastAPI main application — progressive case intake web service.

启动方式 / Start:
    cd <project_root>
    uvicorn api.app:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .schemas import (
    AddMaterialRequest,
    AddMaterialResponse,
    AnalysisResponse,
    CaseInfoResponse,
    CaseStatus,
    ConfirmRequest,
    CreateCaseRequest,
    CreateCaseResponse,
    ExtractionResponse,
)
from .service import run_analysis, run_extraction, store

# ---------------------------------------------------------------------------
# 应用初始化
# ---------------------------------------------------------------------------

app = FastAPI(
    title="案件对抗分析系统",
    description="渐进式案件录入与 AI 对抗分析 API",
    version="1.0.0",
)

_STATIC_DIR = Path(__file__).parent / "static"


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _get_case_or_404(case_id: str):
    record = store.get(case_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"案件不存在：{case_id}")
    return record


def _require_status(record, *allowed: CaseStatus, detail: str = "当前状态不允许该操作"):
    if record.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"{detail}（当前状态：{record.status.value}，"
                   f"需要：{' 或 '.join(s.value for s in allowed)}）",
        )


# ---------------------------------------------------------------------------
# POST /api/cases/ — 创建新案件
# ---------------------------------------------------------------------------

@app.post("/api/cases/", response_model=CreateCaseResponse, status_code=201)
async def create_case(body: CreateCaseRequest) -> CreateCaseResponse:
    """创建新案件，返回 case_id。"""
    info: dict[str, Any] = {
        "case_type": body.case_type,
        "plaintiff": body.plaintiff.model_dump(),
        "defendant": body.defendant.model_dump(),
        "claims": [c.model_dump() for c in body.claims],
        "defenses": [d.model_dump() for d in body.defenses],
    }
    record = store.create(info)
    return CreateCaseResponse(case_id=record.case_id, status=record.status)


# ---------------------------------------------------------------------------
# GET /api/cases/{case_id} — 获取案件状态
# ---------------------------------------------------------------------------

@app.get("/api/cases/{case_id}", response_model=CaseInfoResponse)
async def get_case(case_id: str) -> CaseInfoResponse:
    """获取案件当前状态、基本信息和进度日志。"""
    record = _get_case_or_404(case_id)
    return CaseInfoResponse(
        case_id=record.case_id,
        status=record.status,
        info=record.info,
        progress=record.progress,
        error=record.error,
        has_extraction=record.extraction_data is not None,
        has_analysis=record.analysis_data is not None,
    )


# ---------------------------------------------------------------------------
# POST /api/cases/{case_id}/materials — 上传原始材料（文本 or 文件）
# ---------------------------------------------------------------------------

@app.post("/api/cases/{case_id}/materials", response_model=AddMaterialResponse)
async def add_material_json(case_id: str, body: AddMaterialRequest) -> AddMaterialResponse:
    """通过 JSON 添加文本材料（最常用方式）。"""
    record = _get_case_or_404(case_id)
    _require_status(record, CaseStatus.created, CaseStatus.extracted, CaseStatus.confirmed,
                    detail="只能在案件创建后或提取完成后添加材料")

    role = body.role.lower()
    if role not in ("plaintiff", "defendant"):
        raise HTTPException(status_code=400, detail="role 必须是 plaintiff 或 defendant")

    mat = {
        "source_id": body.source_id,
        "role": role,
        "doc_type": body.doc_type,
        "text": body.text,
    }
    record.materials[role].append(mat)
    # 若已有提取结果，重置为创建状态（需重新提取）
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
    """通过文件上传添加材料（支持 .txt；PDF/Word 仅存元数据，建议使用 JSON 接口直接粘贴文本）。"""
    record = _get_case_or_404(case_id)
    _require_status(record, CaseStatus.created, CaseStatus.extracted, CaseStatus.confirmed,
                    detail="只能在案件创建后或提取完成后添加材料")

    role = role.lower()
    if role not in ("plaintiff", "defendant"):
        raise HTTPException(status_code=400, detail="role 必须是 plaintiff 或 defendant")

    raw = await file.read()
    filename = file.filename or "upload"
    # 尝试 UTF-8 解码（txt 文件）；否则用文件名作占位
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = f"[上传文件：{filename}，共 {len(raw)} 字节。请在提取前确保引擎能处理该格式，或改用 JSON 接口粘贴文本。]"

    sid = source_id or f"src-{filename[:20]}"
    mat = {"source_id": sid, "role": role, "doc_type": doc_type, "text": text}
    record.materials[role].append(mat)

    if record.status in (CaseStatus.extracted, CaseStatus.confirmed):
        record.status = CaseStatus.created
        record.extraction_data = None
        record.ev_index = None
        record.issue_tree = None

    return AddMaterialResponse(
        source_id=sid, role=role, doc_type=doc_type, char_count=len(text)
    )


# ---------------------------------------------------------------------------
# POST /api/cases/{case_id}/extract — 触发 AI 提取
# ---------------------------------------------------------------------------

@app.post("/api/cases/{case_id}/extract", status_code=202)
async def trigger_extraction(case_id: str) -> dict:
    """触发证据索引 + 争点提取（异步后台任务）。"""
    record = _get_case_or_404(case_id)
    _require_status(record, CaseStatus.created, detail="只能在案件创建后触发提取")

    total_mats = len(record.materials["plaintiff"]) + len(record.materials["defendant"])
    if total_mats == 0:
        raise HTTPException(status_code=400, detail="请先上传至少一份材料再触发提取")

    # 重置队列
    record._progress_queue = asyncio.Queue()
    asyncio.create_task(run_extraction(record))
    return {"case_id": case_id, "status": CaseStatus.extracting.value, "message": "提取任务已启动"}


# ---------------------------------------------------------------------------
# GET /api/cases/{case_id}/extraction — 获取提取结果
# ---------------------------------------------------------------------------

@app.get("/api/cases/{case_id}/extraction", response_model=ExtractionResponse)
async def get_extraction(case_id: str) -> ExtractionResponse:
    """获取 AI 提取的证据和争点（提取完成后可用）。"""
    record = _get_case_or_404(case_id)
    if record.status == CaseStatus.extracting:
        raise HTTPException(status_code=202, detail="提取正在进行中，请稍后再试")
    if record.status == CaseStatus.failed:
        raise HTTPException(status_code=500, detail=f"提取失败：{record.error}")
    if record.extraction_data is None:
        raise HTTPException(status_code=400, detail="尚未执行提取，请先调用 POST /extract")

    return ExtractionResponse(
        status=record.status,
        evidence=record.extraction_data.get("evidence", []),
        issues=record.extraction_data.get("issues", []),
    )


# ---------------------------------------------------------------------------
# POST /api/cases/{case_id}/confirm — 确认/修正提取结果
# ---------------------------------------------------------------------------

@app.post("/api/cases/{case_id}/confirm", status_code=200)
async def confirm_extraction(case_id: str, body: ConfirmRequest) -> dict:
    """
    用户确认（或修正）AI 提取的争点和证据。
    修正后的争点 title/description 会写回 IssueTree，供后续分析使用。
    """
    record = _get_case_or_404(case_id)
    _require_status(record, CaseStatus.extracted, CaseStatus.confirmed,
                    detail="只能在提取完成后确认")

    # 将用户编辑的 issue title/description 写回 IssueTree
    if body.issues and record.issue_tree:
        edits = {item["issue_id"]: item for item in body.issues if "issue_id" in item}
        for iss in record.issue_tree.issues:
            if iss.issue_id in edits:
                edit = edits[iss.issue_id]
                if "title" in edit:
                    iss.title = edit["title"]
                if "description" in edit:
                    iss.description = edit["description"]
        # 更新 extraction_data 中的 issues
        if record.extraction_data:
            record.extraction_data["issues"] = [
                i.model_dump(mode="json") for i in record.issue_tree.issues
            ]

    record.status = CaseStatus.confirmed
    return {"case_id": case_id, "status": CaseStatus.confirmed.value, "message": "确认成功，可启动分析"}


# ---------------------------------------------------------------------------
# POST /api/cases/{case_id}/analyze — 启动完整分析
# ---------------------------------------------------------------------------

@app.post("/api/cases/{case_id}/analyze", status_code=202)
async def trigger_analysis(case_id: str) -> dict:
    """触发三轮对抗辩论 + LLM 总结（异步后台任务）。"""
    record = _get_case_or_404(case_id)
    _require_status(
        record,
        CaseStatus.extracted, CaseStatus.confirmed,
        detail="请先完成提取（并可选地确认结果）再启动分析",
    )
    if record.ev_index is None or record.issue_tree is None:
        raise HTTPException(status_code=400, detail="提取数据不完整，请重新提取")

    asyncio.create_task(run_analysis(record))
    return {"case_id": case_id, "status": CaseStatus.analyzing.value, "message": "分析任务已启动"}


# ---------------------------------------------------------------------------
# GET /api/cases/{case_id}/analysis — SSE 流式进度 + 结果
# ---------------------------------------------------------------------------

@app.get("/api/cases/{case_id}/analysis")
async def stream_analysis(case_id: str):
    """
    Server-Sent Events 流：实时推送分析进度，分析完成后发送最终结果。

    事件格式：
      data: {"type": "progress", "message": "..."}
      data: {"type": "done", "result": {...}}
      data: {"type": "error", "message": "..."}
      data: {"type": "ping"}
    """
    record = _get_case_or_404(case_id)

    async def event_stream():
        # 回放历史进度
        for msg in record.progress:
            yield f"data: {json.dumps({'type': 'progress', 'message': msg}, ensure_ascii=False)}\n\n"

        # 已完成或已失败 — 直接返回结果
        if record.status == CaseStatus.analyzed:
            payload = json.dumps(
                {"type": "done", "result": record.analysis_data}, ensure_ascii=False
            )
            yield f"data: {payload}\n\n"
            return

        if record.status == CaseStatus.failed:
            payload = json.dumps(
                {"type": "error", "message": record.error or "未知错误"}, ensure_ascii=False
            )
            yield f"data: {payload}\n\n"
            return

        if record.status not in (CaseStatus.analyzing,):
            yield f"data: {json.dumps({'type': 'error', 'message': '分析尚未启动，请先调用 POST /analyze'}, ensure_ascii=False)}\n\n"
            return

        # 实时跟踪
        async for msg in record.iter_progress():
            if msg == "__ping__":
                yield f"data: {json.dumps({'type': 'ping'}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'progress', 'message': msg}, ensure_ascii=False)}\n\n"

        # 流结束后发送最终结果
        if record.status == CaseStatus.analyzed:
            payload = json.dumps(
                {"type": "done", "result": record.analysis_data}, ensure_ascii=False
            )
            yield f"data: {payload}\n\n"
        else:
            payload = json.dumps(
                {"type": "error", "message": record.error or "分析异常终止"}, ensure_ascii=False
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


# ---------------------------------------------------------------------------
# GET /api/cases/{case_id}/report — 下载 DOCX 报告
# ---------------------------------------------------------------------------

@app.get("/api/cases/{case_id}/report")
async def download_report(case_id: str):
    """下载 Word 格式分析报告（分析完成后可用）。"""
    record = _get_case_or_404(case_id)
    if record.status != CaseStatus.analyzed:
        raise HTTPException(status_code=400, detail="分析尚未完成，无法下载报告")
    if record.report_path is None or not record.report_path.exists():
        raise HTTPException(status_code=404, detail="报告文件不存在（可能生成失败）")

    return FileResponse(
        path=str(record.report_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"case_{case_id[-8:]}_report.docx",
    )


# ---------------------------------------------------------------------------
# 静态文件 + 前端入口
# ---------------------------------------------------------------------------

@app.get("/")
async def serve_frontend():
    return FileResponse(str(_STATIC_DIR / "index.html"))


# 挂载其余静态资源（CSS/JS 等，预留扩展）
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
