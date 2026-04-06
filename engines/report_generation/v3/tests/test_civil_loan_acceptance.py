"""Phase 3a: civil_loan case type structural validation against v3 acceptance matrix.

Acceptance matrix checks (from plans/v3-plan.md §3.2):
  1. MD render contract 10/10 pass
  2. DOCX render contract pass
  3. Fallback ratio ≤ 0.20 (Phase 3d final threshold)
  4. All major sections have substantive content (≥50 chars)
  5. No orphan evidence citations
  6. Amount calculation section present and correct (civil_loan HAS this)
  7. Executive summary non-boilerplate
  8. Layer3 three perspectives (plaintiff/defendant/neutral) have substantive content
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engines.report_generation.v3.models import (
    ConditionalNode,
    ConditionalScenarioTree,
    CoverSummary,
    EvidenceBasicCard,
    EvidenceKeyCard,
    EvidencePriority,
    EvidencePriorityCard,
    FactBaseEntry,
    FourLayerReport,
    IssueMapCard,
    Layer1Cover,
    Layer2Core,
    Layer3Perspective,
    Layer4Appendix,
    PerspectiveOutput,
    SectionTag,
    TimelineEvent,
)
from engines.report_generation.v3.render_contract import (
    LintResult,
    LintSeverity,
    RenderContractViolation,
    compute_fallback_ratio,
    lint_markdown_render_contract,
)
from engines.report_generation.v3.report_writer import (
    build_four_layer_report,
    write_v3_report_md,
)


# ---------------------------------------------------------------------------
# Civil-loan-specific fixtures — realistic data for 王某诉张某 pattern
# ---------------------------------------------------------------------------

_CIVIL_LOAN_EVIDENCE_IDS = {
    "EV-P-TRANSFER",
    "EV-P-CONTRACT",
    "EV-P-CHAT",
    "EV-D-RECEIPT",
    "EV-D-WITNESS",
}


def _make_civil_loan_report(
    *,
    perspective: str = "neutral",
    include_amount: bool = True,
    include_evidence_cards: bool = True,
    include_layer3_content: bool = True,
    fallback_sections: int = 0,
) -> FourLayerReport:
    """Build a realistic civil_loan FourLayerReport for acceptance testing.

    This mimics what the pipeline produces for a 民间借贷纠纷 case with:
    - 2 core issues (借款合意, 还款义务)
    - 5 evidence items (3 plaintiff, 2 defendant)
    - Amount calculation (civil_loan always has this)
    - Both plaintiff and defendant perspectives
    """
    # --- Layer 1: Cover Summary ---
    cover = CoverSummary(
        neutral_conclusion=(
            "本案涉及民间借贷纠纷，原告主张借款20万元，"
            "核心争点在于借款合意是否成立及还款义务的主体认定。"
            "双方在借贷关系主体问题上存在根本性分歧。"
        ),
        winning_move=(
            "银行转账记录（EV-P-TRANSFER）与微信聊天记录（EV-P-CHAT）"
            "的交叉印证是决定案件走向的关键证据链。"
            "若二者能够形成完整的借贷合意证明，原告胜诉概率显著提高。"
        ),
        blocking_conditions=[
            "若法院认定被告仅为代收代付，借款合意不成立，则原告诉请将被驳回",
            "若录音证据因采集程序瑕疵被排除，原告证据链将出现关键缺口",
            "若被告能够证明款项系第三人借款且有充分证据支撑，主体认定将改变",
        ],
    )

    timeline = [
        TimelineEvent(date="2025-01-10", event="原告通过银行转账向被告支付10万元", source="EV-P-TRANSFER"),
        TimelineEvent(date="2025-01-10", event="原告通过支付宝代付10万元", source="EV-P-TRANSFER"),
        TimelineEvent(date="2025-01-15", event="双方微信沟通还款事宜", source="EV-P-CHAT"),
        TimelineEvent(date="2025-02-01", event="被告声称款项系第三人借款", source="EV-D-WITNESS"),
        TimelineEvent(date="2025-03-01", event="原告向法院提起民事诉讼", source="case_data"),
    ]

    evidence_priorities = [
        EvidencePriorityCard(
            evidence_id="EV-P-TRANSFER",
            title="银行转账记录",
            priority=EvidencePriority.core,
            reason="直接证明资金流向，是借贷关系成立的基础证据",
            controls_issue_ids=["ISS-001"],
        ),
        EvidencePriorityCard(
            evidence_id="EV-P-CONTRACT",
            title="借条/借款协议",
            priority=EvidencePriority.core,
            reason="书面借贷合意的直接载体，证明力最强",
            controls_issue_ids=["ISS-001", "ISS-002"],
        ),
        EvidencePriorityCard(
            evidence_id="EV-P-CHAT",
            title="微信聊天记录",
            priority=EvidencePriority.supporting,
            reason="辅助证明双方对借款事实的认知，补强转账记录",
        ),
        EvidencePriorityCard(
            evidence_id="EV-D-RECEIPT",
            title="被告还款凭证",
            priority=EvidencePriority.supporting,
            reason="证明部分还款事实，影响金额计算",
        ),
        EvidencePriorityCard(
            evidence_id="EV-D-WITNESS",
            title="证人证言",
            priority=EvidencePriority.background,
            reason="第三人陈述，需结合其他证据评估可信度",
        ),
    ]

    layer1 = Layer1Cover(
        cover_summary=cover,
        timeline=timeline,
        evidence_priorities=evidence_priorities,
    )

    # --- Layer 2: Neutral Core ---
    fact_base = [
        FactBaseEntry(
            fact_id="FACT-001",
            description="2025年1月10日，原告银行账户向被告账户转账10万元（银行流水确认）",
            source_evidence_ids=["EV-P-TRANSFER"],
        ),
        FactBaseEntry(
            fact_id="FACT-002",
            description="2025年1月10日，支付宝账户向被告关联账户代付10万元（支付宝记录确认）",
            source_evidence_ids=["EV-P-TRANSFER"],
        ),
        FactBaseEntry(
            fact_id="FACT-003",
            description="双方存在微信通讯记录，内容涉及借款及还款事宜的讨论",
            source_evidence_ids=["EV-P-CHAT"],
        ),
    ]

    issue_map = [
        IssueMapCard(
            issue_id="ISS-001",
            issue_title="借款合意是否成立",
            depth=0,
            plaintiff_thesis="原告主张被告以短期资金周转为由借款20万元，双方存在明确借贷合意",
            defendant_thesis="被告主张款项系第三人老庄借款，自己仅为代收代付，否认与原告存在借贷合意",
            decisive_evidence=["EV-P-TRANSFER", "EV-P-CONTRACT", "EV-P-CHAT"],
            current_gaps=["面对面借款合意的直接证据缺失", "第三人老庄是否实际使用资金待查证"],
            outcome_sensitivity="极高",
        ),
        IssueMapCard(
            issue_id="ISS-002",
            issue_title="还款义务主体认定",
            depth=0,
            plaintiff_thesis="原告主张被告小陈和老庄共同承担还款义务",
            defendant_thesis="被告主张还款义务应由实际借款人老庄独自承担",
            decisive_evidence=["EV-D-WITNESS", "EV-P-CONTRACT"],
            current_gaps=["小陈与老庄之间的资金关系待查证"],
            outcome_sensitivity="高",
        ),
        IssueMapCard(
            issue_id="ISS-002-A",
            issue_title="小陈账户是否由老庄实际控制使用",
            parent_issue_id="ISS-002",
            depth=1,
            plaintiff_thesis="否认老庄控制被告账户，主张小陈为借款人",
            defendant_thesis="老庄使用被告账户收付款，被告仅提供账户便利",
            decisive_evidence=["EV-D-WITNESS"],
            current_gaps=["账户使用记录待调取"],
            outcome_sensitivity="中",
        ),
    ]

    evidence_cards = []
    if include_evidence_cards:
        evidence_cards = [
            EvidenceKeyCard(
                evidence_id="EV-P-TRANSFER",
                q1_what="银行转账记录，记载2025年1月10日原告向被告账户转账10万元",
                q2_target="证明资金实际交付，支持借贷关系成立的争点ISS-001",
                q3_key_risk="转账记录仅能证明资金流向，不能单独证明借贷合意",
                q4_best_attack="被告可主张转账系代收代付，非借款行为",
                q5_reinforce="结合借条和微信聊天记录形成完整证据链",
                q6_failure_impact="若银行转账记录被质疑，资金交付事实将无法确认，借贷关系基础动摇",
                priority=EvidencePriority.core,
            ),
            EvidenceKeyCard(
                evidence_id="EV-P-CONTRACT",
                q1_what="借款协议/借条，载明借款金额20万元、借款日期及双方签名",
                q2_target="直接证明借贷合意存在，支持ISS-001和ISS-002",
                q3_key_risk="借条签署真实性可能被质疑，是否为后补存在争议",
                q4_best_attack="被告主张签名非本人所签或系被胁迫签署",
                q5_reinforce="申请笔迹鉴定确认签名真实性",
                q6_failure_impact="借条失效将使借贷合意失去直接书面证据，需依赖间接证据链",
                priority=EvidencePriority.core,
            ),
            EvidenceBasicCard(
                evidence_id="EV-P-CHAT",
                q1_what="微信聊天记录，双方讨论借款和还款事宜",
                q2_target="辅助证明双方对借款事实有共同认知",
                q3_key_risk="电子证据真实性和完整性可能被质疑",
                q4_best_attack="被告可主张聊天记录截取不完整或被篡改",
                priority=EvidencePriority.supporting,
            ),
            EvidenceBasicCard(
                evidence_id="EV-D-RECEIPT",
                q1_what="被告提供的部分还款转账凭证",
                q2_target="证明已部分履行还款义务，影响金额计算",
                q3_key_risk="还款凭证指向的收款人可能不是原告本人",
                q4_best_attack="原告可主张还款对象并非本人，该笔还款不应扣减",
                priority=EvidencePriority.supporting,
            ),
            EvidenceBasicCard(
                evidence_id="EV-D-WITNESS",
                q1_what="第三人老庄的证人证言，称借款系其个人行为",
                q2_target="支持被告关于代收代付的抗辩主张",
                q3_key_risk="证人与被告存在利害关系，证言可信度存疑",
                q4_best_attack="原告可质疑证人与被告串通作证，要求法院降低证言证明力",
                priority=EvidencePriority.background,
            ),
        ]

    scenario_tree = ConditionalScenarioTree(
        tree_id="SCN-001",
        case_id="case-civil-loan-test",
        root_node_id="N1",
        nodes=[
            ConditionalNode(
                node_id="N1",
                condition="借条签名真实性是否被法院采信？",
                yes_child_id="N2",
                no_outcome="借贷合意证据不足，原告需依赖其他间接证据",
                related_evidence_ids=["EV-P-CONTRACT"],
            ),
            ConditionalNode(
                node_id="N2",
                condition="银行转账+支付宝代付是否足以证明资金交付20万元？",
                yes_outcome="借贷关系成立，被告应承担还款义务",
                no_outcome="资金交付存疑，需进一步举证",
                related_evidence_ids=["EV-P-TRANSFER"],
            ),
        ],
    )

    unified_electronic_strategy = (
        "**电子证据补强策略**：微信聊天记录应通过公证保全固定，"
        "确保提交原始设备或公证副本。支付宝代付记录需从支付宝官方获取"
        "加盖公章的交易明细。建议对所有电子数据进行区块链存证。"
    )

    layer2 = Layer2Core(
        fact_base=fact_base,
        issue_map=issue_map,
        evidence_cards=evidence_cards,
        unified_electronic_strategy=unified_electronic_strategy,
        scenario_tree=scenario_tree,
    )

    # --- Layer 3: Perspectives ---
    outputs = []
    if include_layer3_content:
        plaintiff_output = PerspectiveOutput(
            perspective="plaintiff",
            evidence_supplement_checklist=[
                "补充银行流水完整对账单，覆盖借款前后一个月的所有交易记录",
                "申请支付宝官方出具加盖公章的代付交易明细及关联账户信息",
                "对微信聊天记录进行公证保全，确保电子证据的法律效力",
            ],
            cross_examination_points=[
                "针对「证人证言」：质疑证人老庄与被告的利害关系，要求说明为何不出庭作证",
                "针对「还款凭证」：核实还款收款账户是否确为原告本人账户",
            ],
            trial_questions=[
                "问被告（借款合意）：如果仅是代收代付，为何微信中讨论还款安排？",
                "问被告（还款义务）：请说明与老庄之间的资金往来记录",
                "问被告（主体认定）：请提供账户由老庄使用的具体证据",
            ],
            contingency_plans=[
                "若借条签名被质疑：立即申请司法笔迹鉴定，同时准备其他间接证据补强",
                "若支付宝代付记录关联性被质疑：提供原告与代付账户持有人的关系证明",
            ],
            over_assertion_boundaries=[
                "不建议在利息计算上过度主张，因借条未约定利率则按法定标准计算",
                "不建议坚持要求被告承担全部诉讼费用，法院有自由裁量权",
            ],
            unified_electronic_evidence_strategy=unified_electronic_strategy,
        )

        defendant_output = PerspectiveOutput(
            perspective="defendant",
            evidence_supplement_checklist=[
                "提供老庄与被告之间的资金往来记录，证明代收代付关系",
                "收集老庄使用被告账户的其他交易记录作为旁证",
                "准备老庄的书面说明或出庭作证材料",
            ],
            cross_examination_points=[
                "针对「银行转账记录」：主张转账仅证明资金流向，不能证明借贷合意",
                "针对「微信聊天记录」：要求出示完整原始记录，质疑截取的选择性",
            ],
            trial_questions=[
                "问原告（借款合意）：请说明具体在何时何地与被告面对面达成借款合意",
                "问原告（资金交付）：为何分两种方式（银行+支付宝）支付？",
            ],
            contingency_plans=[
                "若法院倾向认定借贷关系成立：转而争取减少认定金额，主张部分已还",
                "若证人证言被质疑：补充老庄的银行流水证明其确实需要借款",
            ],
            over_assertion_boundaries=[
                "不建议完全否认收到款项（银行流水无法否认），应聚焦于款项性质",
                "不建议编造与老庄的代收代付协议，如无书面文件应如实陈述",
            ],
            unified_electronic_evidence_strategy=unified_electronic_strategy,
        )
        outputs = [plaintiff_output, defendant_output]

    layer3 = Layer3Perspective(outputs=outputs)

    # --- Layer 4: Appendix ---
    # Adversarial transcripts
    transcripts_md = (
        "### Round 1 (claim)\n\n"
        "**plaintiff_agent** — 原告主张\n\n"
        "原告主张被告以短期资金周转为由向原告借款20万元。"
        "2025年1月10日，原告通过银行转账和支付宝代付共计支付20万元。"
        "原告持有借条和转账记录，证据链完整。\n\n"
        "*引用证据*: EV-P-TRANSFER, EV-P-CONTRACT\n\n---\n\n"
        "**defendant_agent** — 被告抗辩\n\n"
        "被告否认存在借贷合意，主张款项系第三人老庄借款，"
        "被告仅为代收代付。被告账户由老庄实际使用。\n\n"
        "*引用证据*: EV-D-WITNESS\n\n---\n\n"
        "### Round 2 (rebuttal)\n\n"
        "**plaintiff_agent** — 原告质证\n\n"
        "原告提交微信聊天记录证明被告本人参与借款协商。"
        "聊天记录显示被告承认欠款事实并讨论还款安排。\n\n"
        "*引用证据*: EV-P-CHAT\n\n---\n\n"
        "**defendant_agent** — 被告反驳\n\n"
        "被告质疑微信聊天记录的完整性和真实性，"
        "主张聊天内容系代老庄与原告沟通，非被告本人意思表示。"
        "被告提供部分还款凭证证明老庄已部分还款。\n\n"
        "*引用证据*: EV-D-RECEIPT\n\n---\n\n"
        "### Round 3 (closing)\n\n"
        "**plaintiff_agent** — 原告总结\n\n"
        "综合银行转账、借条、微信聊天记录三重证据，"
        "借贷关系成立的证据链完整。被告的代收代付抗辩缺乏书面协议支撑。\n\n"
        "*引用证据*: EV-P-TRANSFER, EV-P-CONTRACT, EV-P-CHAT\n\n---\n\n"
        "**defendant_agent** — 被告总结\n\n"
        "被告坚持代收代付主张，证人老庄可出庭作证。"
        "原告未能证明与被告面对面达成借款合意。\n\n"
        "*引用证据*: EV-D-WITNESS, EV-D-RECEIPT\n\n---"
    )

    # Evidence index table
    evidence_index_md = (
        "| 编号 | 标题 | 类型 | 提交方 | 状态 |\n"
        "|------|------|------|--------|------|\n"
        "| EV-P-TRANSFER | 银行转账记录 | documentary | party-plaintiff | submitted |\n"
        "| EV-P-CONTRACT | 借款协议 | documentary | party-plaintiff | submitted |\n"
        "| EV-P-CHAT | 微信聊天记录 | electronic | party-plaintiff | submitted |\n"
        "| EV-D-RECEIPT | 还款凭证 | documentary | party-defendant | submitted |\n"
        "| EV-D-WITNESS | 证人证言 | testimonial | party-defendant | submitted |"
    )

    # Timeline
    timeline_md = (
        "| 日期 | 事件 | 来源 | 争议 |\n"
        "|------|------|------|------|\n"
        "| 2025-01-10 | 原告通过银行转账向被告支付10万元 | EV-P-TRANSFER |  |\n"
        "| 2025-01-10 | 原告通过支付宝代付10万元 | EV-P-TRANSFER |  |\n"
        "| 2025-01-15 | 双方微信沟通还款事宜 | EV-P-CHAT |  |\n"
        "| 2025-02-01 | 被告声称款项系第三人借款 | EV-D-WITNESS | ⚠️ |\n"
        "| 2025-03-01 | 原告向法院提起民事诉讼 | case_data |  |"
    )

    # Amount calculation (civil_loan specific!)
    amount_md = ""
    if include_amount:
        amount_md = (
            "| 项目 | 金额 | 说明 |\n"
            "|------|------|------|\n"
            "| 借款本金 | 200,000 元 | 银行转账10万+支付宝代付10万 |\n"
            "| 已还金额 | 30,500 元 | 被告提供的还款凭证确认 |\n"
            "| 剩余本金 | 169,500 元 | 原告诉请偿还金额 |\n"
            "| 利息计算 | 按LPR计算 | 自起诉之日起至实际偿清之日止 |\n"
            "| 诉讼费用 | 待定 | 原告主张由被告承担 |"
        )

    # Glossary (always present)
    glossary_md = (
        "| 术语 | 解释 |\n"
        "|------|------|\n"
        "| 争点 | 双方在事实或法律适用上存在分歧的焦点问题 |\n"
        "| 举证责任 | 当事人应当对其主张的事实承担提供证据并加以证明的责任 |\n"
        "| 质证 | 对对方提交的证据进行审查、核实、反驳的诉讼行为 |\n"
        "| 书证 | 以文字、符号、图形等记载或表示的内容来证明案件事实的证据 |\n"
        "| 电子数据 | 通过电子邮件、聊天记录、电子交易记录等形成的信息数据 |\n"
        "| 证明力 | 证据对待证事实的证明价值和说服力 |\n"
        "| 可采性 | 证据是否符合法定条件，能否被法庭采纳使用 |\n"
        "| 借款合意 | 借贷双方就借款事项达成的一致意思表示 |"
    )

    layer4 = Layer4Appendix(
        adversarial_transcripts_md=transcripts_md,
        evidence_index_md=evidence_index_md,
        timeline_md=timeline_md,
        glossary_md=glossary_md,
        amount_calculation_md=amount_md,
    )

    return FourLayerReport(
        report_id="rpt-v3-civilloan-test",
        case_id="case-civil-loan-wang-v-chen-zhuang-2025",
        run_id="run-test-civil-loan",
        perspective=perspective,
        layer1=layer1,
        layer2=layer2,
        layer3=layer3,
        layer4=layer4,
    )


_CASE_DATA = {
    "case_id": "case-civil-loan-wang-v-chen-zhuang-2025",
    "case_type": "civil_loan",
    "parties": {
        "plaintiff": {"party_id": "party-plaintiff-wang", "name": "老王"},
        "defendant": {"party_id": "party-defendant-chen", "name": "小陈"},
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# Acceptance Matrix Check 1: MD render contract 10/10 pass
# ═══════════════════════════════════════════════════════════════════════════


class TestMDRenderContract:
    """All 10 render contract rules must pass for civil_loan."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_civil_loan_md_passes_full_render_contract(self, _mock_redact):
        """The full pipeline MD output passes all 10 render contract rules."""
        report = _make_civil_loan_report()

        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            )
            content = md_path.read_text(encoding="utf-8")

        # Should not raise — if it does, the test fails with the violation details
        results = lint_markdown_render_contract(
            content, evidence_ids=_CIVIL_LOAN_EVIDENCE_IDS
        )
        # Only WARN results should remain (no ERRORs)
        errors = [r for r in results if r.severity == LintSeverity.ERROR]
        assert errors == [], f"ERROR-level violations: {errors}"

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_no_forbidden_tokens(self, _mock_redact):
        report = _make_civil_loan_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        # No internal IDs leak
        assert not re.search(r"\bissue-[a-z0-9-]+\b", content, re.IGNORECASE)
        assert not re.search(r"\bxexam-[a-z0-9-]+\b", content, re.IGNORECASE)
        assert not re.search(r"\bundefined\b", content, re.IGNORECASE)

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_no_raw_json_leak(self, _mock_redact):
        report = _make_civil_loan_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert '{"' not in content
        assert '[{"' not in content

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_no_duplicate_headings(self, _mock_redact):
        report = _make_civil_loan_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        headings = re.findall(r"(?m)^##\s+(.+?)\s*$", content)
        assert len(headings) == len(set(headings)), (
            f"Duplicate headings found: {[h for h in headings if headings.count(h) > 1]}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Acceptance Matrix Check 2: DOCX render contract pass
# ═══════════════════════════════════════════════════════════════════════════


class TestDOCXRenderContract:
    """DOCX render contract subset must pass for civil_loan."""

    def test_civil_loan_docx_passes_lint(self):
        """Generate DOCX for civil_loan and verify render contract."""
        try:
            from engines.report_generation.docx_generator import generate_docx_v3_report
            from engines.report_generation.v3.docx_lint import lint_docx_render_contract
        except ImportError:
            pytest.skip("docx dependencies not available")

        report = _make_civil_loan_report()
        report_data = json.loads(report.model_dump_json())

        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = generate_docx_v3_report(
                output_dir=Path(tmpdir),
                report_v3=report_data,
            )
            assert docx_path.exists()
            results = lint_docx_render_contract(docx_path)
            errors = [r for r in results if r.severity == LintSeverity.ERROR]
            assert errors == [], f"DOCX lint errors: {errors}"


# ═══════════════════════════════════════════════════════════════════════════
# Acceptance Matrix Check 3: Fallback ratio ≤ threshold
# ═══════════════════════════════════════════════════════════════════════════


class TestFallbackRatio:
    """Fallback ratio must be within acceptable bounds."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_civil_loan_fallback_ratio_below_threshold(self, _mock_redact):
        """With substantive content, fallback ratio should be ≤0.20."""
        report = _make_civil_loan_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        ratio, fb_count, total = compute_fallback_ratio(content)
        assert total > 0, "Report has no ## sections"
        assert ratio <= 0.20, (
            f"Fallback ratio {ratio:.0%} ({fb_count}/{total} sections) "
            f"exceeds 0.20 threshold"
        )

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_fallback_sections_enumerated(self, _mock_redact):
        """Identify any fallback sections for debugging."""
        report = _make_civil_loan_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")

        # Extract all ## sections and identify fallbacks
        fallback_re = re.compile(
            r"\*(?:暂无.+[。.]|No .+ available\.)\*"
            r"|"
            r"（无.+）"
        )
        headings = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", content))
        fallback_sections = []
        for i, m in enumerate(headings):
            title = m.group(1).strip()
            start = m.end()
            end = headings[i + 1].start() if i + 1 < len(headings) else len(content)
            body = content[start:end].strip()
            if fallback_re.fullmatch(body.strip()):
                fallback_sections.append(title)

        # This is informational — track which sections fall back
        if fallback_sections:
            pytest.fail(
                f"Fallback sections found (should be 0 for civil_loan with full data): "
                f"{fallback_sections}"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Acceptance Matrix Check 4: All major sections ≥50 chars
# ═══════════════════════════════════════════════════════════════════════════


class TestSectionContentLength:
    """All major sections must have substantive content (≥50 chars)."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_all_major_sections_substantive(self, _mock_redact):
        report = _make_civil_loan_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")

        headings = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", content))
        short_sections = []
        for i, m in enumerate(headings):
            title = m.group(1).strip()
            start = m.end()
            end = headings[i + 1].start() if i + 1 < len(headings) else len(content)
            body = content[start:end].strip()
            # Strip markdown syntax for clean char count
            clean = re.sub(r"[#*_`>|~\-]", "", body).strip()
            if 0 < len(clean) < 50:
                short_sections.append((title, len(clean)))

        assert short_sections == [], (
            f"Sections with <50 chars: {short_sections}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Acceptance Matrix Check 5: No orphan evidence citations
# ═══════════════════════════════════════════════════════════════════════════


class TestOrphanCitations:
    """No [src-xxx] citations should reference non-existent evidence."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_no_orphan_citations(self, _mock_redact):
        report = _make_civil_loan_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")

        # Verify no orphans when we pass the known evidence IDs
        # lint_markdown_render_contract would raise on orphans,
        # so if write_v3_report_md succeeds, this is already validated.
        # But let's also explicitly check:
        citation_re = re.compile(r"\[src-([^\]]+)\]")
        citations = citation_re.findall(content)
        if citations:
            for ref in citations:
                full_ref = f"src-{ref}"
                assert full_ref in _CIVIL_LOAN_EVIDENCE_IDS or ref in _CIVIL_LOAN_EVIDENCE_IDS, (
                    f"Orphan citation [src-{ref}] not in evidence index"
                )


# ═══════════════════════════════════════════════════════════════════════════
# Acceptance Matrix Check 6: Amount calculation section present + correct
# ═══════════════════════════════════════════════════════════════════════════


class TestAmountCalculation:
    """civil_loan must have an amount calculation section."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_amount_calculation_section_present(self, _mock_redact):
        report = _make_civil_loan_report(include_amount=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "金额计算明细" in content, "Amount calculation section missing"

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_amount_calculation_has_loan_fields(self, _mock_redact):
        """Civil loan amount section must include principal, repaid, and remaining."""
        report = _make_civil_loan_report(include_amount=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "借款本金" in content, "Principal amount missing"
        assert "200,000" in content, "Principal value incorrect"
        assert "已还金额" in content or "30,500" in content, "Repaid amount missing"
        assert "利息" in content, "Interest section missing"

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_amount_section_absent_when_no_amount_report(self, _mock_redact):
        """When amount_report is None, section should NOT appear (not empty)."""
        report = _make_civil_loan_report(include_amount=False)
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        # The section header should not appear when there's no amount data
        # (layer4 render skips it when "暂无" is in the amount_md)
        assert "## 4.4 金额计算明细" not in content, (
            "Amount section should be skipped when no amount data"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Acceptance Matrix Check 7: Executive summary non-boilerplate
# ═══════════════════════════════════════════════════════════════════════════


class TestExecutiveSummary:
    """Executive summary must be substantive, not template text."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_neutral_conclusion_is_substantive(self, _mock_redact):
        report = _make_civil_loan_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")

        # Find the neutral conclusion section
        conclusion_match = re.search(
            r"##\s+A\.\s+中立结论摘要.*?\n(.+?)(?=\n##|\n---|\Z)",
            content,
            re.DOTALL,
        )
        assert conclusion_match, "Neutral conclusion section not found"
        conclusion_text = conclusion_match.group(1).strip()

        # Must be non-boilerplate
        boilerplate_patterns = [
            r"^[?？]+$",  # All question marks (like the sample report)
            r"^\*暂无",  # Fallback
            r"^（无",  # Fallback
            r"^No .+ available",  # English fallback
        ]
        for pattern in boilerplate_patterns:
            assert not re.match(pattern, conclusion_text), (
                f"Conclusion is boilerplate: '{conclusion_text[:50]}'"
            )

        # Must mention case-specific details
        assert len(conclusion_text) >= 30, (
            f"Conclusion too short ({len(conclusion_text)} chars): '{conclusion_text}'"
        )

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_winning_move_present(self, _mock_redact):
        report = _make_civil_loan_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "胜负手" in content, "Winning move section missing"

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_blocking_conditions_present(self, _mock_redact):
        report = _make_civil_loan_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "阻断条件" in content, "Blocking conditions section missing"


# ═══════════════════════════════════════════════════════════════════════════
# Acceptance Matrix Check 8: Layer3 perspectives substantive
# ═══════════════════════════════════════════════════════════════════════════


class TestLayer3Perspectives:
    """Both plaintiff and defendant perspectives must have substantive content."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_both_perspectives_present(self, _mock_redact):
        report = _make_civil_loan_report(perspective="neutral")
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "原告策略" in content, "Plaintiff strategy section missing"
        assert "被告策略" in content, "Defendant strategy section missing"

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_plaintiff_has_five_action_sections(self, _mock_redact):
        """Plaintiff output should include all 5 V3.1 action sections."""
        report = _make_civil_loan_report(perspective="neutral")
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        # Check all 5 action subsections appear under plaintiff
        assert "补证清单" in content, "补证清单 missing"
        assert "质证要点" in content, "质证要点 missing"
        assert "庭审发问" in content, "庭审发问 missing"
        assert "应对预案" in content, "应对预案 missing"
        assert "过度主张边界" in content, "过度主张边界 missing"

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_each_perspective_is_substantive(self, _mock_redact):
        """Each perspective section must have ≥100 chars of content."""
        report = _make_civil_loan_report(perspective="neutral")
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")

        # Find plaintiff and defendant sections
        for label in ["原告策略", "被告策略"]:
            pattern = rf"##\s+{label}.*?\n(.+?)(?=\n##\s+(?:原告|被告)策略|\n---|\n#\s+四|\Z)"
            match = re.search(pattern, content, re.DOTALL)
            assert match, f"{label} section not found"
            section_text = match.group(1).strip()
            clean = re.sub(r"[#*_`>|~\-\d\.]", "", section_text).strip()
            assert len(clean) >= 100, (
                f"{label} section too short ({len(clean)} chars)"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Additional structural checks (civil_loan specific)
# ═══════════════════════════════════════════════════════════════════════════


class TestCivilLoanStructure:
    """Structural integrity checks specific to civil_loan case type."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_four_layer_structure_present(self, _mock_redact):
        """Report must have all 4 top-level layers."""
        report = _make_civil_loan_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "# 一、封面摘要" in content
        assert "# 二、中立对抗内核" in content
        assert "# 三、角色化输出" in content
        assert "# 四、附录" in content

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_issue_map_has_civil_loan_issues(self, _mock_redact):
        """Issue map must contain civil_loan-specific issues."""
        report = _make_civil_loan_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "借款合意" in content, "Core civil loan issue missing"

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_evidence_cards_rendered(self, _mock_redact):
        """Evidence cards (dual-tier) must be rendered in Layer 2."""
        report = _make_civil_loan_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "核心证据详析" in content, "Key evidence cards section missing"
        assert "辅助/背景证据概览" in content, "Basic evidence cards section missing"

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_unified_electronic_strategy_present(self, _mock_redact):
        """Unified electronic evidence strategy must be in report."""
        report = _make_civil_loan_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "电子证据补强策略" in content

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_scenario_tree_rendered(self, _mock_redact):
        """Conditional scenario tree must be rendered."""
        report = _make_civil_loan_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "条件场景树" in content

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_glossary_present(self, _mock_redact):
        """Glossary section must be present in appendix."""
        report = _make_civil_loan_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "术语表" in content
        assert "借款合意" in content  # Civil loan specific term

    def test_report_json_roundtrip(self):
        """FourLayerReport must serialize/deserialize cleanly."""
        report = _make_civil_loan_report()
        json_str = report.model_dump_json(indent=2)
        parsed = json.loads(json_str)
        restored = FourLayerReport.model_validate(parsed)
        assert restored.case_id == report.case_id
        assert len(restored.layer2.evidence_cards) == len(report.layer2.evidence_cards)
        assert len(restored.layer3.outputs) == len(report.layer3.outputs)
        assert restored.layer4.amount_calculation_md == report.layer4.amount_calculation_md


# ═══════════════════════════════════════════════════════════════════════════
# Regression: threshold bug detection
# ═══════════════════════════════════════════════════════════════════════════


class TestThresholdConfiguration:
    """Verify the fallback ratio threshold is correctly set per Phase 3d."""

    def test_hard_gate_threshold_is_0_20(self):
        """Phase 3d should have set the hard gate to 0.20 (not 0.25 or 0.35).

        The plan specifies: Phase 3d final: 0.20.

        This test documents the EXPECTED state. If it fails, the
        threshold in report_writer.py needs updating.
        """
        import ast
        import inspect

        source = inspect.getsource(write_v3_report_md)
        tree = ast.parse(source)

        threshold_values = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                if (
                    isinstance(node.left, ast.Name)
                    and node.left.id == "ratio"
                    and len(node.ops) == 1
                    and isinstance(node.ops[0], ast.Gt)
                    and len(node.comparators) == 1
                    and isinstance(node.comparators[0], ast.Constant)
                ):
                    threshold_values.append(node.comparators[0].value)

        assert 0.20 in threshold_values, (
            f"Hard gate threshold 0.20 not found in write_v3_report_md. "
            f"Current thresholds: {threshold_values}"
        )
        assert 0.25 not in threshold_values, (
            f"Found ratio > 0.25 in write_v3_report_md — "
            f"Phase 3d threshold change (0.25→0.20) was NOT applied. "
            f"Current thresholds: {threshold_values}"
        )
        assert 0.35 not in threshold_values, (
            f"Found ratio > 0.35 in write_v3_report_md — "
            f"original threshold was never tightened. "
            f"Current thresholds: {threshold_values}"
        )
