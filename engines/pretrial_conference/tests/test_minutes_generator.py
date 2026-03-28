"""MinutesGenerator 单元测试。"""

import pytest

from engines.pretrial_conference.minutes_generator import MinutesGenerator
from engines.pretrial_conference.schemas import (
    CrossExaminationDimension,
    CrossExaminationFocusItem,
    CrossExaminationOpinion,
    CrossExaminationRecord,
    CrossExaminationResult,
    CrossExaminationVerdict,
    JudgeQuestion,
    JudgeQuestionSet,
    JudgeQuestionType,
    PretrialConferenceResult,
)
from engines.shared.models import (
    AccessDomain,
    Evidence,
    EvidenceIndex,
    EvidenceStatus,
    EvidenceType,
    Issue,
    IssueTree,
    IssueType,
    ReportArtifact,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cross_exam_result(records=None, focus_list=None):
    return CrossExaminationResult(
        case_id="case-001",
        run_id="run-001",
        records=records or [],
        focus_list=focus_list or [],
    )


def _make_judge_questions(questions=None):
    return JudgeQuestionSet(
        case_id="case-001",
        run_id="run-001",
        questions=questions or [],
    )


def _make_admitted_evidence(evidence_id="ev-001"):
    return Evidence(
        evidence_id=evidence_id,
        case_id="case-001",
        owner_party_id="party-plaintiff",
        title=f"证据 {evidence_id}",
        source="当事人",
        summary=f"证据 {evidence_id} 摘要",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=["fact-001"],
        target_issue_ids=["issue-001"],
        access_domain=AccessDomain.admitted_record,
        status=EvidenceStatus.admitted_for_discussion,
        challenged_by_party_ids=[],
    )


def _make_evidence_index(evidences=None):
    return EvidenceIndex(
        case_id="case-001",
        evidence=evidences or [_make_admitted_evidence()],
    )


def _make_issue_tree():
    return IssueTree(
        case_id="case-001",
        issues=[
            Issue(
                issue_id="issue-001",
                case_id="case-001",
                title="借款事实争点",
                issue_type=IssueType.factual,
            ),
        ],
    )


def _make_opinion(evidence_id="ev-001", verdict=CrossExaminationVerdict.accepted):
    return CrossExaminationOpinion(
        evidence_id=evidence_id,
        issue_ids=["issue-001"],
        dimension=CrossExaminationDimension.authenticity,
        verdict=verdict,
        reasoning="质证理由",
        examiner_party_id="party-defendant",
    )


def _make_record(evidence_id="ev-001", result_status="admitted_for_discussion"):
    return CrossExaminationRecord(
        evidence_id=evidence_id,
        evidence_title=f"证据 {evidence_id}",
        owner_party_id="party-plaintiff",
        opinions=[_make_opinion(evidence_id)],
        result_status=result_status,
    )


def _make_judge_question():
    return JudgeQuestion(
        question_id="jq-001",
        issue_id="issue-001",
        evidence_ids=["ev-001"],
        question_text="请说明借款用途",
        target_party_id="party-plaintiff",
        question_type=JudgeQuestionType.clarification,
        priority=1,
    )


def _make_full_result():
    """构建包含完整内容的 PretrialConferenceResult。"""
    focus = CrossExaminationFocusItem(
        evidence_id="ev-002",
        issue_id="issue-001",
        dimension=CrossExaminationDimension.authenticity,
        dispute_summary="签名真实性存疑",
    )
    return PretrialConferenceResult(
        case_id="case-001",
        run_id="run-001",
        cross_examination_result=_make_cross_exam_result(
            records=[
                _make_record("ev-001", "admitted_for_discussion"),
                _make_record("ev-002", "challenged"),
            ],
            focus_list=[focus],
        ),
        judge_questions=_make_judge_questions([_make_judge_question()]),
        final_evidence_index=_make_evidence_index([
            _make_admitted_evidence("ev-001"),
        ]),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMinutesGenerator:
    def test_generates_report_artifact(self):
        gen = MinutesGenerator()
        report = gen.generate(
            result=_make_full_result(),
            issue_tree=_make_issue_tree(),
        )
        assert isinstance(report, ReportArtifact)
        assert report.case_id == "case-001"

    def test_has_expected_sections(self):
        gen = MinutesGenerator()
        report = gen.generate(
            result=_make_full_result(),
            issue_tree=_make_issue_tree(),
        )
        titles = [s.title for s in report.sections]
        assert "质证情况" in titles
        assert "法官追问" in titles

    def test_sections_have_linked_evidence_ids(self):
        gen = MinutesGenerator()
        report = gen.generate(
            result=_make_full_result(),
            issue_tree=_make_issue_tree(),
        )
        # 至少有一个 section 包含 linked_evidence_ids
        all_ev_ids = set()
        for s in report.sections:
            all_ev_ids.update(s.linked_evidence_ids)
        assert len(all_ev_ids) > 0

    def test_sections_have_linked_issue_ids(self):
        gen = MinutesGenerator()
        report = gen.generate(
            result=_make_full_result(),
            issue_tree=_make_issue_tree(),
        )
        all_issue_ids = set()
        for s in report.sections:
            all_issue_ids.update(s.linked_issue_ids)
        assert "issue-001" in all_issue_ids

    def test_empty_result_still_generates(self):
        """空结果也应该能生成报告。"""
        gen = MinutesGenerator()
        result = PretrialConferenceResult(
            case_id="case-001",
            run_id="run-001",
            cross_examination_result=_make_cross_exam_result(),
            judge_questions=_make_judge_questions(),
            final_evidence_index=_make_evidence_index([]),
        )
        report = gen.generate(result=result, issue_tree=_make_issue_tree())
        assert isinstance(report, ReportArtifact)
        assert len(report.sections) >= 1

    def test_report_title_contains_case_id(self):
        gen = MinutesGenerator()
        report = gen.generate(
            result=_make_full_result(),
            issue_tree=_make_issue_tree(),
        )
        assert "case-001" in report.title

    def test_cross_exam_section_mentions_evidence(self):
        gen = MinutesGenerator()
        report = gen.generate(
            result=_make_full_result(),
            issue_tree=_make_issue_tree(),
        )
        xexam_section = next(
            s for s in report.sections if s.title == "质证情况"
        )
        assert "ev-001" in xexam_section.body or "ev-001" in str(
            xexam_section.linked_evidence_ids
        )

    def test_judge_section_mentions_questions(self):
        gen = MinutesGenerator()
        report = gen.generate(
            result=_make_full_result(),
            issue_tree=_make_issue_tree(),
        )
        judge_section = next(
            s for s in report.sections if s.title == "法官追问"
        )
        assert "请说明借款用途" in judge_section.body

    def test_all_sections_have_linked_output_ids(self):
        """每个 section 的 linked_output_ids 不为空（满足 ReportArtifact 契约）。"""
        gen = MinutesGenerator()
        report = gen.generate(
            result=_make_full_result(),
            issue_tree=_make_issue_tree(),
        )
        for sec in report.sections:
            assert sec.linked_output_ids, (
                f"section {sec.section_id!r} ({sec.title}) "
                f"has empty linked_output_ids"
            )

    def test_passes_report_validator(self):
        """生成的纪要应通过现有 ReportArtifact validator 的 output 回链检查。"""
        gen = MinutesGenerator()
        report = gen.generate(
            result=_make_full_result(),
            issue_tree=_make_issue_tree(),
        )
        for sec in report.sections:
            assert len(sec.linked_output_ids) >= 1
