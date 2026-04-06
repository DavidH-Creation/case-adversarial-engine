"""Phase 3b: labor_dispute case type structural validation against v3 acceptance matrix.

Acceptance matrix checks (from plans/v3-plan.md §3.2):
  1. MD render contract 10/10 pass
  2. DOCX render contract pass
  3. Fallback ratio <= 0.20 (Phase 3d final threshold)
  4. All major sections have substantive content (>=50 chars)
  5. No orphan evidence citations
  6. Amount calculation handled correctly (labor_dispute HAS wage/compensation calc)
  7. Executive summary non-boilerplate
  8. Layer3 three perspectives (plaintiff/defendant/neutral) have substantive content

Key differences from civil_loan:
  - Evidence patterns: labor contracts, termination notices, salary records, IT logs, NDA
  - Issues: termination legality, wage disputes, NDA enforceability
  - Amount calculation: N/2N formula (economic compensation), not principal+interest
  - Legal framework: Labor Contract Law §39/§87, not Civil Code loan provisions
  - Mandatory arbitration prerequisite (unique to labor disputes)
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
# Labor-dispute-specific fixtures — realistic data for 李某诉某科技公司 pattern
# ---------------------------------------------------------------------------

_LABOR_DISPUTE_EVIDENCE_IDS = {
    "EV-P-CONTRACT",
    "EV-P-TERMINATION",
    "EV-P-SALARY",
    "EV-P-WECHAT",
    "EV-P-WITNESS",
    "EV-D-NDA",
    "EV-D-ITLOG",
    "EV-D-POLICY",
}


def _make_labor_dispute_report(
    *,
    perspective: str = "neutral",
    include_amount: bool = True,
    include_evidence_cards: bool = True,
    include_layer3_content: bool = True,
    fallback_sections: int = 0,
) -> FourLayerReport:
    """Build a realistic labor_dispute FourLayerReport for acceptance testing.

    This mimics what the pipeline produces for a 劳动合同解除纠纷 case with:
    - 3 core issues (解除合法性, 工资拖欠, 规章制度效力)
    - 8 evidence items (5 plaintiff, 3 defendant)
    - Amount calculation (labor disputes have wage/compensation calculations)
    - Both plaintiff and defendant perspectives
    """
    # --- Layer 1: Cover Summary ---
    cover = CoverSummary(
        neutral_conclusion=(
            "本案涉及劳动合同解除纠纷，原告李某主张被告某科技公司违法解除劳动合同，"
            "核心争点在于解除行为是否符合《劳动合同法》第39条规定的严重违纪情形。"
            "原告的文件拷贝行为是否构成商业秘密泄露存在重大争议，"
            "公司规章制度的民主制定程序及公示效力亦待审查。"
        ),
        winning_move=(
            "IT系统日志（EV-D-ITLOG）与保密协议（EV-D-NDA）的交叉印证"
            "是决定本案走向的关键。若IT日志能够证明原告确实将核心技术文件"
            "拷贝至外部设备，且保密协议对该行为有明确禁止条款，"
            "则被告解除行为的合法性将获得有力支撑。反之，若原告能证明"
            "文件备份系公司惯例，则解除行为可能被认定为违法。"
        ),
        blocking_conditions=[
            "若法院认定公司规章制度未经民主程序制定或未有效公示，则不能作为解除依据",
            "若IT日志的文件性质鉴定结果显示拷贝文件不构成商业秘密，则严重违纪不成立",
            "若同事证人证言被采信证明文件备份系公司惯例，则原告行为不构成违纪",
        ],
    )

    timeline = [
        TimelineEvent(date="2022-03-01", event="原告入职被告公司，签订劳动合同及保密协议", source="EV-P-CONTRACT"),
        TimelineEvent(date="2024-10-01", event="2024年10月工资正常发放16,000元", source="EV-P-SALARY"),
        TimelineEvent(date="2024-12-01", event="2024年12月工资仅发放4,000元，少发12,000元", source="EV-P-SALARY"),
        TimelineEvent(date="2025-01-10", event="IT日志记录原告通过U盘拷贝312个文件", source="EV-D-ITLOG"),
        TimelineEvent(date="2025-01-15", event="被告发出解除劳动合同通知书", source="EV-P-TERMINATION"),
        TimelineEvent(date="2025-02-01", event="原告向劳动仲裁委员会申请仲裁", source="case_data"),
    ]

    evidence_priorities = [
        EvidencePriorityCard(
            evidence_id="EV-P-CONTRACT",
            title="劳动合同",
            priority=EvidencePriority.core,
            reason="直接证明劳动关系存续及合同约定条款，是认定劳动关系和工资标准的基础证据",
            controls_issue_ids=["ISS-001", "ISS-002"],
        ),
        EvidencePriorityCard(
            evidence_id="EV-P-TERMINATION",
            title="解除劳动合同通知书",
            priority=EvidencePriority.core,
            reason="证明被告解除合同的时间、事由和程序，是判断解除合法性的核心文件",
            controls_issue_ids=["ISS-001"],
        ),
        EvidencePriorityCard(
            evidence_id="EV-D-ITLOG",
            title="IT系统日志",
            priority=EvidencePriority.core,
            reason="记录原告文件拷贝行为的客观电子数据，直接关系违纪事实认定",
            controls_issue_ids=["ISS-001"],
        ),
        EvidencePriorityCard(
            evidence_id="EV-D-NDA",
            title="保密协议",
            priority=EvidencePriority.core,
            reason="约定保密义务范围和违约后果，是认定违纪行为性质的关键文件",
            controls_issue_ids=["ISS-001"],
        ),
        EvidencePriorityCard(
            evidence_id="EV-P-SALARY",
            title="银行工资流水",
            priority=EvidencePriority.supporting,
            reason="证明工资实际发放情况，支持欠薪主张",
            controls_issue_ids=["ISS-002"],
        ),
        EvidencePriorityCard(
            evidence_id="EV-P-WECHAT",
            title="企业微信聊天记录",
            priority=EvidencePriority.supporting,
            reason="辅助证明文件传输系内部工作行为，补强原告主张",
        ),
        EvidencePriorityCard(
            evidence_id="EV-P-WITNESS",
            title="同事书面证明",
            priority=EvidencePriority.supporting,
            reason="证明公司历来允许本机备份工作文件的惯例",
        ),
        EvidencePriorityCard(
            evidence_id="EV-D-POLICY",
            title="公司规章制度及公示记录",
            priority=EvidencePriority.supporting,
            reason="证明公司保密制度内容及民主制定、公示程序",
            controls_issue_ids=["ISS-003"],
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
            description="原告于2022年3月1日入职被告公司，双方签订为期3年的劳动合同，约定月薪16,000元",
            source_evidence_ids=["EV-P-CONTRACT"],
        ),
        FactBaseEntry(
            fact_id="FACT-002",
            description="原告同日签署保密协议，承诺不将公司技术资料传输至外部设备或账户",
            source_evidence_ids=["EV-D-NDA"],
        ),
        FactBaseEntry(
            fact_id="FACT-003",
            description="2024年12月原告工资仅发放4,000元，与合同约定的16,000元相差12,000元",
            source_evidence_ids=["EV-P-SALARY"],
        ),
        FactBaseEntry(
            fact_id="FACT-004",
            description="IT系统日志记录原告于2025年1月10日通过U盘拷贝312个文件至外部存储设备",
            source_evidence_ids=["EV-D-ITLOG"],
        ),
        FactBaseEntry(
            fact_id="FACT-005",
            description="被告于2025年1月15日以严重违反保密制度为由即时解除原告劳动合同，不支付任何补偿",
            source_evidence_ids=["EV-P-TERMINATION"],
        ),
    ]

    issue_map = [
        IssueMapCard(
            issue_id="ISS-001",
            issue_title="解除劳动合同的合法性",
            depth=0,
            plaintiff_thesis=(
                "原告主张被告以虚假理由解除合同，拷贝文件系日常工作备份，"
                "符合公司惯例，不构成严重违纪，解除行为违法"
            ),
            defendant_thesis=(
                "被告主张IT日志证实原告擅自将312个核心技术文件拷贝至U盘，"
                "违反保密协议及公司规章制度第12条，属于严重违纪，"
                "依《劳动合同法》第39条即时解除合法"
            ),
            decisive_evidence=["EV-D-ITLOG", "EV-D-NDA", "EV-P-WECHAT", "EV-P-WITNESS"],
            current_gaps=[
                "拷贝文件是否实际构成商业秘密待鉴定",
                "公司是否实际允许员工本机备份待查证",
            ],
            outcome_sensitivity="极高",
        ),
        IssueMapCard(
            issue_id="ISS-002",
            issue_title="2024年12月工资差额是否属于拖欠工资",
            depth=0,
            plaintiff_thesis="原告主张被告无故克扣工资12,000元，应予补发",
            defendant_thesis=(
                "被告主张依劳动合同附件绩效考核制度扣减绩效奖金，"
                "2024年第四季度原告KPI完成率仅62%，扣减有据"
            ),
            decisive_evidence=["EV-P-SALARY", "EV-P-CONTRACT"],
            current_gaps=["绩效考核制度是否经民主程序制定", "绩效评分标准及过程是否透明"],
            outcome_sensitivity="高",
        ),
        IssueMapCard(
            issue_id="ISS-003",
            issue_title="公司规章制度的效力与适用",
            depth=0,
            plaintiff_thesis="原告质疑公司保密制度未经职代会民主程序审议，不应对员工产生约束力",
            defendant_thesis="被告主张制度经职工代表大会审议通过并全员公示，原告已签署知悉确认书",
            decisive_evidence=["EV-D-POLICY"],
            current_gaps=["职工代表大会会议记录是否完整", "公示方式是否符合法定要求"],
            outcome_sensitivity="高",
        ),
        IssueMapCard(
            issue_id="ISS-001-A",
            issue_title="拷贝文件是否构成商业秘密",
            parent_issue_id="ISS-001",
            depth=1,
            plaintiff_thesis="原告主张拷贝的文件均为日常工作文档，不属于商业秘密范畴",
            defendant_thesis="被告主张文件包含核心产品源代码和技术方案，属于商业秘密",
            decisive_evidence=["EV-D-ITLOG"],
            current_gaps=["文件内容的商业秘密鉴定结果尚未出具"],
            outcome_sensitivity="高",
        ),
    ]

    evidence_cards = []
    if include_evidence_cards:
        evidence_cards = [
            EvidenceKeyCard(
                evidence_id="EV-P-CONTRACT",
                q1_what="劳动合同原件，载明入职日期2022年3月1日、岗位高级研发工程师、月薪16,000元",
                q2_target="证明劳动关系存续及合同约定条款，支持ISS-001（解除合法性）和ISS-002（工资标准）",
                q3_key_risk="合同本身无争议，但被告可能援引合同附件中的绩效考核条款为工资扣减辩护",
                q4_best_attack="被告可主张合同附件绩效条款授权了工资调整权，原告已签字认可",
                q5_reinforce="结合银行流水证明实际发放低于合同约定，排除绩效扣减的合理性",
                q6_failure_impact="若劳动合同条款被认定含有合法的绩效浮动条款，工资差额主张将被削弱",
                priority=EvidencePriority.core,
            ),
            EvidenceKeyCard(
                evidence_id="EV-P-TERMINATION",
                q1_what="解除劳动合同通知书，载明解除日期2025年1月15日及解除事由",
                q2_target="证明被告解除合同的程序和理由，判断是否符合法定解除条件",
                q3_key_risk="通知书仅载明解除事由，未附充分的事实依据",
                q4_best_attack="被告可补充提交调查报告和处分程序记录证明解除程序合法",
                q5_reinforce="审查通知书是否送达工会、是否提前通知等程序要件",
                q6_failure_impact="若通知书程序完备且事由成立，解除行为合法性将被认定",
                priority=EvidencePriority.core,
            ),
            EvidenceKeyCard(
                evidence_id="EV-D-ITLOG",
                q1_what="IT系统日志，记载2025年1月10日原告账户通过U盘拷贝312个文件共2.3GB",
                q2_target="证明原告存在将文件拷贝至外部设备的客观行为事实",
                q3_key_risk="IT日志仅记录文件传输行为，不能证明文件内容构成商业秘密",
                q4_best_attack="原告可主张IT日志不完整或被篡改，要求电子数据鉴定",
                q5_reinforce="结合文件内容清单和商业秘密鉴定报告补强",
                q6_failure_impact="若IT日志被排除或文件内容不构成商业秘密，违纪事实将无法成立",
                priority=EvidencePriority.core,
            ),
            EvidenceBasicCard(
                evidence_id="EV-D-NDA",
                q1_what="保密协议原件，约定原告不得将公司技术资料传输至外部设备",
                q2_target="证明原告知悉并同意保密义务，其行为违反约定",
                q3_key_risk="保密协议条款可能因未支付保密补偿金而效力存疑",
                q4_best_attack="原告可主张保密条款过于宽泛，将日常工作文件等同于商业秘密不合理",
                priority=EvidencePriority.core,
            ),
            EvidenceBasicCard(
                evidence_id="EV-P-SALARY",
                q1_what="银行工资流水，记载2024年10月至2025年1月的工资发放明细",
                q2_target="证明2024年12月实际少发12,000元，支持欠薪主张",
                q3_key_risk="银行流水为客观记录，真实性无争议，争议焦点在于扣减理由",
                q4_best_attack="被告可主张扣减系依据绩效考核制度，非克扣工资",
                priority=EvidencePriority.supporting,
            ),
            EvidenceBasicCard(
                evidence_id="EV-P-WECHAT",
                q1_what="企业微信聊天记录，显示原告通过公司内部渠道传输技术文件",
                q2_target="辅助证明文件传输系正常工作行为，非蓄意泄密",
                q3_key_risk="电子证据真实性和完整性可能被质疑",
                q4_best_attack="被告可主张企业微信记录不完整，无法全面反映原告行为",
                priority=EvidencePriority.supporting,
            ),
            EvidenceBasicCard(
                evidence_id="EV-P-WITNESS",
                q1_what="同事张某、王某书面证明，证明公司技术部门历来允许员工本机备份工作文件",
                q2_target="证明文件备份系公司惯例，原告行为不构成违纪",
                q3_key_risk="证人与原告存在同事关系，证言可信度可能被质疑",
                q4_best_attack="被告可主张证人与原告存在利害关系，证言不足采信",
                priority=EvidencePriority.supporting,
            ),
            EvidenceBasicCard(
                evidence_id="EV-D-POLICY",
                q1_what="公司规章制度及全员签署的知悉确认书",
                q2_target="证明保密制度内容合法且经民主程序制定，对原告具有约束力",
                q3_key_risk="民主制定程序文件是否齐全，职代会记录是否完整",
                q4_best_attack="原告可主张未实质参与民主讨论，签字系形式要求",
                priority=EvidencePriority.supporting,
            ),
        ]

    scenario_tree = ConditionalScenarioTree(
        tree_id="SCN-LABOR-001",
        case_id="case-labor-dispute-li-v-techco-2025",
        root_node_id="N1",
        nodes=[
            ConditionalNode(
                node_id="N1",
                condition="拷贝的312个文件是否被鉴定为商业秘密？",
                yes_child_id="N2",
                no_outcome="文件不构成商业秘密，违纪事实不成立，解除行为违法，原告应获2N赔偿",
                related_evidence_ids=["EV-D-ITLOG"],
            ),
            ConditionalNode(
                node_id="N2",
                condition="公司规章制度是否经民主程序制定且有效公示？",
                yes_child_id="N3",
                no_outcome="规章制度程序瑕疵，不能作为解除依据，解除行为违法",
                related_evidence_ids=["EV-D-POLICY"],
            ),
            ConditionalNode(
                node_id="N3",
                condition="原告的文件备份行为是否被证明系公司惯例？",
                yes_outcome="虽文件构成商业秘密但原告行为符合惯例，不构成严重违纪，解除违法",
                no_outcome="文件构成商业秘密且行为违规，解除合法，原告败诉",
                related_evidence_ids=["EV-P-WITNESS", "EV-P-WECHAT"],
            ),
        ],
    )

    unified_electronic_strategy = (
        "**电子证据补强策略**：IT系统日志应提交原始服务器记录或经公证的副本，"
        "确保日志未经篡改且能反映完整的文件操作记录。"
        "企业微信聊天记录建议通过腾讯企业微信官方平台导出并公证保全。"
        "对U盘拷贝文件的商业秘密性质，应申请第三方技术鉴定。"
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
                "收集技术部门其他同事本机备份工作文件的截图或记录，证明公司惯例",
                "调取原告入职以来的全部绩效考核记录，核查2024年Q4绩效评分过程",
                "申请企业微信官方出具原告账户的完整聊天记录导出报告",
                "准备同事张某、王某的出庭作证材料，增强证人证言的证明力",
            ],
            cross_examination_points=[
                "针对「IT系统日志」：要求被告出示日志的完整操作记录而非选择性截取，质疑日志是否被事后修改",
                "针对「保密协议」：指出协议未约定保密补偿金，质疑竞业限制条款的有效性",
                "针对「公司规章制度」：要求出示职代会会议记录原件及签到表，核查民主程序是否真实",
            ],
            trial_questions=[
                "问被告HR负责人（解除程序）：解除前是否书面通知工会？工会意见是否征求？",
                "问被告IT部门（文件性质）：拷贝的312个文件是否经过商业秘密认定程序？",
                "问被告（工资扣减）：绩效考核扣减12,000元的评分依据和计算公式是什么？",
                "问被告（惯例问题）：公司技术部门其他员工是否存在类似的文件备份行为？",
            ],
            contingency_plans=[
                "若文件被鉴定为商业秘密：转而主张拷贝行为系工作需要而非泄密意图，且未造成实际损失",
                "若绩效考核制度被认定合法：主张扣减比例不合理，超出绩效浮动的合理范围",
            ],
            over_assertion_boundaries=[
                "不建议主张公司完全没有保密制度，因原告已签署保密协议，应聚焦于行为性质认定",
                "不建议要求精神损害赔偿，劳动争议中精神损害赔偿缺乏法律依据",
            ],
            unified_electronic_evidence_strategy=unified_electronic_strategy,
        )

        defendant_output = PerspectiveOutput(
            perspective="defendant",
            evidence_supplement_checklist=[
                "申请第三方鉴定机构对U盘拷贝文件的商业秘密性质进行鉴定",
                "提交职工代表大会会议记录原件、签到表、表决结果等程序文件",
                "提供2024年Q4原告绩效考核的完整评分表和审批流程",
                "提交解除前征求工会意见的书面记录（如有工会组织）",
            ],
            cross_examination_points=[
                "针对「同事证明」：质疑证人与原告的利害关系，要求证人说明备份行为的具体场景",
                "针对「企业微信记录」：指出记录仅反映部分传输行为，不能排除外部泄露可能",
            ],
            trial_questions=[
                "问原告（文件拷贝）：为何选择使用U盘而非公司提供的云存储？",
                "问原告（拷贝目的）：312个文件是否均与当前工作任务直接相关？",
                "问原告（保密义务）：签署保密协议时是否理解其中的禁止条款？",
            ],
            contingency_plans=[
                "若规章制度民主程序被认定存在瑕疵：主张保密协议独立于规章制度，原告仍违反了合同义务",
                "若法院倾向认定解除违法：主张即使违法解除也应按N标准计算，不应适用2N",
            ],
            over_assertion_boundaries=[
                "不建议主张原告已实际向外泄露商业秘密（无直接证据），应聚焦于违反保密制度的行为本身",
                "不建议否认工资差额事实（银行流水无法否认），应聚焦于扣减的合法性",
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
        "原告于2022年3月入职被告公司，担任高级研发工程师，月薪16,000元。"
        "2025年1月15日，被告以原告泄露商业秘密为由违法解除劳动合同。"
        "原告主张拷贝文件系日常工作备份，公司技术部门历来允许此行为。"
        "被告应依《劳动合同法》第87条支付违法解除赔偿金96,000元，"
        "并补发2024年12月拖欠工资12,000元。\n\n"
        "*引用证据*: EV-P-CONTRACT, EV-P-TERMINATION, EV-P-SALARY\n\n---\n\n"
        "**defendant_agent** — 被告抗辩\n\n"
        "IT系统日志显示原告于2025年1月10日通过U盘将312个核心技术文件"
        "拷贝至外部存储设备。该行为严重违反原告签署的保密协议和公司"
        "规章制度第12条。公司依《劳动合同法》第39条即时解除合法，"
        "无需支付任何补偿或赔偿。2024年12月工资扣减系绩效考核扣款，"
        "有合同附件绩效制度依据。\n\n"
        "*引用证据*: EV-D-ITLOG, EV-D-NDA, EV-D-POLICY\n\n---\n\n"
        "### Round 2 (rebuttal)\n\n"
        "**plaintiff_agent** — 原告质证\n\n"
        "原告提交企业微信聊天记录和同事书面证明，证实技术部门员工"
        "历来在本机备份工作文件，公司从未就此行为提出异议或警告。"
        "原告拷贝文件系正常工作行为，被告选择性适用规章制度属于"
        "违法解除。此外，保密协议未约定保密补偿金，条款效力存疑。\n\n"
        "*引用证据*: EV-P-WECHAT, EV-P-WITNESS\n\n---\n\n"
        "**defendant_agent** — 被告反驳\n\n"
        "被告质疑同事证言的客观性，指出证人与原告存在利害关系。"
        "公司规章制度经职代会审议通过并全员公示，原告已签署知悉确认书。"
        "工作文件备份与将商业秘密拷贝至私人U盘性质不同。\n\n"
        "*引用证据*: EV-D-POLICY\n\n---\n\n"
        "### Round 3 (closing)\n\n"
        "**plaintiff_agent** — 原告总结\n\n"
        "原告拷贝行为系工作惯例，拷贝文件是否构成商业秘密待鉴定。"
        "被告未能充分证明原告行为造成实际损失或泄露后果。"
        "绩效考核扣款程序不透明，工资差额应当补发。\n\n"
        "*引用证据*: EV-P-WECHAT, EV-P-WITNESS, EV-P-SALARY\n\n---\n\n"
        "**defendant_agent** — 被告总结\n\n"
        "IT日志客观记录了原告的文件拷贝行为，保密协议和规章制度"
        "均对此行为有明确禁止条款。解除行为事实清楚、程序合法。"
        "绩效扣款依据制度执行，合法有据。\n\n"
        "*引用证据*: EV-D-ITLOG, EV-D-NDA, EV-D-POLICY\n\n---"
    )

    # Evidence index table
    evidence_index_md = (
        "| 编号 | 标题 | 类型 | 提交方 | 状态 |\n"
        "|------|------|------|--------|------|\n"
        "| EV-P-CONTRACT | 劳动合同 | documentary | party-plaintiff | submitted |\n"
        "| EV-P-TERMINATION | 解除通知书 | documentary | party-plaintiff | submitted |\n"
        "| EV-P-SALARY | 银行工资流水 | documentary | party-plaintiff | submitted |\n"
        "| EV-P-WECHAT | 企业微信聊天记录 | electronic | party-plaintiff | submitted |\n"
        "| EV-P-WITNESS | 同事书面证明 | testimonial | party-plaintiff | submitted |\n"
        "| EV-D-NDA | 保密协议 | documentary | party-defendant | submitted |\n"
        "| EV-D-ITLOG | IT系统日志 | electronic | party-defendant | submitted |\n"
        "| EV-D-POLICY | 规章制度及公示记录 | documentary | party-defendant | submitted |"
    )

    # Timeline
    timeline_md = (
        "| 日期 | 事件 | 来源 | 争议 |\n"
        "|------|------|------|------|\n"
        "| 2022-03-01 | 原告入职并签订劳动合同及保密协议 | EV-P-CONTRACT |  |\n"
        "| 2024-10-01 | 2024年10月工资正常发放 | EV-P-SALARY |  |\n"
        "| 2024-12-01 | 2024年12月工资仅发4,000元 | EV-P-SALARY | ⚠️ |\n"
        "| 2025-01-10 | 原告通过U盘拷贝312个文件 | EV-D-ITLOG | ⚠️ |\n"
        "| 2025-01-15 | 被告发出解除通知书 | EV-P-TERMINATION | ⚠️ |\n"
        "| 2025-02-01 | 原告申请劳动仲裁 | case_data |  |"
    )

    # Amount calculation (labor_dispute: compensation formula)
    amount_md = ""
    if include_amount:
        amount_md = (
            "| 项目 | 金额 | 计算依据 |\n"
            "|------|------|----------|\n"
            "| 月工资基数 | 16,000 元 | 劳动合同约定月薪 |\n"
            "| 工龄 | 3年（2022.03-2025.01） | 劳动合同期限 |\n"
            "| 经济补偿金（N） | 48,000 元 | 16,000元 × 3年 |\n"
            "| 违法解除赔偿金（2N） | 96,000 元 | 经济补偿金 × 2 |\n"
            "| 拖欠工资 | 12,000 元 | 2024年12月差额（16,000-4,000） |\n"
            "| 合计主张金额 | 108,000 元 | 赔偿金96,000 + 欠薪12,000 |"
        )

    # Glossary (labor-specific terms)
    glossary_md = (
        "| 术语 | 解释 |\n"
        "|------|------|\n"
        "| 经济补偿金 | 用人单位依法解除或终止劳动合同时应支付给劳动者的补偿，计算公式为N×月工资 |\n"
        "| 赔偿金（2N） | 用人单位违法解除劳动合同时应支付的赔偿金，为经济补偿金的两倍 |\n"
        "| 严重违纪 | 劳动者严重违反用人单位规章制度的行为，用人单位可据此即时解除合同 |\n"
        "| 商业秘密 | 不为公众所知悉、具有商业价值并经权利人采取保密措施的技术信息和经营信息 |\n"
        "| 民主程序 | 用人单位制定规章制度应当经职工代表大会或全体职工讨论的法定程序 |\n"
        "| 劳动仲裁前置 | 劳动争议须先经劳动仲裁委员会仲裁，对裁决不服方可向法院起诉 |\n"
        "| 举证责任倒置 | 劳动争议中用人单位对工资支付、考勤记录等承担举证责任 |"
    )

    layer4 = Layer4Appendix(
        adversarial_transcripts_md=transcripts_md,
        evidence_index_md=evidence_index_md,
        timeline_md=timeline_md,
        glossary_md=glossary_md,
        amount_calculation_md=amount_md,
    )

    return FourLayerReport(
        report_id="rpt-v3-labordispute-test",
        case_id="case-labor-dispute-li-v-techco-2025",
        run_id="run-test-labor-dispute",
        perspective=perspective,
        layer1=layer1,
        layer2=layer2,
        layer3=layer3,
        layer4=layer4,
    )


_CASE_DATA = {
    "case_id": "case-labor-dispute-li-v-techco-2025",
    "case_type": "labor_dispute",
    "parties": {
        "plaintiff": {"party_id": "party-plaintiff-li", "name": "李某"},
        "defendant": {"party_id": "party-defendant-techco", "name": "某科技有限公司"},
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# Acceptance Matrix Check 1: MD render contract 10/10 pass
# ═══════════════════════════════════════════════════════════════════════════


class TestMDRenderContract:
    """All 10 render contract rules must pass for labor_dispute."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_labor_dispute_md_passes_full_render_contract(self, _mock_redact):
        """The full pipeline MD output passes all 10 render contract rules."""
        report = _make_labor_dispute_report()

        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            )
            content = md_path.read_text(encoding="utf-8")

        # Should not raise — if it does, the test fails with the violation details
        results = lint_markdown_render_contract(
            content, evidence_ids=_LABOR_DISPUTE_EVIDENCE_IDS
        )
        # Only WARN results should remain (no ERRORs)
        errors = [r for r in results if r.severity == LintSeverity.ERROR]
        assert errors == [], f"ERROR-level violations: {errors}"

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_no_forbidden_tokens(self, _mock_redact):
        report = _make_labor_dispute_report()
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
        report = _make_labor_dispute_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert '{"' not in content
        assert '[{"' not in content

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_no_duplicate_headings(self, _mock_redact):
        report = _make_labor_dispute_report()
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
    """DOCX render contract subset must pass for labor_dispute."""

    def test_labor_dispute_docx_passes_lint(self):
        """Generate DOCX for labor_dispute and verify render contract."""
        try:
            from engines.report_generation.docx_generator import generate_docx_v3_report
            from engines.report_generation.v3.docx_lint import lint_docx_render_contract
        except ImportError:
            pytest.skip("docx dependencies not available")

        report = _make_labor_dispute_report()
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
# Acceptance Matrix Check 3: Fallback ratio <= threshold
# ═══════════════════════════════════════════════════════════════════════════


