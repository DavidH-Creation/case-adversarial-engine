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
    edges: list[IssueDependencyEdge] | None = None,
) -> IssueDependencyGraph:
    nodes = [IssueDependencyNode(issue_id=iid, depends_on=[]) for iid in issue_ids]
    return IssueDependencyGraph(
        graph_id=str(uuid.uuid4()),
        case_id="CASE-HO-001",
        nodes=nodes,
        edges=edges or [],
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
# 空输入测试
# ---------------------------------------------------------------------------


class TestEmptyInput:
    """空争点列表返回空庭审顺序。"""

    def test_empty_issues_returns_empty_phases(self):
        result = _generate([])
        assert result.phases == []

    def test_empty_issues_returns_empty_presentation_order(self):
        result = _generate([])
        assert result.issue_presentation_order == []

    def test_empty_issues_returns_zero_duration(self):
        result = _generate([])
        assert result.total_estimated_duration_minutes == 0


# ---------------------------------------------------------------------------
# 阶段分组测试
# ---------------------------------------------------------------------------


class TestPhaseClassification:
    """争点按类型正确分组到庭审阶段。"""

    def test_factual_issue_in_factual_phase(self):
        issues = [_make_issue("F-001", IssueType.factual)]
        result = _generate(issues)

        factual = [p for p in result.phases if p.phase_name == "事实争点"]
        assert len(factual) == 1
        assert "F-001" in factual[0].issue_ids

    def test_procedural_before_factual(self):
        issues = [
            _make_issue("PROC-001", IssueType.procedural),
            _make_issue("FACT-001", IssueType.factual),
        ]
        result = _generate(issues)

        names = [p.phase_name for p in result.phases]
        assert names.index("程序性事项") < names.index("事实争点")

    def test_legal_after_factual(self):
        issues = [
            _make_issue("FACT-001", IssueType.factual),
            _make_issue("LEGAL-001", IssueType.legal),
        ]
        result = _generate(issues)

        names = [p.phase_name for p in result.phases]
        assert names.index("事实争点") < names.index("法律争点")

    def test_damages_keyword_detection(self):
        issues = [_make_issue("DMG-001", IssueType.factual, title="利息计算争议")]
        result = _generate(issues)

        damages = [p for p in result.phases if p.phase_name == "损害赔偿争点"]
        assert len(damages) == 1
        assert "DMG-001" in damages[0].issue_ids

    def test_all_four_phases_ordering(self):
        """程序性 → 事实 → 法律 → 损害赔偿 的完整四阶段顺序。"""
        issues = [
            _make_issue("DMG", IssueType.factual, title="赔偿金额"),
            _make_issue("LEGAL", IssueType.legal),
            _make_issue("FACT", IssueType.factual),
            _make_issue("PROC", IssueType.procedural),
        ]
        result = _generate(issues)

        names = [p.phase_name for p in result.phases]
        assert names == ["程序性事项", "事实争点", "法律争点", "损害赔偿争点"]


# ---------------------------------------------------------------------------
# 时间估算测试
# ---------------------------------------------------------------------------


class TestDurationEstimation:
    """庭审时长按 outcome_impact 分级估算。"""

    def test_high_impact_30_min(self):
        issues = [_make_issue("H", outcome_impact=OutcomeImpact.high)]
        result = _generate(issues)
        est = next(e for e in result.issue_time_estimates if e.issue_id == "H")
        assert est.estimated_minutes == 30

    def test_medium_impact_20_min(self):
        issues = [_make_issue("M", outcome_impact=OutcomeImpact.medium)]
        result = _generate(issues)
        est = next(e for e in result.issue_time_estimates if e.issue_id == "M")
        assert est.estimated_minutes == 20

    def test_low_impact_10_min(self):
        issues = [_make_issue("L", outcome_impact=OutcomeImpact.low)]
        result = _generate(issues)
        est = next(e for e in result.issue_time_estimates if e.issue_id == "L")
        assert est.estimated_minutes == 10

    def test_no_impact_defaults_to_15_min(self):
        issues = [_make_issue("N")]
        result = _generate(issues)
        est = next(e for e in result.issue_time_estimates if e.issue_id == "N")
        assert est.estimated_minutes == 15

    def test_total_duration_equals_sum_of_phases(self):
        issues = [
            _make_issue("H", outcome_impact=OutcomeImpact.high),
            _make_issue("M", outcome_impact=OutcomeImpact.medium),
            _make_issue("L", outcome_impact=OutcomeImpact.low),
        ]
        result = _generate(issues)
        phase_total = sum(p.estimated_duration_minutes for p in result.phases)
        assert result.total_estimated_duration_minutes == phase_total


# ---------------------------------------------------------------------------
# 拓扑顺序测试
# ---------------------------------------------------------------------------


class TestTopologicalOrdering:
    """争点按依赖图拓扑排序顺序排列。"""

    def test_topo_order_respected_within_phase(self):
        issues = [
            _make_issue("A", IssueType.factual),
            _make_issue("B", IssueType.factual),
            _make_issue("C", IssueType.factual),
        ]
        topo = ["C", "B", "A"]
        result = _generate(issues, topo_order=topo)

        order = result.issue_presentation_order
        assert order.index("C") < order.index("B") < order.index("A")

    def test_all_issues_present_in_presentation_order(self):
        """所有输入争点均出现在 issue_presentation_order（无遗漏）。"""
        ids = [f"ISS-{i}" for i in range(6)]
        issues = [_make_issue(iid) for iid in ids]
        result = _generate(issues)

        assert set(result.issue_presentation_order) == set(ids)


# ---------------------------------------------------------------------------
# 原告方优先测试
# ---------------------------------------------------------------------------


class TestPlaintiffPriority:
    """原告方优先争点出现在对应阶段首位。"""

    def test_plaintiff_priority_first_in_phase(self):
        issues = [
            _make_issue("A", IssueType.factual),
            _make_issue("B", IssueType.factual),
            _make_issue("C", IssueType.factual),
        ]
        party_positions = [
            PartyPosition(party_id="P", role="plaintiff", priority_issue_ids=["C"]),
        ]
        result = _generate(issues, party_positions=party_positions)

        factual = [p for p in result.phases if p.phase_name == "事实争点"]
        assert factual[0].issue_ids[0] == "C"


# ---------------------------------------------------------------------------
# 环路节点测试
# ---------------------------------------------------------------------------


class TestCycleNodeHandling:
    """环路节点被追加到对应阶段（不从输出中丢弃）。"""

    def test_cycle_nodes_present_in_output(self):
        issues = [
            _make_issue("CLEAN", IssueType.factual),
            _make_issue("CYC-A", IssueType.factual),
            _make_issue("CYC-B", IssueType.factual),
        ]
        result = _generate(
            issues,
            topo_order=["CLEAN"],
            cycles=[["CYC-A", "CYC-B"]],
        )

        pres = result.issue_presentation_order
        assert "CLEAN" in pres
        assert "CYC-A" in pres
        assert "CYC-B" in pres

    def test_cycle_metadata_populated(self):
        issues = [
            _make_issue("CYC-X", IssueType.factual),
            _make_issue("CYC-Y", IssueType.factual),
        ]
        result = _generate(
            issues,
            topo_order=[],
            cycles=[["CYC-X", "CYC-Y"]],
        )

        assert result.metadata["has_cycles"] is True
        assert result.metadata["cycle_node_count"] == 2


# ---------------------------------------------------------------------------
# 元信息测试
# ---------------------------------------------------------------------------


class TestOutputMetadata:
    """产物元信息正确性。"""

    def test_order_id_and_created_at_populated(self):
        issues = [_make_issue("ISS-001")]
        result = _generate(issues)

        assert result.order_id
        assert result.created_at
        assert "T" in result.created_at

    def test_metadata_issue_and_phase_count(self):
        issues = [
            _make_issue("A", IssueType.factual),
            _make_issue("B", IssueType.legal),
        ]
        result = _generate(issues)

        assert result.metadata["issue_count"] == 2
        assert result.metadata["phase_count"] == 2

    def test_case_id_propagated(self):
        result = _generate([_make_issue("X")])
        assert result.case_id == "CASE-HO-001"
