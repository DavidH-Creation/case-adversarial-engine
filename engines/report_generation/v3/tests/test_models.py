"""Tests for V3 4-layer report data models."""

import pytest

from engines.report_generation.v3.models import (
    ConditionalNode,
    ConditionalScenarioTree,
    CoverSummary,
    EvidenceBattleCard,
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