class TestFallbackRatio:
    """Fallback ratio must be within acceptable bounds."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_labor_dispute_fallback_ratio_below_threshold(self, _mock_redact):
        """With substantive content, fallback ratio should be <=0.20."""
        report = _make_labor_dispute_report()
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
        report = _make_labor_dispute_report()
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
                f"Fallback sections found (should be 0 for labor_dispute with full data): "
                f"{fallback_sections}"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Acceptance Matrix Check 4: All major sections >=50 chars
# ═══════════════════════════════════════════════════════════════════════════


class TestSectionContentLength:
    """All major sections must have substantive content (>=50 chars)."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_all_major_sections_substantive(self, _mock_redact):
        report = _make_labor_dispute_report()
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
        report = _make_labor_dispute_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")

        # Check for orphan citations
        citation_re = re.compile(r"\[src-([^\]]+)\]")
        citations = citation_re.findall(content)
        if citations:
            for ref in citations:
                full_ref = f"src-{ref}"
                assert full_ref in _LABOR_DISPUTE_EVIDENCE_IDS or ref in _LABOR_DISPUTE_EVIDENCE_IDS, (
                    f"Orphan citation [src-{ref}] not in evidence index"
                )


# ═══════════════════════════════════════════════════════════════════════════
# Acceptance Matrix Check 6: Amount calculation handled correctly
# ═══════════════════════════════════════════════════════════════════════════


