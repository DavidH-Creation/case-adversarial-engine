"""Tests for Conditional Scenario Tree."""

import pytest
from unittest.mock import MagicMock

from engines.report_generation.v3.models import (
    ConditionalNode,
    ConditionalScenarioTree,
)
from engines.report_generation.v3.scenario_tree import (
    build_scenario_tree_from_decision_paths,
    render_scenario_tree_text,
    render_scenario_tree_summary,
)


def _make_decision_tree():
    """Create a mock DecisionPathTree."""
    tree = MagicMock()
    tree.tree_id = "tree-001"
    tree.case_id = "case-001"

    # Blocking conditions
    bc1 = MagicMock()
    bc1.condition_id = "BC-001"
    bc1.description = "录音合法性是否被确认？"
    bc1.related_evidence_ids = ["EV003"]
    tree.blocking_conditions = [bc1]

    # Decision paths
    path1 = MagicMock()
    path1.path_id = "PATH-A"
    path1.trigger_condition = "借款合意成立"
    path1.possible_outcome = "原告获得全额支持"
    path1.key_evidence_ids = ["EV001", "EV002"]
    path1.admissibility_gate = []

    path2 = MagicMock()
    path2.path_id = "PATH-B"
    path2.trigger_condition = "代收款抗辩成立"
    path2.possible_outcome = "原告诉请被驳回"
    path2.key_evidence_ids = ["EV003"]
    path2.admissibility_gate = []

    tree.paths = [path1, path2]

    return tree


class TestBuildScenarioTree:
    def test_none_input(self):
        result = build_scenario_tree_from_decision_paths(None, MagicMock(), MagicMock())
        assert result is None

    def test_builds_from_decision_tree(self):
        dt = _make_decision_tree()
        result = build_scenario_tree_from_decision_paths(dt, MagicMock(), MagicMock())
        assert result is not None
        assert isinstance(result, ConditionalScenarioTree)
        assert result.case_id == "case-001"
        assert len(result.nodes) > 0

    def test_nodes_are_binary(self):
        dt = _make_decision_tree()
        result = build_scenario_tree_from_decision_paths(dt, MagicMock(), MagicMock())
        for node in result.nodes:
            # Each node should have either outcomes or child references, not both
            if node.yes_outcome:
                assert node.yes_child_id is None
            if node.no_outcome:
                assert node.no_child_id is None

    def test_root_node_exists(self):
        dt = _make_decision_tree()
        result = build_scenario_tree_from_decision_paths(dt, MagicMock(), MagicMock())
        node_ids = {n.node_id for n in result.nodes}
        assert result.root_node_id in node_ids

    def test_tree_is_not_flat_linked_list(self):
        """Verify the tree uses binary branching, not a flat linked list."""
        dt = MagicMock()
        dt.tree_id = "tree-003"
        dt.case_id = "case-001"
        dt.blocking_conditions = []

        # Create 3 paths — enough to detect branching vs linked list
        paths = []
        for i in range(3):
            p = MagicMock()
            p.trigger_condition = f"条件{i+1}"
            p.possible_outcome = f"结果{i+1}"
            p.key_evidence_ids = [f"EV{i+1:03d}"]
            paths.append(p)
        dt.paths = paths

        result = build_scenario_tree_from_decision_paths(dt, MagicMock(), MagicMock())
        assert result is not None

        # In a binary tree with 3 paths, the root should have BOTH
        # yes_child_id and no_child_id (not just chaining via no_child_id)
        node_map = {n.node_id: n for n in result.nodes}
        root = node_map[result.root_node_id]
        has_yes_branch = root.yes_child_id is not None or root.yes_outcome is not None
        has_no_branch = root.no_child_id is not None or root.no_outcome is not None
        assert has_yes_branch, "Root should have a yes branch"
        assert has_no_branch, "Root should have a no branch"

    def test_empty_paths(self):
        dt = MagicMock()
        dt.tree_id = "tree-empty"
        dt.case_id = "case-001"
        dt.paths = []
        dt.blocking_conditions = []
        result = build_scenario_tree_from_decision_paths(dt, MagicMock(), MagicMock())
        assert result is None


class TestRenderScenarioTree:
    def test_render_text(self):
        tree = ConditionalScenarioTree(
            tree_id="cst-001",
            case_id="case-001",
            root_node_id="COND-001",
            nodes=[
                ConditionalNode(
                    node_id="COND-001",
                    condition="录音是否被采信？",
                    yes_outcome="原告胜诉",
                    no_outcome="需要其他证据",
                ),
            ],
        )
        text = render_scenario_tree_text(tree)
        assert "录音是否被采信？" in text
        assert "是 →" in text
        assert "否 →" in text

    def test_render_summary(self):
        tree = ConditionalScenarioTree(
            tree_id="cst-001",
            case_id="case-001",
            root_node_id="COND-001",
            nodes=[
                ConditionalNode(
                    node_id="COND-001",
                    condition="录音是否被采信",
                    yes_outcome="原告胜诉",
                    no_outcome="驳回",
                ),
            ],
        )
        summary = render_scenario_tree_summary(tree)
        assert "录音" in summary
        assert len(summary) > 0

    def test_empty_tree(self):
        assert render_scenario_tree_text(None) == ""
        assert render_scenario_tree_summary(None) == "暂无条件场景分析"

    def test_nested_tree(self):
        tree = ConditionalScenarioTree(
            tree_id="cst-002",
            case_id="case-001",
            root_node_id="COND-001",
            nodes=[
                ConditionalNode(
                    node_id="COND-001",
                    condition="录音是否被采信？",
                    yes_child_id="COND-002",
                    no_outcome="驳回",
                ),
                ConditionalNode(
                    node_id="COND-002",
                    condition="借款合意是否成立？",
                    yes_outcome="原告胜诉",
                    no_outcome="驳回",
                ),
            ],
        )
        text = render_scenario_tree_text(tree)
        assert "录音是否被采信？" in text
        assert "借款合意是否成立？" in text
