"""
HearingOrderGenerator 单元测试。
Unit tests for HearingOrderGenerator.

测试策略：
- 纯规则层，无 LLM 依赖
- 覆盖：空输入、阶段分组、拓扑顺序、时间估算、原告优先、环路节点处理
"""
from __future__ import annotations

import uuid

import pytest

from engines.shared.models import Issue, IssueStatus, IssueType, OutcomeImpact
from engines.simulation_run.hearing_order.generator import HearingOrderGenerator
from engines.simulation_run.hearing_order.schemas import (
    HearingOrderInput,
    HearingOrderResult,
    PartyPosition,
)
from engines.simulation_run.issue_dependency_graph.schemas import (
    IssueDependencyGraph,
    IssueDependencyEdge,
    IssueDependencyNode,
)


# ---------------------------------------------------------------------------
# 辅助工厂
# ---------------------------------------------------------------------------


def _make_issue(
    issue_id: str,
    issue_type: IssueType = IssueType.factual,
    outcome_impact: OutcomeImpact | None = None,
    title: str | None = None,
) -> Issue:
    return Issue(
        issue_id=issue_id,
        case_id="CASE-HO-001",
        title=title or f"争点 {issue_id}",
        issue_type=issue_type,
        status=IssueStatus.open,
        outcome_impact=outcome_impact,
    )


def _make_graph(
    issue_ids: list[str],
    topo_order: list[str] | None = None,
    cycles: list[list[str]] | None = None,
) -> IssueDependencyGraph:
    nodes = [IssueDependencyNode(issue_id=iid, depends_on=[]) for iid in issue_ids]
    return IssueDependencyGraph(
        graph_id=str(uuid.uuid4()),
        case_id="CASE-HO-001",
        nodes=nodes,
        edges=[],
        topological_order=topo_order if topo_order is not None else issue_ids,
        cycles=cycles or [],
        has_cycles=bool(cycles),
        created_at="2026-01-01T00:00:00Z",
    )


def _generate(
    issues: list[Issue],
    topo_order: list[str] | None = None,
    cycles: list[list[str]] | None = None,
    party_positions: list[PartyPosition] | None = None,
) -> HearingOrderResult:
    issue_ids = [i.issue_id for i in issues]
    graph = _make_graph(issue_ids, topo_order, cycles)
    inp = HearingOrderInput(
        case_id="CASE-HO-001",
        dependency_graph=graph,
        issues=issues,
        party_positions=party_positions or [],
    )
    return HearingOrderGenerator().generate(inp)


# ---------------------------------------------------------------------------
# 基础测试
# ---------------------------------------------------------------------------


def test_empty_issues_returns_empty_result():
    """空争点列表返回空庭审顺序。"""
    result = _generate([])
    assert result.phases == []
    assert result.issue_presentation_order == []
    assert result.total_estimated_duration_minutes == 0


def test_single_factual_issue():
    """单个事实争点出现在 factual 阶段。"""
    issues = [_make_issue("ISS-F-001", IssueType.factual)]
    result = _generate(issues)

    assert "ISS-F-001" in result.issue_presentation_order
    factual_phases = [p for p in result.phases if p.phase_name == "事实争点"]
    assert len(factual_phases) == 1
    assert "ISS-F-001" in factual_phases[0].issue_ids


def test_procedural_issues_in_first_phase():
    """程序性争点在 factual 争点之前（阶段顺序）。"""
    issues = [
        _make_issue("PROC-001", IssueType.procedural),
        _make_issue("FACT-001", IssueType.factual),
    ]
    result = _generate(issues)

    phase_names = [p.phase_name for p in result.phases]
    assert "程序性事项" in phase_names
    assert "事实争点" in phase_names
    assert phase_names.index("程序性事项") < phase_names.index("事实争点")


def test_legal_issues_after_factual():
    """法律争点在事实争点之后。"""
    issues = [
        _make_issue("FACT-001", IssueType.factual),
        _make_issue("LEGAL-001", IssueType.legal),
    ]
    result = _generate(issues)

    phase_names = [p.phase_name for p in result.phases]
    assert phase_names.index("事实争点") < phase_names.index("法律争点")


def test_damages_keyword_goes_to_damages_phase():
    """含损害赔偿关键词的争点分到 damages 阶段。"""
    issues = [_make_issue("DMGS-001", IssueType.factual, title="利息计算争议")]
    result = _generate(issues)

    damages_phases = [p for p in result.phases if p.phase_name == "损害赔偿争点"]
    assert len(damages_phases) == 1
    assert "DMGS-001" in damages_phases[0].issue_ids