class TestAmountCalculation:
    """labor_dispute has wage/compensation calculations (N/2N formula)."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_amount_calculation_section_present(self, _mock_redact):
        """Labor dispute with amounts should render the calculation section."""
        report = _make_labor_dispute_report(include_amount=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "金额计算明细" in content, "Amount calculation section missing"

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_amount_calculation_has_labor_fields(self, _mock_redact):
        """Labor dispute amount section must include compensation formula fields."""
        report = _make_labor_dispute_report(include_amount=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        # Labor-specific fields: monthly wage, years of service, N/2N
        assert "月工资基数" in content, "Monthly wage base missing"
        assert "16,000" in content, "Monthly wage amount incorrect"
        assert "经济补偿金" in content, "Economic compensation (N) missing"
        assert "赔偿金" in content, "Damages (2N) missing"
        assert "96,000" in content, "2N amount (96,000) missing"
        assert "拖欠工资" in content, "Wage arrears missing"
        assert "12,000" in content, "Wage arrears amount missing"

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_amount_section_absent_when_no_amount_data(self, _mock_redact):
        """When amount data is not provided, section should NOT appear."""
        report = _make_labor_dispute_report(include_amount=False)
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        # The section header should not appear when there's no amount data
        assert "## 4.4 金额计算明细" not in content, (
            "Amount section should be skipped when no amount data"
        )

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_amount_uses_labor_formula_not_loan_formula(self, _mock_redact):
        """Verify amount section uses labor compensation terms, not loan terms."""
        report = _make_labor_dispute_report(include_amount=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        # Should NOT contain civil_loan terms
        assert "借款本金" not in content, "Loan principal should not appear in labor report"
        assert "LPR" not in content, "LPR interest rate should not appear in labor report"


# ═══════════════════════════════════════════════════════════════════════════
# Acceptance Matrix Check 7: Executive summary non-boilerplate
# ═══════════════════════════════════════════════════════════════════════════


class TestExecutiveSummary:
    """Executive summary must be substantive, not template text."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_neutral_conclusion_is_substantive(self, _mock_redact):
        report = _make_labor_dispute_report()
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
            r"^[?？]+$",
            r"^\*暂无",
            r"^（无",
            r"^No .+ available",
        ]
        for pattern in boilerplate_patterns:
            assert not re.match(pattern, conclusion_text), (
                f"Conclusion is boilerplate: '{conclusion_text[:50]}'"
            )

        # Must contain labor-specific details
        assert len(conclusion_text) >= 30, (
            f"Conclusion too short ({len(conclusion_text)} chars): '{conclusion_text}'"
        )

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_winning_move_present(self, _mock_redact):
        report = _make_labor_dispute_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "胜负手" in content, "Winning move section missing"

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_blocking_conditions_present(self, _mock_redact):
        report = _make_labor_dispute_report()
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
        report = _make_labor_dispute_report(perspective="neutral")
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
        report = _make_labor_dispute_report(perspective="neutral")
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
        report = _make_labor_dispute_report(perspective="neutral")
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


