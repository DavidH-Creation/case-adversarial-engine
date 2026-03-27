"""
ActionRecommender 单元测试（P1.8）。

测试策略：
- 使用 Pydantic 模型构建测试数据（不用 Mock）
- 验证每个规则的推导结果
- 边界条件：空输入、混合 recommended_action、多 claim 绑定
- 合约保证：零 LLM 调用（纯规则层）
"""
from __future__ import annotations

import pytest

from engines.shared.models import (
    ActionRecommendation,
    AmountCalculationReport,
    AmountConsistencyCheck,
    ClaimAbandonSuggestion,
    ClaimAmendmentSuggestion,
    EvidenceGapItem,
    Issue,
    IssueType,
    OutcomeImpactSize,
    PracticallyObtainable,
    RecommendedAction,
    SupplementCost,
    TrialExplanationPriority,
)
from engines.simulation_run.action_recommender.recommender import ActionRecommender
from engines.simulation_run.action_recommender.schemas import ActionRecommenderInput


# ---------------------------------------------------------------------------
# 测试辅助函数 / Test helpers
# ---------------------------------------------------------------------------

def make_issue(
    issue_id: str,
    recommended_action: RecommendedAction | None = None,
    related_claim_ids: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    recommended_action_basis: str | None = None,
    title: str = "测试争点",
) -> Issue:
    return Issue(
        issue_id=issue_id,
        case_id="case1",
        title=title,
        issue_type=IssueType.factual,
        related_claim_ids=related_claim_ids or [],
        evidence_ids=evidence_ids or [],
        recommended_action=recommended_action,
        recommended_action_basis=recommended_action_basis,
    )


def make_gap_item(
    gap_id: str,
    related_issue_id: str,
    roi_rank: int,
) -> EvidenceGapItem:
    return EvidenceGapItem(
        gap_id=gap_id,
        case_id="case1",
        run_id="run1",
        related_issue_id=related_issue_id,
        gap_description="缺证说明",
        supplement_cost=SupplementCost.medium,
        outcome_impact_size=OutcomeImpactSize.significant,
        practically_obtainable=PracticallyObtainable.yes,
        roi_rank=roi_rank,
    )


def make_amount_report() -> AmountCalculationReport:
    """最小合法 AmountCalculationReport（无流水记录，仅满足 Pydantic 约束）。"""
    return AmountCalculationReport(
        report_id="rpt1",
        case_id="case1",
        run_id="run1",
        loan_transactions=[],
        repayment_transactions=[],
        claim_calculation_table=[],
        consistency_check_result=AmountConsistencyCheck(
            principal_base_unique=True,
            all_repayments_attributed=True,
            text_table_amount_consistent=True,
            duplicate_interest_penalty_claim=False,
            claim_total_reconstructable=True,
            unresolved_conflicts=[],
            verdict_block_active=False,
        ),
    )


def make_input(
    issues: list[Issue] | None = None,
    gaps: list[EvidenceGapItem] | None = None,
) -> ActionRecommenderInput:
    return ActionRecommenderInput(
        case_id="case1",
        run_id="run1",
        issue_list=issues or [],
        evidence_gap_list=gaps or [],
        amount_calculation_report=make_amount_report(),
    )


# ---------------------------------------------------------------------------
# 基础行为 / Basic behavior
# ---------------------------------------------------------------------------

class TestBasicBehavior:
    def test_returns_action_recommendation(self):
        rec = ActionRecommender().recommend(make_input())
        assert isinstance(rec, ActionRecommendation)

    def test_output_has_correct_case_and_run_id(self):
        rec = ActionRecommender().recommend(make_input())
        assert rec.case_id == "case1"
        assert rec.run_id == "run1"

    def test_recommendation_id_non_empty(self):
        rec = ActionRecommender().recommend(make_input())
        assert rec.recommendation_id

    def test_created_at_non_empty(self):
        rec = ActionRecommender().recommend(make_input())
        assert rec.created_at

    def test_empty_input_returns_empty_lists(self):
        rec = ActionRecommender().recommend(make_input())
        assert rec.recommended_claim_amendments == []
        assert rec.evidence_supplement_priorities == []
        assert rec.trial_explanation_priorities == []
        assert rec.claims_to_abandon == []


# ---------------------------------------------------------------------------
# evidence_supplement_priorities（来自 P1.7 ROI 排序）
# ---------------------------------------------------------------------------

