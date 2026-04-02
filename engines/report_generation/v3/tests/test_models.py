"""Tests for V3 4-layer report data models."""

import pytest

from engines.report_generation.v3.models import (
    ConditionalNode,
    ConditionalScenarioTree,
    CoverSummary,
    EvidenceBasicCard,
    EvidenceBattleCard,
    EvidenceKeyCard,
    EvidencePriority,
    EvidencePriorityCard,
    EvidenceRiskLevel,
    EvidenceTrafficLight,
    FactBaseEntry,
    FourLayerReport,
    IssueMapCard,
    Layer1Cover,
    Layer2Core,
    Layer3Perspective,
    Layer4Appendix,
    PerspectiveDefendantSummary,
    PerspectivePlaintiffSummary,
    PerspectiveOutput,
    SectionTag,
    TimelineEvent,
)


class TestSectionTag:
    def test_tag_values(self):
        assert SectionTag.fact == "事实"
        assert SectionTag.inference == "推断"
        assert SectionTag.assumption == "假设"
        assert SectionTag.opinion == "观点"
        assert SectionTag.recommendation == "建议"


class TestEvidenceRiskLevel:
    def test_levels(self):
        assert EvidenceRiskLevel.green == "green"
        assert EvidenceRiskLevel.yellow == "yellow"
        assert EvidenceRiskLevel.red == "red"


class TestEvidenceTrafficLight:
    def test_create(self):
        tl = EvidenceTrafficLight(
            evidence_id="EV001",
            title="Bank Transfer",
            risk_level=EvidenceRiskLevel.green,
            reason="Third-party verifiable",
        )
        assert tl.evidence_id == "EV001"
        assert tl.risk_level == EvidenceRiskLevel.green


class TestCoverSummary:
    def test_neutral(self):
        cs = CoverSummary(neutral_conclusion="Test conclusion")
        assert cs.plaintiff_summary is None
        assert cs.defendant_summary is None

    def test_with_plaintiff(self):
        ps = PerspectivePlaintiffSummary(
            top3_strengths=["s1", "s2", "s3"],
            top2_dangers=["d1", "d2"],
            top3_actions=["a1", "a2", "a3"],
        )
        cs = CoverSummary(
            neutral_conclusion="Test",
            plaintiff_summary=ps,
        )
        assert len(cs.plaintiff_summary.top3_strengths) == 3

    def test_with_defendant(self):
        ds = PerspectiveDefendantSummary(
            top3_defenses=["d1", "d2", "d3"],
        )
        cs = CoverSummary(
            neutral_conclusion="Test",
            defendant_summary=ds,
        )
        assert len(cs.defendant_summary.top3_defenses) == 3


class TestConditionalNode:
    def test_leaf_node(self):
        node = ConditionalNode(
            node_id="COND-001",
            condition="录音是否被采信？",
            yes_outcome="原告胜诉",
            no_outcome="驳回",
        )
        assert node.yes_child_id is None
        assert node.no_child_id is None
        assert node.yes_outcome == "原告胜诉"

    def test_branch_node(self):
        node = ConditionalNode(
            node_id="COND-001",
            condition="录音是否被采信？",
            yes_child_id="COND-002",
            no_child_id="COND-003",
        )
        assert node.yes_outcome is None
        assert node.yes_child_id == "COND-002"


class TestIssueMapCard:
    def test_create(self):
        card = IssueMapCard(
            issue_id="ISS001",
            issue_title="借款合意",
            plaintiff_thesis="双方存在借贷关系",
            defendant_thesis="不存在借贷合意",
        )
        assert card.tag == SectionTag.inference


class TestEvidenceBattleCard:
    def test_seven_questions(self):
        card = EvidenceBattleCard(
            evidence_id="EV001",
            q1_what="银行转账凭证",
            q2_proves="原告向被告转账20万元",
            q3_direction="支持原告",
            q4_risks="无明显风险",
            q5_opponent_attack="被告可能主张非借款而是投资",
            q6_reinforce="提供转账备注截图",
            q7_failure_impact="若失败则本金金额无法证实",
        )
        assert card.risk_level == EvidenceRiskLevel.yellow  # default


