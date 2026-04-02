from engines.shared.display_resolver import resolve_path
from engines.shared.models import DecisionPath, DecisionPathTree


def test_resolve_path_omits_probability_suffix() -> None:
    tree = DecisionPathTree(
        tree_id="tree-001",
        case_id="case-001",
        run_id="run-001",
        paths=[
            DecisionPath(
                path_id="path-001",
                trigger_condition="Trigger",
                trigger_issue_ids=["ISS-001"],
                key_evidence_ids=["EV-001"],
                possible_outcome="Court supports the claim",
                probability=0.72,
                probability_rationale="legacy only",
            )
        ],
        blocking_conditions=[],
    )

    assert resolve_path("path-001", tree) == "Court supports the claim"
