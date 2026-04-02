from engines.shared.consistency_checker import ConsistencyChecker
from engines.shared.models import ActionRecommendation, DecisionPath, DecisionPathTree


def test_recommendation_failure_message_is_probability_free() -> None:
    checker = ConsistencyChecker()
    decision_tree = DecisionPathTree(
        tree_id="tree-001",
        case_id="case-001",
        run_id="run-001",
        paths=[
            DecisionPath(
                path_id="path-defendant",
                trigger_condition="The defendant proves repayment",
                trigger_issue_ids=["ISS-001"],
                possible_outcome="Court rejects the claim",
                probability=0.81,
                probability_rationale="legacy only",
                party_favored="defendant",
            )
        ],
        blocking_conditions=[],
        most_likely_path="path-defendant",
    )
    recommendation = ActionRecommendation(
        recommendation_id="rec-001",
        case_id="case-001",
        run_id="run-001",
        strategic_headline="Push for full recovery immediately",
    )

    result = checker.check(decision_tree=decision_tree, recommendation=recommendation)

    assert result.recommendation_consistent is False
    assert result.failures
    assert "prob=" not in result.failures[0]
    assert "%" not in result.failures[0]
    assert "path=path-defendant" in result.failures[0]