class TestFourLayerReport:
    def test_create_minimal(self):
        report = FourLayerReport(
            report_id="rpt-001",
            case_id="case-001",
            run_id="run-001",
            layer1=Layer1Cover(
                cover_summary=CoverSummary(neutral_conclusion="Test"),
            ),
            layer2=Layer2Core(),
            layer3=Layer3Perspective(),
            layer4=Layer4Appendix(),
        )
        assert report.perspective == "neutral"
        assert report.layer1.cover_summary.neutral_conclusion == "Test"

    def test_perspective_field(self):
        report = FourLayerReport(
            report_id="rpt-001",
            case_id="case-001",
            run_id="run-001",
            perspective="plaintiff",
            layer1=Layer1Cover(
                cover_summary=CoverSummary(neutral_conclusion="Test"),
            ),
            layer2=Layer2Core(),
            layer3=Layer3Perspective(),
            layer4=Layer4Appendix(),
        )
        assert report.perspective == "plaintiff"


class TestPerspectiveOutput:
    def test_plaintiff_fields(self):
        output = PerspectiveOutput(
            perspective="plaintiff",
            top_claims=["claim1"],
            defendant_attack_chains=["attack1"],
        )
        assert output.perspective == "plaintiff"
        assert len(output.top_claims) == 1

    def test_defendant_fields(self):
        output = PerspectiveOutput(
            perspective="defendant",
            top_defenses=["defense1"],
            motions_to_file=["motion1"],
        )
        assert output.perspective == "defendant"

    def test_invalid_perspective_rejected(self):
        """Perspective must be Literal['plaintiff','defendant','neutral']."""
        with pytest.raises(Exception):
            PerspectiveOutput(perspective="judge")

    def test_report_invalid_perspective_rejected(self):
        """FourLayerReport.perspective must be Literal type."""
        with pytest.raises(Exception):
            FourLayerReport(
                report_id="rpt-001",
                case_id="case-001",
                run_id="run-001",
                perspective="judge",
                layer1=Layer1Cover(
                    cover_summary=CoverSummary(neutral_conclusion="Test"),
                ),
                layer2=Layer2Core(),
                layer3=Layer3Perspective(),
                layer4=Layer4Appendix(),
            )

    def test_action_oriented_fields(self):
        """V3.1 action-oriented fields work."""
        output = PerspectiveOutput(
            perspective="plaintiff",
            evidence_supplement_checklist=["获取借条原件", "传唤证人C"],
            cross_examination_points=["质疑录音合法性"],
            trial_questions=["问被告：账户何时交给老庄？"],
            contingency_plans=["若录音被采信→追加老庄为被告"],
            over_assertion_boundaries=["不建议坚持面对面场景"],
        )
        assert len(output.evidence_supplement_checklist) == 2
        assert len(output.cross_examination_points) == 1
        assert len(output.trial_questions) == 1
        assert len(output.contingency_plans) == 1
        assert len(output.over_assertion_boundaries) == 1


# ── V3.1 New Models ──────────────────────────────────────────────


class TestEvidencePriority:
    def test_priority_values(self):
        assert EvidencePriority.core == "核心证据"
        assert EvidencePriority.supporting == "辅助证据"
        assert EvidencePriority.background == "背景证据"


class TestEvidencePriorityCard:
    def test_create(self):
        card = EvidencePriorityCard(
            evidence_id="EV001",
            title="银行转账回单",
            priority=EvidencePriority.core,
            reason="控制争点一结果",
            controls_issue_ids=["ISS001"],
        )
        assert card.priority == EvidencePriority.core
        assert len(card.controls_issue_ids) == 1

    def test_defaults(self):
        card = EvidencePriorityCard(
            evidence_id="EV002",
            title="身份信息",
            priority=EvidencePriority.background,
            reason="仅提供上下文",
        )
        assert card.controls_issue_ids == []


class TestEvidenceBasicCard:
    def test_four_fields(self):
        card = EvidenceBasicCard(
            evidence_id="EV001",
            q1_what="银行转账凭证 — documentary类证据",
            q2_target="服务争点二（款项交付），支持原告",
            q3_key_risk="极低——银行系统生成的客观记录",
            q4_best_attack="不否认转账事实，但主张转账≠借款交付",
        )
        assert card.priority == EvidencePriority.supporting  # default
        assert card.tag == SectionTag.inference

    def test_with_priority(self):
        card = EvidenceBasicCard(
            evidence_id="EV001",
            q1_what="test",
            q2_target="test",
            q3_key_risk="test",
            q4_best_attack="test",
            priority=EvidencePriority.background,
        )
        assert card.priority == EvidencePriority.background