class TestEvidenceSupplementPriorities:
    def test_gap_ids_sorted_by_roi_rank(self):
        gaps = [
            make_gap_item("gap3", "i1", roi_rank=3),
            make_gap_item("gap1", "i1", roi_rank=1),
            make_gap_item("gap2", "i1", roi_rank=2),
        ]
        rec = ActionRecommender().recommend(make_input(gaps=gaps))
        assert rec.evidence_supplement_priorities == ["gap1", "gap2", "gap3"]

    def test_single_gap_item(self):
        gaps = [make_gap_item("gap1", "i1", roi_rank=1)]
        rec = ActionRecommender().recommend(make_input(gaps=gaps))
        assert rec.evidence_supplement_priorities == ["gap1"]

    def test_no_gaps_returns_empty_list(self):
        rec = ActionRecommender().recommend(make_input(gaps=[]))
        assert rec.evidence_supplement_priorities == []

    def test_gap_ids_are_strings(self):
        gaps = [make_gap_item("gap-abc", "i1", roi_rank=1)]
        rec = ActionRecommender().recommend(make_input(gaps=gaps))
        assert all(isinstance(g, str) for g in rec.evidence_supplement_priorities)


# ---------------------------------------------------------------------------
# recommended_claim_amendments（来自 recommended_action = amend_claim）
# ---------------------------------------------------------------------------

class TestRecommendedClaimAmendments:
    def test_amend_claim_issue_generates_amendment(self):
        issues = [make_issue("i1", RecommendedAction.amend_claim, related_claim_ids=["c1"])]
        rec = ActionRecommender().recommend(make_input(issues=issues))
        assert len(rec.recommended_claim_amendments) == 1
        assert rec.recommended_claim_amendments[0].original_claim_id == "c1"

    def test_non_amend_issue_does_not_generate_amendment(self):
        issues = [make_issue("i1", RecommendedAction.abandon, related_claim_ids=["c1"])]
        rec = ActionRecommender().recommend(make_input(issues=issues))
        assert rec.recommended_claim_amendments == []

    def test_issue_with_multiple_claims_generates_multiple_amendments(self):
        issues = [
            make_issue("i1", RecommendedAction.amend_claim, related_claim_ids=["c1", "c2"])
        ]
        rec = ActionRecommender().recommend(make_input(issues=issues))
        assert len(rec.recommended_claim_amendments) == 2
        claim_ids = {a.original_claim_id for a in rec.recommended_claim_amendments}
        assert claim_ids == {"c1", "c2"}

    def test_amendment_binds_issue_id(self):
        issues = [make_issue("i1", RecommendedAction.amend_claim, related_claim_ids=["c1"])]
        rec = ActionRecommender().recommend(make_input(issues=issues))
        assert rec.recommended_claim_amendments[0].amendment_reason_issue_id == "i1"

    def test_amendment_description_non_empty(self):
        issues = [make_issue("i1", RecommendedAction.amend_claim, related_claim_ids=["c1"])]
        rec = ActionRecommender().recommend(make_input(issues=issues))
        assert rec.recommended_claim_amendments[0].amendment_description

    def test_amendment_suggestion_id_unique_per_entry(self):
        issues = [
            make_issue("i1", RecommendedAction.amend_claim, related_claim_ids=["c1", "c2"])
        ]
        rec = ActionRecommender().recommend(make_input(issues=issues))
        ids = [a.suggestion_id for a in rec.recommended_claim_amendments]
        assert len(ids) == len(set(ids)), "suggestion_id 必须唯一"

    def test_issue_without_recommended_action_skipped(self):
        issues = [make_issue("i1", recommended_action=None, related_claim_ids=["c1"])]
        rec = ActionRecommender().recommend(make_input(issues=issues))
        assert rec.recommended_claim_amendments == []

    def test_amend_claim_issue_without_claims_skipped(self):
        """争点有 amend_claim 但 related_claim_ids 为空时，不生成建议。"""
        issues = [make_issue("i1", RecommendedAction.amend_claim, related_claim_ids=[])]
        rec = ActionRecommender().recommend(make_input(issues=issues))
        assert rec.recommended_claim_amendments == []

    def test_evidence_ids_propagated_to_amendment(self):
        issues = [
            make_issue(
                "i1",
                RecommendedAction.amend_claim,
                related_claim_ids=["c1"],
                evidence_ids=["e1", "e2"],
            )
        ]
        rec = ActionRecommender().recommend(make_input(issues=issues))
        assert set(rec.recommended_claim_amendments[0].amendment_reason_evidence_ids) == {"e1", "e2"}


# ---------------------------------------------------------------------------
# claims_to_abandon（来自 recommended_action = abandon）
# ---------------------------------------------------------------------------

