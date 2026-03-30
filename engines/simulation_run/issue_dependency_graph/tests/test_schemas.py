"""
issue_dependency_graph schemas 单元测试。
Unit tests for issue_dependency_graph schemas.

测试策略：
- Pydantic 模型的 validation 行为
- 默认值、边界值、非法值
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from engines.simulation_run.issue_dependency_graph.schemas import (
    IssueDependencyEdge,
    IssueDependencyGraph,
    IssueDependencyGraphInput,
    IssueDependencyNode,
)


# ---------------------------------------------------------------------------
# IssueDependencyNode 验证
# ---------------------------------------------------------------------------


class TestIssueDependencyNode:
    """节点模型验证。"""

    def test_valid_node(self):
        node = IssueDependencyNode(issue_id="ISS-001", depends_on=["ISS-002"])
        assert node.issue_id == "ISS-001"

    def test_empty_issue_id_rejected(self):
        with pytest.raises(ValidationError):
            IssueDependencyNode(issue_id="")

    def test_default_depends_on(self):
        node = IssueDependencyNode(issue_id="ISS-001")
        assert node.depends_on == []


# ---------------------------------------------------------------------------
# IssueDependencyEdge 验证
# ---------------------------------------------------------------------------


class TestIssueDependencyEdge:
    """边模型验证。"""

    def test_valid_edge(self):
        edge = IssueDependencyEdge(from_issue_id="A", to_issue_id="B")
        assert edge.from_issue_id == "A"
        assert edge.to_issue_id == "B"

    def test_empty_from_rejected(self):
        with pytest.raises(ValidationError):
            IssueDependencyEdge(from_issue_id="", to_issue_id="B")

    def test_empty_to_rejected(self):
        with pytest.raises(ValidationError):
            IssueDependencyEdge(from_issue_id="A", to_issue_id="")


# ---------------------------------------------------------------------------
# IssueDependencyGraphInput 验证
# ---------------------------------------------------------------------------


class TestIssueDependencyGraphInput:
    """输入 wrapper 验证。"""

    def test_empty_case_id_rejected(self):
        with pytest.raises(ValidationError):
            IssueDependencyGraphInput(case_id="", issues=[])

    def test_default_issues(self):
        inp = IssueDependencyGraphInput(case_id="CASE-001")
        assert inp.issues == []

    def test_valid_input(self):
        inp = IssueDependencyGraphInput(case_id="CASE-001", issues=[])
        assert inp.case_id == "CASE-001"


# ---------------------------------------------------------------------------
# IssueDependencyGraph 验证
# ---------------------------------------------------------------------------


class TestIssueDependencyGraph:
    """图产物模型验证。"""

    def test_valid_graph(self):
        graph = IssueDependencyGraph(
            graph_id="G-001",
            case_id="CASE-001",
            nodes=[],
            edges=[],
            topological_order=[],
            created_at="2026-01-01T00:00:00Z",
        )
        assert graph.graph_id == "G-001"
        assert graph.has_cycles is False
        assert graph.cycles == []

    def test_empty_graph_id_rejected(self):
        with pytest.raises(ValidationError):
            IssueDependencyGraph(
                graph_id="",
                case_id="CASE-001",
                nodes=[],
                edges=[],
                topological_order=[],
                created_at="2026-01-01T00:00:00Z",
            )

    def test_has_cycles_default_false(self):
        graph = IssueDependencyGraph(
            graph_id="G-001",
            case_id="CASE-001",
            nodes=[],
            edges=[],
            topological_order=[],
            created_at="2026-01-01T00:00:00Z",
        )
        assert graph.has_cycles is False

    def test_metadata_default_empty(self):
        graph = IssueDependencyGraph(
            graph_id="G-001",
            case_id="CASE-001",
            nodes=[],
            edges=[],
            topological_order=[],
            created_at="2026-01-01T00:00:00Z",
        )
        assert graph.metadata == {}
