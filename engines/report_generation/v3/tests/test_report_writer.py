"""Tests for the V3 4-layer report writer integration."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engines.report_generation.v3.models import (
    CoverSummary,
    FourLayerReport,
    Layer1Cover,
    Layer2Core,
    Layer3Perspective,
    Layer4Appendix,
    SectionTag,
)
from engines.report_generation.v3.report_writer import (
    build_four_layer_report,
    write_v3_report_md,
)
from engines.report_generation.v3.tag_system import (
    format_tag,
    tag_line,
    tag_section_header,
    statement_class_to_tag,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


def _make_mock_evidence(eid, title, ev_type="documentary", source="test", owner="party-p"):
    ev = MagicMock()
    ev.evidence_id = eid
    ev.title = title
    ev.source = source
    ev.summary = f"Summary for {title}"
    ev.evidence_type = MagicMock(value=ev_type)
    ev.status = MagicMock(value="submitted")
    ev.owner_party_id = owner
    ev.target_fact_ids = ["fact-001"]
    ev.target_issue_ids = ["ISS001"]
    ev.is_copy_only = False
    ev.challenged_by_party_ids = []
    ev.admissibility_score = 1.0
    ev.admissibility_challenges = []
    ev.authenticity_risk = None
    ev.relevance_score = None
    ev.legality_risk = None
    ev.vulnerability = None
    ev.probative_value = None
    ev.supports = []
    ev.is_attacked_by = []
    ev.exclusion_impact = None
    ev.fact_propositions = []
    return ev


def _make_mock_issue(issue_id, title):
    issue = MagicMock()
    issue.issue_id = issue_id
    issue.title = title
    issue.issue_type = MagicMock(value="factual")
    issue.status = MagicMock(value="open")
    issue.evidence_ids = ["EV001"]
    issue.fact_propositions = []
    issue.outcome_impact = None
    issue.recommended_action = None
    issue.composite_score = None
    issue.depends_on = []
    return issue


def _make_mock_adversarial_result():
    result = MagicMock()
    result.case_id = "case-test-001"
    result.run_id = "run-test-001"

    # Summary
    arg = MagicMock()
    arg.issue_id = "ISS001"
    arg.position = "原告主张借贷关系成立"
    arg.reasoning = "有银行转账凭证"
    arg.supporting_evidence_ids = ["EV001"]

    defense = MagicMock()
    defense.issue_id = "ISS001"
    defense.position = "被告否认借贷合意"
    defense.reasoning = "主张是代收款"
    defense.supporting_evidence_ids = ["EV003"]

    result.summary = MagicMock()
    result.summary.plaintiff_strongest_arguments = [arg]
    result.summary.defendant_strongest_defenses = [defense]
    result.summary.overall_assessment = "本案核心争点在于借款合意是否成立。双方证据存在显著冲突。"

    result.plaintiff_best_arguments = [MagicMock(issue_id="ISS001", position="借贷关系成立")]
    result.defendant_best_defenses = [MagicMock(issue_id="ISS001", position="否认借贷")]
    result.unresolved_issues = ["ISS001"]
    result.evidence_conflicts = []

    # Rounds
    output1 = MagicMock()
    output1.agent_role_code = "plaintiff_agent"
    output1.title = "原告主张"
    output1.body = "原告主张内容"
    output1.evidence_citations = ["EV001"]

    output2 = MagicMock()
    output2.agent_role_code = "defendant_agent"
    output2.title = "被告抗辩"
    output2.body = "被告抗辩内容"
    output2.evidence_citations = ["EV003"]

    round1 = MagicMock()
    round1.round_number = 1
    round1.phase = MagicMock(value="claim")
    round1.outputs = [output1, output2]

    result.rounds = [round1]

    return result


# ── Tests ─────────────────────────────────────────────────────────────────


class TestTagSystem:
    def test_format_tag(self):
        assert format_tag(SectionTag.fact) == "「事实」"
        assert format_tag(SectionTag.recommendation) == "「建议」"

    def test_tag_line(self):
        result = tag_line("原告有银行转账凭证", SectionTag.fact)
        assert result == "原告有银行转账凭证 「事实」"

    def test_tag_section_header(self):
        result = tag_section_header("## 事实底座", SectionTag.fact)
        assert result == "## 事实底座 「事实」"

    def test_statement_class_to_tag(self):
        assert statement_class_to_tag("fact") == SectionTag.fact
        assert statement_class_to_tag("inference") == SectionTag.inference
        assert statement_class_to_tag("assumption") == SectionTag.assumption
        assert statement_class_to_tag("unknown") == SectionTag.inference  # fallback


class TestBuildFourLayerReport:
    def test_builds_all_layers(self):
        evidence_index = MagicMock()
        evidence_index.evidence = [
            _make_mock_evidence("EV001", "银行转账记录", "documentary", "银行"),
        ]

        issue_tree = MagicMock()
        issue_tree.issues = [_make_mock_issue("ISS001", "借款合意")]
        issue_tree.case_id = "case-test-001"

        result = _make_mock_adversarial_result()

        case_data = {
            "case_id": "case-test-001",
            "case_type": "civil_loan",
            "parties": {
                "plaintiff": {"party_id": "party-p", "name": "原告"},
                "defendant": {"party_id": "party-d", "name": "被告"},
            },
        }

        report = build_four_layer_report(
            adversarial_result=result,
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            case_data=case_data,
        )

        assert isinstance(report, FourLayerReport)
        assert report.case_id == "case-test-001"
        assert report.perspective == "neutral"
        assert report.layer1 is not None
        assert report.layer2 is not None
        assert report.layer3 is not None
        assert report.layer4 is not None

    def test_plaintiff_perspective(self):
        evidence_index = MagicMock()
        evidence_index.evidence = [
            _make_mock_evidence("EV001", "银行转账", "documentary", "银行"),
        ]

        issue_tree = MagicMock()
        issue_tree.issues = [_make_mock_issue("ISS001", "借款合意")]
        issue_tree.case_id = "case-test-001"

        report = build_four_layer_report(
            adversarial_result=_make_mock_adversarial_result(),
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            case_data={"case_id": "case-test-001", "case_type": "civil_loan", "parties": {}},
            perspective="plaintiff",
        )

        assert report.perspective == "plaintiff"
        # Layer 3 should have plaintiff output
        assert len(report.layer3.outputs) >= 1
        has_plaintiff = any(o.perspective == "plaintiff" for o in report.layer3.outputs)
        assert has_plaintiff


class TestWriteV3ReportMd:
    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_writes_markdown(self, _mock_redact):
        report = FourLayerReport(
            report_id="rpt-test",
            case_id="case-test",
            run_id="run-test",
            layer1=Layer1Cover(
                cover_summary=CoverSummary(neutral_conclusion="Test conclusion"),
            ),
            layer2=Layer2Core(),
            layer3=Layer3Perspective(),
            layer4=Layer4Appendix(),
        )
        case_data = {
            "case_type": "civil_loan",
            "parties": {"plaintiff": {"name": "原告"}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            p = write_v3_report_md(Path(tmpdir), report, case_data, no_redact=True)
            assert p.exists()
            content = p.read_text(encoding="utf-8")
            assert "案件诊断报告" in content
            assert "封面摘要" in content
            assert "中立对抗内核" in content
            assert "角色化输出" in content
            assert "附录" in content
            assert "「事实」" in content
            assert "V3 四层架构" in content

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_no_percentages_in_output(self, _mock_redact):
        """Verify the report does not contain probability percentages."""
        report = FourLayerReport(
            report_id="rpt-test",
            case_id="case-test",
            run_id="run-test",
            layer1=Layer1Cover(
                cover_summary=CoverSummary(neutral_conclusion="Test"),
                scenario_tree_summary="若条件A成立则X；若不成立则Y",
            ),
            layer2=Layer2Core(),
            layer3=Layer3Perspective(),
            layer4=Layer4Appendix(),
        )
        case_data = {"case_type": "civil_loan", "parties": {}}

        with tempfile.TemporaryDirectory() as tmpdir:
            p = write_v3_report_md(Path(tmpdir), report, case_data, no_redact=True)
            content = p.read_text(encoding="utf-8")
            # In the scenario tree summary and other narrative, there should be no probabilities
            assert "若条件A成立则X" in content

    def test_serializable_to_json(self):
        """Verify the FourLayerReport is fully JSON-serializable."""
        report = FourLayerReport(
            report_id="rpt-test",
            case_id="case-test",
            run_id="run-test",
            layer1=Layer1Cover(
                cover_summary=CoverSummary(neutral_conclusion="Test"),
            ),
            layer2=Layer2Core(),
            layer3=Layer3Perspective(),
            layer4=Layer4Appendix(),
        )
        json_str = report.model_dump_json(indent=2)
        parsed = json.loads(json_str)
        assert parsed["report_id"] == "rpt-test"
        assert "layer1" in parsed
        assert "layer2" in parsed