class TestClaimsToAbandon:
    def test_abandon_issue_generates_suggestion(self):
        issues = [make_issue("i1", RecommendedAction.abandon, related_claim_ids=["c1"])]
        rec = ActionRecommender().recommend(make_input(issues=issues))
        assert len(rec.claims_to_abandon) == 1
        assert rec.claims_to_abandon[0].claim_id == "c1"

    def test_non_abandon_issue_does_not_generate_suggestion(self):
        issues = [make_issue("i1", RecommendedAction.supplement_evidence, related_claim_ids=["c1"])]
        rec = ActionRecommender().recommend(make_input(issues=issues))
        assert rec.claims_to_abandon == []

    def test_issue_with_multiple_claims_generates_multiple_suggestions(self):
        issues = [
            make_issue("i1", RecommendedAction.abandon, related_claim_ids=["c1", "c2"])
        ]
        rec = ActionRecommender().recommend(make_input(issues=issues))
        assert len(rec.claims_to_abandon) == 2

    def test_abandon_suggestion_binds_issue_id(self):
        issues = [make_issue("i1", RecommendedAction.abandon, related_claim_ids=["c1"])]
        rec = ActionRecommender().recommend(make_input(issues=issues))
        assert rec.claims_to_abandon[0].abandon_reason_issue_id == "i1"

    def test_abandon_reason_non_empty(self):
        issues = [make_issue("i1", RecommendedAction.abandon, related_claim_ids=["c1"])]
        rec = ActionRecommender().recommend(make_input(issues=issues))
        assert rec.claims_to_abandon[0].abandon_reason

    def test_abandon_suggestion_id_unique(self):
        issues = [
            make_issue("i1", RecommendedAction.abandon, related_claim_ids=["c1", "c2"])
        ]
        rec = ActionRecommender().recommend(make_input(issues=issues))
        ids = [a.suggestion_id for a in rec.claims_to_abandon]
        assert len(ids) == len(set(ids))

    def test_abandon_without_claims_skipped(self):
        issues = [make_issue("i1", RecommendedAction.abandon, related_claim_ids=[])]
        rec = ActionRecommender().recommend(make_input(issues=issues))
        assert rec.claims_to_abandon == []


# ---------------------------------------------------------------------------
# trial_explanation_priorities（来自 recommended_action = explain_in_trial）
# ---------------------------------------------------------------------------

class TestTrialExplanationPriorities:
    def test_explain_issue_generates_priority(self):
        issues = [make_issue("i1", RecommendedAction.explain_in_trial)]
        rec = ActionRecommender().recommend(make_input(issues=issues))
        assert len(rec.trial_explanation_priorities) == 1

    def test_priority_binds_issue_id(self):
        issues = [make_issue("i1", RecommendedAction.explain_in_trial)]
        rec = ActionRecommender().recommend(make_input(issues=issues))
        assert rec.trial_explanation_priorities[0].issue_id == "i1"

    def test_explanation_text_non_empty(self):
        issues = [make_issue("i1", RecommendedAction.explain_in_trial)]
        rec = ActionRecommender().recommend(make_input(issues=issues))
        assert rec.trial_explanation_priorities[0].explanation_text

    def test_multiple_explain_issues(self):
        issues = [
            make_issue("i1", RecommendedAction.explain_in_trial),
            make_issue("i2", RecommendedAction.explain_in_trial),
        ]
        rec = ActionRecommender().recommend(make_input(issues=issues))
        assert len(rec.trial_explanation_priorities) == 2
        issue_ids = {p.issue_id for p in rec.trial_explanation_priorities}
        assert issue_ids == {"i1", "i2"}

    def test_non_explain_issue_skipped(self):
        issues = [make_issue("i1", RecommendedAction.supplement_evidence)]
        rec = ActionRecommender().recommend(make_input(issues=issues))
        assert rec.trial_explanation_priorities == []

    def test_priority_id_unique(self):
        issues = [
            make_issue("i1", RecommendedAction.explain_in_trial),
            make_issue("i2", RecommendedAction.explain_in_trial),
        ]
        rec = ActionRecommender().recommend(make_input(issues=issues))
        ids = [p.priority_id for p in rec.trial_explanation_priorities]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# 混合场景 / Mixed scenario
# ---------------------------------------------------------------------------

class TestMixedScenario:
    def test_all_action_types_simultaneously(self):
        """所有四种 recommended_action 同时存在时，正确分发。"""
        issues = [
            make_issue("i1", RecommendedAction.amend_claim, related_claim_ids=["c1"]),
            make_issue("i2", RecommendedAction.abandon, related_claim_ids=["c2"]),
            make_issue("i3", RecommendedAction.explain_in_trial),
            make_issue("i4", RecommendedAction.supplement_evidence),  # supplement 不生成任何条目
        ]
        gaps = [
            make_gap_item("gap1", "i1", roi_rank=1),
            make_gap_item("gap2", "i4", roi_rank=2),
        ]
        rec = ActionRecommender().recommend(make_input(issues=issues, gaps=gaps))

        assert len(rec.recommended_claim_amendments) == 1
        assert len(rec.claims_to_abandon) == 1
        assert len(rec.trial_explanation_priorities) == 1
        assert rec.evidence_supplement_priorities == ["gap1", "gap2"]

    def test_supplement_evidence_not_in_amendments_or_abandon(self):
        """supplement_evidence 争点不会出现在 amendments 或 claims_to_abandon 中。"""
        issues = [make_issue("i1", RecommendedAction.supplement_evidence, related_claim_ids=["c1"])]
        rec = ActionRecommender().recommend(make_input(issues=issues))
        assert rec.recommended_claim_amendments == []
        assert rec.claims_to_abandon == []