class TestEvidenceKeyCard:
    def test_six_fields(self):
        card = EvidenceKeyCard(
            evidence_id="EV001",
            q1_what="录音光盘",
            q2_target="服务争点一+争点四，支持被告",
            q3_key_risk="录制合法性存疑",
            q4_best_attack="质疑录音合法性（未经同意录音）",
            q5_reinforce="提供录音完整版 + 申请声纹鉴定",
            q6_failure_impact="若录音被排除：被告核心证据链断裂",
            priority=EvidencePriority.core,
        )
        assert card.priority == EvidencePriority.core
        assert card.q5_reinforce != ""
        assert card.q6_failure_impact != ""

    def test_inherits_basic(self):
        """EvidenceKeyCard is a subclass of EvidenceBasicCard."""
        card = EvidenceKeyCard(
            evidence_id="EV001",
            q1_what="test",
            q2_target="test",
            q3_key_risk="test",
            q4_best_attack="test",
            q5_reinforce="test",
            q6_failure_impact="test",
        )
        assert isinstance(card, EvidenceBasicCard)


class TestTimelineEvent:
    def test_create(self):
        event = TimelineEvent(
            date="2025-01-10",
            event="原告银行转账10万元至小陈账户",
            source="evidence-plaintiff-003",
        )
        assert event.tag == SectionTag.fact
        assert event.disputed is False

    def test_disputed(self):
        event = TimelineEvent(
            date="2025-01-10 21:11",
            event="小陈打车离开",
            source="evidence-defendant-006",
            disputed=True,
        )
        assert event.disputed is True


class TestIssueMapCardTree:
    def test_root_issue(self):
        card = IssueMapCard(
            issue_id="ISS001",
            issue_title="借贷关系是否成立",
            plaintiff_thesis="存在借贷关系",
            defendant_thesis="不存在借贷关系",
            depth=0,
        )
        assert card.parent_issue_id is None
        assert card.depth == 0

    def test_child_issue(self):
        card = IssueMapCard(
            issue_id="ISS002",
            issue_title="借贷合意是否存在",
            parent_issue_id="ISS001",
            depth=1,
            plaintiff_thesis="合意存在",
            defendant_thesis="合意不存在",
        )
        assert card.parent_issue_id == "ISS001"
        assert card.depth == 1


class TestCoverSummaryV31:
    def test_winning_move(self):
        cs = CoverSummary(
            neutral_conclusion="被告证据优势明显",
            winning_move="录音证据（被告证据7）",
            blocking_conditions=["录音真实性与合法性", "滴滴记录完整性"],
        )
        assert cs.winning_move != ""
        assert len(cs.blocking_conditions) == 2

    def test_backward_compat(self):
        """Old plaintiff/defendant summaries still work."""
        ps = PerspectivePlaintiffSummary(
            top3_strengths=["s1"],
            top2_dangers=["d1"],
            top3_actions=["a1"],
        )
        cs = CoverSummary(
            neutral_conclusion="Test",
            plaintiff_summary=ps,
        )
        assert cs.plaintiff_summary is not None
        assert cs.winning_move == ""


class TestLayer1CoverV31:
    def test_with_timeline_and_priorities(self):
        layer1 = Layer1Cover(
            cover_summary=CoverSummary(neutral_conclusion="Test"),
            timeline=[
                TimelineEvent(date="2025-01-10", event="转账"),
                TimelineEvent(date="2025-01-11", event="催款"),
            ],
            evidence_priorities=[
                EvidencePriorityCard(
                    evidence_id="EV001",
                    title="录音",
                    priority=EvidencePriority.core,
                    reason="控制争点一",
                ),
            ],
        )
        assert len(layer1.timeline) == 2
        assert len(layer1.evidence_priorities) == 1
        assert layer1.evidence_traffic_lights == []  # backward compat default


class TestLayer2CoreV31:
    def test_evidence_cards(self):
        layer2 = Layer2Core(
            evidence_cards=[
                EvidenceBasicCard(
                    evidence_id="EV001",
                    q1_what="test",
                    q2_target="test",
                    q3_key_risk="test",
                    q4_best_attack="test",
                ),
            ],
            unified_electronic_strategy="申请司法鉴定确认数据完整性",
        )
        assert len(layer2.evidence_cards) == 1
        assert layer2.unified_electronic_strategy != ""
        assert layer2.evidence_battle_matrix == []  # backward compat default
