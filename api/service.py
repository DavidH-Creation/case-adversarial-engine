"""
业务逻辑层 — 桥接 FastAPI 和现有对抗式分析引擎。
Service layer — bridges FastAPI endpoints and the existing adversarial engine.

运行逻辑 / Runtime flow:
  POST /cases/         → CaseRecord 创建
  POST /materials      → 追加原始材料文本
  POST /extract        → asyncio.create_task(_run_extraction)
                         EvidenceIndexer + IssueExtractor
  POST /confirm        → 用户编辑后的争点写回 IssueTree
  POST /analyze        → asyncio.create_task(_run_analysis)
                         三轮对抗辩论 + LLM 总结
  GET  /analysis (SSE) → record._progress_queue 驱动的事件流
  GET  /report         → 返回 outputs/<ts>/report.docx 字节
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Optional

# ── 项目根目录注入 sys.path ──────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ── 引擎导入 ─────────────────────────────────────────────────────────────────
from engines.adversarial.agents.defendant import DefendantAgent
from engines.adversarial.agents.evidence_mgr import EvidenceManagerAgent
from engines.adversarial.agents.plaintiff import PlaintiffAgent
from engines.adversarial.round_engine import RoundEngine
from engines.adversarial.schemas import AdversarialResult, RoundConfig, RoundPhase, RoundState
from engines.adversarial.summarizer import AdversarialSummarizer
from engines.case_structuring.evidence_indexer.indexer import EvidenceIndexer
from engines.case_structuring.issue_extractor.extractor import IssueExtractor
from engines.shared.access_control import AccessController
from engines.shared.cli_adapter import ClaudeCLIClient
from engines.shared.evidence_state_machine import EvidenceStateMachine
from engines.shared.models import (
    AgentRole,
    EvidenceIndex,
    EvidenceStatus,
    IssueTree,
    RawMaterial,
    WorkflowStage,
)
from engines.shared.workspace_manager import WorkspaceManager

from .schemas import CaseStatus

DEFAULT_MODEL = "claude-sonnet-4-6"

# Workspace base dir for API case persistence (Unit 6).
# Set to None to disable workspace writes (useful in tests).
_WORKSPACE_BASE: Optional[Path] = _PROJECT_ROOT / "workspaces" / "api"


# ---------------------------------------------------------------------------
# CaseRecord — 单案件运行时状态
# ---------------------------------------------------------------------------


class CaseRecord:
    """单案件的运行时状态容器。线程/任务安全性由 asyncio 单线程保证。"""

    def __init__(self, case_id: str, info: dict[str, Any]) -> None:
        self.case_id = case_id
        self.status = CaseStatus.created
        self.info = info  # case_type, plaintiff, defendant, claims, defenses
        # 原始材料按角色分组: {"plaintiff": [...], "defendant": [...]}
        self.materials: dict[str, list[dict]] = {"plaintiff": [], "defendant": []}
        # 引擎对象（跨 extract / analyze 步骤共享）
        self.ev_index: Optional[EvidenceIndex] = None
        self.issue_tree: Optional[IssueTree] = None
        # API 返回给前端的提取结果（可被用户编辑后写回）
        self.extraction_data: Optional[dict] = None
        # 最终分析结果
        self.analysis_data: Optional[dict] = None
        # 本轮分析的 run_id（Unit 5: stable id for scenario API）
        self.run_id: Optional[str] = None
        # 生成的报告路径
        self.report_path: Optional[Path] = None
        # 中间产物（按文件名索引的 JSON 字典）
        self.artifacts: dict[str, Any] = {}
        # Markdown 格式报告内容
        self.report_markdown: Optional[str] = None
        # 分析 run_id（用于场景推演 baseline 定位）
        self.run_id: Optional[str] = None
        # 工作区管理器（用于持久化，进程重启后可恢复状态）
        self.workspace_manager: Optional[WorkspaceManager] = None
        # 进度日志
        self.progress: list[str] = []
        self.error: Optional[str] = None
        # SSE 进度队列（None 为终止哨兵）
        self._progress_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()

    # ── 进度 ─────────────────────────────────────────────────────────────────

    def log(self, msg: str) -> None:
        """记录进度消息并推入 SSE 队列。"""
        self.progress.append(msg)
        self._progress_queue.put_nowait(msg)

    def _signal_done(self) -> None:
        """向 SSE 流发送终止信号。"""
        self._progress_queue.put_nowait(None)

    async def iter_progress(self):
        """SSE 用异步生成器 — 先回放历史进度，再跟踪实时进度。"""
        # 先回放已有历史（重连时客户端可获取完整进度）
        for msg in self.progress:
            yield msg
        # 已完成/失败状态无需继续监听
        if self.status in (CaseStatus.analyzed, CaseStatus.failed):
            return
        # 实时跟踪
        while True:
            try:
                msg = await asyncio.wait_for(self._progress_queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                yield "__ping__"
                continue
            if msg is None:
                break
            yield msg


# ---------------------------------------------------------------------------
# CaseStore — 全局案件注册表
# ---------------------------------------------------------------------------


class CaseStore:
    def __init__(self, ttl_seconds: float = 86400, workspaces_dir: Optional[Path] = None) -> None:
        # value: (record, created_at_timestamp)
        self._cases: dict[str, tuple[CaseRecord, float]] = {}
        self._ttl = ttl_seconds
        self._lock = Lock()
        # None means "use _WORKSPACE_BASE global at call time" so patching in tests works
        self._workspaces_dir = workspaces_dir
        # TTL-evicted IDs: skip disk fallback for these (intentionally expired)
        self._evicted: set[str] = set()

    def create(self, info: dict[str, Any]) -> CaseRecord:
        case_id = f"case-{uuid.uuid4().hex[:12]}"
        record = CaseRecord(case_id, info)

        # P2-3: 初始化 WorkspaceManager 并持久化案件元数据
        ws_base = self._workspaces_dir or _WORKSPACE_BASE
        if ws_base is not None:
            try:
                wm = WorkspaceManager(ws_base, case_id)
                wm.init_workspace(info.get("case_type", "civil_loan"))
                wm.save_case_meta(
                    {
                        "case_id": case_id,
                        "info": info,
                        "status": record.status.value,
                        "materials": record.materials,
                    }
                )
                record.workspace_manager = wm
            except Exception:
                pass  # non-fatal: workspace write failure doesn't block creation

        with self._lock:
            self._cases[case_id] = (record, time.time())
            self._evicted.discard(case_id)
        return record

    def get(self, case_id: str) -> Optional[CaseRecord]:
        with self._lock:
            if case_id in self._evicted:
                return None  # TTL-evicted: never fall back to disk
            entry = self._cases.get(case_id)
            if entry is not None:
                record, created_at = entry
                if time.time() - created_at <= self._ttl:
                    return record
                # Lazy TTL eviction
                del self._cases[case_id]
                self._evicted.add(case_id)
                return None
        # Not in memory (e.g. after process restart / _cases.clear()): try disk recovery
        return self._load_from_disk(case_id, self._workspaces_dir or _WORKSPACE_BASE)

    def load_from_workspace(self, case_id: str) -> Optional["CaseRecord"]:
        """Reconstruct a CaseRecord from workspace persistence (restart recovery)."""
        ws_base = self._workspaces_dir or _WORKSPACE_BASE
        if ws_base is None:
            return None
        return self._load_from_disk(case_id, ws_base)

    def _load_from_disk(
        self, case_id: str, ws_base: Optional[Path] = None
    ) -> Optional["CaseRecord"]:
        """从 WorkspaceManager 持久化存储中恢复 CaseRecord。"""
        base = ws_base or self._workspaces_dir or _WORKSPACE_BASE
        if base is None:
            return None
        wm = WorkspaceManager(base, case_id)
        meta = wm.load_case_meta()
        if meta is None:
            return None

        from .schemas import CaseStatus as _CaseStatus

        record = CaseRecord(case_id, meta["info"])
        try:
            record.status = _CaseStatus(meta.get("status", "created"))
        except ValueError:
            record.status = _CaseStatus.created
        record.materials = meta.get("materials", {"plaintiff": [], "defendant": []})
        record.workspace_manager = wm

        # 恢复提取产物
        record.ev_index = wm.load_evidence_index()
        record.issue_tree = wm.load_issue_tree()
        if record.ev_index is not None and record.issue_tree is not None:
            record.extraction_data = {
                "evidence": [e.model_dump(mode="json") for e in record.ev_index.evidence],
                "issues": [i.model_dump(mode="json") for i in record.issue_tree.issues],
            }

        # 恢复分析产物
        analysis_path = wm.workspace_dir / "artifacts" / "analysis_data.json"
        if analysis_path.exists():
            record.analysis_data = json.loads(analysis_path.read_text(encoding="utf-8"))
            record.run_id = (record.analysis_data or {}).get("run_id")

        return record

    def evict_expired(self) -> int:
        """清理过期条目，返回清理数量。"""
        now = time.time()
        with self._lock:
            expired = [k for k, (_, t) in self._cases.items() if now - t > self._ttl]
            for k in expired:
                del self._cases[k]
                self._evicted.add(k)
            return len(expired)


# 全局单例
store = CaseStore()


# ---------------------------------------------------------------------------
# Unit 6: workspace persistence helpers
# ---------------------------------------------------------------------------


def _record_to_meta(record: "CaseRecord") -> dict:
    """Serialize durable CaseRecord fields for workspace persistence."""
    return {
        "case_id": record.case_id,
        "status": record.status.value,
        "info": record.info,
        "analysis_data": record.analysis_data,
        "run_id": record.run_id,
        "artifact_names": list(record.artifacts.keys()),
        "report_markdown": record.report_markdown,
        "error": record.error,
    }


def _persist_case_meta(record: "CaseRecord") -> None:
    """Write durable CaseRecord state to workspace (non-fatal on failure)."""
    if _WORKSPACE_BASE is None:
        return
    try:
        wm = WorkspaceManager(_WORKSPACE_BASE, record.case_id)
        wm.save_case_meta(_record_to_meta(record))
    except Exception:
        pass


def _load_case_from_workspace(case_id: str) -> Optional["CaseRecord"]:
    """Reconstruct a CaseRecord from workspace persistence for restart recovery."""
    if _WORKSPACE_BASE is None:
        return None
    try:
        wm = WorkspaceManager(_WORKSPACE_BASE, case_id)
        meta = wm.load_case_meta()
        if meta is None:
            return None
        record: CaseRecord = CaseRecord.__new__(CaseRecord)
        # Initialize asyncio-dependent fields that can't be serialized
        import asyncio as _asyncio

        record.case_id = meta["case_id"]
        record.status = CaseStatus(meta["status"])
        record.info = meta["info"]
        record.materials = {"plaintiff": [], "defendant": []}
        record.ev_index = None
        record.issue_tree = None
        record.extraction_data = None
        record.analysis_data = meta.get("analysis_data")
        record.run_id = meta.get("run_id")
        record.report_path = None
        record.artifacts = {}  # content not persisted; names only
        record.report_markdown = meta.get("report_markdown")
        record.progress = []
        record.error = meta.get("error")
        record._progress_queue = _asyncio.Queue()
        return record
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 材料转换
# ---------------------------------------------------------------------------


def build_raw_materials(mats: list[dict]) -> list[RawMaterial]:
    return [
        RawMaterial(
            source_id=m["source_id"],
            text=m["text"].strip(),
            metadata={
                "document_type": m.get("doc_type", "general"),
                "submitter": m.get("role", ""),
            },
        )
        for m in mats
        if m.get("text", "").strip()
    ]


def claims_to_dicts(claims: list[dict], case_id: str, plaintiff_id: str) -> list[dict]:
    return [{**c, "case_id": case_id, "owner_party_id": plaintiff_id} for c in claims]


def defenses_to_dicts(defenses: list[dict], case_id: str, defendant_id: str) -> list[dict]:
    return [{**d, "case_id": case_id, "owner_party_id": defendant_id} for d in defenses]


# ---------------------------------------------------------------------------
# 提取任务（Step 2）
# ---------------------------------------------------------------------------


async def run_extraction(record: CaseRecord) -> None:
    """异步后台任务：索引证据 + 提取争点。"""
    record.status = CaseStatus.extracting
    try:
        info = record.info
        case_id = record.case_id
        case_type = info.get("case_type", "civil_loan")
        model = info.get("model", DEFAULT_MODEL)
        p_id = info["plaintiff"]["party_id"]
        d_id = info["defendant"]["party_id"]
        case_slug = f"api{case_id[-8:]}"

        claude = ClaudeCLIClient(timeout=600.0)
        indexer = EvidenceIndexer(
            llm_client=claude, case_type=case_type, model=model, max_retries=2
        )

        # 索引原告证据
        p_mats = build_raw_materials(record.materials["plaintiff"])
        record.log(f"[提取] 正在索引原告材料（{len(p_mats)} 份）…")
        p_ev = await indexer.index(p_mats, case_id, p_id, "plaintiff") if p_mats else []
        record.log(f"[提取] 原告证据 {len(p_ev)} 条")

        # 索引被告证据
        d_mats = build_raw_materials(record.materials["defendant"])
        record.log(f"[提取] 正在索引被告材料（{len(d_mats)} 份）…")
        d_ev = await indexer.index(d_mats, case_id, d_id, "defendant") if d_mats else []
        record.log(f"[提取] 被告证据 {len(d_ev)} 条")

        all_ev = p_ev + d_ev
        record.ev_index = EvidenceIndex(case_id=case_id, evidence=all_ev)
        record.log(f"[提取] 合计证据 {len(all_ev)} 条")

        # 提取争点
        extractor = IssueExtractor(
            llm_client=claude, case_type=case_type, model=model, max_retries=2
        )
        ev_dicts = [e.model_dump() for e in all_ev]
        claims = claims_to_dicts(info.get("claims", []), case_id, p_id)
        defenses = defenses_to_dicts(info.get("defenses", []), case_id, d_id)

        record.log(f"[提取] 正在提取争点（{len(claims)} 项诉请，{len(defenses)} 项抗辩）…")
        record.issue_tree = await extractor.extract(claims, defenses, ev_dicts, case_id, case_slug)
        record.log(
            f"[提取] 争点 {len(record.issue_tree.issues)} 个，举证责任 {len(record.issue_tree.burdens)} 项"
        )

        # 序列化供前端展示
        record.extraction_data = {
            "evidence": [e.model_dump(mode="json") for e in all_ev],
            "issues": [i.model_dump(mode="json") for i in record.issue_tree.issues],
        }
        record.status = CaseStatus.extracted

        # P2-3: 持久化提取产物到工作区
        if record.workspace_manager is not None:
            record.workspace_manager.save_evidence_index(record.ev_index)
            record.workspace_manager.save_issue_tree(record.issue_tree)
            record.workspace_manager.save_case_meta(
                {
                    "case_id": record.case_id,
                    "info": record.info,
                    "status": CaseStatus.extracted.value,
                    "materials": record.materials,
                }
            )

        record.log("[提取] 完成 ✓")

    except Exception as exc:
        record.status = CaseStatus.failed
        record.error = str(exc)
        record.log(f"[错误] 提取失败：{exc}")
    finally:
        record._signal_done()


# ---------------------------------------------------------------------------
# 三轮对抗辩论（内部辅助，适配自 scripts/run_case.py）
# ---------------------------------------------------------------------------


async def _run_rounds(
    record: CaseRecord,
    issue_tree,
    evidence_index: EvidenceIndex,
    claude: ClaudeCLIClient,
    config: RoundConfig,
    plaintiff_id: str,
    defendant_id: str,
) -> AdversarialResult:
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    case_id = issue_tree.case_id

    plaintiff = PlaintiffAgent(claude, plaintiff_id, config)
    defendant = DefendantAgent(claude, defendant_id, config)
    ev_mgr = EvidenceManagerAgent(claude, config)

    ac = AccessController()
    p_ev = ac.filter_evidence_for_agent(
        role_code=AgentRole.plaintiff_agent.value,
        owner_party_id=plaintiff_id,
        all_evidence=evidence_index.evidence,
    )
    d_ev = ac.filter_evidence_for_agent(
        role_code=AgentRole.defendant_agent.value,
        owner_party_id=defendant_id,
        all_evidence=evidence_index.evidence,
    )
    record.log(f"[辩论] 原告证据 {len(p_ev)} 条 | 被告证据 {len(d_ev)} 条")

    rounds, all_out, conflicts = [], [], []

    # 第一轮：开庭陈述
    record.log("[辩论] 第一轮：开庭陈述…")
    sid1 = f"state-r1-{uuid.uuid4().hex[:8]}"
    p1 = await plaintiff.generate_claim(issue_tree, p_ev, [], run_id, sid1, 1)
    p1 = p1.model_copy(update={"case_id": case_id})
    record.log(f"[辩论] 原告：{p1.title}")
    d1 = await defendant.generate_claim(issue_tree, d_ev, [p1], run_id, sid1, 1)
    d1 = d1.model_copy(update={"case_id": case_id})
    record.log(f"[辩论] 被告：{d1.title}")
    rounds.append(RoundState(round_number=1, phase=RoundPhase.claim, outputs=[p1, d1]))
    all_out += [p1, d1]

    # 第二轮：证据审查
    record.log("[辩论] 第二轮：证据审查…")
    sid2 = f"state-r2-{uuid.uuid4().hex[:8]}"
    ev_out, new_conf = await ev_mgr.analyze(
        issue_tree,
        evidence_index,
        [p1],
        [d1],
        run_id,
        sid2,
        2,
    )
    ev_out = ev_out.model_copy(update={"case_id": case_id})
    conflicts += new_conf
    record.log(f"[辩论] 证据管理员：{ev_out.title}（{len(new_conf)} 处冲突）")
    rounds.append(RoundState(round_number=2, phase=RoundPhase.evidence, outputs=[ev_out]))
    all_out.append(ev_out)

    # 第三轮：反驳
    record.log("[辩论] 第三轮：反驳…")
    sid3 = f"state-r3-{uuid.uuid4().hex[:8]}"
    p3 = await plaintiff.generate_rebuttal(issue_tree, p_ev, all_out, [d1], run_id, sid3, 3)
    p3 = p3.model_copy(update={"case_id": case_id})
    record.log(f"[辩论] 原告反驳：{p3.title}")
    d3 = await defendant.generate_rebuttal(issue_tree, d_ev, all_out, [p1], run_id, sid3, 3)
    d3 = d3.model_copy(update={"case_id": case_id})
    record.log(f"[辩论] 被告反驳：{d3.title}")
    rounds.append(RoundState(round_number=3, phase=RoundPhase.rebuttal, outputs=[p3, d3]))
    all_out += [p3, d3]

    p_best = RoundEngine._extract_best_arguments(p1, p3)
    d_best = RoundEngine._extract_best_arguments(d1, d3)
    unresolved = RoundEngine._compute_unresolved_issues(issue_tree, conflicts)
    missing = RoundEngine._build_missing_evidence_report(
        issue_tree,
        p_ev,
        d_ev,
        plaintiff_id,
        defendant_id,
    )

    result = AdversarialResult(
        case_id=case_id,
        run_id=run_id,
        rounds=rounds,
        plaintiff_best_arguments=p_best,
        defendant_best_defenses=d_best,
        unresolved_issues=unresolved,
        evidence_conflicts=conflicts,
        missing_evidence_report=missing,
    )

    record.log("[辩论] 生成 LLM 总结…")
    summarizer = AdversarialSummarizer(claude, config)
    summary = await summarizer.summarize(result, issue_tree)
    return result.model_copy(update={"summary": summary})


# ---------------------------------------------------------------------------
# 分析任务（Step 4）
# ---------------------------------------------------------------------------


async def run_analysis(record: CaseRecord) -> None:
    """异步后台任务：三轮对抗辩论 + LLM 总结 + 生成 DOCX 报告。"""
    # 重置进度队列（extract 阶段的哨兵可能还在）
    record._progress_queue = asyncio.Queue()
    record.status = CaseStatus.analyzing
    try:
        info = record.info
        model = info.get("model", DEFAULT_MODEL)
        p_id = info["plaintiff"]["party_id"]
        d_id = info["defendant"]["party_id"]

        if record.issue_tree is None or record.ev_index is None:
            raise RuntimeError("请先完成提取步骤（extract）再启动分析。")

        claude = ClaudeCLIClient(timeout=600.0)
        config = RoundConfig(model=model, max_tokens_per_output=2000, max_retries=2)

        # 将辩论中引用的证据提升至 admitted_for_discussion
        record.log("[分析] 启动三轮对抗辩论…")
        result = await _run_rounds(
            record,
            record.issue_tree,
            record.ev_index,
            claude,
            config,
            p_id,
            d_id,
        )

        # ── Unit 4: route evidence promotion through EvidenceStateMachine ──
        cited_ids: set[str] = set()
        for rd in result.rounds:
            for o in rd.outputs:
                cited_ids.update(o.evidence_citations)

        # P1-1: 通过 EvidenceStateMachine 提升被引用证据状态，确保 access_domain 同步更新。
        # private → submitted → admitted_for_discussion（两步合法迁移）
        # submitted/challenged → admitted_for_discussion（单步合法迁移）
        esm = EvidenceStateMachine()
        promoted = 0
        new_evidence = []
        for ev in record.ev_index.evidence:
            if ev.evidence_id in cited_ids:
                if ev.status == EvidenceStatus.private:
                    ev = esm.submit(ev, ev.owner_party_id)
                    ev = esm.admit(ev)
                    promoted += 1
                elif ev.status in (EvidenceStatus.submitted, EvidenceStatus.challenged):
                    ev = esm.admit(ev)
                    promoted += 1
                # EvidenceStatus.admitted_for_discussion: 终态，无需操作
            new_evidence.append(ev)
        # 用不可变副本替换证据列表，保证 access_domain 一致性
        record.ev_index = record.ev_index.model_copy(update={"evidence": new_evidence})
        record.log(
            f"[分析] 证据提升至 admitted_for_discussion：{promoted}/{len(record.ev_index.evidence)}"
        )

        # P1-2: 持久化 baseline 文件到 outputs/<run_id>/，供场景推演 API 使用。
        # 在证据状态更新后写入，确保 baseline 反映最新的 access_domain。
        run_id = result.run_id
        record.run_id = run_id
        baseline_dir = _PROJECT_ROOT / "outputs" / run_id
        baseline_dir.mkdir(parents=True, exist_ok=True)
        (baseline_dir / "issue_tree.json").write_text(
            record.issue_tree.model_dump_json(), encoding="utf-8"
        )
        (baseline_dir / "evidence_index.json").write_text(
            record.ev_index.model_dump_json(), encoding="utf-8"
        )

        # 序列化分析结果
        result_dict = json.loads(result.model_dump_json())
        summary = result.summary

        # 写入 result.json（load_baseline 用其中的 run_id 字段）
        (baseline_dir / "result.json").write_text(
            json.dumps(result_dict, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        record.log(f"[分析] baseline 已写入 outputs/{run_id}/")

        record.analysis_data = {
            "run_id": run_id,  # P1-2: 暴露给场景推演 API
            "overall_assessment": summary.overall_assessment if summary else None,
            "plaintiff_args": [
                a.model_dump(mode="json") for a in summary.plaintiff_strongest_arguments
            ]
            if summary
            else [],
            "defendant_defenses": [
                d.model_dump(mode="json") for d in summary.defendant_strongest_defenses
            ]
            if summary
            else [],
            "unresolved_issues": list(result.unresolved_issues),
            "evidence_conflicts": [c.model_dump(mode="json") for c in result.evidence_conflicts],
            "rounds": [
                {
                    "round_number": rs.round_number,
                    "phase": rs.phase.value,
                    "outputs": [
                        {
                            "agent_role_code": o.agent_role_code,
                            "title": o.title,
                            "body": o.body,
                            "evidence_citations": o.evidence_citations,
                        }
                        for o in rs.outputs
                    ],
                }
                for rs in result.rounds
            ],
        }

        # 生成 DOCX 报告（可选，依赖 python-docx）
        record.log("[分析] 生成 Word 报告…")
        try:
            from engines.report_generation.docx_generator import generate_docx_report

            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            out_dir = _PROJECT_ROOT / "outputs" / ts
            out_dir.mkdir(parents=True, exist_ok=True)
            case_data = _build_case_data_dict(record)
            docx_path = generate_docx_report(
                output_dir=out_dir,
                case_data=case_data,
                result=result_dict,
                issue_tree=record.issue_tree,
                decision_tree=None,
                attack_chain=None,
                exec_summary=None,
                amount_report=None,
            )
            record.report_path = docx_path
            record.log(f"[分析] Word 报告：{docx_path.name}")
        except Exception as doc_err:
            record.log(f"[警告] Word 报告生成失败（{doc_err}），可继续使用分析结果")

        # 存储产物
        record.artifacts["result.json"] = result_dict
        record.artifacts["analysis_summary.json"] = record.analysis_data

        # 生成 Markdown 报告
        try:
            record.report_markdown = _generate_markdown_report(record)
            record.artifacts["report.md"] = record.report_markdown
        except Exception as md_err:
            record.log(f"[警告] Markdown 报告生成失败（{md_err}），可继续使用分析结果")

        record.status = CaseStatus.analyzed

        # P2-3: 持久化分析产物和案件状态到工作区，确保进程重启后可恢复。
        if record.workspace_manager is not None:
            try:
                # 持久化更新后的证据索引（状态已由 EvidenceStateMachine 更新）
                record.workspace_manager.save_evidence_index(record.ev_index)
                # 持久化分析数据（含 run_id）
                analysis_path = (
                    record.workspace_manager.workspace_dir / "artifacts" / "analysis_data.json"
                )
                analysis_path.parent.mkdir(parents=True, exist_ok=True)
                analysis_path.write_text(
                    json.dumps(record.analysis_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                # 更新案件状态元数据
                record.workspace_manager.save_case_meta(
                    {
                        "case_id": record.case_id,
                        "info": record.info,
                        "status": CaseStatus.analyzed.value,
                        "materials": record.materials,
                    }
                )
            except Exception as ws_err:
                record.log(f"[警告] 工作区持久化失败（{ws_err}），不影响分析结果")

        record.log("[分析] 完成 ✓")

        # Unit 6: persist durable state to workspace
        _persist_case_meta(record)

    except Exception as exc:
        record.status = CaseStatus.failed
        record.error = str(exc)
        record.log(f"[错误] 分析失败：{exc}")
    finally:
        record._signal_done()


# ---------------------------------------------------------------------------
# ScenarioService — 封装 ScenarioSimulator 的 Web 服务层
# ---------------------------------------------------------------------------


class ScenarioService:
    """封装 ScenarioSimulator 调用，管理场景结果的存储和查询。"""

    def __init__(self, outputs_dir: Path) -> None:
        self._outputs_dir = outputs_dir
        self._results: dict[str, dict] = {}

    async def run(self, run_id: str, change_set: list[dict], case_type: str = "civil_loan") -> dict:
        """从 outputs/{run_id}/ 加载 baseline，执行场景推演，返回序列化的 ScenarioResult。"""
        from engines.simulation_run.schemas import ChangeItem, ScenarioInput
        from engines.simulation_run.simulator import ScenarioSimulator, load_baseline

        baseline_dir = self._outputs_dir / run_id
        if not baseline_dir.is_dir():
            raise FileNotFoundError(f"run_id 不存在: {run_id}")

        issue_tree, evidence_index, baseline_run_id = load_baseline(baseline_dir)

        scenario_id = f"scenario-{uuid.uuid4().hex[:12]}"
        new_run_id = f"run-scenario-{uuid.uuid4().hex[:12]}"
        change_items = [ChangeItem.model_validate(c) for c in change_set]
        scenario_input = ScenarioInput(
            scenario_id=scenario_id,
            baseline_run_id=baseline_run_id,
            change_set=change_items,
            workspace_id=f"workspace-{run_id}",
        )

        claude = ClaudeCLIClient(timeout=600.0)
        simulator = ScenarioSimulator(llm_client=claude, case_type=case_type, model=DEFAULT_MODEL)
        result = await simulator.simulate(scenario_input, issue_tree, evidence_index, new_run_id)

        result_dict = result.model_dump(mode="json")
        self._results[scenario_id] = result_dict

        out_dir = self._outputs_dir / f"scenario_{scenario_id}"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "diff_summary.json").write_text(
            json.dumps(result_dict, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return result_dict

    def get(self, scenario_id: str) -> Optional[dict]:
        """查询已运行 scenario 的结果（先查内存，再查磁盘）。"""
        if scenario_id in self._results:
            return self._results[scenario_id]
        diff_path = self._outputs_dir / f"scenario_{scenario_id}" / "diff_summary.json"
        if diff_path.exists():
            return json.loads(diff_path.read_text(encoding="utf-8"))
        return None


# 全局单例
scenario_service = ScenarioService(_PROJECT_ROOT / "outputs")


# ---------------------------------------------------------------------------
# 产物访问（供 API 端点调用）
# ---------------------------------------------------------------------------


def list_artifacts(record: CaseRecord) -> list[str]:
    """返回该 run 所有已就绪的产物文件名。"""
    return list(record.artifacts.keys())


def get_artifact(record: CaseRecord, name: str) -> Optional[Any]:
    """返回具体产物内容，不存在时返回 None。"""
    return record.artifacts.get(name)


# ---------------------------------------------------------------------------
# Markdown 报告生成
# ---------------------------------------------------------------------------


def _generate_markdown_report(record: CaseRecord) -> str:
    """从 analysis_data 和 case info 生成 Markdown 格式报告。"""
    info = record.info
    analysis = record.analysis_data or {}
    plaintiff_name = info.get("plaintiff", {}).get("name", "原告")
    defendant_name = info.get("defendant", {}).get("name", "被告")
    case_type = info.get("case_type", "unknown")

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        f"# {case_type} 对抗分析报告",
        "",
        f"**案件ID**: {record.case_id}  |  **生成时间**: {ts}",
        "",
        "## 案件摘要",
        "",
        "| 项目 | 内容 |",
        "|------|------|",
        f"| 原告 | {plaintiff_name} |",
        f"| 被告 | {defendant_name} |",
        f"| 案件类型 | {case_type} |",
        "",
    ]

    overall = analysis.get("overall_assessment")
    if overall:
        lines += ["## 综合评估", "", overall, ""]

    unresolved = analysis.get("unresolved_issues", [])
    if unresolved:
        lines += ["## 未解决争点", ""]
        for issue_id in unresolved:
            lines.append(f"- {issue_id}")
        lines.append("")

    rounds = analysis.get("rounds", [])
    if rounds:
        lines += ["## 三轮对抗记录", ""]
        for rd in rounds:
            lines.append(f"### Round {rd.get('round_number', '?')}（{rd.get('phase', '')}）")
            lines.append("")
            for o in rd.get("outputs", []):
                role = o.get("agent_role_code", "")
                title = o.get("title", "")
                body = o.get("body", "")
                lines.append(f"**{role}** — {title}")
                lines.append("")
                lines.append(body)
                citations = o.get("evidence_citations", [])
                if citations:
                    lines.append(f"\n*引用证据*: {', '.join(citations)}")
                lines += ["---", ""]

    conflicts = analysis.get("evidence_conflicts", [])
    if conflicts:
        lines += ["## 证据冲突", ""]
        for c in conflicts:
            issue_id = c.get("issue_id", "")
            desc = c.get("description", "")
            lines.append(f"- `{issue_id}`: {desc}")
        lines.append("")

    return "\n".join(lines)


def _build_case_data_dict(record: CaseRecord) -> dict[str, Any]:
    """将 CaseRecord.info 转换为 generate_docx_report 期望的 case_data dict。"""
    info = record.info
    return {
        "case_id": record.case_id,
        "case_slug": f"api{record.case_id[-8:]}",
        "case_type": info.get("case_type", "civil_loan"),
        "parties": {
            "plaintiff": info["plaintiff"],
            "defendant": info["defendant"],
        },
        "summary": [],
        "materials": {"plaintiff": [], "defendant": []},
        "claims": info.get("claims", []),
        "defenses": info.get("defenses", []),
        "financials": {},
    }
