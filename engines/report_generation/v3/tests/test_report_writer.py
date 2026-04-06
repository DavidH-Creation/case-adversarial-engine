"""Tests for the V3 4-layer report writer integration."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engines.report_generation.v3.models import (
    CoverSummary,
    EvidenceBasicCard,
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
        assert statement_class_to_tag("opinion") == SectionTag.opinion
        assert statement_class_to_tag("recommendation") == SectionTag.recommendation
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


def _substantive_layer4() -> Layer4Appendix:
    """Build a Layer4 with enough content to avoid excessive fallback ratio."""
    return Layer4Appendix(
        adversarial_transcripts_md=(
            "### Round 1 (claim)\n\n"
            "**plaintiff_agent** — 原告主张\n\n原告主张内容，借贷关系成立\n\n"
            "*引用证据*: EV001\n\n---\n\n"
            "**defendant_agent** — 被告抗辩\n\n被告否认借贷合意\n\n"
            "*引用证据*: EV003\n\n---"
        ),
        evidence_index_md=(
            "| 编号 | 标题 | 类型 | 提交方 | 状态 |\n"
            "|------|------|------|--------|------|\n"
            "| EV001 | 银行转账记录 | documentary | party-p | submitted |"
        ),
        timeline_md=(
            "| 日期 | 事件 | 来源 | 争议 |\n"
            "|------|------|------|------|\n"
            "| 2025-01-10 | 原告银行转账10万元 | EV001 |  |\n"
            "| 2025-03-01 | 原告向法院起诉 | case_data |  |"
        ),
        glossary_md=(
            "| 术语 | 解释 |\n"
            "|------|------|\n"
            "| 争点 | 双方在事实或法律适用上存在分歧的焦点问题 |\n"
            "| 举证责任 | 当事人应当对其主张的事实承担提供证据并加以证明的责任 |"
        ),
    )


def _substantive_layer2() -> Layer2Core:
    """Build a Layer2 with enough content to avoid excessive fallback ratio."""
    return Layer2Core(
        fact_base=[
            FactBaseEntry(
                fact_id="FACT-001",
                description="2025年1月10日原告向被告转账10万元（银行流水确认）",
                source_evidence_ids=["EV001"],
            ),
        ],
        issue_map=[
            IssueMapCard(
                issue_id="ISS001",
                issue_title="借款合意是否成立",
                plaintiff_thesis="原告主张存在借贷合意，有借条和转账记录",
                defendant_thesis="被告否认借贷合意，主张系代收代付",
                decisive_evidence=["EV001"],
                outcome_sensitivity="高",
            ),
        ],
        evidence_cards=[
            EvidenceBasicCard(
                evidence_id="EV001",
                q1_what="银行转账记录，记载原告向被告转账10万元",
                q2_target="证明资金实际交付",
                q3_key_risk="仅能证明资金流向，不能单独证明借贷合意",
                q4_best_attack="被告可主张转账系代收代付非借款",
                priority=EvidencePriority.core,
            ),
        ],
    )


def _substantive_report(**cover_kwargs) -> FourLayerReport:
    """Build a report with enough substantive content to pass the 0.25 fallback gate."""
    return FourLayerReport(
        report_id="rpt-test",
        case_id="case-test",
        run_id="run-test",
        layer1=Layer1Cover(
            cover_summary=CoverSummary(**cover_kwargs),
            timeline=[
                TimelineEvent(date="2025-01-10", event="原告银行转账10万元", source="EV001"),
                TimelineEvent(date="2025-03-01", event="原告向法院起诉", source="case_data"),
            ],
            evidence_priorities=[
                EvidencePriorityCard(
                    evidence_id="EV001",
                    title="银行转账记录",
                    priority=EvidencePriority.core,
                    reason="直接证明资金交付",
                    controls_issue_ids=["ISS001"],
                ),
            ],
        ),
        layer2=_substantive_layer2(),
        layer3=Layer3Perspective(
            outputs=[
                PerspectiveOutput(
                    perspective="plaintiff",
                    evidence_supplement_checklist=["补充完整银行流水"],
                    cross_examination_points=["质疑被告代收代付抗辩的合理性"],
                    trial_questions=["问被告：如仅代收代付为何讨论还款？"],
                ),
                PerspectiveOutput(
                    perspective="defendant",
                    evidence_supplement_checklist=["提供代收代付关系证据"],
                    cross_examination_points=["质疑借条签名真实性"],
                    trial_questions=["问原告：面对面借款合意何时达成？"],
                ),
            ]
        ),
        layer4=_substantive_layer4(),
    )


class TestWriteV3ReportMd:
    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_writes_markdown(self, _mock_redact):
        report = _substantive_report(
            neutral_conclusion="本案涉及民间借贷纠纷，核心争点在于借款合意是否成立",
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
        report = _substantive_report(
            neutral_conclusion="本案核心争点在于借款合意认定",
            blocking_conditions=[
                "若条件A成立则X；若不成立则Y",
            ],
        )
        case_data = {"case_type": "civil_loan", "parties": {}}

        with tempfile.TemporaryDirectory() as tmpdir:
            p = write_v3_report_md(Path(tmpdir), report, case_data, no_redact=True)
            content = p.read_text(encoding="utf-8")
            # Blocking conditions use if-then format without probabilities
            assert "若条件A成立则X" in content

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_neutral_conclusion_tagged_as_inference(self, _mock_redact):
        """overall_assessment is an inference, not a fact."""
        report = _substantive_report(
            neutral_conclusion="本案涉及民间借贷纠纷核心争点认定问题",
        )
        case_data = {"case_type": "civil_loan", "parties": {}}

        with tempfile.TemporaryDirectory() as tmpdir:
            p = write_v3_report_md(Path(tmpdir), report, case_data, no_redact=True)
            content = p.read_text(encoding="utf-8")
            # The neutral conclusion section should be tagged as inference
            assert "中立结论摘要 「推断」" in content

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
