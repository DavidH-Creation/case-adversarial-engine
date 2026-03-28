"""pretrial_conference/schemas.py 数据模型单元测试。"""

import pytest
from pydantic import ValidationError

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
from engines.shared.models import EvidenceIndex


# ---------------------------------------------------------------------------
# CrossExaminationOpinion
# ---------------------------------------------------------------------------


class TestCrossExaminationOpinion:
    def test_valid_construction(self):
        op = CrossExaminationOpinion(
            evidence_id="ev-001",
            issue_ids=["issue-001"],
            dimension=CrossExaminationDimension.authenticity,
            verdict=CrossExaminationVerdict.accepted,
            reasoning="原件核对一致",
            examiner_party_id="party-defendant",
        )
        assert op.verdict == CrossExaminationVerdict.accepted

    def test_empty_issue_ids_rejected(self):
        with pytest.raises(ValidationError):
            CrossExaminationOpinion(
                evidence_id="ev-001",
                issue_ids=[],
                dimension=CrossExaminationDimension.authenticity,
                verdict=CrossExaminationVerdict.accepted,
                reasoning="理由",
                examiner_party_id="party-defendant",
            )

    def test_empty_evidence_id_rejected(self):
        with pytest.raises(ValidationError):
            CrossExaminationOpinion(
                evidence_id="",
                issue_ids=["issue-001"],
                dimension=CrossExaminationDimension.authenticity,
                verdict=CrossExaminationVerdict.accepted,
                reasoning="理由",
                examiner_party_id="party-defendant",
            )


# ---------------------------------------------------------------------------
# CrossExaminationRecord
# ---------------------------------------------------------------------------


class TestCrossExaminationRecord:
    def test_valid_construction(self):
        rec = CrossExaminationRecord(
            evidence_id="ev-001",
            evidence_title="借条",
            owner_party_id="party-plaintiff",
            result_status="admitted_for_discussion",
        )
        assert rec.result_status == "admitted_for_discussion"
        assert rec.opinions == []

    def test_with_opinions(self):
        op = CrossExaminationOpinion(
            evidence_id="ev-001",
            issue_ids=["issue-001"],
            dimension=CrossExaminationDimension.authenticity,
            verdict=CrossExaminationVerdict.challenged,
            reasoning="签名疑似伪造",
            examiner_party_id="party-defendant",
        )
        rec = CrossExaminationRecord(
            evidence_id="ev-001",
            owner_party_id="party-plaintiff",
            opinions=[op],
            result_status="challenged",
        )
        assert len(rec.opinions) == 1


# ---------------------------------------------------------------------------
# CrossExaminationResult
# ---------------------------------------------------------------------------


class TestCrossExaminationResult:
    def test_valid_empty(self):
        result = CrossExaminationResult(case_id="case-001", run_id="run-001")
        assert result.records == []
        assert result.focus_list == []


# ---------------------------------------------------------------------------
# JudgeQuestion
# ---------------------------------------------------------------------------


class TestJudgeQuestion:
    def test_valid_construction(self):
        q = JudgeQuestion(
            question_id="jq-001",
            issue_id="issue-001",
            evidence_ids=["ev-001"],
            question_text="原告能否解释借条金额与转账记录不一致？",
            target_party_id="party-plaintiff",
            question_type=JudgeQuestionType.contradiction,
            priority=1,
        )
        assert q.priority == 1

    def test_empty_evidence_ids_rejected(self):
        with pytest.raises(ValidationError):
            JudgeQuestion(
                question_id="jq-001",
                issue_id="issue-001",
                evidence_ids=[],
                question_text="问题",
                target_party_id="party-plaintiff",
                question_type=JudgeQuestionType.clarification,
                priority=1,
            )

    def test_priority_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            JudgeQuestion(
                question_id="jq-001",
                issue_id="issue-001",
                evidence_ids=["ev-001"],
                question_text="问题",
                target_party_id="party-plaintiff",
                question_type=JudgeQuestionType.clarification,
                priority=11,
            )

    def test_priority_zero_rejected(self):
        with pytest.raises(ValidationError):
            JudgeQuestion(
                question_id="jq-001",
                issue_id="issue-001",
                evidence_ids=["ev-001"],
                question_text="问题",
                target_party_id="party-plaintiff",
                question_type=JudgeQuestionType.clarification,
                priority=0,
            )


