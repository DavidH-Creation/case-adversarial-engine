"""
IssueDependencyGraphGenerator 单元测试。
Unit tests for IssueDependencyGraphGenerator.

测试策略：
- 纯规则层，无 LLM 依赖
- 覆盖：空输入、无依赖、线性链、DAG、环路检测、非法引用过滤
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
    """创建测试用 Issue（通过 object.__setattr__ 注入 depends_on 字段）。"""
    issue = Issue(
        issue_id=issue_id,
        case_id="CASE-TEST-001",
        title=f"争点 {issue_id}",
        issue_type=IssueType.factual,
        status=IssueStatus.open,
    )
    # depends_on 字段由另一任务添加，使用 model_copy 注入以兼容两种情况
    if depends_on is not None:
        issue = issue.model_copy(update={"depends_on": depends_on})
    return issue


def _build(issues: list[Issue]) -> IssueDependencyGraph:
    gen = IssueDependencyGraphGenerator()
    return gen.build(IssueDependencyGraphInput(case_id="CASE-TEST-001", issues=issues))


# ---------------------------------------------------------------------------
# 基础测试
# ---------------------------------------------------------------------------


def test_empty_issues_returns_empty_graph():
    """空争点列表返回空图。"""
    graph = _build([])
    assert graph.nodes == []
    assert graph.edges == []
    assert graph.topological_order == []
    assert graph.cycles == []
    assert not graph.has_cycles


def test_single_issue_no_deps():
    """单个无依赖争点。"""
    graph = _build([_make_issue("ISS-001")])
    assert len(graph.nodes) == 1
    assert graph.nodes[0].issue_id == "ISS-001"
    assert graph.edges == []
    assert graph.topological_order == ["ISS-001"]
    assert not graph.has_cycles


def test_three_issues_no_deps_all_in_topo():
    """三个无依赖争点均出现在拓扑排序中。"""
    issues = [_make_issue("A"), _make_issue("B"), _make_issue("C")]
    graph = _build(issues)
    assert set(graph.topological_order) == {"A", "B", "C"}
    assert not graph.has_cycles


# ---------------------------------------------------------------------------
# 依赖关系测试
# ---------------------------------------------------------------------------


def test_linear_chain_topo_order():
    """线性链 A → B → C（A depends_on B, B depends_on C）。

    拓扑顺序应为 [C, B, A]（被依赖方先出现）。
    """
    issues = [
        _make_issue("A", depends_on=["B"]),
        _make_issue("B", depends_on=["C"]),
        _make_issue("C", depends_on=[]),
    ]
    graph = _build(issues)
    assert not graph.has_cycles
    topo = graph.topological_order
    assert topo.index("C") < topo.index("B") < topo.index("A")


def test_dag_diamond():
    """菱形 DAG: D depends_on B,C; B depends_on A; C depends_on A。

    拓扑顺序中 A 必须在 B、C 之前，B/C 必须在 D 之前。
    """
    issues = [
        _make_issue("A", depends_on=[]),
        _make_issue("B", depends_on=["A"]),
        _make_issue("C", depends_on=["A"]),
        _make_issue("D", depends_on=["B", "C"]),
    ]
    graph = _build(issues)
    assert not graph.has_cycles
    topo = graph.topological_order
    assert topo.index("A") < topo.index("B")
    assert topo.index("A") < topo.index("C")
    assert topo.index("B") < topo.index("D")
    assert topo.index("C") < topo.index("D")
    assert set(topo) == {"A", "B", "C", "D"}


def test_edges_built_correctly():
    """边的 from/to 方向正确（from=依赖方，to=被依赖方）。"""
    issues = [
        _make_issue("X", depends_on=["Y"]),
        _make_issue("Y", depends_on=[]),
    ]
    graph = _build(issues)
    assert len(graph.edges) == 1
    edge = graph.edges[0]
    assert edge.from_issue_id == "X"
    assert edge.to_issue_id == "Y"


# ---------------------------------------------------------------------------
# 环路检测测试
# ---------------------------------------------------------------------------


def test_simple_cycle_detected():
    """简单环路 A depends_on B, B depends_on A。"""
    issues = [
        _make_issue("A", depends_on=["B"]),
        _make_issue("B", depends_on=["A"]),
    ]
    graph = _build(issues)
    assert graph.has_cycles
    assert len(graph.cycles) >= 1
    # 环路节点不出现在 topological_order 中
    cycle_ids = {iid for cycle in graph.cycles for iid in cycle}
    for iid in cycle_ids:
        assert iid not in graph.topological_order


def test_mixed_graph_cycle_plus_clean():
    """部分节点成环，其余正常节点仍在拓扑排序中。"""
    issues = [
        _make_issue("CLEAN-1", depends_on=[]),
        _make_issue("CLEAN-2", depends_on=["CLEAN-1"]),
        _make_issue("CYCLE-A", depends_on=["CYCLE-B"]),
        _make_issue("CYCLE-B", depends_on=["CYCLE-A"]),
    ]
    graph = _build(issues)
    assert graph.has_cycles
    assert "CLEAN-1" in graph.topological_order
    assert "CLEAN-2" in graph.topological_order
    cycle_ids = {iid for cycle in graph.cycles for iid in cycle}
    assert "CYCLE-A" in cycle_ids or "CYCLE-B" in cycle_ids


# ---------------------------------------------------------------------------
# 非法引用过滤测试
# ---------------------------------------------------------------------------


def test_unknown_depends_on_filtered():
    """depends_on 中引用不存在的 issue_id 被过滤，不产生边。"""
    issues = [
        _make_issue("A", depends_on=["NONEXISTENT-999"]),
    ]
    graph = _build(issues)
    assert graph.edges == []
    assert graph.nodes[0].depends_on == []
    assert "A" in graph.topological_order


# ---------------------------------------------------------------------------
# 元信息测试
# ---------------------------------------------------------------------------


def test_metadata_populated():
    """metadata 包含 issue_count 和 edge_count。"""
    issues = [
        _make_issue("P", depends_on=["Q"]),
        _make_issue("Q", depends_on=[]),
    ]
    graph = _build(issues)
    assert graph.metadata["issue_count"] == 2
    assert graph.metadata["edge_count"] == 1


def test_graph_has_created_at():
    """图产物包含 created_at 时间戳。"""
    graph = _build([_make_issue("X")])
    assert graph.created_at
    assert "T" in graph.created_at  # ISO-8601 格式检查
