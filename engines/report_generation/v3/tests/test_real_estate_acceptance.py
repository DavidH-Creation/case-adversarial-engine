"""Phase 3c: real_estate case type structural validation against v3 acceptance matrix.

Acceptance matrix checks (from plans/v3-plan.md S3.2):
  1. MD render contract 10/10 pass
  2. DOCX render contract pass
  3. Fallback ratio <= 0.20 (Phase 3d final threshold)
  4. All major sections have substantive content (>=50 chars)
  5. No orphan evidence citations
  6. Amount calculation handled correctly (real_estate HAS deposit/contract price/penalty)
  7. Executive summary non-boilerplate
  8. Layer3 three perspectives (plaintiff/defendant/neutral) have substantive content

Key differences from civil_loan and labor_dispute:
  - Evidence patterns: purchase contracts, deposit receipts, property records, WeChat refusal,
    bank approval letters, appraisal reports, defense statements
  - Issues: contract validity, specific performance vs rescission, deposit penalty (dingjin),
    breach of contract damages, mortgage/lien encumbrances
  - Amount calculation: deposit (dingjin vs dingjin), contract price, penalty (20% clause),
    double-return deposit, appraisal appreciation — not principal+interest or N/2N
  - Legal framework: Civil Code contract chapters + Real Property Registration Ordinance,
    not loan provisions or Labor Contract Law
  - Property-specific: ownership transfer (guohu), mortgage release, appraisal valuation
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from unittest.mock import patch

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
# Real-estate-specific fixtures -- realistic data for 陈某诉刘某 pattern
# (house purchase dispute: buyer sues seller who refuses to complete transfer)
# ---------------------------------------------------------------------------

_REAL_ESTATE_EVIDENCE_IDS = {
    "EV-P-CONTRACT",
    "EV-P-DEPOSIT",
    "EV-P-WECHAT",
    "EV-P-BANK",
    "EV-P-APPRAISAL",
    "EV-D-DEFENSE",
    "EV-D-MORTGAGE",
}


def _make_real_estate_report(
    *,
    perspective: str = "neutral",
    include_amount: bool = True,
    include_evidence_cards: bool = True,
    include_layer3_content: bool = True,
    fallback_sections: int = 0,
) -> FourLayerReport:
    """Build a realistic real_estate FourLayerReport for acceptance testing.

    This mimics what the pipeline produces for a 房屋买卖合同纠纷 case with:
    - 3 core issues (合同效力, 继续履行, 违约责任/定金罚则)
    - 7 evidence items (5 plaintiff, 2 defendant)
    - Amount calculation (deposit, contract price, penalty, appraisal delta)
    - Both plaintiff and defendant perspectives
    """
    # --- Layer 1: Cover Summary ---
    cover = CoverSummary(
        neutral_conclusion=(
            "本案涉及房屋买卖合同纠纷，原告陈某（买方）主张被告刘某（卖方）"
            "拒绝履行已签订的房屋买卖合同，要求继续履行合同完成过户。"
            "核心争点在于合同效力是否因被告主张的重大误解而受影响，"
            "以及房产存在抵押是否构成客观履行障碍。"
            "被告在房价上涨后反悔，双方在违约责任承担上存在根本分歧。"
        ),
        winning_move=(
            "房屋买卖合同（EV-P-CONTRACT）与定金收据（EV-P-DEPOSIT）"
            "形成完整的合同成立证据链。银行预批函（EV-P-BANK）证明原告"
            "具备全部履约能力。微信聊天记录（EV-P-WECHAT）直接证明被告"
            "拒绝过户系因房价上涨而非合同瑕疵，是认定被告恶意违约的关键证据。"
            "若法院采信上述证据链，判决继续履行的概率显著高于合同解除。"
        ),
        blocking_conditions=[
            "若法院认定被告签约时对房价存在重大误解，合同可能被撤销，原告仅能主张返还定金",
            "若房产抵押无法在判决执行期内解除，继续履行可能因客观障碍被驳回",
            "若法院认定违约金56万元明显过高，可能酌减至实际损失（房价差额38万元）水平",
        ],
    )

    timeline = [
        TimelineEvent(date="2025-01-08", event="双方签订房屋买卖合同，约定成交价280万元", source="EV-P-CONTRACT"),
        TimelineEvent(date="2025-01-08", event="原告支付定金28万元（合同价10%），被告出具收据", source="EV-P-DEPOSIT"),
        TimelineEvent(date="2025-02-15", event="被告微信告知不想卖房，称行情好280万太亏", source="EV-P-WECHAT"),
        TimelineEvent(date="2025-02-18", event="房产评估报告出具，评估价318万元（较合同价上涨38万）", source="EV-P-APPRAISAL"),
        TimelineEvent(date="2025-02-20", event="银行出具贷款预批函，批准按揭贷款140万元", source="EV-P-BANK"),
        TimelineEvent(date="2025-03-01", event="原告向法院提起民事诉讼", source="case_data"),
    ]

    evidence_priorities = [
        EvidencePriorityCard(
            evidence_id="EV-P-CONTRACT",
            title="房屋买卖合同",
            priority=EvidencePriority.core,
            reason="直接证明买卖合意成立、价格条款及违约责任约定，是认定合同关系的基础证据",
            controls_issue_ids=["ISS-001", "ISS-002"],
        ),
        EvidencePriorityCard(
            evidence_id="EV-P-DEPOSIT",
            title="定金收据及银行转账凭证",
            priority=EvidencePriority.core,
            reason="证明定金28万元已实际交付，触发定金罚则的前提条件成立",
            controls_issue_ids=["ISS-003"],
        ),
        EvidencePriorityCard(
            evidence_id="EV-P-WECHAT",
            title="微信聊天记录",
            priority=EvidencePriority.core,
            reason="直接证明被告拒绝过户系因房价上涨而非合同瑕疵，认定恶意违约的关键",
            controls_issue_ids=["ISS-001", "ISS-002"],
        ),
        EvidencePriorityCard(
            evidence_id="EV-P-BANK",
            title="银行按揭贷款预批函",
            priority=EvidencePriority.supporting,
            reason="证明原告具备全部履约���力，排除原告违约可能",
            controls_issue_ids=["ISS-002"],
        ),
        EvidencePriorityCard(
            evidence_id="EV-P-APPRAISAL",
            title="房产评估报告",
            priority=EvidencePriority.supporting,
            reason="证明房价上涨幅度（38万元），为违约金调整和损失计算提供参考依据",
        ),
        EvidencePriorityCard(
            evidence_id="EV-D-DEFENSE",
            title="被告答辩意见",
            priority=EvidencePriority.supporting,
            reason="记载被告主张的合同撤销事由（重大误解、中介诱导），需逐一审查",
        ),
        EvidencePriorityCard(
            evidence_id="EV-D-MORTGAGE",
            title="房产查档记录（含抵押信息）",
            priority=EvidencePriority.supporting,
            reason="证明房产存在抵押，被告据此主张客观履行障碍",
            controls_issue_ids=["ISS-002"],
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
            description="2025年1月8日，原告陈某与被告刘某签订房屋买卖合同，约定成交价280万元，经中介公司见证",
            source_evidence_ids=["EV-P-CONTRACT"],
        ),
        FactBaseEntry(
            fact_id="FACT-002",
            description="同日原告通过银行转账支付定金28万元（合同价10%），被告出具定金收据",
            source_evidence_ids=["EV-P-DEPOSIT"],
        ),
        FactBaseEntry(
            fact_id="FACT-003",
            description="2025年2月15日被告通过微信明确表示不愿继续履行合同，称280万元太亏，房价行情好",
            source_evidence_ids=["EV-P-WECHAT"],
        ),
        FactBaseEntry(
            fact_id="FACT-004",
            description="该房产存在一笔2022年设定的银行抵押，至诉讼时尚未解除",
            source_evidence_ids=["EV-D-MORTGAGE"],
        ),
        FactBaseEntry(
            fact_id="FACT-005",
            description="2025年2月评估报告显示房产市场价值318万元，较合同价上涨约38万元",
            source_evidence_ids=["EV-P-APPRAISAL"],
        ),
    ]

    issue_map = [
        IssueMapCard(
            issue_id="ISS-001",
            issue_title="合同效力：买卖合同是否有效成立",
            depth=0,
            plaintiff_thesis=(
                "原告主张合同系双方真实意思表示，经中介见证签订，"
                "付款方式、过户时间、违约责任等条款完整，合法有效"
            ),
            defendant_thesis=(
                "被告主张签约时未充分了解市场行情，存在重大误解，"
                "且中介有诱导行为，合同系在信息不对等下签订，有权撤销"
            ),
            decisive_evidence=["EV-P-CONTRACT", "EV-P-WECHAT", "EV-D-DEFENSE"],
            current_gaps=[
                "中介是否向被告充分披露市场行情信息待查证",
                "被告签约时的认知状态是否构成法定重大误解待认定",
            ],
            outcome_sensitivity="极高",
        ),
        IssueMapCard(
            issue_id="ISS-002",
            issue_title="继续履行：合同能否强制继续履行",
            depth=0,
            plaintiff_thesis=(
                "原告主张合同有效且具备全部履约条件，银行已批准按揭贷款，"
                "被告应配合完成过户，抵押可在过户前由被告解除"
            ),
            defendant_thesis=(
                "被告主张房产存在抵押，过户存在客观障碍，"
                "且被告资金困难无法提前还贷解除抵押，非主观恶意"
            ),
            decisive_evidence=["EV-P-BANK", "EV-D-MORTGAGE", "EV-P-CONTRACT"],
            current_gaps=[
                "被告抵押贷款余额及能否通过交易款项解押待查证",
                "法院能否在判决中直接处理抵押解除问题",
            ],
            outcome_sensitivity="极高",
        ),
        IssueMapCard(
            issue_id="ISS-003",
            issue_title="违约责任与定金罚则",
            depth=0,
            plaintiff_thesis=(
                "原告主张被告构成根本违约，应支付合同约定的20%违约金56万元；"
                "若合同解除，被告应依定金罚则双倍返还定金56万元"
            ),
            defendant_thesis=(
                "被告主张即使承担违约责任，56万元违约金明显过高，"
                "应以原告实际损失为基础酌减"
            ),
            decisive_evidence=["EV-P-CONTRACT", "EV-P-APPRAISAL", "EV-P-DEPOSIT"],
            current_gaps=["原告实际损失（房价差额、机会成本）的具体数额待认定"],
            outcome_sensitivity="高",
        ),
        IssueMapCard(
            issue_id="ISS-002-A",
            issue_title="抵押解除的可行性分析",
            parent_issue_id="ISS-002",
            depth=1,
            plaintiff_thesis="原告主张合同已约定过户前由被告解��抵押，被告不得以此为由拒绝履行",
            defendant_thesis="被告主张资金困难，解除抵押需先还清贷款，存在客观障碍",
            decisive_evidence=["EV-D-MORTGAGE"],
            current_gaps=["被告抵押贷款余额及可用交易款项偿还的可行性"],
            outcome_sensitivity="高",
        ),
    ]

    evidence_cards = []
    if include_evidence_cards:
        evidence_cards = [
            EvidenceKeyCard(
                evidence_id="EV-P-CONTRACT",
                q1_what="房屋买卖合同原件，载明房产地址（某路88号601室）、成交价280万元、付款方式、过户期限及违约责任条款",
                q2_target="直接证明买卖合意成立、价格条款确定，支持ISS-001（合同效力）和ISS-002（继续履行）",
                q3_key_risk="合同条款本身无瑕疵，被告可能从签约过程（重大误解、信息不对等）角度攻击",
                q4_best_attack="被告可主张中介未充分告知市场行情，签约过程存在信息不对等，构成可撤销事由",
                q5_reinforce="提供中介公司的居间服务记录，证明信息披露充分，排除重大误解",
                q6_failure_impact="若合同被撤销，所有基于合同的诉请均失去基础，原告仅能主张返还���金",
                priority=EvidencePriority.core,
            ),
            EvidenceKeyCard(
                evidence_id="EV-P-DEPOSIT",
                q1_what="定金收据及银行转账凭证，记载2025年1月8日陈某向刘某支付定金28万元",
                q2_target="证明定金已实际交付，定金罚则适用的前提条件满足，支持ISS-003",
                q3_key_risk="被告可能主张款项性质为订金（意向金）而非定金，试图排除双倍返还",
                q4_best_attack="被告可主张收据上仅写'定金'但双方口头约定为订金，要求法院重新认定款项性质",
                q5_reinforce="合同中明确约定款项为'定金'且引用定金罚则条款，排除其他解释",
                q6_failure_impact="若款项被认定为订金，被告仅需原额退还28万元，原告损失定金罚则保护",
                priority=EvidencePriority.core,
            ),
            EvidenceKeyCard(
                evidence_id="EV-P-WECHAT",
                q1_what="微信聊天记录（2025年2月15-20日），被告明确表示不想卖房、行情好280万太亏",
                q2_target="直接证明被告拒绝履约系因房价上涨，非合同瑕疵，认定恶意违约的关键证据",
                q3_key_risk="电子证据真实性可能被质疑，聊天记录可能被主张不完整",
                q4_best_attack="被告可主张聊天记录经过筛选截取，未反映完整沟通过程",
                q5_reinforce="通过微信公证保全固定证据，提交原始手机设备供法庭核验",
                q6_failure_impact="若聊天记录不被采信，被告可坚持重大误解抗辩，合同撤销风险增大",
                priority=EvidencePriority.core,
            ),
            EvidenceBasicCard(
                evidence_id="EV-P-BANK",
                q1_what="银行按���贷款预批函（2025年2月20日），批准贷款金额140万元",
                q2_target="证明原告具备全部履约能���，排除原告违约可能",
                q3_key_risk="预批函有效期有限，被告可主张拖延至过期后原告丧失履约能力",
                q4_best_attack="被告可质疑预批函仅为意向性文件，非正式贷款承诺",
                priority=EvidencePriority.supporting,
            ),
            EvidenceBasicCard(
                evidence_id="EV-P-APPRAISAL",
                q1_what="房产评估报告（2025年2月18日），评估价318万元，较合同价上涨38万元",
                q2_target="量化房价上涨幅度，为违约金调整和损失计算提供客观依据",
                q3_key_risk="评估方法和时间选择可能被质疑，不同评估机构可能得出不同结论",
                q4_best_attack="被告可申请重新评估或质疑评估基准日选择",
                priority=EvidencePriority.supporting,
            ),
            EvidenceBasicCard(
                evidence_id="EV-D-DEFENSE",
                q1_what="被告答辩意见，主张重大误解、中介诱导及合同可撤销",
                q2_target="记载被告全部抗辩理由，需逐一审查法律依据和证据支撑",
                q3_key_risk="答辩意见系被告单方陈述，无证据支撑则不影响案件认定",
                q4_best_attack="原告可逐条反驳，结合微信记录证明被告真实动机是房价上涨",
                priority=EvidencePriority.supporting,
            ),
            EvidenceBasicCard(
                evidence_id="EV-D-MORTGAGE",
                q1_what="房产查档记��，显示房产存在2022年设定的银行抵押尚未解除",
                q2_target="被告据此主张过户存在客观障碍，非主观违约",
                q3_key_risk="合同已约定过户前由被告解除抵押，被告不得以此为由拒绝",
                q4_best_attack="原告可主张被告隐瞒抵押状态或怠于解除抵押，构成违约",
                priority=EvidencePriority.supporting,
            ),
        ]

    scenario_tree = ConditionalScenarioTree(
        tree_id="SCN-RE-001",
        case_id="case-real-estate-sale-chen-v-liu-2025",
        root_node_id="N1",
        nodes=[
            ConditionalNode(
                node_id="N1",
                condition="法院是否认定被告签约时存在重大误解？",
                yes_outcome="合同可撤销，被告返还定金28万元，原告不享有定金罚则和违约金",
                no_child_id="N2",
                related_evidence_ids=["EV-P-CONTRACT", "EV-D-DEFENSE"],
            ),
            ConditionalNode(
                node_id="N2",
                condition="房产抵押能否在判决执行期内解除？",
                yes_child_id="N3",
                no_outcome="继续履行存在客观障碍，合同解除，被告依定金罚则双倍返还56万元",
                related_evidence_ids=["EV-D-MORTGAGE"],
            ),
            ConditionalNode(
                node_id="N3",
                condition="法院是否支持继续履行合同？",
                yes_outcome="判决被告继续履行，完成过户，原告取得房产所有权",
                no_outcome="合同解除，被告支付违约金（可能酌减）或双倍返还定金",
                related_evidence_ids=["EV-P-BANK", "EV-P-CONTRACT"],
            ),
        ],
    )

    unified_electronic_strategy = (
        "**电子证据补强策略**：微信聊天记录应通过公证机关保全，"
        "提交公证书及原始手机设备供法庭核验。银行转账凭证应从银行调取"
        "加盖公章的交易流水原件。房产评估报告确保评估机构资质有效。"
        "建议对关键电子证据同步进行区块链存证，增强证据不可篡改性。"
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
                "调取中介公司居间服务合同及带看记录，证明信息披露充分，排除被告重大误解主张",
                "申请法院查询被告抵押贷款余���，评估以交易款项偿还抵押贷款的可行性",
                "对微信聊天记录进行公证保全，确保电子证据的法律效力和完整性",
                "调取房产所在小区近期成交案例，补强评估报告的市场比较法依据",
            ],
            cross_examination_points=[
                "针对「重大误解」：要求被告说明签约前是否自行了解过周边房价，中介是否提供了市场参考",
                "针对「抵押障碍」：追问被告抵押贷款余额是多少，能否用买方支付的房款偿还",
                "针对「中介诱导」：要求被告明确中介具体哪些行为构成诱导及相应证据",
            ],
            trial_questions=[
                "问被告（合同效力）：签约前您是否了解过该小区的市场行情���是否咨询过其他中介或评估机构？",
                "问被告（违约动机）：微信中您说280万太亏、行情好，是否因房价上涨才不想履约？",
                "问被告（抵押解除）：您的银行抵押贷款余额是多少？交易款项是否足以偿还？",
                "问中介（签约过程）：签约时是否向被告充分告知了市场行情信息？",
            ],
            contingency_plans=[
                "若法院倾向不支持继续履行：转而主张合同解除加违约金56万元，同时主张定金双倍返还",
                "若违约金可能被酌减：提交房价上涨差额（38万元）作为实际损失证据，主张违约金不应低于此",
            ],
            over_assertion_boundaries=[
                "不建议同时主张继续履行和违约金，二者存在逻辑矛盾，应设为主备关系",
                "不建议要求被告赔偿精神损失，房屋买卖纠纷中精神损害赔偿缺乏法律依据",
                "不建议过度渲染被告恶意，聚焦于违约事实本身即可",
            ],
            unified_electronic_evidence_strategy=unified_electronic_strategy,
        )

        defendant_output = PerspectiveOutput(
            perspective="defendant",
            evidence_supplement_checklist=[
                "收集签约前中介推送的房源信息，证明中介未提供全面市场行情对比",
                "提供银行抵押贷款余额��明，证实解除抵押的资金困难",
                "准备市场行情研究报告，证明签约时对价格存在重大误解的合理性",
            ],
            cross_examination_points=[
                "针对「银行预批函」：指出预批函仅为意向文件，正式贷款审批尚未完成",
                "针对「评估报告」：质疑评估基准日选择和可比案例的代表性",
            ],
            trial_questions=[
                "问原告（履约能力）：除银行预批函外，首付款112万元是否已准备到位？资金来源？",
                "问原告（损失计算）：除房价差额外，有无其他实际损失？看房成本多少？",
                "问中介（信息披露）：签约时是否告知被告该房产近期的市场估价？",
            ],
            contingency_plans=[
                "若合同撤销被驳回：转而主张抵押障碍导致客观不能履行，请求解除合同并减轻违约责任",
                "若需承担违约金：请求法院依《民法典》第585条酌减违约金至实际损失水平",
            ],
            over_assertion_boundaries=[
                "不建议否认收到定金（银行转账无法否认），应聚焦于款项性质和合同效力争议",
                "不建议主张中介欺诈（缺乏直接证据），聚焦于重大误解更具可操作性",
            ],
            unified_electronic_evidence_strategy=unified_electronic_strategy,
        )
        outputs = [plaintiff_output, defendant_output]

    layer3 = Layer3Perspective(outputs=outputs)

    # --- Layer 4: Appendix ---
    # Adversarial transcripts
    transcripts_md = (
        "### Round 1 (claim)\n\n"
        "**plaintiff_agent** -- 原告主张\n\n"
        "原告与被告于2025年1月8日签订房屋买卖合同，约定购买某路88号601室，"
        "成交价280万元。原告已支付定金28万元并取得银行贷款预批。"
        "2025年2月15日，被告以房价上涨为由拒绝继续履行合同。"
        "原告请求判决继续履行合同并完成过户，或被告支付违约金56万元。\n\n"
        "*引用证据*: EV-P-CONTRACT, EV-P-DEPOSIT, EV-P-BANK\n\n---\n\n"
        "**defendant_agent** -- 被告抗辩\n\n"
        "被告主张签约时未充分了解市场行情，对280万元的价格存在重大误��。"
        "中介有诱导行为，合同系在信息不对等下签订。"
        "此外房产存在抵押，过户存在客观障碍。"
        "请求法院认定合同可撤销，退还定金。\n\n"
        "*引用证据*: EV-D-DEFENSE, EV-D-MORTGAGE\n\n---\n\n"
        "### Round 2 (rebuttal)\n\n"
        "**plaintiff_agent** -- 原告质证\n\n"
        "微信聊天记录直接证明被告拒绝履约系因房价上涨而非合同瑕疵。"
        "被告说'行情好，280万太亏'，说明其完全知晓房价情况，不构成重大误解。"
        "房产评估报告显示房价上涨38万元，被告动机明显。"
        "抵押可在过户前用交易款项解除，不构成客观障碍。\n\n"
        "*引用证据*: EV-P-WECHAT, EV-P-APPRAISAL\n\n---\n\n"
        "**defendant_agent** -- 被告反驳\n\n"
        "被告承认房价有所上涨，但主张签约时确实对市场价格缺乏判断。"
        "中介未提供市场行情分析，被告系在信息不充分情况下签约。"
        "抵押贷款余额较高，被告资金困难无法���前还贷。\n\n"
        "*引用证据*: EV-D-DEFENSE, EV-D-MORTGAGE\n\n---\n\n"
        "### Round 3 (closing)\n\n"
        "**plaintiff_agent** -- 原告总结\n\n"
        "合同系双方真实意思表示，经中介见证签订，合法有效。"
        "被告微信已自认房价上涨是拒绝履约的真实原因。"
        "原告具备全部履约能力，请求判决继续履行。"
        "若合同解除，依定金罚则被告应双倍返还定金。\n\n"
        "*引用证据*: EV-P-CONTRACT, EV-P-WECHAT, EV-P-BANK\n\n---\n\n"
        "**defendant_agent** -- 被告总结\n\n"
        "被告坚持合同存在重大误解，请求撤销。"
        "若不予撤销，请求法院酌减违约金至合理水平。"
        "被告并非恶意违约，资金困难和抵押障碍客观存在。\n\n"
        "*引用证据*: EV-D-DEFENSE, EV-D-MORTGAGE\n\n---"
    )

    # Evidence index table
    evidence_index_md = (
        "| 编号 | 标题 | 类型 | 提交方 | 状态 |\n"
        "|------|------|------|--------|------|\n"
        "| EV-P-CONTRACT | 房屋买卖合同 | documentary | party-plaintiff | submitted |\n"
        "| EV-P-DEPOSIT | 定金收据 | documentary | party-plaintiff | submitted |\n"
        "| EV-P-WECHAT | 微信聊天记录 | electronic | party-plaintiff | submitted |\n"
        "| EV-P-BANK | 银行预批函 | documentary | party-plaintiff | submitted |\n"
        "| EV-P-APPRAISAL | 房产评估报告 | documentary | party-plaintiff | submitted |\n"
        "| EV-D-DEFENSE | 被告答辩意见 | documentary | party-defendant | submitted |\n"
        "| EV-D-MORTGAGE | 房产查档记录 | documentary | party-defendant | submitted |"
    )

    # Timeline
    timeline_md = (
        "| 日期 | 事件 | 来源 | 争议 |\n"
        "|------|------|------|------|\n"
        "| 2025-01-08 | 双方签订房屋买卖合同 | EV-P-CONTRACT |  |\n"
        "| 2025-01-08 | 原告支付定���28万元 | EV-P-DEPOSIT |  |\n"
        "| 2025-02-15 | 被告微信告知不想卖房 | EV-P-WECHAT | ⚠️ |\n"
        "| 2025-02-18 | 房产评估报���出具 | EV-P-APPRAISAL |  |\n"
        "| 2025-02-20 | 银行出具贷款预批函 | EV-P-BANK |  |\n"
        "| 2025-03-01 | 原告向法院提起诉讼 | case_data |  |"
    )

    # Amount calculation (real_estate specific: deposit, contract price, penalty, appraisal)
    amount_md = ""
    if include_amount:
        amount_md = (
            "| 项目 | 金额 | 说明 |\n"
            "|------|------|------|\n"
            "| 合同成交价 | 2,800,000 元 | 房屋买卖合同约定 |\n"
            "| 已付定金 | 280,000 元 | 合同价10%，银行转账已付 |\n"
            "| 约定违约金 | 560,000 元 | 合同价20%（合同第8条） |\n"
            "| 定金双倍返还 | 560,000 元 | 依定金罚则（备选主张） |\n"
            "| 评估增值 | 380,000 元 | 评估价318万-合同价280万 |\n"
            "| 原告实际损失参考 | 380,000 元 | 房价差额（违约金酌减依据） |"
        )

    # Glossary (real estate specific terms)
    glossary_md = (
        "| 术语 | 解释 |\n"
        "|------|------|\n"
        "| 定金 | 合同当事人约定的担保形式，收受定金方违约应双倍返还，支付方违约无权要求返还 |\n"
        "| 订金 | 预付款性质，不适用双倍返还罚则，仅需原额返还 |\n"
        "| 过户 | 不动产物权变更登记，房屋所有权转移的法定要件 |\n"
        "| 继续履行 | 守约方有权要求违约方按合同约定继续履行合同义务 |\n"
        "| 违约金酌减 | 约定违约金过高时，法院可依当事人请求酌情调整至实际损失水平 |\n"
        "| 抵押权 | 债务人或第三人以不动产为债权提供担保的物权，未解除前影响过户 |\n"
        "| 重大误解 | 行为人对行为性质、对方当事人、标的物等产生错误认识的可撤销事由 |"
    )

    layer4 = Layer4Appendix(
        adversarial_transcripts_md=transcripts_md,
        evidence_index_md=evidence_index_md,
        timeline_md=timeline_md,
        glossary_md=glossary_md,
        amount_calculation_md=amount_md,
    )

    return FourLayerReport(
        report_id="rpt-v3-realestate-test",
        case_id="case-real-estate-sale-chen-v-liu-2025",
        run_id="run-test-real-estate",
        perspective=perspective,
        layer1=layer1,
        layer2=layer2,
        layer3=layer3,
        layer4=layer4,
    )


_CASE_DATA = {
    "case_id": "case-real-estate-sale-chen-v-liu-2025",
    "case_type": "real_estate",
    "parties": {
        "plaintiff": {"party_id": "party-plaintiff-chen", "name": "陈某"},
        "defendant": {"party_id": "party-defendant-liu", "name": "刘某"},
    },
}


# =====================================================================
# Acceptance Matrix Check 1: MD render contract 10/10 pass
# =====================================================================


class TestMDRenderContract:
    """All 10 render contract rules must pass for real_estate."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_real_estate_md_passes_full_render_contract(self, _mock_redact):
        """The full pipeline MD output passes all 10 render contract rules."""
        report = _make_real_estate_report()

        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            )
            content = md_path.read_text(encoding="utf-8")

        results = lint_markdown_render_contract(
            content, evidence_ids=_REAL_ESTATE_EVIDENCE_IDS
        )
        errors = [r for r in results if r.severity == LintSeverity.ERROR]
        assert errors == [], f"ERROR-level violations: {errors}"

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_no_forbidden_tokens(self, _mock_redact):
        report = _make_real_estate_report()
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
        report = _make_real_estate_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert '{"' not in content
        assert '[{"' not in content

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_no_duplicate_headings(self, _mock_redact):
        report = _make_real_estate_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        headings = re.findall(r"(?m)^##\s+(.+?)\s*$", content)
        assert len(headings) == len(set(headings)), (
            f"Duplicate headings found: {[h for h in headings if headings.count(h) > 1]}"
        )