# ---------------------------------------------------------------------------
# JudgeQuestionSet
# ---------------------------------------------------------------------------


class TestJudgeQuestionSet:
    def test_max_10_questions(self):
        questions = [
            JudgeQuestion(
                question_id=f"jq-{i:03d}",
                issue_id="issue-001",
                evidence_ids=["ev-001"],
                question_text=f"问题 {i}",
                target_party_id="party-plaintiff",
                question_type=JudgeQuestionType.clarification,
                priority=min(i, 10),
            )
            for i in range(1, 12)  # 11 questions
        ]
        with pytest.raises(ValidationError):
            JudgeQuestionSet(
                case_id="case-001",
                run_id="run-001",
                questions=questions,
            )

    def test_10_questions_accepted(self):
        questions = [
            JudgeQuestion(
                question_id=f"jq-{i:03d}",
                issue_id="issue-001",
                evidence_ids=["ev-001"],
                question_text=f"问题 {i}",
                target_party_id="party-plaintiff",
                question_type=JudgeQuestionType.clarification,
                priority=min(i, 10),
            )
            for i in range(1, 11)
        ]
        qs = JudgeQuestionSet(
            case_id="case-001", run_id="run-001", questions=questions
        )
        assert len(qs.questions) == 10


# ---------------------------------------------------------------------------
# CrossExaminationFocusItem
# ---------------------------------------------------------------------------


class TestCrossExaminationFocusItem:
    def test_valid_construction(self):
        item = CrossExaminationFocusItem(
            evidence_id="ev-001",
            issue_id="issue-001",
            dimension=CrossExaminationDimension.authenticity,
            dispute_summary="签名真实性存疑",
        )
        assert item.is_resolved is False

    def test_empty_dispute_summary_rejected(self):
        with pytest.raises(ValidationError):
            CrossExaminationFocusItem(
                evidence_id="ev-001",
                issue_id="issue-001",
                dimension=CrossExaminationDimension.authenticity,
                dispute_summary="",
            )


# ---------------------------------------------------------------------------
# PretrialConferenceResult
# ---------------------------------------------------------------------------


class TestPretrialConferenceResult:
    def test_valid_construction(self):
        result = PretrialConferenceResult(
            case_id="case-001",
            run_id="run-001",
            cross_examination_result=CrossExaminationResult(
                case_id="case-001", run_id="run-001"
            ),
            judge_questions=JudgeQuestionSet(
                case_id="case-001", run_id="run-001"
            ),
            final_evidence_index=EvidenceIndex(
                case_id="case-001", evidence=[]
            ),
        )
        assert result.case_id == "case-001"

    def test_dict_final_evidence_index_rejected(self):
        """object / dict 不再被接受为 final_evidence_index。"""
        with pytest.raises(ValidationError):
            PretrialConferenceResult(
                case_id="case-001",
                run_id="run-001",
                cross_examination_result=CrossExaminationResult(
                    case_id="case-001", run_id="run-001"
                ),
                judge_questions=JudgeQuestionSet(
                    case_id="case-001", run_id="run-001"
                ),
                final_evidence_index={},
            )


# ---------------------------------------------------------------------------
# Enum coverage
# ---------------------------------------------------------------------------


class TestEnumCoverage:
    def test_cross_examination_dimensions(self):
        assert len(CrossExaminationDimension) == 4

    def test_verdict_values(self):
        assert len(CrossExaminationVerdict) == 3

    def test_judge_question_types(self):
        assert len(JudgeQuestionType) == 4
