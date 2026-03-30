"""
IssueDependencyGraphGenerator 单元测试。
Unit tests for IssueDependencyGraphGenerator.

测试策略：
- 纯规则层，无 LLM 依赖
- 覆盖：空输入、无依赖、线性链、DAG、环路检测、非法引用过滤、元信息
"""
from __future__ import annotations

import pytest

from engines.shared.models import Issue, IssueStatus, IssueType
from engines.simulation_run.issue_dependency_graph.generator import (
    IssueDependencyGraphGenerator,
)
from engines.simulation_run.issue_dependency_graph.schemas import (
    IssueDependencyGraph,
    IssueDependencyGraphInput,
)


# ---------------------------------------------------------------------------
# 辅助工厂
# ---------------------------------------------------------------------------


def _make_issue(issue_id: str, depends_on: list[str] | None = None) -> Issue:
    """创建测试用 Issue（通过 model_copy 注入 depends_on 字段）。"""
    issue = Issue(
        issue_id=issue_id,
        case_id="CASE-IDG-001",
        title=f"争点 {issue_id}",
        issue_type=IssueType.factual,
        status=IssueStatus.open,
    )
    if depends_on is not None:
        issue = issue.model_copy(update={"depends_on": depends_on})
    return issue


def _build(issues: list[Issue]) -> IssueDependencyGraph:
    gen = IssueDependencyGraphGenerator()
    return gen.build(IssueDependencyGraphInput(case_id="CASE-IDG-001", issues=issues))


# ---------------------------------------------------------------------------
# 空输入测试
# ---------------------------------------------------------------------------


class TestEmptyInput:
    """空争点列表返回空图。"""

    def test_empty_nodes(self):
        graph = _build([])
        assert graph.nodes == []

    def test_empty_edges(self):
        graph = _build([])
        assert graph.edges == []

    def test_empty_topo_order(self):
        graph = _build([])
        assert graph.topological_order == []

    def test_no_cycles(self):
        graph = _build([])
        assert graph.cycles == []
        assert not graph.has_cycles


# ---------------------------------------------------------------------------
# 无依赖测试
# ---------------------------------------------------------------------------


class TestNoDependencies:
    """无依赖关系的争点。"""

    def test_single_issue_in_topo_order(self):
        graph = _build([_make_issue("A")])
        assert graph.topological_order == ["A"]

    def test_multiple_issues_all_in_topo_order(self):
        issues = [_make_issue("A"), _make_issue("B"), _make_issue("C")]
        graph = _build(issues)
        assert set(graph.topological_order) == {"A", "B", "C"}

    def test_no_edges_created(self):
        issues = [_make_issue("A"), _make_issue("B")]
        graph = _build(issues)
        assert graph.edges == []

    def test_nodes_created_correctly(self):
        graph = _build([_make_issue("X")])
        assert len(graph.nodes) == 1
        assert graph.nodes[0].issue_id == "X"
        assert graph.nodes[0].depends_on == []


# ---------------------------------------------------------------------------
# 线性链测试
# ---------------------------------------------------------------------------


class TestLinearChain:
    """线性依赖链的拓扑排序。"""

    def test_a_depends_b_depends_c(self):
        """A → B → C: 拓扑顺序 C 在 B 前，B 在 A 前。"""
        issues = [
            _make_issue("A", depends_on=["B"]),
            _make_issue("B", depends_on=["C"]),
            _make_issue("C", depends_on=[]),
        ]
        graph = _build(issues)
        topo = graph.topological_order
        assert topo.index("C") < topo.index("B") < topo.index("A")
        assert not graph.has_cycles


# ---------------------------------------------------------------------------
# DAG 测试
# ---------------------------------------------------------------------------


class TestDAG:
    """有向无环图（DAG）的拓扑排序。"""

    def test_diamond_dag(self):
        """菱形: D depends_on B,C; B,C depends_on A。"""
        issues = [
            _make_issue("A", depends_on=[]),
            _make_issue("B", depends_on=["A"]),
            _make_issue("C", depends_on=["A"]),
            _make_issue("D", depends_on=["B", "C"]),
        ]
        graph = _build(issues)
        topo = graph.topological_order
        assert topo.index("A") < topo.index("B")
        assert topo.index("A") < topo.index("C")
        assert topo.index("B") < topo.index("D")
        assert topo.index("C") < topo.index("D")

    def test_all_nodes_in_topo_order(self):
        issues = [
            _make_issue("A", depends_on=[]),
            _make_issue("B", depends_on=["A"]),
            _make_issue("C", depends_on=["A"]),
            _make_issue("D", depends_on=["B", "C"]),
        ]
        graph = _build(issues)
        assert set(graph.topological_order) == {"A", "B", "C", "D"}


# ---------------------------------------------------------------------------
# 边方向测试
# ---------------------------------------------------------------------------


