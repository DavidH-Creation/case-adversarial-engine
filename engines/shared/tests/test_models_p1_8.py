"""
P1.8 数据模型单元测试 — ClaimAmendmentSuggestion / ClaimAbandonSuggestion /
TrialExplanationPriority / ActionRecommendation
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from engines.shared.models import (
    ActionRecommendation,
    ClaimAbandonSuggestion,
    ClaimAmendmentSuggestion,
    TrialExplanationPriority,
)


# ---------------------------------------------------------------------------
# ClaimAmendmentSuggestion
# ---------------------------------------------------------------------------

class TestClaimAmendmentSuggestion:
    def test_valid_minimal(self):
        obj = ClaimAmendmentSuggestion(
            suggestion_id="s1",
            original_claim_id="c1",
            amendment_description="建议将诉请金额调整为已举证部分",
            amendment_reason_issue_id="i1",
            amendment_reason_evidence_ids=["e1"],
        )
        assert obj.suggestion_id == "s1"
        assert obj.original_claim_id == "c1"

    def test_empty_suggestion_id_raises(self):
        with pytest.raises(ValidationError):
            ClaimAmendmentSuggestion(
                suggestion_id="",
                original_claim_id="c1",
                amendment_description="desc",
                amendment_reason_issue_id="i1",
                amendment_reason_evidence_ids=["e1"],
            )

    def test_empty_original_claim_id_raises(self):
        with pytest.raises(ValidationError):
            ClaimAmendmentSuggestion(
                suggestion_id="s1",
                original_claim_id="",
                amendment_description="desc",
                amendment_reason_issue_id="i1",
                amendment_reason_evidence_ids=["e1"],
            )

    def test_empty_description_raises(self):
        with pytest.raises(ValidationError):
            ClaimAmendmentSuggestion(
                suggestion_id="s1",
                original_claim_id="c1",
                amendment_description="",
                amendment_reason_issue_id="i1",
                amendment_reason_evidence_ids=["e1"],
            )

    def test_empty_issue_id_raises(self):
        with pytest.raises(ValidationError):
            ClaimAmendmentSuggestion(
                suggestion_id="s1",
                original_claim_id="c1",
                amendment_description="desc",
                amendment_reason_issue_id="",
                amendment_reason_evidence_ids=["e1"],
            )

    def test_empty_evidence_ids_list_allowed(self):
        """evidence_ids 可为空列表（某些争点无直接证据绑定）。"""
        obj = ClaimAmendmentSuggestion(
            suggestion_id="s1",
            original_claim_id="c1",
            amendment_description="desc",
            amendment_reason_issue_id="i1",
            amendment_reason_evidence_ids=[],
        )
        assert obj.amendment_reason_evidence_ids == []


# ---------------------------------------------------------------------------
# ClaimAbandonSuggestion
# ---------------------------------------------------------------------------

class TestClaimAbandonSuggestion:
    def test_valid_minimal(self):
        obj = ClaimAbandonSuggestion(
            suggestion_id="ab1",
            claim_id="c2",
            abandon_reason="该诉请缺乏充足证据支撑，建议放弃以减少败诉风险",
            abandon_reason_issue_id="i2",
        )
        assert obj.claim_id == "c2"
        assert obj.abandon_reason_issue_id == "i2"

    def test_empty_claim_id_raises(self):
        with pytest.raises(ValidationError):
            ClaimAbandonSuggestion(
                suggestion_id="ab1",
                claim_id="",
                abandon_reason="reason",
                abandon_reason_issue_id="i2",
            )

    def test_empty_abandon_reason_raises(self):
        with pytest.raises(ValidationError):
            ClaimAbandonSuggestion(
                suggestion_id="ab1",
                claim_id="c2",
                abandon_reason="",
                abandon_reason_issue_id="i2",
            )

    def test_empty_issue_id_raises(self):
        with pytest.raises(ValidationError):
            ClaimAbandonSuggestion(
                suggestion_id="ab1",
                claim_id="c2",
                abandon_reason="reason",
                abandon_reason_issue_id="",
            )


# ---------------------------------------------------------------------------
# TrialExplanationPriority
# ---------------------------------------------------------------------------

class TestTrialExplanationPriority:
    def test_valid_minimal(self):
        obj = TrialExplanationPriority(
            priority_id="tp1",
            issue_id="i3",
            explanation_text="需在庭审中优先解释还款归因差异",
        )
        assert obj.issue_id == "i3"

    def test_empty_issue_id_raises(self):
        with pytest.raises(ValidationError):
            TrialExplanationPriority(
                priority_id="tp1",
                issue_id="",
                explanation_text="text",
            )

    def test_empty_explanation_text_raises(self):
        with pytest.raises(ValidationError):
            TrialExplanationPriority(
                priority_id="tp1",
                issue_id="i3",
                explanation_text="",
            )


# ---------------------------------------------------------------------------
# ActionRecommendation
# ---------------------------------------------------------------------------

class TestActionRecommendation:
    def _make_valid(self, **kwargs):
        defaults = dict(
            recommendation_id="rec1",
            case_id="case1",
            run_id="run1",
            recommended_claim_amendments=[],
            evidence_supplement_priorities=[],
            trial_explanation_priorities=[],
            claims_to_abandon=[],
        )
        defaults.update(kwargs)
        return ActionRecommendation(**defaults)

    def test_valid_empty_lists(self):
        rec = self._make_valid()
        assert rec.recommendation_id == "rec1"
        assert isinstance(rec.created_at, str)

    def test_created_at_auto_populated(self):
        rec = self._make_valid()
        assert rec.created_at  # non-empty string

    def test_with_amendments(self):
        amendment = ClaimAmendmentSuggestion(
            suggestion_id="s1",
            original_claim_id="c1",
            amendment_description="desc",
            amendment_reason_issue_id="i1",
            amendment_reason_evidence_ids=["e1"],
        )
        rec = self._make_valid(recommended_claim_amendments=[amendment])
        assert len(rec.recommended_claim_amendments) == 1

    def test_with_gap_ids(self):
        rec = self._make_valid(evidence_supplement_priorities=["gap1", "gap2"])
        assert rec.evidence_supplement_priorities == ["gap1", "gap2"]

    def test_with_trial_explanations(self):
        tp = TrialExplanationPriority(
            priority_id="tp1",
            issue_id="i3",
            explanation_text="text",
        )
        rec = self._make_valid(trial_explanation_priorities=[tp])
        assert len(rec.trial_explanation_priorities) == 1

    def test_with_abandon(self):
        ab = ClaimAbandonSuggestion(
            suggestion_id="ab1",
            claim_id="c2",
            abandon_reason="reason",
            abandon_reason_issue_id="i2",
        )
        rec = self._make_valid(claims_to_abandon=[ab])
        assert len(rec.claims_to_abandon) == 1

    def test_empty_recommendation_id_raises(self):
        with pytest.raises(ValidationError):
            self._make_valid(recommendation_id="")

    def test_empty_case_id_raises(self):
        with pytest.raises(ValidationError):
            self._make_valid(case_id="")

    def test_empty_run_id_raises(self):
        with pytest.raises(ValidationError):
            self._make_valid(run_id="")
