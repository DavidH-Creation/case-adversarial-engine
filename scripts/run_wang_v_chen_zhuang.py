#!/usr/bin/env python3
"""
民间借贷真实案件对抗模拟（2025年，老王诉小陈、老庄）

用法: python scripts/run_wang_v_chen_zhuang.py [--claude-only]
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
    AgentRole, ClaimType, EvidenceIndex, EvidenceStatus, LoanTransaction,
    RawMaterial, RepaymentTransaction,
)

# Post-debate analysis modules
from decimal import Decimal
from engines.case_structuring.amount_calculator import AmountCalculator, AmountCalculatorInput, AmountClaimDescriptor
from engines.simulation_run.issue_impact_ranker.ranker import IssueImpactRanker
from engines.simulation_run.issue_impact_ranker.schemas import IssueImpactRankerInput
from engines.simulation_run.decision_path_tree import DecisionPathTreeGenerator, DecisionPathTreeInput
from engines.simulation_run.attack_chain_optimizer import AttackChainOptimizer, AttackChainOptimizerInput
from engines.simulation_run.action_recommender import ActionRecommender
from engines.simulation_run.action_recommender.schemas import ActionRecommenderInput
from engines.report_generation.executive_summarizer import ExecutiveSummarizer
from engines.report_generation.executive_summarizer.schemas import ExecutiveSummarizerInput

CASE_ID = "case-civil-loan-wang-v-chen-zhuang-2025"
CASE_SLUG = "wangchenzhuang2025"
P_PARTY = "party-plaintiff-wang"
D_PARTY = "party-defendant-chen"

PLAINTIFF_MATERIALS: list[RawMaterial] = [
    RawMaterial(
        source_id="src-p-id",
        text=(
            "当事人身份信息：\n"
            "原告：老王，男，汉族。\n"
            "被告：小陈，女，汉族。\n"
            "被告：老庄，男，汉族。"
        ),
        metadata={"document_type": "identity_documents", "submitter": "plaintiff"},
    ),
    RawMaterial(
        source_id="src-p-complaint",
        text=(
            "民事起诉状\n"
            "诉讼请求：\n"
            "1、二被告立即偿还原告借款本金20万元及资金占用利息损失，以20万元为基数，"
            "自起诉之日起至实际偿清款项之日止按全国银行间同业拆借中心公布的一年期"
            "贷款市场报价利率计算；\n"
            "2、被告承担本案全部诉讼费用（包括但不限于案件受理费、公告费，财产保全费等）。\n\n"
            "事实与理由：\n"
            "2025年1月10日，被告以短期资金周转为由向原告借款20万元。当日，原告通过"
            "本人银行账户向被告支付10万元，通过C支付宝账户代付10万元，上述款项合计20万元。"
            "但截止起诉之日，被告仍未偿还原告款项。原告为维护自身合法权益，特向贵院提起诉讼。"
        ),
        metadata={"document_type": "complaint", "submitter": "plaintiff"},
    ),
    RawMaterial(
        source_id="src-p-transfers",
        text=(
            "支付业务回单、支付宝电子凭证、汇款声明、身份证复印件\n"
            "证明：原告通过本人民生银行账户向被告转账10万元，通过C支付宝共向被告转账10万元，"
            "合计20万元的事实。\n"
            "2025-01-10  老王（银行账户）→小陈  100,000元\n"
            "2025-01-10  C支付宝→小陈  100,000元\n"
            "合计：200,000元。"
        ),
        metadata={"document_type": "bank_transfer_records", "direction": "outgoing", "submitter": "plaintiff"},
    ),
    RawMaterial(
        source_id="src-p-sms",
        text=("短信记录\n证明：原告向被告催款的事实。"),
        metadata={"document_type": "communication_records", "submitter": "plaintiff"},
    ),
    RawMaterial(
        source_id="src-p-wechat-moments",
        text=(
            "补充证据：微信朋友圈截图、录屏（附光盘）\n"
            "证明：\n"
            "1、原告出借案涉借款的时间是2025年1月10日。而被告小陈自称老庄入股\"A公司\"的"
            "时间为2025年2月20日至2025年5月2日止。故该笔借款发生时，老庄与公司无关。\n"
            "2、被告小陈自称其为\"原A负责人\"，证明其非员工。"
        ),
        metadata={"document_type": "social_media_records", "submitter": "plaintiff"},
    ),
]

DEFENDANT_MATERIALS: list[RawMaterial] = [
    RawMaterial(
        source_id="src-d-id",
        text="被告：小陈，女，汉族。",
        metadata={"document_type": "identity_documents", "submitter": "defendant"},
    ),
    RawMaterial(
        source_id="src-d-business-license",
        text=(
            "营业执照影印件、微信截图（工资表）、银行明细\n"
            "1、证明被告小陈系A公司的员工，公司的实际经营者是老庄；\n"
            "2、证明被告的账户（开户行：X支行、账号：1111111）在2025年5月份前是"
            "A公司（老庄）在使用收付款的事实。"
        ),
        metadata={"document_type": "business_records", "submitter": "defendant"},
    ),
    RawMaterial(
        source_id="src-d-wechat-transfer-instructions",
        text=(
            "微信截图\n"
            "1、证明案涉款项是原告要支付给老庄，老庄叫原告转到被告的账上，"
            "被告收到款项就立即根据老庄的指示，将款项汇给老庄指定的账户；\n"
            "2、证明被告没有向原告借款，双方之间没有借贷合意。"
        ),
        metadata={"document_type": "communication_records", "submitter": "defendant"},
    ),
    RawMaterial(
        source_id="src-d-didi-record",
        text=(
            "补充证据：滴滴打车记录截图\n"
            "证明被告小陈在2025年1月10日当晚21时11分就已打车回家，"
            "不存在原告庭审所陈述的原告与二被告三方面对面达成借款合意。"
        ),
        metadata={"document_type": "transportation_records", "submitter": "defendant"},
    ),
    RawMaterial(
        source_id="src-d-recordings-wechat",
        text=(
            "补充证据：录音光盘、微信聊天记录截图、录屏光盘\n"
            "1、证明案涉款项是原告要支付给老庄，老庄叫原告转到被告小陈的账号，"
            "被告小陈没有向原告借款，双方之间没有借贷合意；\n"
            "2、证明原告一直劝被告老庄不要应诉，让老庄不要承认款项是他所借的，"
            "也不要承认店铺及被告小陈的卡是其使用和经营，且让被告老庄将其手机上"
            "与原告的微信聊天记录当场删除，并让被告老庄在庭审上陈述微信号不是"
            "其本人在使用，被告老庄在录音中也陈述了被告小陈所发的微信朋友圈"
            "系其编辑好后才让被告小陈发的。\n"
            "3、证明原告2025年1月10日转给被告小陈的案涉20万元款项系被告老庄向原告所借，"
            "原告老王在2025年1月11日通过微信询问被告老庄\"大概什么时候能回款\"，"
            "与庭审时被告二老庄陈述说答应原告第二天还款一致，也与原告证据中的短信截图内容"
            "\"我跟你老板说了，明天要带上我，不难就翻脸\"相对应。\n"
            "上述录音足以证实原告2025年1月10日转给被告小陈的20万元款项系被告老庄"
            "向原告所借，与被告小陈无关，否则原告不会在2025年1月11日向老庄催讨款项，"
            "也无需阻止被告老庄出庭，更无需让老庄将微信聊天记录删除。"
        ),
        metadata={"document_type": "audio_video_records", "submitter": "defendant"},
    ),
]

PLAINTIFF_CLAIMS: list[dict] = [
    {
        "claim_id": "c-001", "case_id": CASE_ID, "owner_party_id": P_PARTY,
        "claim_category": "返还借款", "title": "二被告偿还借款本金20万元",
        "claim_text": (
            "2025年1月10日，被告以短期资金周转为由向原告借款20万元。"
            "原告通过银行转账10万元、支付宝代付10万元，合计出借20万元。"
            "被告至今未偿还任何款项，应立即偿还全部借款本金。"
        ),
    },
    {
        "claim_id": "c-002", "case_id": CASE_ID, "owner_party_id": P_PARTY,
        "claim_category": "利息", "title": "支付资金占用利息损失",
        "claim_text": (
            "以20万元为基数，自起诉之日起至实际偿清款项之日止，"
            "按全国银行间同业拆借中心公布的一年期贷款市场报价利率计算资金占用利息损失。"
        ),
    },
    {
        "claim_id": "c-003", "case_id": CASE_ID, "owner_party_id": P_PARTY,
        "claim_category": "诉讼费用", "title": "被告承担全部诉讼费用",
        "claim_text": "被告承担本案全部诉讼费用（包括但不限于案件受理费、公告费、财产保全费等）。",
    },
]

DEFENDANT_DEFENSES: list[dict] = [
    {
        "defense_id": "d-001", "case_id": CASE_ID, "owner_party_id": D_PARTY,
        "defense_category": "借贷关系不成立", "against_claim_id": "c-001",
        "title": "被告小陈与原告之间不存在借贷合意",
        "defense_text": (
            "案涉20万元款项系原告要支付给老庄的，老庄指示原告转入被告小陈的账户。"
            "被告小陈仅为代收代付，收到款项后立即根据老庄指示将款项汇给老庄指定账户。"
            "被告小陈系A公司员工，其账户在2025年5月前一直由老庄用于公司收付款。"
            "被告小陈与原告之间不存在借贷合意，不应承担还款责任。"
        ),
    },
    {
        "defense_id": "d-002", "case_id": CASE_ID, "owner_party_id": D_PARTY,
        "defense_category": "实际借款人抗辩", "against_claim_id": "c-001",
        "title": "实际借款人为老庄，非被告小陈",
        "defense_text": (
            "录音证据、微信聊天记录证实：(1)原告在2025年1月11日向老庄催讨回款，"
            "而非向小陈催讨；(2)原告劝老庄不要应诉、删除微信聊天记录、不要承认"
            "款项是老庄所借；(3)老庄在录音中承认答应原告第二天还款。"
            "上述事实充分证明实际借款人为老庄，与被告小陈无关。"
        ),
    },
    {
        "defense_id": "d-003", "case_id": CASE_ID, "owner_party_id": D_PARTY,
        "defense_category": "面对面合意不存在", "against_claim_id": "c-001",
        "title": "不存在三方面对面达成借款合意",
        "defense_text": (
            "滴滴打车记录显示被告小陈在2025年1月10日当晚21时11分已打车回家，"
            "不存在原告庭审所陈述的三方面对面达成借款合意的场景。"
            "原告关于当面借款合意的陈述与客观证据矛盾，不应采信。"
        ),
    },
    {
        "defense_id": "d-004", "case_id": CASE_ID, "owner_party_id": D_PARTY,
        "defense_category": "原告妨碍诉讼", "against_claim_id": "c-001",
        "title": "原告存在妨碍诉讼行为",
        "defense_text": (
            "原告劝被告老庄不要应诉，让老庄删除与原告的微信聊天记录，"
            "让老庄不承认款项系其所借，也不承认店铺及小陈的卡是其使用和经营。"
            "被告老庄的微信朋友圈内容也是老庄编辑好后让小陈发的。"
            "原告的上述行为构成妨碍诉讼、隐匿证据，其诉称的事实不应采信。"
        ),
    },
]


# ── 金额计算数据（供 AmountCalculator 使用） ─────────────────────────────────
LOAN_TRANSACTIONS = [
    LoanTransaction(tx_id="tx-loan-001", date="2025-01-10", amount=Decimal("100000"), evidence_id="src-p-transfers", principal_base_contribution=True),
    LoanTransaction(tx_id="tx-loan-002", date="2025-01-10", amount=Decimal("100000"), evidence_id="src-p-transfers", principal_base_contribution=True),
]

# 被告未还款
REPAYMENT_TRANSACTIONS: list[RepaymentTransaction] = []

CLAIM_ENTRIES = [
    AmountClaimDescriptor(claim_id="c-001", claim_type=ClaimType.principal, claimed_amount=Decimal("200000"), evidence_ids=["src-p-transfers"]),
    AmountClaimDescriptor(claim_id="c-002", claim_type=ClaimType.interest, claimed_amount=Decimal("0"), evidence_ids=[]),
]


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
        "| 原告 | 老王 |",
        "| 被告 | 小陈、老庄 |",
        "| 借款日期 | 2025年1月10日 |",
        "| 借款金额 | 20万元（银行转账10万 + 支付宝代付10万） |",
        "| 原告主张 | 被告以短期资金周转为由借款，应偿还本金+利息 |",
        "| 被告抗辩 | 款项系老庄借款，小陈仅为代收代付（账户由老庄使用） |",
        "| 核心争议 | 借贷关系主体：小陈 vs 老庄；是否存在面对面借款合意 |",
        "",
        "## 争点列表",
        "",
    ]
    # 争点排序（若有 ranked_issues，按 outcome_impact 排列）
    display_issues = ranked_issues.issues if ranked_issues else issue_tree.issues
    for iss in display_issues:
        impact_tag = f" **{iss.outcome_impact.value}**" if getattr(iss, "outcome_impact", None) else ""
        action_tag = f" [{iss.recommended_action.value}]" if getattr(iss, "recommended_action", None) else ""
        lines.append(f"- **[{iss.issue_id}]** {iss.title} `{iss.issue_type.value}`{impact_tag}{action_tag}")
    lines += ["", "## 三轮对抗记录", ""]
    for rs in result.rounds:
        lines.append(f"### Round {rs.round_number}（{rs.phase.value}）")
        lines.append("")
        for o in rs.outputs:
            lines += [f"**{o.agent_role_code}** — {o.title}", "", o.body, "",
                      f"*引用证据*: {', '.join(o.evidence_citations)}", "---", ""]
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
            ev_str = iss.proponent_evidence_strength.value if iss.proponent_evidence_strength else "-"
            action = iss.recommended_action.value if iss.recommended_action else "-"
            lines.append(f"| {iss.issue_id} | {iss.title[:20]} | {impact} | {attack} | {ev_str} | {action} |")
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
        lines.append(f"**攻击方**: {attack_chain.owner_party_id}  |  **推荐顺序**: {' -> '.join(attack_chain.recommended_order)}")
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
                lines.append(f"- **{am.suggestion_id}** ({am.original_claim_id}): {am.amendment_description}")
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
        lines.append(f"**Top3 对方最优攻击**: {', '.join(exec_summary.top3_adversary_optimal_attacks)}")
        lines.append("")
        lines.append(f"**最稳诉请版本**: {exec_summary.current_most_stable_claim}")
        lines.append("")
        if isinstance(exec_summary.critical_evidence_gaps, list):
            lines.append(f"**关键缺证**: {', '.join(exec_summary.critical_evidence_gaps) if exec_summary.critical_evidence_gaps else '无'}")
        else:
            lines.append(f"**关键缺证**: {exec_summary.critical_evidence_gaps}")
        lines.append("")

    p.write_text("\n".join(lines), encoding="utf-8")
    return p


async def _run_rounds(
    issue_tree,
    evidence_index: EvidenceIndex,
    p_client,
    d_client,
    j_client,
    config: RoundConfig,
) -> AdversarialResult:
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

    print("\n[R2] 证据整理...")
    sid2 = f"state-r2-{uuid.uuid4().hex[:8]}"
    ev_out, new_conf = await ev_mgr.analyze(issue_tree, evidence_index, [p1], [d1], run_id, sid2, 2)
    ev_out = ev_out.model_copy(update={"case_id": case_id})
    conflicts += new_conf
    print(f"  ✓ 证据管理: {ev_out.title}，冲突 {len(new_conf)} 条")
    rounds.append(RoundState(round_number=2, phase=RoundPhase.evidence, outputs=[ev_out]))
    all_out.append(ev_out)

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
        case_id=case_id, run_id=run_id, rounds=rounds,
        plaintiff_best_arguments=p_best, defendant_best_defenses=d_best,
        unresolved_issues=unresolved, evidence_conflicts=conflicts,
        missing_evidence_report=missing,
    )

    print("\n[总结] 生成LLM综合分析...")
    summarizer = AdversarialSummarizer(j_client, config)
    summary = await summarizer.summarize(result, issue_tree)
    return result.model_copy(update={"summary": summary})


async def main(claude_only: bool = False) -> None:
    print("=" * 60)
    print("民间借贷纠纷对抗模拟 — 真实案件（2025年，老王诉小陈、老庄）")
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

    print("\n[Step 1] 索引双方证据...")
    indexer = EvidenceIndexer(llm_client=claude, case_type="civil_loan", model="claude-opus-4-6", max_retries=2)
    p_ev = await indexer.index(PLAINTIFF_MATERIALS, CASE_ID, P_PARTY, "plaintiff")
    print(f"  ✓ 原告证据: {len(p_ev)} 条")
    d_ev = await indexer.index(DEFENDANT_MATERIALS, CASE_ID, D_PARTY, "defendant")
    print(f"  ✓ 被告证据: {len(d_ev)} 条")
    all_ev = p_ev + d_ev
    ev_index = EvidenceIndex(case_id=CASE_ID, evidence=all_ev)
    print(f"  ✓ 合并索引: {len(all_ev)} 条")

    print("\n[Step 2] 提取争点树...")
    extractor = IssueExtractor(llm_client=claude, case_type="civil_loan", model="claude-opus-4-6", max_retries=2)
    ev_dicts = [e.model_dump() for e in all_ev]
    issue_tree = await extractor.extract(PLAINTIFF_CLAIMS, DEFENDANT_DEFENSES, ev_dicts, CASE_ID, CASE_SLUG)
    print(f"  ✓ 争点树: {len(issue_tree.issues)} 个争点, {len(issue_tree.burdens)} 个举证责任")
    for iss in issue_tree.issues:
        print(f"    - [{iss.issue_id}] {iss.title}")

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
        case_id=CASE_ID, run_id=run_id,
        source_material_ids=["src-p-transfers"],
        claim_entries=CLAIM_ENTRIES,
        loan_transactions=LOAN_TRANSACTIONS,
        repayment_transactions=REPAYMENT_TRANSACTIONS,
    )
    amount_report = AmountCalculator().calculate(amount_input)
    print(f"    ✓ 阻断裁判: {amount_report.consistency_check_result.verdict_block_active}")
    print(f"    ✓ 未解决冲突: {len(amount_report.consistency_check_result.unresolved_conflicts)} 条")

    # P0.1: IssueImpactRanker（LLM）
    print("  - 争点影响排序...")
    ranker = IssueImpactRanker(
        llm_client=claude, model="claude-opus-4-6",
        temperature=0.0, max_retries=2,
    )
    ranking_result = await ranker.rank(IssueImpactRankerInput(
        case_id=CASE_ID, run_id=run_id,
        issue_tree=issue_tree,
        evidence_index=ev_index,
        amount_calculation_report=amount_report,
        proponent_party_id=P_PARTY,
    ))
    ranked_tree = ranking_result.ranked_issue_tree
    print(f"    ✓ 已排序争点: {len(ranked_tree.issues)} 个")
    for iss in ranked_tree.issues:
        impact = iss.outcome_impact.value if iss.outcome_impact else "?"
        lines_hint = f"[{impact}] {iss.issue_id}: {iss.title}"
        print(f"      {lines_hint}")

    # P0.3 + P0.4: DecisionPathTree + AttackChainOptimizer（可并行）
    print("  - 裁判路径树 + 攻击链优化...")
    dpt_gen = DecisionPathTreeGenerator(
        llm_client=claude, model="claude-opus-4-6",
        temperature=0.0, max_retries=2,
    )
    aco = AttackChainOptimizer(
        llm_client=claude, model="claude-opus-4-6",
        temperature=0.0, max_retries=2,
    )
    decision_tree, attack_chain = await asyncio.gather(
        dpt_gen.generate(DecisionPathTreeInput(
            case_id=CASE_ID, run_id=run_id,
            ranked_issue_tree=ranked_tree,
            evidence_index=ev_index,
            amount_calculation_report=amount_report,
        )),
        aco.optimize(AttackChainOptimizerInput(
            case_id=CASE_ID, run_id=run_id,
            owner_party_id=D_PARTY,
            issue_tree=ranked_tree,
            evidence_index=ev_index,
        )),
    )
    print(f"    ✓ 裁判路径: {len(decision_tree.paths)} 条")
    print(f"    ✓ 攻击节点: {len(attack_chain.top_attacks)} 个")

    # P1.8: ActionRecommender (async, rule-based without LLM client)
    print("  - 行动建议生成...")
    action_rec = await ActionRecommender().recommend(ActionRecommenderInput(
        case_id=CASE_ID, run_id=run_id,
        issue_list=ranked_tree.issues,
        evidence_gap_list=[],   # P1.7 暂未启用
        amount_calculation_report=amount_report,
    ))
    print(f"    ✓ 建议修改诉请: {len(action_rec.recommended_claim_amendments)} 条")
    print(f"    ✓ 建议放弃: {len(action_rec.claims_to_abandon)} 条")

    # P2.12: ExecutiveSummarizer（纯规则，同步）
    print("  - 执行摘要...")
    exec_summary = ExecutiveSummarizer().summarize(ExecutiveSummarizerInput(
        case_id=CASE_ID, run_id=run_id,
        issue_list=ranked_tree.issues,
        adversary_attack_chain=attack_chain,
        amount_calculation_report=amount_report,
        action_recommendation=action_rec,
        evidence_gap_items=None,    # P1.7 暂未启用
    ))
    print(f"    ✓ Top5 决定性争点: {exec_summary.top5_decisive_issues}")
    print(f"    ✓ 最稳诉请: {exec_summary.current_most_stable_claim[:60]}...")

    print("\n[Step 4] 写入输出文件...")
    out = _output_dir()
    jp = _write_json(out, result)
    mp = _write_md(
        out, result, issue_tree,
        ranked_issues=ranked_tree,
        decision_tree=decision_tree,
        attack_chain=attack_chain,
        action_rec=action_rec,
        exec_summary=exec_summary,
        amount_report=amount_report,
    )
    # 序列化新产物
    (out / "decision_tree.json").write_text(decision_tree.model_dump_json(indent=2), encoding="utf-8")
    (out / "executive_summary.json").write_text(exec_summary.model_dump_json(indent=2), encoding="utf-8")
    (out / "attack_chain.json").write_text(attack_chain.model_dump_json(indent=2), encoding="utf-8")
    (out / "amount_report.json").write_text(amount_report.model_dump_json(indent=2), encoding="utf-8")

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
        description="民间借贷真实案件对抗模拟（老王诉小陈、老庄）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--claude-only", action="store_true", help="被告也用 Claude CLI（Codex 不可用时的 fallback）")
    args = parser.parse_args()
    try:
        asyncio.run(main(claude_only=args.claude_only))
    except CLINotFoundError as e:
        print(f"\n[错误] CLI 不可用: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[中断] 用户取消。")
        sys.exit(0)