class TestEdgeDirection:
    """边的 from/to 方向正确。"""

    def test_from_is_dependent_to_is_dependency(self):
        """X depends_on Y → edge(from=X, to=Y)"""
        issues = [
            _make_issue("X", depends_on=["Y"]),
            _make_issue("Y", depends_on=[]),
        ]
        graph = _build(issues)
        assert len(graph.edges) == 1
        assert graph.edges[0].from_issue_id == "X"
        assert graph.edges[0].to_issue_id == "Y"

    def test_multiple_deps_create_multiple_edges(self):
        issues = [
            _make_issue("D", depends_on=["A", "B"]),
            _make_issue("A", depends_on=[]),
            _make_issue("B", depends_on=[]),
        ]
        graph = _build(issues)
        assert len(graph.edges) == 2
        froms = {e.from_issue_id for e in graph.edges}
        tos = {e.to_issue_id for e in graph.edges}
        assert froms == {"D"}
        assert tos == {"A", "B"}


# ---------------------------------------------------------------------------
# 环路检测测试
# ---------------------------------------------------------------------------


class TestCycleDetection:
    """环路检测和处理。"""

    def test_simple_cycle_ab(self):
        """A ↔ B 互相依赖。"""
        issues = [
            _make_issue("A", depends_on=["B"]),
            _make_issue("B", depends_on=["A"]),
        ]
        graph = _build(issues)
        assert graph.has_cycles
        assert len(graph.cycles) >= 1
        cycle_ids = {iid for cycle in graph.cycles for iid in cycle}
        assert "A" in cycle_ids or "B" in cycle_ids

    def test_cycle_nodes_excluded_from_topo(self):
        """环路节点不出现在 topological_order。"""
        issues = [
            _make_issue("A", depends_on=["B"]),
            _make_issue("B", depends_on=["A"]),
        ]
        graph = _build(issues)
        for iid in graph.topological_order:
            cycle_ids = {cid for cycle in graph.cycles for cid in cycle}
            assert iid not in cycle_ids

    def test_mixed_cycle_and_clean(self):
        """部分环路、部分正常。"""
        issues = [
            _make_issue("CLEAN-1", depends_on=[]),
            _make_issue("CLEAN-2", depends_on=["CLEAN-1"]),
            _make_issue("CYC-A", depends_on=["CYC-B"]),
            _make_issue("CYC-B", depends_on=["CYC-A"]),
        ]
        graph = _build(issues)
        assert graph.has_cycles
        assert "CLEAN-1" in graph.topological_order
        assert "CLEAN-2" in graph.topological_order

    def test_three_node_cycle(self):
        """三节点环路: A → B → C → A。"""
        issues = [
            _make_issue("A", depends_on=["C"]),
            _make_issue("B", depends_on=["A"]),
            _make_issue("C", depends_on=["B"]),
        ]
        graph = _build(issues)
        assert graph.has_cycles
        assert graph.topological_order == []


# ---------------------------------------------------------------------------
# 非法引用过滤测试
# ---------------------------------------------------------------------------


class TestInvalidReferenceFiltering:
    """depends_on 中引用不存在的 issue_id 被过滤。"""

    def test_unknown_dep_filtered_no_edge(self):
        issues = [_make_issue("A", depends_on=["NONEXISTENT"])]
        graph = _build(issues)
        assert graph.edges == []
        assert graph.nodes[0].depends_on == []
        assert "A" in graph.topological_order

    def test_partial_valid_deps_kept(self):
        """部分有效、部分无效的 depends_on，只保留有效引用。"""
        issues = [
            _make_issue("A", depends_on=["B", "GHOST"]),
            _make_issue("B", depends_on=[]),
        ]
        graph = _build(issues)
        assert len(graph.edges) == 1
        assert graph.edges[0].to_issue_id == "B"


# ---------------------------------------------------------------------------
# 元信息测试
# ---------------------------------------------------------------------------


class TestMetadata:
    """产物元信息正确性。"""

    def test_issue_and_edge_count(self):
        issues = [
            _make_issue("P", depends_on=["Q"]),
            _make_issue("Q", depends_on=[]),
        ]
        graph = _build(issues)
        assert graph.metadata["issue_count"] == 2
        assert graph.metadata["edge_count"] == 1

    def test_created_at_iso8601(self):
        graph = _build([_make_issue("X")])
        assert graph.created_at
        assert "T" in graph.created_at

    def test_graph_id_populated(self):
        graph = _build([_make_issue("X")])
        assert graph.graph_id

    def test_case_id_propagated(self):
        graph = _build([_make_issue("X")])
        assert graph.case_id == "CASE-IDG-001"

    def test_cycle_count_in_metadata(self):
        issues = [
            _make_issue("A", depends_on=["B"]),
            _make_issue("B", depends_on=["A"]),
        ]
        graph = _build(issues)
        assert graph.metadata["cycle_count"] >= 1
