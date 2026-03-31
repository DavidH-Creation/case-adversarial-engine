"""
集成测试 — 模块间数据流断点修复验证 (Unit 7)。
Integration tests — inter-module data flow breakpoint fixes.

覆盖路径 / Coverage:
1. test_derive_evidence_gaps_from_conference     — pretrial focus items → evidence gap items
2. test_derive_evidence_gaps_skips_resolved      — resolved focus items are excluded
3. test_derive_evidence_gaps_no_conference       — conference_result=None → empty list
4. test_action_recommender_receives_evidence_gaps — evidence gaps flow to ActionRecommenderInput
5. test_action_recommender_receives_decision_tree — decision tree flows to ActionRecommenderInput
6. test_exec_summarizer_receives_defense_chain   — defense chain flows to ExecutiveSummarizerInput
7. test_exec_summarizer_receives_decision_tree   — decision tree flows to ExecutiveSummarizerInput
8. test_exec_summarizer_receives_evidence_gaps   — evidence gaps flow to ExecutiveSummarizerInput
9. test_exec_summary_artifact_has_defense_chain_id — defense_chain_id in output artifact
10. test_exec_summary_risk_includes_defense_info  — risk assessment includes defense chain info
11. test_run_post_debate_signature_accepts_conference — function signature accepts conference_result
12. test_empty_conference_focus_list_safe          — empty focus list → empty gaps, no crash
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from engines.pretrial_conference.schemas import (
    CrossExaminationDimension,
    CrossExaminationFocusItem,
    CrossExaminationResult,
    JudgeQuestionSet,
    PretrialConferenceResult,
)
from engines.report_generation.executive_summarizer import ExecutiveSummarizer
from engines.report_generation.executive_summarizer.schemas import ExecutiveSummarizerInput
from engines.shared.models import (
    AmountCalculationReport,
    AmountConsistencyCheck,
    ClaimCalculationEntry,
    ClaimType,
    DecisionPath,
    DecisionPathTree,
    EvidenceGapItem,
    EvidenceIndex,
    Issue,
    IssueType,
    OptimalAttackChain,
    OutcomeImpact,
)
from engines.simulation_run.action_recommender.schemas import ActionRecommenderInput
from engines.simulation_run.defense_chain.models import (
    DefensePoint,
    PlaintiffDefenseChain,
)
from engines.simulation_run.defense_chain.schemas import DefenseChainResult

from .conftest import CASE_ID

# ---------------------------------------------------------------------------
# Shared test constants
# ---------------------------------------------------------------------------

RUN_ID = "run-dataflow-001"
P_ID = "party-plaintiff-001"
D_ID = "party-defendant-001"


# ---------------------------------------------------------------------------
# Shared test builders
# ---------------------------------------------------------------------------


def _make_issue(issue_id: str, title: str = "Test issue") -> Issue:
    return Issue(
        issue_id=issue_id,
        case_id=CASE_ID,
        title=title,
        issue_type=IssueType.factual,
        evidence_ids=["ev-001"],
        outcome_impact=OutcomeImpact.high,
        composite_score=80.0,
    )


def _make_amount_report() -> AmountCalculationReport:
    return AmountCalculationReport(
        report_id="rpt-001",
        case_id=CASE_ID,
        run_id=RUN_ID,
        loan_transactions=[],
        repayment_transactions=[],
        claim_calculation_table=[
            ClaimCalculationEntry(
                claim_id="claim-001",
                claim_type=ClaimType.principal,
                claimed_amount=Decimal("500000"),
                calculated_amount=Decimal("500000"),
                delta=Decimal("0"),
            ),
        ],
        consistency_check_result=AmountConsistencyCheck(
            principal_base_unique=True,
            all_repayments_attributed=True,
            text_table_amount_consistent=True,
            duplicate_interest_penalty_claim=False,
            claim_total_reconstructable=True,
            verdict_block_active=False,
            unresolved_conflicts=[],
        ),
    )


def _make_attack_chain() -> OptimalAttackChain:
    return OptimalAttackChain(
        chain_id="ac-001",
        case_id=CASE_ID,
        run_id=RUN_ID,
        owner_party_id=D_ID,
        top_attacks=[],
    )


def _make_decision_tree() -> DecisionPathTree:
    return DecisionPathTree(
        tree_id="dt-001",
        case_id=CASE_ID,
        run_id=RUN_ID,
        paths=[
            DecisionPath(
                path_id="path-001",
                trigger_condition="Loan agreement proven",
                possible_outcome="Plaintiff wins principal claim",
                probability=0.7,
                party_favored="plaintiff",
                key_evidence_ids=["ev-001"],
            ),
        ],
        most_likely_path="path-001",
    )


def _make_defense_chain_result() -> DefenseChainResult:
    chain = PlaintiffDefenseChain(
        chain_id="dc-001",
        case_id=CASE_ID,
        target_issues=["issue-001"],
        defense_points=[
            DefensePoint(
                point_id="dp-001",
                issue_id="issue-001",
                defense_strategy="Challenge loan agreement authenticity",
                supporting_argument="Transfer records show inconsistency",
                evidence_ids=["ev-001"],
                priority=1,
            ),
        ],
        evidence_support=["ev-001"],
        confidence_score=0.75,
    )
    return DefenseChainResult(
        chain=chain,
        unevaluated_issue_ids=[],
        metadata={"model": "test"},
    )


def _make_conference_result(
    *,
    focus_items: list[CrossExaminationFocusItem] | None = None,
) -> PretrialConferenceResult:
    """Build a minimal PretrialConferenceResult with optional focus items."""
    if focus_items is None:
        focus_items = [
            CrossExaminationFocusItem(
                evidence_id="ev-001",
                issue_id="issue-001",
                dimension=CrossExaminationDimension.authenticity,
                dispute_summary="Transfer date does not match promissory note",
                is_resolved=False,
            ),
            CrossExaminationFocusItem(
                evidence_id="ev-002",
                issue_id="issue-002",
                dimension=CrossExaminationDimension.relevance,
                dispute_summary="Evidence relevance already confirmed",
                is_resolved=True,
            ),
        ]
    return PretrialConferenceResult(
        case_id=CASE_ID,
        run_id=RUN_ID,
        cross_examination_result=CrossExaminationResult(
            case_id=CASE_ID,
            run_id=RUN_ID,
            records=[],
            focus_list=focus_items,
        ),
        judge_questions=JudgeQuestionSet(
            case_id=CASE_ID,
            run_id=RUN_ID,
            questions=[],
        ),
        final_evidence_index=EvidenceIndex(case_id=CASE_ID, evidence=[]),
    )


# ---------------------------------------------------------------------------
# Import the helper under test from run_case.py
# ---------------------------------------------------------------------------

# We import _derive_evidence_gaps directly to unit-test the derivation logic.
# The function is module-private but testing it directly is more robust than
# running the full async pipeline with many LLM mocks.
import importlib
import sys

_PROJECT_ROOT_STR = str(__import__("pathlib").Path(__file__).parent.parent.parent)
if _PROJECT_ROOT_STR not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_STR)

# Import the private helper via the module
_run_case_mod = importlib.import_module("scripts.run_case")
_derive_evidence_gaps = _run_case_mod._derive_evidence_gaps


# ---------------------------------------------------------------------------
# Tests: _derive_evidence_gaps
# ---------------------------------------------------------------------------


class TestDeriveEvidenceGaps:
    """Test evidence gap derivation from pretrial cross-examination results."""

    def test_derive_evidence_gaps_from_conference(self):
        """Unresolved focus items become evidence gap items."""
        conference = _make_conference_result()
        gaps = _derive_evidence_gaps(conference, CASE_ID, RUN_ID)

        assert len(gaps) == 1  # Only the unresolved item
        gap = gaps[0]
        assert isinstance(gap, EvidenceGapItem)
        assert gap.gap_id == "xexam-ev-001-issue-001"
        assert gap.case_id == CASE_ID
        assert gap.run_id == RUN_ID
        assert gap.related_issue_id == "issue-001"
        assert "质证争议" in gap.gap_description
        assert gap.roi_rank == 1

    def test_derive_evidence_gaps_skips_resolved(self):
        """Resolved focus items are excluded from evidence gaps."""
        conference = _make_conference_result(
            focus_items=[
                CrossExaminationFocusItem(
                    evidence_id="ev-resolved",
                    issue_id="issue-001",
                    dimension=CrossExaminationDimension.authenticity,
                    dispute_summary="Already resolved",
                    is_resolved=True,
                ),
            ]
        )
        gaps = _derive_evidence_gaps(conference, CASE_ID, RUN_ID)
        assert gaps == []

    def test_derive_evidence_gaps_no_conference(self):
        """No conference result → empty gap list."""
        gaps = _derive_evidence_gaps(None, CASE_ID, RUN_ID)
        assert gaps == []

    def test_empty_conference_focus_list_safe(self):
        """Empty focus list → empty gaps, no crash."""
        conference = _make_conference_result(focus_items=[])
        gaps = _derive_evidence_gaps(conference, CASE_ID, RUN_ID)
        assert gaps == []


# ---------------------------------------------------------------------------
# Tests: ActionRecommenderInput data flow
# ---------------------------------------------------------------------------


class TestActionRecommenderDataFlow:
    """Verify evidence gaps and decision tree flow to ActionRecommenderInput."""

    def test_action_recommender_receives_evidence_gaps(self):
        """ActionRecommenderInput accepts non-empty evidence_gap_list."""
        conference = _make_conference_result()
        gaps = _derive_evidence_gaps(conference, CASE_ID, RUN_ID)

        inp = ActionRecommenderInput(
            case_id=CASE_ID,
            run_id=RUN_ID,
            issue_list=[_make_issue("issue-001")],
            evidence_gap_list=gaps,
            amount_calculation_report=_make_amount_report(),
            proponent_party_id=P_ID,
        )
        assert len(inp.evidence_gap_list) == 1
        assert inp.evidence_gap_list[0].gap_id == "xexam-ev-001-issue-001"

    def test_action_recommender_receives_decision_tree(self):
        """ActionRecommenderInput accepts decision_path_tree."""
        tree = _make_decision_tree()
        inp = ActionRecommenderInput(
            case_id=CASE_ID,
            run_id=RUN_ID,
            issue_list=[_make_issue("issue-001")],
            evidence_gap_list=[],
            amount_calculation_report=_make_amount_report(),
            proponent_party_id=P_ID,
            decision_path_tree=tree,
        )
        assert inp.decision_path_tree is not None
        assert inp.decision_path_tree.tree_id == "dt-001"


# ---------------------------------------------------------------------------
# Tests: ExecutiveSummarizer data flow
# ---------------------------------------------------------------------------


class TestExecutiveSummarizerDataFlow:
    """Verify defense chain, decision tree, and evidence gaps flow to ExecutiveSummarizer."""

    def _make_summarizer_input(
        self,
        *,
        defense_chain: DefenseChainResult | None = None,
        decision_tree: DecisionPathTree | None = None,
        evidence_gaps: list[EvidenceGapItem] | None = None,
    ) -> ExecutiveSummarizerInput:
        return ExecutiveSummarizerInput(
            case_id=CASE_ID,
            run_id=RUN_ID,
            issue_list=[_make_issue("issue-001")],
            adversary_attack_chain=_make_attack_chain(),
            amount_calculation_report=_make_amount_report(),
            defense_chain_result=defense_chain,
            decision_path_tree=decision_tree,
            evidence_gap_items=evidence_gaps,
        )

    def test_exec_summarizer_receives_defense_chain(self):
        """ExecutiveSummarizerInput accepts defense_chain_result."""
        dc = _make_defense_chain_result()
        inp = self._make_summarizer_input(defense_chain=dc)
        assert inp.defense_chain_result is not None
        assert inp.defense_chain_result.chain.chain_id == "dc-001"

    def test_exec_summarizer_receives_decision_tree(self):
        """ExecutiveSummarizerInput accepts decision_path_tree."""
        tree = _make_decision_tree()
        inp = self._make_summarizer_input(decision_tree=tree)
        assert inp.decision_path_tree is not None
        assert inp.decision_path_tree.tree_id == "dt-001"

    def test_exec_summarizer_receives_evidence_gaps(self):
        """ExecutiveSummarizerInput accepts evidence_gap_items from conference."""
        conference = _make_conference_result()
        gaps = _derive_evidence_gaps(conference, CASE_ID, RUN_ID)
        inp = self._make_summarizer_input(evidence_gaps=gaps)
        assert inp.evidence_gap_items is not None
        assert len(inp.evidence_gap_items) == 1

    def test_exec_summary_artifact_has_defense_chain_id(self):
        """ExecutiveSummaryArtifact includes defense_chain_id when defense chain provided."""
        dc = _make_defense_chain_result()
        inp = self._make_summarizer_input(defense_chain=dc)
        artifact = ExecutiveSummarizer().summarize(inp)
        assert artifact.defense_chain_id == "dc-001"

    def test_exec_summary_artifact_no_defense_chain(self):
        """defense_chain_id is None when no defense chain provided."""
        inp = self._make_summarizer_input(defense_chain=None)
        artifact = ExecutiveSummarizer().summarize(inp)
        assert artifact.defense_chain_id is None

    def test_exec_summary_risk_includes_defense_info(self):
        """Risk assessment text includes defense chain info when available."""
        dc = _make_defense_chain_result()
        inp = self._make_summarizer_input(defense_chain=dc)
        artifact = ExecutiveSummarizer().summarize(inp)
        risk = artifact.structured_output.risk_assessment
        assert "防御论点" in risk
        assert "75%" in risk  # confidence_score = 0.75

    def test_exec_summary_risk_no_defense_info(self):
        """Risk assessment does not mention defense when chain is None."""
        inp = self._make_summarizer_input(defense_chain=None)
        artifact = ExecutiveSummarizer().summarize(inp)
        risk = artifact.structured_output.risk_assessment
        assert "防御论点" not in risk


# ---------------------------------------------------------------------------
# Tests: Pipeline wiring (_run_post_debate signature)
# ---------------------------------------------------------------------------


class TestPipelineWiring:
    """Verify _run_post_debate accepts conference_result parameter."""

    def test_run_post_debate_signature_accepts_conference(self):
        """_run_post_debate has conference_result parameter."""
        import inspect

        sig = inspect.signature(_run_case_mod._run_post_debate)
        params = list(sig.parameters.keys())
        assert "conference_result" in params

    def test_run_post_debate_conference_default_is_none(self):
        """conference_result defaults to None for backward compatibility."""
        import inspect

        sig = inspect.signature(_run_case_mod._run_post_debate)
        param = sig.parameters["conference_result"]
        assert param.default is None

    def test_no_hardcoded_evidence_gap_list(self):
        """Verify evidence_gap_list=[] is no longer hardcoded in run_case.py source."""
        import inspect

        source = inspect.getsource(_run_case_mod._run_post_debate)
        assert "evidence_gap_list=[]" not in source
        assert "evidence_gap_list=evidence_gaps" in source

    def test_no_hardcoded_evidence_gap_items_none(self):
        """Verify evidence_gap_items=None is no longer hardcoded in run_case.py source."""
        import inspect

        source = inspect.getsource(_run_case_mod._run_post_debate)
        # Should use evidence_gaps or None, not hardcoded None
        assert "evidence_gap_items=evidence_gaps" in source
