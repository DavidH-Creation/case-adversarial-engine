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
import uuid
from datetime import datetime, timezone
from pathlib import Path
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
from engines.shared.models import (
    AgentRole,
    EvidenceIndex,
    EvidenceStatus,
    IssueTree,
    RawMaterial,
)

from .schemas import CaseStatus

DEFAULT_MODEL = "claude-sonnet-4-6"


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
        # 生成的报告路径
        self.report_path: Optional[Path] = None
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
        # 已完成/失败状态直接返回
        if self.status in (CaseStatus.analyzed, CaseStatus.failed):
            return
        # 实时跟踪
        while True:
            try:
                msg = await asyncio.wait_for(
                    self._progress_queue.get(), timeout=30.0
                )
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
    def __init__(self) -> None:
        self._cases: dict[str, CaseRecord] = {}

    def create(self, info: dict[str, Any]) -> CaseRecord:
        case_id = f"case-{uuid.uuid4().hex[:12]}"
        record = CaseRecord(case_id, info)
        self._cases[case_id] = record
        return record

    def get(self, case_id: str) -> Optional[CaseRecord]:
        return self._cases.get(case_id)


# 全局单例
store = CaseStore()


# ---------------------------------------------------------------------------
# 材料转换
# ---------------------------------------------------------------------------

def build_raw_materials(mats: list[dict]) -> list[RawMaterial]:
    return [
        RawMaterial(
            source_id=m["source_id"],
            text=m["text"].strip(),
            metadata={"document_type": m.get("doc_type", "general"), "submitter": m.get("role", "")},
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
        indexer = EvidenceIndexer(llm_client=claude, case_type=case_type, model=model, max_retries=2)

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
        extractor = IssueExtractor(llm_client=claude, case_type=case_type, model=model, max_retries=2)
        ev_dicts = [e.model_dump() for e in all_ev]
        claims = claims_to_dicts(info.get("claims", []), case_id, p_id)
        defenses = defenses_to_dicts(info.get("defenses", []), case_id, d_id)

        record.log(f"[提取] 正在提取争点（{len(claims)} 项诉请，{len(defenses)} 项抗辩）…")
        record.issue_tree = await extractor.extract(claims, defenses, ev_dicts, case_id, case_slug)
        record.log(f"[提取] 争点 {len(record.issue_tree.issues)} 个，举证责任 {len(record.issue_tree.burdens)} 项")

        # 序列化供前端展示
        record.extraction_data = {
            "evidence": [e.model_dump(mode="json") for e in all_ev],
            "issues": [i.model_dump(mode="json") for i in record.issue_tree.issues],
        }
        record.status = CaseStatus.extracted
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
        issue_tree, evidence_index, [p1], [d1], run_id, sid2, 2,
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
        issue_tree, p_ev, d_ev, plaintiff_id, defendant_id,
    )

    result = AdversarialResult(
        case_id=case_id, run_id=run_id, rounds=rounds,
        plaintiff_best_arguments=p_best, defendant_best_defenses=d_best,
        unresolved_issues=unresolved, evidence_conflicts=conflicts,
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
            record, record.issue_tree, record.ev_index,
            claude, config, p_id, d_id,
        )

        cited_ids: set[str] = set()
        for rd in result.rounds:
            for o in rd.outputs:
                cited_ids.update(o.evidence_citations)
        promoted = 0
        for ev in record.ev_index.evidence:
            if ev.evidence_id in cited_ids and ev.status == EvidenceStatus.private:
                ev.status = EvidenceStatus.admitted_for_discussion
                promoted += 1
        record.log(f"[分析] 证据提升至 admitted_for_discussion：{promoted}/{len(record.ev_index.evidence)}")

        # 序列化分析结果
        result_dict = json.loads(result.model_dump_json())
        summary = result.summary

        record.analysis_data = {
            "overall_assessment": summary.overall_assessment if summary else None,
            "plaintiff_args": [a.model_dump(mode="json") for a in summary.plaintiff_strongest_arguments] if summary else [],
            "defendant_defenses": [d.model_dump(mode="json") for d in summary.defendant_strongest_defenses] if summary else [],
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

        record.status = CaseStatus.analyzed
        record.log("[分析] 完成 ✓")

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