# =====================================================================
# Acceptance Matrix Check 2: DOCX render contract pass
# =====================================================================


class TestDOCXRenderContract:
    """DOCX render contract subset must pass for real_estate."""

    def test_real_estate_docx_passes_lint(self):
        """Generate DOCX for real_estate and verify render contract."""
        try:
            from engines.report_generation.docx_generator import generate_docx_v3_report
            from engines.report_generation.v3.docx_lint import lint_docx_render_contract
        except ImportError:
            pytest.skip("docx dependencies not available")

        report = _make_real_estate_report()
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


# =====================================================================
# Acceptance Matrix Check 3: Fallback ratio <= threshold
# =====================================================================


class TestFallbackRatio:
    """Fallback ratio must be within acceptable bounds."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_real_estate_fallback_ratio_below_threshold(self, _mock_redact):
        """With substantive content, fallback ratio should be <=0.20."""
        report = _make_real_estate_report()
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
        report = _make_real_estate_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")

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

        if fallback_sections:
            pytest.fail(
                f"Fallback sections found (should be 0 for real_estate with full data): "
                f"{fallback_sections}"
            )


# =====================================================================
# Acceptance Matrix Check 4: All major sections >=50 chars
# =====================================================================


class TestSectionContentLength:
    """All major sections must have substantive content (>=50 chars)."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_all_major_sections_substantive(self, _mock_redact):
        report = _make_real_estate_report()
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
            clean = re.sub(r"[#*_`>|~\-]", "", body).strip()
            if 0 < len(clean) < 50:
                short_sections.append((title, len(clean)))

        assert short_sections == [], (
            f"Sections with <50 chars: {short_sections}"
        )


