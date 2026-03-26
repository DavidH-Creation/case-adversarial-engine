#!/usr/bin/env python3
"""
民间借贷真实案件对抗模拟脚本
Real civil loan adversarial simulation script.

案件事实 / Case facts:
  - 原告（小王）向被告（小张）出借 228,000 元，用于偿还信用卡欠款
  - 被告已还款（证据目录显示 40,500 元），尚欠本金 187,500 元
  - 原告诉请：187,500 元本金 + 年利率 13.8% 逾期利息 + 律师费 8,000 元
  - 被告抗辩：还款金额争议、利率过高、违约金超标、律师费争议

用法 / Usage::

    python scripts/run_real_case.py [--claude-only]

参数 / Args:
    --claude-only   被告也用 Claude CLI（Codex 不可用时的 fallback）

输出 / Output:
    outputs/<timestamp>/result.json   — 完整对抗结果（JSON）
    outputs/<timestamp>/report.md     — 可读的 Markdown 报告
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ── 确保 project root 在 sys.path 中 / Ensure project root is in sys.path ──────
_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from engines.adversarial.agents.defendant import DefendantAgent
from engines.adversarial.agents.evidence_mgr import EvidenceManagerAgent
from engines.adversarial.agents.plaintiff import PlaintiffAgent
from engines.adversarial.round_engine import RoundEngine
from engines.adversarial.schemas import (
    AdversarialResult,
    RoundConfig,
    RoundPhase,
    RoundState,
)
from engines.adversarial.summarizer import AdversarialSummarizer
from engines.case_structuring.evidence_indexer.indexer import EvidenceIndexer
from engines.case_structuring.issue_extractor.extractor import IssueExtractor
from engines.shared.access_control import AccessController
from engines.shared.cli_adapter import CLINotFoundError, ClaudeCLIClient, CodexCLIClient
from engines.shared.models import AgentRole, EvidenceIndex, RawMaterial


# ============================================================================
# 案件静态数据 / Static case data
# ============================================================================

CASE_ID = "case-civil-loan-wang-zhang-2026"
CASE_SLUG = "wangzhang"
PLAINTIFF_PARTY_ID = "party-plaintiff-wang"
DEFENDANT_PARTY_ID = "party-defendant-zhang"


# ── 原告原始材料 / Plaintiff raw materials ───────────────────────────────────

PLAINTIFF_MATERIALS: list[RawMaterial] = [
    RawMaterial(
        source_id="src-p-id",
        text=(
            "当事人身份信息：\n"
            "原告：王某，男，公民身份证号 110101198501011234，住北京市朝阳区。\n"
            "被告：张某，男，公民身份证号 110101199001011234，住北京市海淀区。"
        ),
        metadata={"document_type": "identity_documents", "submitter": "plaintiff"},
    ),
    RawMaterial(
        source_id="src-p-note",
        text=(
            "借条（原件）：\n"
            "今借到王某人民币贰拾贰万捌仟元整（228,000.00元），借款用途：偿还本人信用卡欠款，"
            "借款期限为2023年3月1日至2024年3月1日，"
            "逾期利息按年利率13.8%（LPR四倍）计算，"
            "逾期违约金按剩余本金的30%一次性支付。"
            "借款人：张某，2023年3月1日。"
        ),
        metadata={"document_type": "loan_note", "date": "2023-03-01", "submitter": "plaintiff"},
    ),
    RawMaterial(
        source_id="src-p-transfers-out",
        text=(
            "银行转账记录（原告出借款项）：\n"
            "2023-03-01  王某→张某  50,000元  备注：借款第一笔\n"
            "2023-03-05  王某→张某  60,000元  备注：借款第二笔\n"
            "2023-03-10  王某→张某  50,000元  备注：借款第三笔\n"
            "2023-03-15  王某→张某  38,000元  备注：借款第四笔\n"
            "2023-03-20  王某→张某  30,000元  备注：借款第五笔\n"
            "合计出借：228,000元"
        ),
        metadata={"document_type": "bank_transfer_records", "direction": "outgoing", "submitter": "plaintiff"},
    ),
    RawMaterial(
        source_id="src-p-transfers-in",
        text=(
            "银行转账记录（被告还款）：\n"
            "2023-09-01  张某→王某  20,000元  备注：还款\n"
            "2024-01-15  张某→王某  20,500元  备注：还款\n"
            "合计收到还款：40,500元\n"
            "尚欠本金：228,000 - 40,500 = 187,500元"
        ),
        metadata={"document_type": "bank_transfer_records", "direction": "incoming", "submitter": "plaintiff"},
    ),
    RawMaterial(
        source_id="src-p-lawyer-contract",
        text=(
            "律师服务合同：\n"
            "委托人：王某，受托律师：李律师（某律师事务所）。\n"
            "代理案件：民间借贷纠纷（王某诉张某案）。\n"
            "代理费：8,000元，已付清。\n"
            "签署日期：2025年10月01日。"
        ),
        metadata={"document_type": "attorney_contract", "amount": "8000", "submitter": "plaintiff"},
    ),
]


# ── 被告原始材料 / Defendant raw materials ───────────────────────────────────

DEFENDANT_MATERIALS: list[RawMaterial] = [
    RawMaterial(
        source_id="src-d-id",
        text=(
            "被告身份信息：\n"
            "张某，男，公民身份证号 110101199001011234，住北京市海淀区。"
        ),
        metadata={"document_type": "identity_documents", "submitter": "defendant"},
    ),
    RawMaterial(
        source_id="src-d-repayment-bank",
        text=(
            "被告银行转账还款凭证：\n"
            "2023-09-01  张某→王某  20,000元（与原告记录一致）\n"
            "2024-01-15  张某→王某  20,500元（与原告记录一致）\n"
            "注：上述两笔合计40,500元，原告诉状中所述30,500元与实际不符，"
            "实际还款应为40,500元，故尚欠本金为187,500元而非197,500元。"
        ),
        metadata={"document_type": "bank_transfer_records", "direction": "outgoing", "submitter": "defendant"},
    ),
    RawMaterial(
        source_id="src-d-wechat-payment",
        text=(
            "微信转账记录（被告主张额外还款）：\n"
            "2024-03-10  张某→王某微信  10,000元  备注：还钱\n"
            "2024-06-05  张某→王某微信  8,000元   备注：还款\n"
            "合计额外微信还款：18,000元\n"
            "被告主张：上述微信转账亦属还款，实际已还共计 40,500 + 18,000 = 58,500元，"
            "尚欠本金应为 228,000 - 58,500 = 169,500元。"
        ),
        metadata={"document_type": "wechat_transfer_records", "direction": "outgoing", "submitter": "defendant"},
    ),
    RawMaterial(
        source_id="src-d-interest-objection",
        text=(
            "利率及违约金异议声明：\n"
            "1. 借条约定年利率13.8%，被告认为该利率超过法律保护上限，\n"
            "   依据《最高人民法院关于审理民间借贷案件适用法律若干问题的规定》，\n"
            "   民间借贷利率不得超过合同成立时一年期贷款市场报价利率（LPR）的四倍。\n"
            "   2023年3月LPR为3.65%，四倍上限为14.6%，13.8%在法律保护范围内，\n"
            "   但主张如LPR下调导致13.8%超标，应按届时LPR四倍计算。\n"
            "2. 违约金约定30%一次性支付，明显过高，请求法院酌减至实际损失范围。\n"
            "3. 律师费8,000元系原告自行产生，请求法院不予支持或酌减。"
        ),
        metadata={"document_type": "objection_statement", "submitter": "defendant"},
    ),
]


# ── 诉请清单（dict 格式供 IssueExtractor 使用）/ Claims as dicts for IssueExtractor ──

PLAINTIFF_CLAIMS: list[dict] = [
    {
        "claim_id": "claim-001",
        "title": "返还借款本金",
        "claim_text": (
            "被告张某应偿还原告王某借款本金187,500元。"
            "（原始借款228,000元，已还40,500元，尚欠187,500元）"
        ),
        "claim_category": "返还借款",
        "case_id": CASE_ID,
        "owner_party_id": PLAINTIFF_PARTY_ID,
    },
    {
        "claim_id": "claim-002",
        "title": "支付逾期利息",
        "claim_text": (
            "被告应按年利率13.8%（LPR四倍）支付自2024年3月2日起至实际还清之日止的逾期利息。"
        ),
        "claim_category": "利息",
        "case_id": CASE_ID,
        "owner_party_id": PLAINTIFF_PARTY_ID,
    },
    {
        "claim_id": "claim-003",
        "title": "支付律师费",
        "claim_text": (
            "被告应承担原告为本案支出的合理律师费8,000元。"
        ),
        "claim_category": "律师费",
        "case_id": CASE_ID,
        "owner_party_id": PLAINTIFF_PARTY_ID,
    },
]

DEFENDANT_DEFENSES: list[dict] = [
    {
        "defense_id": "def-001",
        "title": "还款金额争议",
        "defense_text": (
            "被告已通过银行转账还款40,500元（与原告证据目录一致），"
            "且另有微信转账记录证明额外还款18,000元，实际已还合计58,500元，"
            "尚欠本金应为169,500元而非187,500元。"
        ),
        "defense_category": "还款抗辩",
        "against_claim_id": "claim-001",
        "case_id": CASE_ID,
        "owner_party_id": DEFENDANT_PARTY_ID,
    },
    {
        "defense_id": "def-002",
        "title": "利率调减请求",
        "defense_text": (
            "借条约定年利率13.8%，当LPR变动导致约定利率超过LPR四倍上限时，"
            "超出部分不受法律保护，应按届时LPR四倍调减计算。"
        ),
        "defense_category": "利率抗辩",
        "against_claim_id": "claim-002",
        "case_id": CASE_ID,
        "owner_party_id": DEFENDANT_PARTY_ID,
    },
    {
        "defense_id": "def-003",
        "title": "违约金过高请求酌减",
        "defense_text": (
            "借条约定违约金为剩余本金的30%，明显高于实际损失，"
            "请求法院依据《民法典》第585条酌减至合理范围（不超过实际损失的130%）。"
        ),
        "defense_category": "违约金抗辩",
        "against_claim_id": "claim-002",
        "case_id": CASE_ID,
        "owner_party_id": DEFENDANT_PARTY_ID,
    },
    {
        "defense_id": "def-004",
        "title": "律师费争议",
        "defense_text": (
            "律师费系原告自行产生，本案无合同约定由败诉方承担律师费的条款，"
            "请求法院不予支持原告的律师费诉请；退一步说，8,000元明显高于当地指导标准，"
            "应予酌减。"
        ),
        "defense_category": "律师费抗辩",
        "against_claim_id": "claim-003",
        "case_id": CASE_ID,
        "owner_party_id": DEFENDANT_PARTY_ID,
    },
]


# ============================================================================
# 输出工具 / Output utilities
# ============================================================================


def _outputs_dir() -> Path:
    """返回本次运行的输出目录（按时间戳创建）。"""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = _PROJECT_ROOT / "outputs" / ts
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write_result_json(out_dir: Path, result: AdversarialResult) -> Path:
    """将 AdversarialResult 序列化为 JSON 文件。"""
    path = out_dir / "result.json"
    path.write_text(
        result.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return path


def _write_markdown_report(
    out_dir: Path,
    result: AdversarialResult,
    issue_tree,
) -> Path:
    """生成可读的 Markdown 报告。"""
    path = out_dir / "report.md"
    lines: list[str] = []

    lines += [
        "# 民间借贷纠纷对抗分析报告",
        "",
        f"**案件 ID**: {result.case_id}",
        f"**运行 ID**: {result.run_id}",
        f"**生成时间**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "---",
        "",
        "## 案件概述",
        "",
        "| 项目 | 内容 |",
        "|------|------|",
        "| 原告 | 王某（小王） |",
        "| 被告 | 张某（小张） |",
        "| 借款本金 | 228,000 元 |",
        "| 已还款 | 40,500 元（银行转账，原告确认） |",
        "| 诉请本金 | 187,500 元 |",
        "| 利率 | 年利率 13.8%（LPR×4） |",
        "| 律师费 | 8,000 元 |",
        "",
        "---",
        "",
        "## 争点列表",
        "",
    ]
    for issue in issue_tree.issues:
        lines.append(f"- **[{issue.issue_id}]** {issue.title} `{issue.issue_type.value}`")
    lines += ["", "---", "", "## 三轮对抗记录", ""]

    for round_state in result.rounds:
        lines.append(f"### Round {round_state.round_number}（{round_state.phase.value}）")
        lines.append("")
        for output in round_state.outputs:
            lines.append(f"**{output.agent_role_code}** — {output.title}")
            lines.append("")
            lines.append(output.body)
            lines.append("")
            lines.append(f"*引用证据*: {', '.join(output.evidence_citations)}")
            lines.append("")
            lines.append("---")
            lines.append("")

    if result.evidence_conflicts:
        lines += ["## 证据冲突", ""]
        for c in result.evidence_conflicts:
            lines.append(f"- 争点 `{c.issue_id}`: {c.conflict_description}")
        lines.append("")

    if result.unresolved_issues:
        lines += ["## 未决争点", ""]
        for iid in result.unresolved_issues:
            lines.append(f"- `{iid}`")
        lines.append("")

    if result.summary:
        s = result.summary
        lines += ["## LLM 综合分析", "", "### 原告最强论点", ""]
        for arg in s.plaintiff_strongest_arguments:
            lines.append(f"**[{arg.issue_id}]** {arg.position}")
            lines.append(f"> *理由*: {arg.reasoning}")
            lines.append("")
        lines += ["### 被告最强抗辩", ""]
        for d in s.defendant_strongest_defenses:
            lines.append(f"**[{d.issue_id}]** {d.position}")
            lines.append(f"> *理由*: {d.reasoning}")
            lines.append("")
        lines += ["### 整体态势", "", s.overall_assessment, ""]

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ============================================================================
# 对抗轮次（手动编排，支持混合 LLM 客户端）
# Manual 3-round orchestration with mixed LLM clients.
# ============================================================================


async def _run_adversarial_rounds(
    issue_tree,
    evidence_index: EvidenceIndex,
    plaintiff_client,
    defendant_client,
    judge_client,
    config: RoundConfig,
) -> AdversarialResult:
    """手动编排三轮对抗，允许为每个 Agent 分配不同的 LLM 客户端。
    Manually orchestrate three rounds, allowing different LLM clients per agent.

    和 RoundEngine.run() 逻辑相同，但不依赖单一 llm_client。
    Same logic as RoundEngine.run() but without the single-llm-client constraint.
    """
    run_id = f"run-real-{uuid.uuid4().hex[:12]}"
    case_id = issue_tree.case_id
    all_evidence = evidence_index.evidence

    # 创建各角色代理
    plaintiff = PlaintiffAgent(plaintiff_client, PLAINTIFF_PARTY_ID, config)
    defendant = DefendantAgent(defendant_client, DEFENDANT_PARTY_ID, config)
    ev_manager = EvidenceManagerAgent(judge_client, config)

    # 按角色过滤可见证据
    access_ctrl = AccessController()
    plaintiff_evidence = access_ctrl.filter_evidence_for_agent(
        role_code=AgentRole.plaintiff_agent.value,
        owner_party_id=PLAINTIFF_PARTY_ID,
        all_evidence=all_evidence,
    )
    defendant_evidence = access_ctrl.filter_evidence_for_agent(
        role_code=AgentRole.defendant_agent.value,
        owner_party_id=DEFENDANT_PARTY_ID,
        all_evidence=all_evidence,
    )

    print(f"  原告可见证据: {len(plaintiff_evidence)} 条")
    print(f"  被告可见证据: {len(defendant_evidence)} 条")

    rounds: list[RoundState] = []
    all_outputs = []
    evidence_conflicts = []

    # ── Round 1: 首轮主张 ─────────────────────────────────────────────────
    print("\n[Round 1] 首轮主张...")
    state_id_r1 = f"state-r1-{uuid.uuid4().hex[:8]}"

    print("  原告提交主张...")
    p_claim = await plaintiff.generate_claim(
        issue_tree=issue_tree,
        visible_evidence=plaintiff_evidence,
        context_outputs=[],
        run_id=run_id,
        state_id=state_id_r1,
        round_index=1,
    )
    p_claim = p_claim.model_copy(update={"case_id": case_id})
    print(f"  ✓ 原告: {p_claim.title}")

    print("  被告提交抗辩...")
    d_claim = await defendant.generate_claim(
        issue_tree=issue_tree,
        visible_evidence=defendant_evidence,
        context_outputs=[p_claim],
        run_id=run_id,
        state_id=state_id_r1,
        round_index=1,
    )
    d_claim = d_claim.model_copy(update={"case_id": case_id})
    print(f"  ✓ 被告: {d_claim.title}")

    round1 = RoundState(round_number=1, phase=RoundPhase.claim, outputs=[p_claim, d_claim])
    rounds.append(round1)
    all_outputs.extend([p_claim, d_claim])

    # ── Round 2: 证据整理 ────────────────────────────────────────────────
    print("\n[Round 2] 证据整理...")
    state_id_r2 = f"state-r2-{uuid.uuid4().hex[:8]}"

    ev_output, conflicts = await ev_manager.analyze(
        issue_tree=issue_tree,
        evidence_index=evidence_index,
        plaintiff_outputs=[p_claim],
        defendant_outputs=[d_claim],
        run_id=run_id,
        state_id=state_id_r2,
        round_index=2,
    )
    ev_output = ev_output.model_copy(update={"case_id": case_id})
    evidence_conflicts.extend(conflicts)
    print(f"  ✓ 证据管理: {ev_output.title}，冲突 {len(conflicts)} 条")

    round2 = RoundState(round_number=2, phase=RoundPhase.evidence, outputs=[ev_output])
    rounds.append(round2)
    all_outputs.append(ev_output)

    # ── Round 3: 针对性反驳 ───────────────────────────────────────────────
    print("\n[Round 3] 针对性反驳...")
    state_id_r3 = f"state-r3-{uuid.uuid4().hex[:8]}"

    print("  原告反驳...")
    p_rebuttal = await plaintiff.generate_rebuttal(
        issue_tree=issue_tree,
        visible_evidence=plaintiff_evidence,
        context_outputs=all_outputs,
        opponent_outputs=[d_claim],
        run_id=run_id,
        state_id=state_id_r3,
        round_index=3,
    )
    p_rebuttal = p_rebuttal.model_copy(update={"case_id": case_id})
    print(f"  ✓ 原告反驳: {p_rebuttal.title}")

    print("  被告反驳...")
    d_rebuttal = await defendant.generate_rebuttal(
        issue_tree=issue_tree,
        visible_evidence=defendant_evidence,
        context_outputs=all_outputs,
        opponent_outputs=[p_claim],
        run_id=run_id,
        state_id=state_id_r3,
        round_index=3,
    )
    d_rebuttal = d_rebuttal.model_copy(update={"case_id": case_id})
    print(f"  ✓ 被告反驳: {d_rebuttal.title}")

    round3 = RoundState(round_number=3, phase=RoundPhase.rebuttal, outputs=[p_rebuttal, d_rebuttal])
    rounds.append(round3)
    all_outputs.extend([p_rebuttal, d_rebuttal])

    # ── 后处理 ─────────────────────────────────────────────────────────────
    plaintiff_best = RoundEngine._extract_best_arguments(p_claim, p_rebuttal)
    defendant_best = RoundEngine._extract_best_arguments(d_claim, d_rebuttal)
    unresolved = RoundEngine._compute_unresolved_issues(issue_tree, evidence_conflicts)
    missing_ev = RoundEngine._build_missing_evidence_report(
        issue_tree, plaintiff_evidence, defendant_evidence,
        PLAINTIFF_PARTY_ID, DEFENDANT_PARTY_ID,
    )

    result = AdversarialResult(
        case_id=case_id,
        run_id=run_id,
        rounds=rounds,
        plaintiff_best_arguments=plaintiff_best,
        defendant_best_defenses=defendant_best,
        unresolved_issues=unresolved,
        evidence_conflicts=evidence_conflicts,
        missing_evidence_report=missing_ev,
    )

    # ── LLM 总结 ─────────────────────────────────────────────────────────
    print("\n[总结] 生成 LLM 综合分析...")
    summarizer = AdversarialSummarizer(judge_client, config)
    summary = await summarizer.summarize(result, issue_tree)
    return result.model_copy(update={"summary": summary})


# ============================================================================
# 主入口 / Main entry point
# ============================================================================


async def main(claude_only: bool = False) -> None:
    """主执行流程 / Main execution flow."""
    print("=" * 60)
    print("民间借贷纠纷对抗模拟 — 真实案件运行")
    print("=" * 60)

    # ── 初始化 LLM 客户端 ─────────────────────────────────────────────────
    claude_client = ClaudeCLIClient(timeout=180.0)

    if claude_only:
        print("\n[配置] 使用 Claude CLI 作为所有代理的 LLM 后端（--claude-only 模式）")
        defendant_client = claude_client
    else:
        try:
            import shutil
            if not shutil.which("codex"):
                print("\n[警告] 未找到 codex CLI，被告代理自动降级为 Claude CLI")
                defendant_client = claude_client
            else:
                print("\n[配置] 原告/证据管理/总结 → Claude CLI；被告 → Codex CLI")
                defendant_client = CodexCLIClient(timeout=180.0)
        except CLINotFoundError:
            print("\n[警告] codex 不可用，被告代理降级为 Claude CLI")
            defendant_client = claude_client

    # ── Step 1: 索引双方证据 ──────────────────────────────────────────────
    print("\n[Step 1] 索引双方证据...")
    indexer = EvidenceIndexer(
        llm_client=claude_client,
        case_type="civil_loan",
        model="claude-opus-4-6",
        max_retries=2,
    )

    print("  索引原告证据...")
    plaintiff_evidence = await indexer.index(
        materials=PLAINTIFF_MATERIALS,
        case_id=CASE_ID,
        owner_party_id=PLAINTIFF_PARTY_ID,
        case_slug="plaintiff",
    )
    print(f"  ✓ 原告证据: {len(plaintiff_evidence)} 条")

    print("  索引被告证据...")
    defendant_evidence = await indexer.index(
        materials=DEFENDANT_MATERIALS,
        case_id=CASE_ID,
        owner_party_id=DEFENDANT_PARTY_ID,
        case_slug="defendant",
    )
    print(f"  ✓ 被告证据: {len(defendant_evidence)} 条")

    all_evidence = plaintiff_evidence + defendant_evidence
    evidence_index = EvidenceIndex(case_id=CASE_ID, evidence=all_evidence)
    print(f"  ✓ 合并证据索引: {len(all_evidence)} 条")

    # ── Step 2: 提取争点 ──────────────────────────────────────────────────
    print("\n[Step 2] 提取争点树...")
    extractor = IssueExtractor(
        llm_client=claude_client,
        case_type="civil_loan",
        model="claude-opus-4-6",
        max_retries=2,
    )

    evidence_dicts = [e.model_dump() for e in all_evidence]
    issue_tree = await extractor.extract(
        claims=PLAINTIFF_CLAIMS,
        defenses=DEFENDANT_DEFENSES,
        evidence=evidence_dicts,
        case_id=CASE_ID,
        case_slug=CASE_SLUG,
    )
    print(f"  ✓ 争点树: {len(issue_tree.issues)} 个争点, {len(issue_tree.burdens)} 个举证责任")
    for issue in issue_tree.issues:
        print(f"    - [{issue.issue_id}] {issue.title}")

    # ── Step 3: 三轮对抗 ─────────────────────────────────────────────────
    print("\n[Step 3] 开始三轮对抗辩论...")
    config = RoundConfig(
        model="claude-opus-4-6",
        max_tokens_per_output=2000,
        max_retries=2,
    )

    result = await _run_adversarial_rounds(
        issue_tree=issue_tree,
        evidence_index=evidence_index,
        plaintiff_client=claude_client,
        defendant_client=defendant_client,
        judge_client=claude_client,
        config=config,
    )

    # ── Step 4: 输出结果 ─────────────────────────────────────────────────
    print("\n[Step 4] 写入输出文件...")
    out_dir = _outputs_dir()
    json_path = _write_result_json(out_dir, result)
    md_path = _write_markdown_report(out_dir, result, issue_tree)

    print(f"\n{'=' * 60}")
    print("✓ 运行完成")
    print(f"  JSON 结果: {json_path}")
    print(f"  Markdown 报告: {md_path}")
    if result.summary:
        print(f"\n整体态势评估:")
        print(f"  {result.summary.overall_assessment[:300]}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="民间借贷真实案件对抗模拟",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--claude-only",
        action="store_true",
        help="被告也用 Claude CLI（Codex 不可用时的 fallback）",
    )
    args = parser.parse_args()
    asyncio.run(main(claude_only=args.claude_only))
