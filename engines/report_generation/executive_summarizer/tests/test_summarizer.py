"""
engines/report_generation/executive_summarizer/tests/test_summarizer.py

ExecutiveSummarizer 单元测试（P2.12）。
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from engines.report_generation.executive_summarizer import ExecutiveSummarizer
from engines.report_generation.executive_summarizer.schemas import ExecutiveSummarizerInput
from engines.shared.models import (
    ActionRecommendation,
    AmountCalculationReport,
    AmountConsistencyCheck,
    AttackNode,
    ClaimAbandonSuggestion,
    ClaimAmendmentSuggestion,
    ClaimCalculationEntry,
    ClaimType,
    EvidenceGapItem,
    ExecutiveSummaryArtifact,
    Issue,
    IssueStatus,
    IssueType,
    OptimalAttackChain,
    OutcomeImpact,
    OutcomeImpactSize,
    PracticallyObtainable,
    RecommendedAction,
    SupplementCost,
    TrialExplanationPriority,
)


# ---------------------------------------------------------------------------
# 辅助构建函数
# ---------------------------------------------------------------------------


def _make_issue(issue_id: str, outcome_impact: OutcomeImpact) -> Issue:
    return Issue(
        issue_id=issue_id,
        case_id="CASE-001",
        title=f"争点 {issue_id}",
        issue_type=IssueType.factual,
        status=IssueStatus.open,
        outcome_impact=outcome_impact,
        related_claim_ids=[],
        evidence_ids=[],
    )


def _make_attack_node(node_id: str) -> AttackNode:
    return AttackNode(
        attack_node_id=node_id,
        target_issue_id="ISS-001",
        attack_description=f"攻击 {node_id}",
        supporting_evidence_ids=["EV-001"],
    )


def _make_attack_chain(chain_id: str, nodes: list[AttackNode]) -> OptimalAttackChain:
    return OptimalAttackChain(
        chain_id=chain_id,
        case_id="CASE-001",
        run_id="RUN-001",
        owner_party_id="PARTY-DEF",
        top_attacks=nodes,
        recommended_order=[n.attack_node_id for n in nodes],
    )


def _make_amount_report(
    report_id: str = "RPT-001",
    entries: list[ClaimCalculationEntry] | None = None,
) -> AmountCalculationReport:
    if entries is None:
        entries = [
            ClaimCalculationEntry(
                claim_id="CLM-001",
                claim_type=ClaimType.principal,
                claimed_amount=Decimal("100000"),
                calculated_amount=Decimal("100000"),
                delta=Decimal("0"),
            )
        ]
    return AmountCalculationReport(
        report_id=report_id,
        case_id="CASE-001",
        run_id="RUN-001",
        loan_transactions=[],
        repayment_transactions=[],
        claim_calculation_table=entries,
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


def _make_action_recommendation(
    rec_id: str = "REC-001",
    abandon_ids: list[str] | None = None,
    gap_ids: list[str] | None = None,
    amendment_ids: list[str] | None = None,
    trial_ids: list[str] | None = None,
) -> ActionRecommendation:
    claims_to_abandon = [
        ClaimAbandonSuggestion(
            suggestion_id=sid,
            claim_id="CLM-001",
            abandon_reason="证据不足",
            abandon_reason_issue_id="ISS-001",
        )
        for sid in (abandon_ids or [])
    ]
    amendments = [
        ClaimAmendmentSuggestion(
            suggestion_id=sid,
            original_claim_id="CLM-001",
            amendment_description="修改方向",
            amendment_reason_issue_id="ISS-001",
        )
        for sid in (amendment_ids or [])
    ]
    trial_explanations = [
        TrialExplanationPriority(
            priority_id=pid,
            issue_id="ISS-001",
            explanation_text="庭审解释",
        )
        for pid in (trial_ids or [])
    ]
    return ActionRecommendation(
        recommendation_id=rec_id,
        case_id="CASE-001",
        run_id="RUN-001",
        claims_to_abandon=claims_to_abandon,
        evidence_supplement_priorities=gap_ids or [],
        recommended_claim_amendments=amendments,
        trial_explanation_priorities=trial_explanations,
    )


def _make_gap_item(gap_id: str, roi_rank: int) -> EvidenceGapItem:
    return EvidenceGapItem(
        gap_id=gap_id,
        case_id="CASE-001",
        run_id="RUN-001",
        related_issue_id="ISS-001",
        gap_description="缺证说明",
        supplement_cost=SupplementCost.medium,
        outcome_impact_size=OutcomeImpactSize.significant,
        practically_obtainable=PracticallyObtainable.yes,
        roi_rank=roi_rank,
    )


def _make_full_input(**overrides) -> ExecutiveSummarizerInput:
    """构建包含所有依赖产物的完整输入。"""
    issues = [
        _make_issue("ISS-001", OutcomeImpact.high),
        _make_issue("ISS-002", OutcomeImpact.high),
        _make_issue("ISS-003", OutcomeImpact.medium),
        _make_issue("ISS-004", OutcomeImpact.medium),
        _make_issue("ISS-005", OutcomeImpact.low),
        _make_issue("ISS-006", OutcomeImpact.low),
    ]
    attack_chain = _make_attack_chain(
        "CHAIN-001",
        [_make_attack_node(f"ATK-00{i}") for i in range(1, 4)],
    )
    amount_report = _make_amount_report()
    action_rec = _make_action_recommendation(
        abandon_ids=["ABD-001"],
        gap_ids=["GAP-001", "GAP-002"],
        amendment_ids=["AMD-001"],
    )
    gap_items = [
        _make_gap_item("GAP-001", 1),
        _make_gap_item("GAP-002", 2),
        _make_gap_item("GAP-003", 3),
        _make_gap_item("GAP-004", 4),
    ]
    defaults = dict(
        case_id="CASE-001",
        run_id="RUN-001",
        issue_list=issues,
        adversary_attack_chain=attack_chain,
        amount_calculation_report=amount_report,
        action_recommendation=action_rec,
        evidence_gap_items=gap_items,
    )
    defaults.update(overrides)
    return ExecutiveSummarizerInput(**defaults)


# ---------------------------------------------------------------------------
# 基础运行测试（全依赖存在）
# ---------------------------------------------------------------------------


class TestExecutiveSummarizerBasic:
    def setup_method(self):
        self.summarizer = ExecutiveSummarizer()

    def test_returns_executive_summary_artifact(self):
        inp = _make_full_input()
        result = self.summarizer.summarize(inp)
        assert isinstance(result, ExecutiveSummaryArtifact)

    def test_result_case_id_matches_input(self):
        inp = _make_full_input()
        result = self.summarizer.summarize(inp)
        assert result.case_id == "CASE-001"

    def test_result_run_id_matches_input(self):
        inp = _make_full_input()
        result = self.summarizer.summarize(inp)
        assert result.run_id == "RUN-001"

    def test_summary_id_non_empty(self):
        inp = _make_full_input()
        result = self.summarizer.summarize(inp)
        assert result.summary_id != ""

    def test_created_at_set(self):
        inp = _make_full_input()
        result = self.summarizer.summarize(inp)
        assert result.created_at is not None

    def test_two_runs_produce_different_summary_ids(self):
        inp = _make_full_input()
        r1 = self.summarizer.summarize(inp)
        r2 = self.summarizer.summarize(inp)
        assert r1.summary_id != r2.summary_id


# ---------------------------------------------------------------------------
# top5_decisive_issues
# ---------------------------------------------------------------------------


class TestTop5DecisiveIssues:
    def setup_method(self):
        self.summarizer = ExecutiveSummarizer()

    def test_top5_contains_issue_ids(self):
        inp = _make_full_input()
        result = self.summarizer.summarize(inp)
        assert len(result.top5_decisive_issues) <= 5

    def test_high_impact_issues_come_first(self):
        """high impact 的争点必须排在 medium/low 之前。"""
        inp = _make_full_input()
        result = self.summarizer.summarize(inp)
        ids = result.top5_decisive_issues
        high_ids = {"ISS-001", "ISS-002"}
        for i, issue_id in enumerate(ids):
            if issue_id in high_ids:
                for prev in ids[:i]:
                    assert prev in high_ids, (
                        f"{prev} (non-high) appeared before high {issue_id}"
                    )

    def test_returns_exactly_five_when_six_available(self):
        inp = _make_full_input()
        result = self.summarizer.summarize(inp)
        assert len(result.top5_decisive_issues) == 5

    def test_returns_fewer_than_five_when_not_enough(self):
        inp = _make_full_input(issue_list=[_make_issue("ISS-001", OutcomeImpact.high)])
        result = self.summarizer.summarize(inp)
        assert result.top5_decisive_issues == ["ISS-001"]

    def test_empty_issue_list_returns_empty(self):
        inp = _make_full_input(issue_list=[])
        result = self.summarizer.summarize(inp)
        assert result.top5_decisive_issues == []

    def test_medium_before_low(self):
        """medium impact 的争点必须排在 low 之前。"""
        issues = [
            _make_issue("ISS-LOW", OutcomeImpact.low),
            _make_issue("ISS-MED", OutcomeImpact.medium),
        ]
        inp = _make_full_input(issue_list=issues)
        result = self.summarizer.summarize(inp)
        ids = result.top5_decisive_issues
        assert ids.index("ISS-MED") < ids.index("ISS-LOW")


# ---------------------------------------------------------------------------
# top3_immediate_actions
# ---------------------------------------------------------------------------


class TestTop3ImmediateActions:
    def setup_method(self):
        self.summarizer = ExecutiveSummarizer()

    def test_disabled_when_action_recommendation_none(self):
        inp = _make_full_input(action_recommendation=None)
        result = self.summarizer.summarize(inp)
        assert result.top3_immediate_actions == "未启用"
        assert result.action_recommendation_id is None

    def test_list_when_action_recommendation_present(self):
        inp = _make_full_input()
        result = self.summarizer.summarize(inp)
        assert isinstance(result.top3_immediate_actions, list)

    def test_at_most_three_actions(self):
        rec = _make_action_recommendation(
            abandon_ids=["ABD-001", "ABD-002"],
            gap_ids=["GAP-001", "GAP-002"],
            amendment_ids=["AMD-001"],
        )
        inp = _make_full_input(action_recommendation=rec)
        result = self.summarizer.summarize(inp)
        assert len(result.top3_immediate_actions) <= 3

    def test_action_recommendation_id_bound(self):
        rec = _make_action_recommendation(rec_id="REC-XYZ")
        inp = _make_full_input(action_recommendation=rec)
        result = self.summarizer.summarize(inp)
        assert result.action_recommendation_id == "REC-XYZ"

    def test_abandon_suggestions_have_highest_priority(self):
        """claims_to_abandon 的 suggestion_id 优先于其他条目出现在 top3。"""
        rec = _make_action_recommendation(
            abandon_ids=["ABD-001"],
            gap_ids=["GAP-001", "GAP-002"],
            amendment_ids=["AMD-001"],
        )
        inp = _make_full_input(action_recommendation=rec)
        result = self.summarizer.summarize(inp)
        actions = result.top3_immediate_actions
        assert isinstance(actions, list)
        assert "ABD-001" in actions
        assert actions.index("ABD-001") == 0

    def test_empty_action_recommendation_returns_empty_list_with_rec_id(self):
        rec = _make_action_recommendation(rec_id="REC-EMPTY")
        inp = _make_full_input(action_recommendation=rec)
        result = self.summarizer.summarize(inp)
        assert result.top3_immediate_actions == []
        assert result.action_recommendation_id == "REC-EMPTY"

    def test_gap_ids_appear_when_no_abandon_suggestions(self):
        rec = _make_action_recommendation(gap_ids=["GAP-A", "GAP-B", "GAP-C"])
        inp = _make_full_input(action_recommendation=rec)
        result = self.summarizer.summarize(inp)
        assert result.top3_immediate_actions == ["GAP-A", "GAP-B", "GAP-C"]


# ---------------------------------------------------------------------------
# top3_adversary_optimal_attacks
# ---------------------------------------------------------------------------


class TestTop3AdversaryAttacks:
    def setup_method(self):
        self.summarizer = ExecutiveSummarizer()

    def test_returns_attack_node_ids(self):
        inp = _make_full_input()
        result = self.summarizer.summarize(inp)
        assert result.top3_adversary_optimal_attacks == ["ATK-001", "ATK-002", "ATK-003"]

    def test_chain_id_bound(self):
        inp = _make_full_input()
        result = self.summarizer.summarize(inp)
        assert result.adversary_attack_chain_id == "CHAIN-001"

    def test_fewer_than_three_attacks_when_chain_has_fewer(self):
        chain = _make_attack_chain("CHAIN-X", [_make_attack_node("ATK-ONLY")])
        inp = _make_full_input(adversary_attack_chain=chain)
        result = self.summarizer.summarize(inp)
        assert result.top3_adversary_optimal_attacks == ["ATK-ONLY"]

    def test_empty_attack_chain_returns_empty_list(self):
        chain = _make_attack_chain("CHAIN-EMPTY", [])
        inp = _make_full_input(adversary_attack_chain=chain)
        result = self.summarizer.summarize(inp)
        assert result.top3_adversary_optimal_attacks == []


# ---------------------------------------------------------------------------
# current_most_stable_claim
# ---------------------------------------------------------------------------


class TestCurrentMostStableClaim:
    def setup_method(self):
        self.summarizer = ExecutiveSummarizer()

    def test_binds_amount_report_id(self):
        inp = _make_full_input()
        result = self.summarizer.summarize(inp)
        assert "RPT-001" in result.current_most_stable_claim
        assert result.amount_report_id == "RPT-001"

    def test_prefers_delta_zero_entry(self):
        entries = [
            ClaimCalculationEntry(
                claim_id="CLM-A",
                claim_type=ClaimType.principal,
                claimed_amount=Decimal("100000"),
                calculated_amount=Decimal("100000"),
                delta=Decimal("0"),
            ),
            ClaimCalculationEntry(
                claim_id="CLM-B",
                claim_type=ClaimType.interest,
                claimed_amount=Decimal("5000"),
                calculated_amount=Decimal("4000"),
                delta=Decimal("1000"),
            ),
        ]
        report = _make_amount_report(entries=entries)
        inp = _make_full_input(amount_calculation_report=report)
        result = self.summarizer.summarize(inp)
        assert "principal" in result.current_most_stable_claim

    def test_selects_smallest_delta_when_no_zero(self):
        entries = [
            ClaimCalculationEntry(
                claim_id="CLM-A",
                claim_type=ClaimType.interest,
                claimed_amount=Decimal("5000"),
                calculated_amount=Decimal("4500"),
                delta=Decimal("500"),
            ),
            ClaimCalculationEntry(
                claim_id="CLM-B",
                claim_type=ClaimType.principal,
                claimed_amount=Decimal("100000"),
                calculated_amount=Decimal("80000"),
                delta=Decimal("20000"),
            ),
        ]
        report = _make_amount_report(entries=entries)
        inp = _make_full_input(amount_calculation_report=report)
        result = self.summarizer.summarize(inp)
        assert "interest" in result.current_most_stable_claim

    def test_handles_non_calculable_entries(self):
        entries = [
            ClaimCalculationEntry(
                claim_id="CLM-A",
                claim_type=ClaimType.attorney_fee,
                claimed_amount=Decimal("10000"),
                calculated_amount=None,
                delta=None,
            ),
        ]
        report = _make_amount_report(entries=entries)
        inp = _make_full_input(amount_calculation_report=report)
        result = self.summarizer.summarize(inp)
        assert "attorney_fee" in result.current_most_stable_claim
        assert "RPT-001" in result.current_most_stable_claim

    def test_handles_empty_claim_table(self):
        report = _make_amount_report(entries=[])
        inp = _make_full_input(amount_calculation_report=report)
        result = self.summarizer.summarize(inp)
        assert "RPT-001" in result.current_most_stable_claim


# ---------------------------------------------------------------------------
# strategic_summary
# ---------------------------------------------------------------------------


class TestStrategicSummary:
    def setup_method(self):
        self.summarizer = ExecutiveSummarizer()

    def test_none_when_no_strategic_headline(self):
        """无 strategic_headline 时 strategic_summary 为 None。"""
        rec = _make_action_recommendation(abandon_ids=["AB-001"])
        inp = _make_full_input(action_recommendation=rec)
        result = self.summarizer.summarize(inp)
        assert result.strategic_summary is None

    def test_none_when_no_action_recommendation(self):
        """无 ActionRecommendation 时 strategic_summary 为 None。"""
        inp = _make_full_input(action_recommendation=None)
        result = self.summarizer.summarize(inp)
        assert result.strategic_summary is None

    def test_contains_headline_when_present(self):
        """有 strategic_headline 时 strategic_summary 包含策略内容。"""
        rec = _make_action_recommendation(abandon_ids=["AB-001"])
        rec.strategic_headline = "聚焦借款人主体适格性，弱化金额争议"
        rec.case_dispute_category = "borrower_identity"
        inp = _make_full_input(action_recommendation=rec)
        result = self.summarizer.summarize(inp)
        assert result.strategic_summary is not None
        assert "核心策略" in result.strategic_summary
        assert "borrower_identity" in result.strategic_summary
        assert "聚焦借款人主体适格性" in result.strategic_summary

    def test_claim_stays_amount_centric_with_strategic_headline(self):
        """有 strategic_headline 时 current_most_stable_claim 仍输出金额语义。"""
        rec = _make_action_recommendation(abandon_ids=["AB-001"])
        rec.strategic_headline = "聚焦借款人主体适格性"
        rec.case_dispute_category = "borrower_identity"
        inp = _make_full_input(action_recommendation=rec)
        result = self.summarizer.summarize(inp)
        # current_most_stable_claim 应该是金额相关的，不包含"核心策略"
        assert "核心策略" not in result.current_most_stable_claim
        assert "principal" in result.current_most_stable_claim or "RPT-001" in result.current_most_stable_claim


# ---------------------------------------------------------------------------
# critical_evidence_gaps
# ---------------------------------------------------------------------------


class TestCriticalEvidenceGaps:
    def setup_method(self):
        self.summarizer = ExecutiveSummarizer()

    def test_disabled_when_gap_items_none(self):
        inp = _make_full_input(evidence_gap_items=None)
        result = self.summarizer.summarize(inp)
        assert result.critical_evidence_gaps == "未启用"

    def test_returns_top3_gap_ids_by_roi_rank(self):
        gaps = [
            _make_gap_item("GAP-A", 3),
            _make_gap_item("GAP-B", 1),
            _make_gap_item("GAP-C", 2),
            _make_gap_item("GAP-D", 4),
        ]
        inp = _make_full_input(evidence_gap_items=gaps)
        result = self.summarizer.summarize(inp)
        assert result.critical_evidence_gaps == ["GAP-B", "GAP-C", "GAP-A"]

    def test_returns_all_when_fewer_than_three(self):
        gaps = [_make_gap_item("GAP-X", 1), _make_gap_item("GAP-Y", 2)]
        inp = _make_full_input(evidence_gap_items=gaps)
        result = self.summarizer.summarize(inp)
        assert result.critical_evidence_gaps == ["GAP-X", "GAP-Y"]

    def test_empty_gap_list_returns_empty_list(self):
        inp = _make_full_input(evidence_gap_items=[])
        result = self.summarizer.summarize(inp)
        assert result.critical_evidence_gaps == []