# =====================================================================
# Acceptance Matrix Check 5: No orphan evidence citations
# =====================================================================


class TestOrphanCitations:
    """No [src-xxx] citations should reference non-existent evidence."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_no_orphan_citations(self, _mock_redact):
        report = _make_real_estate_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")

        citation_re = re.compile(r"\[src-([^\]]+)\]")
        citations = citation_re.findall(content)
        if citations:
            for ref in citations:
                full_ref = f"src-{ref}"
                assert full_ref in _REAL_ESTATE_EVIDENCE_IDS or ref in _REAL_ESTATE_EVIDENCE_IDS, (
                    f"Orphan citation [src-{ref}] not in evidence index"
                )


# =====================================================================
# Acceptance Matrix Check 6: Amount calculation handled correctly
# =====================================================================


class TestAmountCalculation:
    """real_estate has deposit/penalty/appraisal-based calculations."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_amount_calculation_section_present(self, _mock_redact):
        """Real estate with amounts should render the calculation section."""
        report = _make_real_estate_report(include_amount=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "金额计算明细" in content, "Amount calculation section missing"

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_amount_calculation_has_real_estate_fields(self, _mock_redact):
        """Real estate amount section must include deposit, contract price, penalty."""
        report = _make_real_estate_report(include_amount=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        # Real-estate-specific fields
        assert "合同成交价" in content, "Contract price missing"
        assert "2,800,000" in content, "Contract price value missing"
        assert "定金" in content, "Deposit field missing"
        assert "280,000" in content, "Deposit amount missing"
        assert "违约金" in content, "Penalty field missing"
        assert "560,000" in content, "Penalty amount missing"
        assert "评估增值" in content or "380,000" in content, "Appraisal appreciation missing"

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_amount_section_absent_when_no_amount_data(self, _mock_redact):
        """When amount data is not provided, section should NOT appear."""
        report = _make_real_estate_report(include_amount=False)
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "## 4.4 金额计算明细" not in content, (
            "Amount section should be skipped when no amount data"
        )

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_amount_uses_real_estate_terms_not_other_case_types(self, _mock_redact):
        """Verify amount section uses property terms, not loan or labor terms."""
        report = _make_real_estate_report(include_amount=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        # Should NOT contain civil_loan terms
        assert "借款本金" not in content, "Loan principal should not appear in real estate report"
        assert "LPR" not in content, "LPR rate should not appear in real estate report"
        # Should NOT contain labor_dispute terms
        assert "经济补偿金" not in content, "N compensation should not appear in real estate report"
        assert "赔偿金（2N）" not in content, "2N damages should not appear in real estate report"


# =====================================================================
# Acceptance Matrix Check 7: Executive summary non-boilerplate
# =====================================================================


class TestExecutiveSummary:
    """Executive summary must be substantive, not template text."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_neutral_conclusion_is_substantive(self, _mock_redact):
        report = _make_real_estate_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")

        conclusion_match = re.search(
            r"##\s+A\.\s+中立结论摘要.*?\n(.+?)(?=\n##|\n---|\Z)",
            content,
            re.DOTALL,
        )
        assert conclusion_match, "Neutral conclusion section not found"
        conclusion_text = conclusion_match.group(1).strip()

        boilerplate_patterns = [
            r"^[?？]+$",
            r"^\*暂无",
            r"^（无",
            r"^No .+ available",
        ]
        for pattern in boilerplate_patterns:
            assert not re.match(pattern, conclusion_text), (
                f"Conclusion is boilerplate: '{conclusion_text[:50]}'"
            )

        assert len(conclusion_text) >= 30, (
            f"Conclusion too short ({len(conclusion_text)} chars): '{conclusion_text}'"
        )

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_winning_move_present(self, _mock_redact):
        report = _make_real_estate_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "胜负手" in content, "Winning move section missing"

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_blocking_conditions_present(self, _mock_redact):
        report = _make_real_estate_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "阻断条件" in content, "Blocking conditions section missing"


# =====================================================================
# Acceptance Matrix Check 8: Layer3 perspectives substantive
# =====================================================================


class TestLayer3Perspectives:
    """Both plaintiff and defendant perspectives must have substantive content."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_both_perspectives_present(self, _mock_redact):
        report = _make_real_estate_report(perspective="neutral")
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
        report = _make_real_estate_report(perspective="neutral")
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "补证清单" in content, "补证清单 missing"
        assert "质证要点" in content, "质证要点 missing"
        assert "庭审发问" in content, "庭审发问 missing"
        assert "应对预案" in content, "应对预案 missing"
        assert "过度主张边界" in content, "过度主张边界 missing"

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_each_perspective_is_substantive(self, _mock_redact):
        """Each perspective section must have >=100 chars of content."""
        report = _make_real_estate_report(perspective="neutral")
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")

        for label in ["原告策略", "被告策略"]:
            pattern = rf"##\s+{label}.*?\n(.+?)(?=\n##\s+(?:原告|被告)策略|\n---|\n#\s+四|\Z)"
            match = re.search(pattern, content, re.DOTALL)
            assert match, f"{label} section not found"
            section_text = match.group(1).strip()
            clean = re.sub(r"[#*_`>|~\-\d\.]", "", section_text).strip()
            assert len(clean) >= 100, (
                f"{label} section too short ({len(clean)} chars)"
            )


# =====================================================================
# Additional structural checks (real_estate specific)
# =====================================================================


class TestRealEstateStructure:
    """Structural integrity checks specific to real_estate case type."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_four_layer_structure_present(self, _mock_redact):
        """Report must have all 4 top-level layers."""
        report = _make_real_estate_report()
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
    def test_issue_map_has_real_estate_issues(self, _mock_redact):
        """Issue map must contain real_estate-specific issues."""
        report = _make_real_estate_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        # Real-estate-specific issues
        assert "合同效力" in content, "Contract validity issue missing"
        assert "继续履行" in content, "Specific performance issue missing"

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_evidence_cards_rendered(self, _mock_redact):
        """Evidence cards (dual-tier) must be rendered in Layer 2."""
        report = _make_real_estate_report()
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
        report = _make_real_estate_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "电子证据补强策略" in content

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_scenario_tree_rendered(self, _mock_redact):
        """Conditional scenario tree must be rendered."""
        report = _make_real_estate_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "条件场景树" in content

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_glossary_has_real_estate_terms(self, _mock_redact):
        """Glossary section must contain real-estate-specific terminology."""
        report = _make_real_estate_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "术语表" in content
        assert "定金" in content, "Real estate term '定金' missing from glossary"
        assert "过户" in content, "Real estate term '过户' missing from glossary"

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_no_other_case_type_terms_in_report(self, _mock_redact):
        """Real estate report should not contain civil_loan or labor terms."""
        report = _make_real_estate_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        # Civil loan specific
        assert "借款合意" not in content, "Civil loan term should not be in real estate report"
        assert "借条" not in content, "Civil loan term '借条' should not be in real estate report"
        # Labor dispute specific
        assert "劳动合同法" not in content, "Labor law term should not be in real estate report"
        assert "严重违纪" not in content, "Labor term '严重违纪' should not be in real estate report"

    def test_report_json_roundtrip(self):
        """FourLayerReport must serialize/deserialize cleanly."""
        report = _make_real_estate_report()
        json_str = report.model_dump_json(indent=2)
        parsed = json.loads(json_str)
        restored = FourLayerReport.model_validate(parsed)
        assert restored.case_id == report.case_id
        assert len(restored.layer2.evidence_cards) == len(report.layer2.evidence_cards)
        assert len(restored.layer3.outputs) == len(report.layer3.outputs)
        assert restored.layer4.amount_calculation_md == report.layer4.amount_calculation_md

    def test_evidence_count_matches_fixture(self):
        """Real estate fixture should have 7 evidence items."""
        report = _make_real_estate_report()
        assert len(report.layer2.evidence_cards) == 7, (
            f"Expected 7 evidence cards, got {len(report.layer2.evidence_cards)}"
        )
        card_ids = {c.evidence_id for c in report.layer2.evidence_cards}
        assert card_ids == _REAL_ESTATE_EVIDENCE_IDS

    def test_issue_map_has_parent_child_structure(self):
        """Issue map should include sub-issues with parent references."""
        report = _make_real_estate_report()
        sub_issues = [i for i in report.layer2.issue_map if i.parent_issue_id]
        assert len(sub_issues) >= 1, "Expected at least 1 sub-issue in real estate"
        top_ids = {i.issue_id for i in report.layer2.issue_map}
        for sub in sub_issues:
            assert sub.parent_issue_id in top_ids, (
                f"Sub-issue {sub.issue_id} references invalid parent {sub.parent_issue_id}"
            )


# =====================================================================
# Regression: threshold bug detection
# =====================================================================


class TestThresholdConfiguration:
    """Verify the fallback ratio threshold is correctly set per Phase 1."""

    def test_hard_gate_threshold_is_0_20(self):
        """Phase 3d should have set the hard gate to 0.20 (not 0.25 or 0.35).

        The plan specifies: Phase 3d final: 0.20

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
        assert 0.35 not in threshold_values, (
            f"Found ratio > 0.35 in write_v3_report_md -- "
            f"Phase 1 threshold change (0.35->0.25) was NOT applied. "
            f"Current thresholds: {threshold_values}"
        )
        assert 0.25 not in threshold_values, (
            f"Found ratio > 0.25 in write_v3_report_md -- "
            f"Phase 3d threshold change (0.25->0.20) was NOT applied. "
            f"Current thresholds: {threshold_values}"
        )