# ═══════════════════════════════════════════════════════════════════════════
# Additional structural checks (labor_dispute specific)
# ═══════════════════════════════════════════════════════════════════════════


class TestLaborDisputeStructure:
    """Structural integrity checks specific to labor_dispute case type."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_four_layer_structure_present(self, _mock_redact):
        """Report must have all 4 top-level layers."""
        report = _make_labor_dispute_report()
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
    def test_issue_map_has_labor_dispute_issues(self, _mock_redact):
        """Issue map must contain labor-dispute-specific issues."""
        report = _make_labor_dispute_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        # Labor-specific issues
        assert "解除" in content, "Termination issue not found in report"
        assert "工资" in content, "Wage issue not found in report"

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_evidence_cards_rendered(self, _mock_redact):
        """Evidence cards (dual-tier) must be rendered in Layer 2."""
        report = _make_labor_dispute_report()
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
        report = _make_labor_dispute_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "电子证据补强策略" in content

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_scenario_tree_rendered(self, _mock_redact):
        """Conditional scenario tree must be rendered."""
        report = _make_labor_dispute_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "条件场景树" in content

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_glossary_has_labor_terms(self, _mock_redact):
        """Glossary section must contain labor-specific terminology."""
        report = _make_labor_dispute_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        assert "术语表" in content
        assert "经济补偿金" in content, "Labor term '经济补偿金' missing from glossary"
        assert "严重违纪" in content, "Labor term '严重违纪' missing from glossary"

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_no_civil_loan_terms_in_report(self, _mock_redact):
        """Labor dispute report should not contain civil_loan-specific terms."""
        report = _make_labor_dispute_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = write_v3_report_md(
                Path(tmpdir), report, _CASE_DATA, no_redact=True
            ).read_text(encoding="utf-8")
        # These are civil_loan-specific terms that should NOT appear
        assert "借款合意" not in content, "Civil loan term '借款合意' should not be in labor report"
        assert "借条" not in content, "Civil loan term '借条' should not be in labor report"

    def test_report_json_roundtrip(self):
        """FourLayerReport must serialize/deserialize cleanly."""
        report = _make_labor_dispute_report()
        json_str = report.model_dump_json(indent=2)
        parsed = json.loads(json_str)
        restored = FourLayerReport.model_validate(parsed)
        assert restored.case_id == report.case_id
        assert len(restored.layer2.evidence_cards) == len(report.layer2.evidence_cards)
        assert len(restored.layer3.outputs) == len(report.layer3.outputs)
        assert restored.layer4.amount_calculation_md == report.layer4.amount_calculation_md

    def test_evidence_count_matches_fixture(self):
        """Labor dispute fixture should have 8 evidence items."""
        report = _make_labor_dispute_report()
        assert len(report.layer2.evidence_cards) == 8, (
            f"Expected 8 evidence cards, got {len(report.layer2.evidence_cards)}"
        )
        # Verify IDs match
        card_ids = {c.evidence_id for c in report.layer2.evidence_cards}
        assert card_ids == _LABOR_DISPUTE_EVIDENCE_IDS

    def test_issue_map_has_parent_child_structure(self):
        """Issue map should include sub-issues with parent references."""
        report = _make_labor_dispute_report()
        sub_issues = [i for i in report.layer2.issue_map if i.parent_issue_id]
        assert len(sub_issues) >= 1, "Expected at least 1 sub-issue in labor dispute"
        # Verify parent reference is valid
        top_ids = {i.issue_id for i in report.layer2.issue_map}
        for sub in sub_issues:
            assert sub.parent_issue_id in top_ids, (
                f"Sub-issue {sub.issue_id} references invalid parent {sub.parent_issue_id}"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Regression: threshold bug detection
# ═══════════════════════════════════════════════════════════════════════════


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
            f"Found ratio > 0.35 in write_v3_report_md — "
            f"Phase 3d threshold change to 0.20 was NOT applied. "
            f"Current thresholds: {threshold_values}"
        )
        assert 0.25 not in threshold_values, (
            f"Found ratio > 0.25 in write_v3_report_md — "
            f"Phase 1 transitional threshold should have been replaced by 0.20 in Phase 3d. "
            f"Current thresholds: {threshold_values}"
        )