# ---------------------------------------------------------------------------
# 时间估算测试
# ---------------------------------------------------------------------------


def test_duration_high_impact_30_min():
    """high impact 争点预估 30 分钟。"""
    issues = [_make_issue("ISS-H", outcome_impact=OutcomeImpact.high)]
    result = _generate(issues)

    est = next((e for e in result.issue_time_estimates if e.issue_id == "ISS-H"), None)
    assert est is not None
    assert est.estimated_minutes == 30


def test_duration_medium_impact_20_min():
    """medium impact 争点预估 20 分钟。"""
    issues = [_make_issue("ISS-M", outcome_impact=OutcomeImpact.medium)]
    result = _generate(issues)

    est = next((e for e in result.issue_time_estimates if e.issue_id == "ISS-M"), None)
    assert est is not None
    assert est.estimated_minutes == 20


def test_duration_low_impact_10_min():
    """low impact 争点预估 10 分钟。"""
    issues = [_make_issue("ISS-L", outcome_impact=OutcomeImpact.low)]
    result = _generate(issues)

    est = next((e for e in result.issue_time_estimates if e.issue_id == "ISS-L"), None)
    assert est is not None
    assert est.estimated_minutes == 10


def test_total_duration_equals_sum_of_phases():
    """total_estimated_duration_minutes == sum of all phases。"""
    issues = [
        _make_issue("ISS-1", outcome_impact=OutcomeImpact.high),
        _make_issue("ISS-2", outcome_impact=OutcomeImpact.medium),
        _make_issue("ISS-3", outcome_impact=OutcomeImpact.low),
    ]
    result = _generate(issues)

    phase_total = sum(p.estimated_duration_minutes for p in result.phases)
    assert result.total_estimated_duration_minutes == phase_total


# ---------------------------------------------------------------------------
# 拓扑顺序测试
# ---------------------------------------------------------------------------


def test_topological_order_respected_within_phase():
    """同阶段内争点按拓扑排序顺序排列。"""
    issues = [
        _make_issue("A", IssueType.factual),
        _make_issue("B", IssueType.factual),
        _make_issue("C", IssueType.factual),
    ]
    topo = ["C", "B", "A"]  # C 被 B 依赖，B 被 A 依赖
    result = _generate(issues, topo_order=topo)

    pres_order = result.issue_presentation_order
    assert pres_order.index("C") < pres_order.index("B") < pres_order.index("A")


def test_all_issues_in_presentation_order():
    """所有输入争点均出现在 issue_presentation_order 中（无遗漏）。"""
    issue_ids = [f"ISS-{i}" for i in range(6)]
    issues = [_make_issue(iid) for iid in issue_ids]
    result = _generate(issues)

    assert set(result.issue_presentation_order) == set(issue_ids)


# ---------------------------------------------------------------------------
# 原告方优先测试
# ---------------------------------------------------------------------------


def test_plaintiff_priority_issues_appear_first_in_phase():
    """原告方优先争点出现在对应阶段首位。"""
    issues = [
        _make_issue("A", IssueType.factual),
        _make_issue("B", IssueType.factual),
        _make_issue("C", IssueType.factual),
    ]
    party_positions = [
        PartyPosition(
            party_id="PARTY-P",
            role="plaintiff",
            priority_issue_ids=["C"],
        )
    ]
    result = _generate(issues, party_positions=party_positions)

    factual_phases = [p for p in result.phases if p.phase_name == "事实争点"]
    assert factual_phases[0].issue_ids[0] == "C"


# ---------------------------------------------------------------------------
# 环路节点测试
# ---------------------------------------------------------------------------


def test_cycle_nodes_appended_to_phases():
    """环路节点被追加到对应阶段（不从拓扑排序中丢弃）。"""
    issues = [
        _make_issue("CLEAN", IssueType.factual),
        _make_issue("CYCLE-A", IssueType.factual),
        _make_issue("CYCLE-B", IssueType.factual),
    ]
    result = _generate(
        issues,
        topo_order=["CLEAN"],
        cycles=[["CYCLE-A", "CYCLE-B"]],
    )

    pres = result.issue_presentation_order
    assert "CLEAN" in pres
    assert "CYCLE-A" in pres
    assert "CYCLE-B" in pres
