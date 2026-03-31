#!/usr/bin/env python3
"""
民间借贷真实案件对抗模拟（2022年，王某诉张某）

案件：2022-02-26~27分5笔转228,000元；2022-02-28还10,000；
2022-03-01借条218,000元/3%/月还9,000/2024-03-01还清/逾期月1.3%/律师费条款；
还款争议：原告主张30,500，证据目录显示40,500（差额10,000元）；
诉请：187,500元本金 + 13.8%逾期利息 + 律师费8,000元。

用法: python scripts/run_real_case.py [--claude-only]
输出: outputs/<timestamp>/result.json  outputs/<timestamp>/report.md
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Windows 默认用 GBK 编码输出，遇到 ✓ 等 Unicode 字符会崩溃。
# 强制 UTF-8 以避免 UnicodeEncodeError。
# Windows defaults to GBK for console output; force UTF-8 to avoid UnicodeEncodeError.
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from engines.adversarial.agents.defendant import DefendantAgent
from engines.adversarial.agents.evidence_mgr import EvidenceManagerAgent
from engines.adversarial.agents.plaintiff import PlaintiffAgent
from engines.adversarial.round_engine import RoundEngine
from engines.adversarial.schemas import AdversarialResult, RoundConfig, RoundPhase, RoundState
from engines.adversarial.summarizer import AdversarialSummarizer
from engines.case_structuring.evidence_indexer.indexer import EvidenceIndexer
from engines.case_structuring.issue_extractor.extractor import IssueExtractor
from engines.shared.access_control import AccessController
from engines.shared.cli_adapter import CLINotFoundError, ClaudeCLIClient, CodexCLIClient
from engines.shared.models import (
    AgentRole,
    ClaimType,
    EvidenceIndex,
    EvidenceStatus,
    LoanTransaction,
    RawMaterial,
    RepaymentAttribution,
    RepaymentTransaction,
    DisputedAmountAttribution,
)

# Post-debate analysis modules
from decimal import Decimal
from engines.case_structuring.amount_calculator import (
    AmountCalculator,
    AmountCalculatorInput,
    AmountClaimDescriptor,
)
from engines.simulation_run.issue_impact_ranker.ranker import IssueImpactRanker
from engines.simulation_run.issue_impact_ranker.schemas import IssueImpactRankerInput
from engines.simulation_run.decision_path_tree import (
    DecisionPathTreeGenerator,
    DecisionPathTreeInput,
)
from engines.simulation_run.attack_chain_optimizer import (
    AttackChainOptimizer,
    AttackChainOptimizerInput,
)
from engines.simulation_run.action_recommender import ActionRecommender
from engines.simulation_run.action_recommender.schemas import ActionRecommenderInput
from engines.report_generation.executive_summarizer import ExecutiveSummarizer
from engines.report_generation.executive_summarizer.schemas import ExecutiveSummarizerInput

# ── 案件标识 ─────────────────────────────────────────────────────────────────
CASE_ID = "case-civil-loan-wang-zhang-2022"
CASE_SLUG = "wangzhang2022"
P_PARTY = "party-plaintiff-wang"
D_PARTY = "party-defendant-zhang"

# ── 原告证据材料 ──────────────────────────────────────────────────────────────
PLAINTIFF_MATERIALS: list[RawMaterial] = [
    RawMaterial(
        source_id="src-p-id",
        text=(
            "当事人身份信息：\n"
            "原告：王某，男，110101198501011234，住北京市朝阳区。\n"
            "被告：张某，男，110101199001011234，住北京市海淀区。"
        ),
        metadata={"document_type": "identity_documents", "submitter": "plaintiff"},
    ),
    RawMaterial(
        source_id="src-p-transfers-out",
        text=(
            "原告出借款银行转账记录（共5笔，合计228,000元）：\n"
            "2022-02-26  王某→张某  50,000元\n"
            "2022-02-26  王某→张某  60,000元\n"
            "2022-02-26  王某→张某  50,000元\n"
            "2022-02-27  王某→张某  38,000元\n"
            "2022-02-27  王某→张某  30,000元\n"
            "用途：被告偿还本人信用卡欠款，合计出借228,000元。"
        ),
        metadata={
            "document_type": "bank_transfer_records",
            "direction": "outgoing",
            "submitter": "plaintiff",
        },
    ),
    RawMaterial(
        source_id="src-p-pre-note-repayment",
        text=(
            "借条签署前还款记录：\n"
            "2022-02-28  张某→王某  10,000元  备注：还款\n"
            "该笔还款发生于借条签署前，借条本金228,000 - 10,000 = 218,000元。"
        ),
        metadata={
            "document_type": "bank_transfer_records",
            "direction": "incoming",
            "date": "2022-02-28",
            "submitter": "plaintiff",
        },
    ),
    RawMaterial(
        source_id="src-p-note",
        text=(
            "借条（原件，2022-03-01）：\n"
            "今借到王某人民币贰拾壹万捌仟元整（218,000.00元），借款用途：偿还本人信用卡欠款。\n"
            "借款期限：2022年3月1日至2024年3月1日。\n"
            "年利率3%，每月归还9,000元。\n"
            "逾期违约金：按每月剩余本金的1.3%计算。\n"
            "借款人承担出借人为追偿本借款发生的全部律师费及诉讼费用。\n"
            "借款人：张某，2022年3月1日。"
        ),
        metadata={
            "document_type": "loan_note",
            "date": "2022-03-01",
            "principal": "218000",
            "submitter": "plaintiff",
        },
    ),
    RawMaterial(
        source_id="src-p-repayments",
        text=(
            "借条签署后张某还款记录（原告主张口径，共30,500元）：\n"
            "2022-06-15  张某→王某  10,000元\n"
            "2022-12-20  张某→王某  10,000元\n"
            "2023-05-08  张某→王某  10,500元\n"
            "注：证据目录另列2023-03-30一笔10,000元，原告未计入，双方存在争议。\n"
            "按原告主张：尚欠本金 218,000 - 30,500 = 187,500元。"
        ),
        metadata={
            "document_type": "bank_transfer_records",
            "direction": "incoming",
            "submitter": "plaintiff",
        },
    ),
    RawMaterial(
        source_id="src-p-lawyer",
        text=(
            "律师服务合同：\n"
            "委托人：王某，受托律师：李律师（某律师事务所）。\n"
            "代理案件：民间借贷纠纷（王某诉张某案）。\n"
            "代理费：8,000元，已付清。签署日期：2025年10月1日。"
        ),
        metadata={"document_type": "attorney_contract", "amount": "8000", "submitter": "plaintiff"},
    ),
]

# ── 被告证据材料 ──────────────────────────────────────────────────────────────
DEFENDANT_MATERIALS: list[RawMaterial] = [
    RawMaterial(
        source_id="src-d-id",
        text="被告：张某，男，110101199001011234，住北京市海淀区。",
        metadata={"document_type": "identity_documents", "submitter": "defendant"},
    ),
    RawMaterial(
        source_id="src-d-repayments",
        text=(
            "被告银行转账还款凭证（证据目录口径，共40,500元）：\n"
            "2022-06-15  张某→王某  10,000元\n"
            "2022-12-20  张某→王某  10,000元\n"
            "2023-03-30  张某→王某  10,000元（原告诉状未计入此笔，与证据目录存矛盾）\n"
            "2023-05-08  张某→王某  10,500元\n"
            "合计：40,500元。正确剩余本金：218,000 - 40,500 = 177,500元，非原告所称187,500元。"
        ),
        metadata={
            "document_type": "bank_transfer_records",
            "direction": "outgoing",
            "submitter": "defendant",
        },
    ),
    RawMaterial(
        source_id="src-d-objections",
        text=(
            "利率及违约金异议：\n"
            "1. 借条约定年利率3%，原告主张13.8%无合同依据；逾期利息应按3%计算。\n"
            "2. 违约金月1.3%（年化15.6%）与利息不应重叠，依《民法典》第585条请求酌减。\n"
            "3. 律师费8,000元高于当地指导标准，请求酌减。"
        ),
        metadata={"document_type": "objection_statement", "submitter": "defendant"},
    ),
]

# ── 诉请与抗辩 ────────────────────────────────────────────────────────────────
PLAINTIFF_CLAIMS: list[dict] = [
    {
        "claim_id": "c-001",
        "case_id": CASE_ID,
        "owner_party_id": P_PARTY,
        "claim_category": "返还借款",
        "title": "返还借款本金187,500元",
        "claim_text": "被告应偿还借款本金187,500元（借条本金218,000元，已还30,500元，余欠187,500元）。",
    },
    {
        "claim_id": "c-002",
        "case_id": CASE_ID,
        "owner_party_id": P_PARTY,
        "claim_category": "利息",
        "title": "按年利率13.8%支付逾期利息",
        "claim_text": "自2024年3月2日起至实际还清之日，按年利率13.8%（LPR四倍）计算逾期利息。",
    },
    {
        "claim_id": "c-003",
        "case_id": CASE_ID,
        "owner_party_id": P_PARTY,
        "claim_category": "律师费",
        "title": "支付律师费8,000元",
        "claim_text": "借条明确约定借款人承担律师费，原告为追偿支出律师费8,000元，依约应由被告承担。",
    },
]

DEFENDANT_DEFENSES: list[dict] = [
    {
        "defense_id": "d-001",
        "case_id": CASE_ID,
        "owner_party_id": D_PARTY,
        "defense_category": "还款金额争议",
        "against_claim_id": "c-001",
        "title": "实际已还40,500元，剩余本金应为177,500元",
        "defense_text": (
            "证据目录显示被告已还款40,500元，原告诉状仅认可30,500元，"
            "差额10,000元（2023-03-30转账）有银行凭证，应予认定。"
            "正确剩余本金为177,500元，而非187,500元。"
        ),
    },
    {
        "defense_id": "d-002",
        "case_id": CASE_ID,
        "owner_party_id": D_PARTY,
        "defense_category": "利率争议",
        "against_claim_id": "c-002",
        "title": "逾期利率应按借条3%计算，不应适用13.8%",
        "defense_text": (
            "借条仅约定年利率3%，原告以LPR四倍13.8%主张逾期利息无合同依据。"
            "违约金月1.3%与利息不应重叠，请求法院酌减至合理范围。"
        ),
    },
    {
        "defense_id": "d-003",
        "case_id": CASE_ID,
        "owner_party_id": D_PARTY,
        "defense_category": "律师费争议",
        "against_claim_id": "c-003",
        "title": "律师费8,000元超出合理标准，请求酌减",
        "defense_text": "虽借条有律师费条款，但8,000元超出当地指导收费标准，请求法院酌减至合理金额。",
    },
]

# ── 金额计算数据（供 AmountCalculator 使用） ─────────────────────────────────
LOAN_TRANSACTIONS = [
    LoanTransaction(
        tx_id="tx-loan-001",
        date="2022-02-26",
        amount=Decimal("50000"),
        evidence_id="src-p-transfers-out",
        principal_base_contribution=True,
    ),
    LoanTransaction(
        tx_id="tx-loan-002",
        date="2022-02-26",
        amount=Decimal("60000"),
        evidence_id="src-p-transfers-out",
        principal_base_contribution=True,
    ),
    LoanTransaction(
        tx_id="tx-loan-003",
        date="2022-02-26",
        amount=Decimal("50000"),
        evidence_id="src-p-transfers-out",
        principal_base_contribution=True,
    ),
    LoanTransaction(
        tx_id="tx-loan-004",
        date="2022-02-27",
        amount=Decimal("38000"),
        evidence_id="src-p-transfers-out",
        principal_base_contribution=True,
    ),
    LoanTransaction(
        tx_id="tx-loan-005",
        date="2022-02-27",
        amount=Decimal("30000"),
        evidence_id="src-p-transfers-out",
        principal_base_contribution=True,
    ),
]

REPAYMENT_TRANSACTIONS = [
    RepaymentTransaction(
        tx_id="tx-repay-000",
        date="2022-02-28",
        amount=Decimal("10000"),
        evidence_id="src-p-pre-note-repayment",
        attributed_to=RepaymentAttribution.principal,
        attribution_basis="借条签署前还款，双方无争议",
    ),
    RepaymentTransaction(
        tx_id="tx-repay-001",
        date="2022-06-15",
        amount=Decimal("10000"),
        evidence_id="src-d-repayments",
        attributed_to=RepaymentAttribution.principal,
        attribution_basis="双方均认可",
    ),
    RepaymentTransaction(
        tx_id="tx-repay-002",
        date="2022-12-20",
        amount=Decimal("10000"),
        evidence_id="src-d-repayments",
        attributed_to=RepaymentAttribution.principal,
        attribution_basis="双方均认可",
    ),
    RepaymentTransaction(
        tx_id="tx-repay-003",
        date="2023-03-30",
        amount=Decimal("10000"),
        evidence_id="src-d-repayments",
        attributed_to=None,
        attribution_basis="被告主张已还，原告未计入，有争议",
    ),
    RepaymentTransaction(
        tx_id="tx-repay-004",
        date="2023-05-08",
        amount=Decimal("10500"),
        evidence_id="src-d-repayments",
        attributed_to=RepaymentAttribution.principal,
        attribution_basis="双方均认可",
    ),
]

DISPUTED_AMOUNTS = [
    DisputedAmountAttribution(
        item_id="disp-001",
        amount=Decimal("10000"),
        dispute_description="2023-03-30还款10,000元，原告诉状未计入",
        plaintiff_attribution="不认可为本案还款",
        defendant_attribution="已还款，应从本金中扣除",
    ),
]

CLAIM_ENTRIES = [
    AmountClaimDescriptor(
        claim_id="c-001",
        claim_type=ClaimType.principal,
        claimed_amount=Decimal("187500"),
        evidence_ids=["src-p-note", "src-p-repayments"],
    ),
    AmountClaimDescriptor(
        claim_id="c-002",
        claim_type=ClaimType.interest,
        claimed_amount=Decimal("0"),
        evidence_ids=["src-p-note"],
    ),
    AmountClaimDescriptor(
        claim_id="c-003",
        claim_type=ClaimType.attorney_fee,
        claimed_amount=Decimal("8000"),
        evidence_ids=["src-p-lawyer"],
    ),
]


# ── 输出工具 ──────────────────────────────────────────────────────────────────
def _output_dir() -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    d = _PROJECT_ROOT / "outputs" / ts
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_json(out: Path, result: AdversarialResult) -> Path:
    p = out / "result.json"
    p.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return p


def _write_md(
    out: Path,
    result: AdversarialResult,
    issue_tree,
    *,
    ranked_issues=None,
    decision_tree=None,
    attack_chain=None,
    action_rec=None,
    exec_summary=None,
    amount_report=None,
) -> Path:
    p = out / "report.md"
    lines = [
        "# 民间借贷纠纷对抗分析报告",
        "",
        f"**案件ID**: {result.case_id}  |  **运行ID**: {result.run_id}",
        f"**生成时间**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## 案件摘要",
        "",
        "| 项目 | 内容 |",
        "|------|------|",
        "| 出借转账 | 2022-02-26~27 分5笔转出 228,000元 |",
        "| 借条签署 | 2022-03-01，本金218,000元，年利率3%，月还9,000元 |",
        "| 逾期违约金 | 月1.3%（借款人另承担律师费诉讼费） |",
        "| 还款争议 | 原告主张已还30,500元；证据目录显示40,500元（差额10,000元） |",
        "| 诉请本金 | 187,500元（以30,500元已还为准） |",
        "| 诉请利率 | 年利率13.8%（LPR四倍） |",
        "| 律师费 | 8,000元 |",
        "",
        "## 争点列表",
        "",
    ]
    # 争点排序（若有 ranked_issues，按 outcome_impact 排列）
    display_issues = ranked_issues.issues if ranked_issues else issue_tree.issues
    for iss in display_issues:
        impact_tag = (
            f" **{iss.outcome_impact.value}**" if getattr(iss, "outcome_impact", None) else ""
        )
        action_tag = (
            f" [{iss.recommended_action.value}]" if getattr(iss, "recommended_action", None) else ""
        )
        lines.append(
            f"- **[{iss.issue_id}]** {iss.title} `{iss.issue_type.value}`{impact_tag}{action_tag}"
        )
    lines += ["", "## 三轮对抗记录", ""]
    for rs in result.rounds:
        lines.append(f"### Round {rs.round_number}（{rs.phase.value}）")
        lines.append("")
        for o in rs.outputs:
            lines += [
                f"**{o.agent_role_code}** — {o.title}",
                "",
                o.body,
                "",
                f"*引用证据*: {', '.join(o.evidence_citations)}",
                "---",
                "",
            ]
    if result.evidence_conflicts:
        lines += ["## 证据冲突", ""]
        for c in result.evidence_conflicts:
            lines.append(f"- `{c.issue_id}`: {c.conflict_description}")
        lines.append("")
    if result.missing_evidence_report:
        lines += ["## 缺失证据分析", ""]
        for m in result.missing_evidence_report:
            lines.append(f"- **[{m.issue_id}]** `{m.missing_for_party_id}`: {m.description}")
        lines.append("")
    if result.summary:
        s = result.summary
        lines += ["## LLM综合分析", "", "### 原告最强论点", ""]
        for a in s.plaintiff_strongest_arguments:
            lines += [f"**[{a.issue_id}]** {a.position}", f"> {a.reasoning}", ""]
        lines += ["### 被告最强抗辩", ""]
        for d in s.defendant_strongest_defenses:
            lines += [f"**[{d.issue_id}]** {d.position}", f"> {d.reasoning}", ""]
        lines += ["### 整体态势", "", s.overall_assessment, ""]

    # ── 争点影响排序表 ──────────────────────────────────────────────────────
    if ranked_issues:
        lines += ["", "## 争点影响排序", ""]
        lines.append("| 争点ID | 标题 | 影响 | 攻击强度 | 证据强度 | 建议行动 |")
        lines.append("|--------|------|------|----------|----------|----------|")
        for iss in ranked_issues.issues:
            impact = iss.outcome_impact.value if iss.outcome_impact else "-"
            attack = iss.opponent_attack_strength.value if iss.opponent_attack_strength else "-"
            ev_str = (
                iss.proponent_evidence_strength.value if iss.proponent_evidence_strength else "-"
            )
            action = iss.recommended_action.value if iss.recommended_action else "-"
            lines.append(
                f"| {iss.issue_id} | {iss.title[:20]} | {impact} | {attack} | {ev_str} | {action} |"
            )
        lines.append("")

    # ── 裁判路径树 ──────────────────────────────────────────────────────────
    if decision_tree:
        lines += ["## 裁判路径树", ""]
        for path in decision_tree.paths:
            lines.append(f"### 路径 {path.path_id}")
            lines.append(f"**触发条件**: {path.trigger_condition}")
            lines.append(f"**触发争点**: {', '.join(path.trigger_issue_ids)}")
            lines.append(f"**关键证据**: {', '.join(path.key_evidence_ids)}")
            lines.append(f"**可能结果**: {path.possible_outcome}")
            if path.confidence_interval:
                ci = path.confidence_interval
                lines.append(f"**置信区间**: {ci.low:.0%} ~ {ci.high:.0%}")
            if path.path_notes:
                lines.append(f"**备注**: {path.path_notes}")
            lines.append("")
        if decision_tree.blocking_conditions:
            lines += ["### 阻断条件", ""]
            for bc in decision_tree.blocking_conditions:
                lines.append(f"- **{bc.condition_id}**: {bc.description}")
            lines.append("")

    # ── 对方最优攻击链 ──────────────────────────────────────────────────────
    if attack_chain:
        lines += ["## 对方最优攻击链", ""]
        lines.append(
            f"**攻击方**: {attack_chain.owner_party_id}  |  **推荐顺序**: {' -> '.join(attack_chain.recommended_order)}"
        )
        lines.append("")
        for node in attack_chain.top_attacks:
            lines.append(f"### {node.attack_node_id}")
            lines.append(f"**目标争点**: {node.target_issue_id}")
            lines.append(f"**攻击论点**: {node.attack_description}")
            lines.append(f"**成功条件**: {node.success_conditions}")
            lines.append(f"**支撑证据**: {', '.join(node.supporting_evidence_ids)}")
            lines.append(f"**反制动作**: {node.counter_measure}")
            lines.append(f"**对方补证策略**: {node.adversary_pivot_strategy}")
            lines.append("")

    # ── 行动建议 ────────────────────────────────────────────────────────────
    if action_rec:
        lines += ["## 行动建议", ""]
        if action_rec.claims_to_abandon:
            lines.append("### 建议放弃")
            for ab in action_rec.claims_to_abandon:
                lines.append(f"- **{ab.suggestion_id}** ({ab.claim_id}): {ab.abandon_reason}")
            lines.append("")
        if action_rec.recommended_claim_amendments:
            lines.append("### 建议修改诉请")
            for am in action_rec.recommended_claim_amendments:
                lines.append(
                    f"- **{am.suggestion_id}** ({am.original_claim_id}): {am.amendment_description}"
                )
            lines.append("")
        if action_rec.evidence_supplement_priorities:
            lines.append("### 补证优先级")
            for gap_id in action_rec.evidence_supplement_priorities:
                lines.append(f"- {gap_id}")
            lines.append("")
        if action_rec.trial_explanation_priorities:
            lines.append("### 庭审解释优先事项")
            for tp in action_rec.trial_explanation_priorities:
                lines.append(f"- **{tp.priority_id}** ({tp.issue_id}): {tp.explanation_text}")
            lines.append("")

    # ── 执行摘要 ────────────────────────────────────────────────────────────
    if exec_summary:
        lines += ["## 执行摘要", ""]
        lines.append(f"**Top5 决定性争点**: {', '.join(exec_summary.top5_decisive_issues)}")
        lines.append("")
        if isinstance(exec_summary.top3_immediate_actions, list):
            lines.append(f"**Top3 立即行动**: {', '.join(exec_summary.top3_immediate_actions)}")
        else:
            lines.append(f"**Top3 立即行动**: {exec_summary.top3_immediate_actions}")
        lines.append("")
        lines.append(
            f"**Top3 对方最优攻击**: {', '.join(exec_summary.top3_adversary_optimal_attacks)}"
        )
        lines.append("")
        lines.append(f"**最稳诉请版本**: {exec_summary.current_most_stable_claim}")
        lines.append("")
        if isinstance(exec_summary.critical_evidence_gaps, list):
            lines.append(
                f"**关键缺证**: {', '.join(exec_summary.critical_evidence_gaps) if exec_summary.critical_evidence_gaps else '无'}"
            )
        else:
            lines.append(f"**关键缺证**: {exec_summary.critical_evidence_gaps}")
        lines.append("")

    p.write_text("\n".join(lines), encoding="utf-8")
    return p


# ── 三轮对抗手动编排 ──────────────────────────────────────────────────────────
async def _run_rounds(
    issue_tree,
    evidence_index: EvidenceIndex,
    p_client,
    d_client,
    j_client,
    config: RoundConfig,
) -> AdversarialResult:
    """手动编排三轮对抗，允许为每个代理分配不同的 LLM 客户端。"""
    run_id = f"run-real-{uuid.uuid4().hex[:12]}"
    case_id = issue_tree.case_id

    plaintiff = PlaintiffAgent(p_client, P_PARTY, config)
    defendant = DefendantAgent(d_client, D_PARTY, config)
    ev_mgr = EvidenceManagerAgent(j_client, config)

    ac = AccessController()
    p_ev = ac.filter_evidence_for_agent(
        role_code=AgentRole.plaintiff_agent.value,
        owner_party_id=P_PARTY,
        all_evidence=evidence_index.evidence,
    )
    d_ev = ac.filter_evidence_for_agent(
        role_code=AgentRole.defendant_agent.value,
        owner_party_id=D_PARTY,
        all_evidence=evidence_index.evidence,
    )
    print(f"  原告可见证据: {len(p_ev)} 条  被告可见证据: {len(d_ev)} 条")

    rounds, all_out, conflicts = [], [], []

    # Round 1: 首轮主张
    print("\n[R1] 首轮主张...")
    sid1 = f"state-r1-{uuid.uuid4().hex[:8]}"
    p1 = await plaintiff.generate_claim(issue_tree, p_ev, [], run_id, sid1, 1)
    p1 = p1.model_copy(update={"case_id": case_id})
    print(f"  ✓ 原告: {p1.title}")
    d1 = await defendant.generate_claim(issue_tree, d_ev, [p1], run_id, sid1, 1)
    d1 = d1.model_copy(update={"case_id": case_id})
    print(f"  ✓ 被告: {d1.title}")
    rounds.append(RoundState(round_number=1, phase=RoundPhase.claim, outputs=[p1, d1]))
    all_out += [p1, d1]

    # Round 2: 证据整理
    print("\n[R2] 证据整理...")
    sid2 = f"state-r2-{uuid.uuid4().hex[:8]}"
    ev_out, new_conf = await ev_mgr.analyze(issue_tree, evidence_index, [p1], [d1], run_id, sid2, 2)
    ev_out = ev_out.model_copy(update={"case_id": case_id})
    conflicts += new_conf
    print(f"  ✓ 证据管理: {ev_out.title}，冲突 {len(new_conf)} 条")
    rounds.append(RoundState(round_number=2, phase=RoundPhase.evidence, outputs=[ev_out]))
    all_out.append(ev_out)

    # Round 3: 针对性反驳
    print("\n[R3] 针对性反驳...")
    sid3 = f"state-r3-{uuid.uuid4().hex[:8]}"
    p3 = await plaintiff.generate_rebuttal(issue_tree, p_ev, all_out, [d1], run_id, sid3, 3)
    p3 = p3.model_copy(update={"case_id": case_id})
    print(f"  ✓ 原告反驳: {p3.title}")
    d3 = await defendant.generate_rebuttal(issue_tree, d_ev, all_out, [p1], run_id, sid3, 3)
    d3 = d3.model_copy(update={"case_id": case_id})
    print(f"  ✓ 被告反驳: {d3.title}")
    rounds.append(RoundState(round_number=3, phase=RoundPhase.rebuttal, outputs=[p3, d3]))
    all_out += [p3, d3]

    p_best = RoundEngine._extract_best_arguments(p1, p3)
    d_best = RoundEngine._extract_best_arguments(d1, d3)
    unresolved = RoundEngine._compute_unresolved_issues(issue_tree, conflicts)
    missing = RoundEngine._build_missing_evidence_report(issue_tree, p_ev, d_ev, P_PARTY, D_PARTY)

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

    print("\n[总结] 生成LLM综合分析...")
    summarizer = AdversarialSummarizer(j_client, config)
    summary = await summarizer.summarize(result, issue_tree)
    return result.model_copy(update={"summary": summary})


# ── 主入口 ────────────────────────────────────────────────────────────────────
async def main(claude_only: bool = False) -> None:
    print("=" * 60)
    print("民间借贷纠纷对抗模拟 — 真实案件（2022年，王某诉张某）")
    print("=" * 60)

    claude = ClaudeCLIClient(timeout=180.0)
    if claude_only:
        print("\n[配置] 全部代理使用 Claude CLI（--claude-only 模式）")
        codex = claude
    else:
        import shutil as _sh

        if not _sh.which("codex"):
            print("\n[警告] codex 不在 PATH，被告代理降级为 Claude CLI")
            codex = claude
        else:
            print("\n[配置] 原告/证据管理/总结 → Claude CLI；被告 → Codex CLI")
            codex = CodexCLIClient(timeout=180.0)

    # Step 1: 索引双方证据
    print("\n[Step 1] 索引双方证据...")
    indexer = EvidenceIndexer(
        llm_client=claude, case_type="civil_loan", model="claude-opus-4-6", max_retries=2
    )
    p_ev = await indexer.index(PLAINTIFF_MATERIALS, CASE_ID, P_PARTY, "plaintiff")
    print(f"  ✓ 原告证据: {len(p_ev)} 条")
    d_ev = await indexer.index(DEFENDANT_MATERIALS, CASE_ID, D_PARTY, "defendant")
    print(f"  ✓ 被告证据: {len(d_ev)} 条")
    all_ev = p_ev + d_ev
    ev_index = EvidenceIndex(case_id=CASE_ID, evidence=all_ev)
    print(f"  ✓ 合并索引: {len(all_ev)} 条")

    # Step 2: 提取争点树
    print("\n[Step 2] 提取争点树...")
    extractor = IssueExtractor(
        llm_client=claude, case_type="civil_loan", model="claude-opus-4-6", max_retries=2
    )
    ev_dicts = [e.model_dump() for e in all_ev]
    issue_tree = await extractor.extract(
        PLAINTIFF_CLAIMS, DEFENDANT_DEFENSES, ev_dicts, CASE_ID, CASE_SLUG
    )
    print(f"  ✓ 争点树: {len(issue_tree.issues)} 个争点, {len(issue_tree.burdens)} 个举证责任")
    for iss in issue_tree.issues:
        print(f"    - [{iss.issue_id}] {iss.title}")

    # Step 3: 三轮对抗
    print("\n[Step 3] 开始三轮对抗辩论...")
    config = RoundConfig(model="claude-opus-4-6", max_tokens_per_output=2000, max_retries=2)
    result = await _run_rounds(issue_tree, ev_index, claude, codex, claude, config)

    # Promote cited evidence to admitted_for_discussion
    cited_ids: set[str] = set()
    for rd in result.rounds:
        for o in rd.outputs:
            cited_ids.update(o.evidence_citations)
    promoted = 0
    for ev in ev_index.evidence:
        if ev.evidence_id in cited_ids and ev.status == EvidenceStatus.private:
            ev.status = EvidenceStatus.admitted_for_discussion
            promoted += 1
    print(f"\n  Promoted {promoted}/{len(ev_index.evidence)} evidence to admitted_for_discussion")

    # Step 3.5: 争点排序 + 裁判路径 + 行动建议
    print("\n[Step 3.5] 争点排序 + 裁判路径 + 行动建议...")
    run_id = result.run_id

    # P0.2: AmountCalculator（纯规则，同步）
    print("  - 金额一致性校验...")
    amount_input = AmountCalculatorInput(
        case_id=CASE_ID,
        run_id=run_id,
        source_material_ids=["src-p-note", "src-p-repayments", "src-d-repayments"],
        claim_entries=CLAIM_ENTRIES,
        loan_transactions=LOAN_TRANSACTIONS,
        repayment_transactions=REPAYMENT_TRANSACTIONS,
        disputed_amount_attributions=DISPUTED_AMOUNTS,
    )
    amount_report = AmountCalculator().calculate(amount_input)
    print(f"    ✓ 阻断裁判: {amount_report.consistency_check_result.verdict_block_active}")
    print(
        f"    ✓ 未解决冲突: {len(amount_report.consistency_check_result.unresolved_conflicts)} 条"
    )

    # P0.1: IssueImpactRanker（LLM）
    print("  - 争点影响排序...")
    ranker = IssueImpactRanker(
        llm_client=claude,
        model="claude-opus-4-6",
        temperature=0.0,
        max_retries=2,
    )
    ranking_result = await ranker.rank(
        IssueImpactRankerInput(
            case_id=CASE_ID,
            run_id=run_id,
            issue_tree=issue_tree,
            evidence_index=ev_index,
            amount_calculation_report=amount_report,
            proponent_party_id=P_PARTY,
        )
    )
    ranked_tree = ranking_result.ranked_issue_tree
    print(f"    ✓ 已排序争点: {len(ranked_tree.issues)} 个")
    for iss in ranked_tree.issues:
        impact = iss.outcome_impact.value if iss.outcome_impact else "?"
        lines_hint = f"[{impact}] {iss.issue_id}: {iss.title}"
        print(f"      {lines_hint}")

    # P0.3 + P0.4: DecisionPathTree + AttackChainOptimizer（可并行）
    print("  - 裁判路径树 + 攻击链优化...")
    dpt_gen = DecisionPathTreeGenerator(
        llm_client=claude,
        model="claude-opus-4-6",
        temperature=0.0,
        max_retries=2,
    )
    aco = AttackChainOptimizer(
        llm_client=claude,
        model="claude-opus-4-6",
        temperature=0.0,
        max_retries=2,
    )
    decision_tree, attack_chain = await asyncio.gather(
        dpt_gen.generate(
            DecisionPathTreeInput(
                case_id=CASE_ID,
                run_id=run_id,
                ranked_issue_tree=ranked_tree,
                evidence_index=ev_index,
                amount_calculation_report=amount_report,
            )
        ),
        aco.optimize(
            AttackChainOptimizerInput(
                case_id=CASE_ID,
                run_id=run_id,
                owner_party_id=D_PARTY,
                issue_tree=ranked_tree,
                evidence_index=ev_index,
            )
        ),
    )
    print(f"    ✓ 裁判路径: {len(decision_tree.paths)} 条")
    print(f"    ✓ 攻击节点: {len(attack_chain.top_attacks)} 个")

    # P1.8: ActionRecommender（规则层 + 可选 LLM 策略层）
    print("  - 行动建议生成...")
    action_rec = await ActionRecommender().recommend(
        ActionRecommenderInput(
            case_id=CASE_ID,
            run_id=run_id,
            issue_list=ranked_tree.issues,
            evidence_gap_list=[],  # P1.7 暂未启用
            amount_calculation_report=amount_report,
        )
    )
    print(f"    ✓ 建议修改诉请: {len(action_rec.recommended_claim_amendments)} 条")
    print(f"    ✓ 建议放弃: {len(action_rec.claims_to_abandon)} 条")

    # P2.12: ExecutiveSummarizer（纯规则，同步）
    print("  - 执行摘要...")
    exec_summary = ExecutiveSummarizer().summarize(
        ExecutiveSummarizerInput(
            case_id=CASE_ID,
            run_id=run_id,
            issue_list=ranked_tree.issues,
            adversary_attack_chain=attack_chain,
            amount_calculation_report=amount_report,
            action_recommendation=action_rec,
            evidence_gap_items=None,  # P1.7 暂未启用
        )
    )
    print(f"    ✓ Top5 决定性争点: {exec_summary.top5_decisive_issues}")
    print(f"    ✓ 最稳诉请: {exec_summary.current_most_stable_claim[:60]}...")

    # Step 4: 写入输出
    print("\n[Step 4] 写入输出文件...")
    out = _output_dir()
    jp = _write_json(out, result)
    mp = _write_md(
        out,
        result,
        issue_tree,
        ranked_issues=ranked_tree,
        decision_tree=decision_tree,
        attack_chain=attack_chain,
        action_rec=action_rec,
        exec_summary=exec_summary,
        amount_report=amount_report,
    )
    # 序列化新产物
    (out / "decision_tree.json").write_text(
        decision_tree.model_dump_json(indent=2), encoding="utf-8"
    )
    (out / "executive_summary.json").write_text(
        exec_summary.model_dump_json(indent=2), encoding="utf-8"
    )
    (out / "attack_chain.json").write_text(attack_chain.model_dump_json(indent=2), encoding="utf-8")
    (out / "amount_report.json").write_text(
        amount_report.model_dump_json(indent=2), encoding="utf-8"
    )

    print(f"\n{'=' * 60}")
    print(f"✓ 运行完成")
    print(f"  JSON 结果: {jp}")
    print(f"  Markdown 报告: {mp}")
    print(f"  裁判路径树: {out / 'decision_tree.json'}")
    print(f"  执行摘要: {out / 'executive_summary.json'}")
    print(f"  攻击链: {out / 'attack_chain.json'}")
    print(f"  金额报告: {out / 'amount_report.json'}")
    if result.summary:
        print(f"\n整体态势评估:")
        print(f"  {result.summary.overall_assessment[:300]}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="民间借贷真实案件对抗模拟",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--claude-only",
        action="store_true",
        help="被告也用 Claude CLI（Codex 不可用时的 fallback）",
    )
    args = parser.parse_args()
    try:
        asyncio.run(main(claude_only=args.claude_only))
    except CLINotFoundError as e:
        print(f"\n[错误] CLI 不可用: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[中断] 用户取消。")
        sys.exit(0)
