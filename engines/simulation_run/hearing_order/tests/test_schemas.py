"""
hearing_order schemas 单元测试。
Unit tests for hearing_order schemas.

测试策略：
- Pydantic 模型的 validation 行为
- 默认值、边界值、非法值
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from engines.simulation_run.hearing_order.schemas import (
    HearingOrderInput,
    HearingOrderResult,
    HearingPhase,
    IssueTimeEstimate,
    PartyPosition,
)
from engines.simulation_run.issue_dependency_graph.schemas import (
    IssueDependencyGraph,
    IssueDependencyNode,
)


# ---------------------------------------------------------------------------
# HearingPhase 验证
# ---------------------------------------------------------------------------


class TestHearingPhase:
    """庭审阶段模型验证。"""

    def test_valid_phase(self):
        phase = HearingPhase(
            phase_id="phase-1",
            phase_name="事实争点",
            issue_ids=["ISS-001"],
            estimated_duration_minutes=30,
        )
        assert phase.phase_id == "phase-1"

    def test_empty_phase_id_rejected(self):
        with pytest.raises(ValidationError):
            HearingPhase(
                phase_id="",
                phase_name="事实争点",
                issue_ids=[],
                estimated_duration_minutes=0,
            )

    def test_negative_duration_rejected(self):
        with pytest.raises(ValidationError):
            HearingPhase(
                phase_id="phase-1",
                phase_name="事实争点",
                issue_ids=[],
                estimated_duration_minutes=-1,
            )

    def test_zero_duration_accepted(self):
        phase = HearingPhase(
            phase_id="phase-1",
            phase_name="事实争点",
            issue_ids=[],
            estimated_duration_minutes=0,
        )
        assert phase.estimated_duration_minutes == 0


# ---------------------------------------------------------------------------
# IssueTimeEstimate 验证
# ---------------------------------------------------------------------------


class TestIssueTimeEstimate:
    """时间预估模型验证。"""

    def test_valid_estimate(self):
        est = IssueTimeEstimate(
            issue_id="ISS-001",
            estimated_minutes=30,
            rationale="高影响争点",
        )
        assert est.estimated_minutes == 30

    def test_zero_minutes_rejected(self):
        with pytest.raises(ValidationError):
            IssueTimeEstimate(
                issue_id="ISS-001",
                estimated_minutes=0,
            )

    def test_empty_issue_id_rejected(self):
        with pytest.raises(ValidationError):
            IssueTimeEstimate(
                issue_id="",
                estimated_minutes=10,
            )


# ---------------------------------------------------------------------------
# PartyPosition 验证
# ---------------------------------------------------------------------------


class TestPartyPosition:
    """当事方立场模型验证。"""

    def test_valid_plaintiff(self):
        pos = PartyPosition(
            party_id="P-001",
            role="plaintiff",
            priority_issue_ids=["ISS-001"],
        )
        assert pos.role == "plaintiff"

    def test_valid_defendant(self):
        pos = PartyPosition(
            party_id="D-001",
            role="defendant",
        )
        assert pos.role == "defendant"

    def test_invalid_role_rejected(self):
        with pytest.raises(ValidationError):
            PartyPosition(
                party_id="P-001",
                role="judge",
            )

    def test_empty_party_id_rejected(self):
        with pytest.raises(ValidationError):
            PartyPosition(
                party_id="",
                role="plaintiff",
            )

    def test_default_priority_issue_ids(self):
        pos = PartyPosition(party_id="P-001", role="plaintiff")
        assert pos.priority_issue_ids == []


# ---------------------------------------------------------------------------
# HearingOrderInput 验证
# ---------------------------------------------------------------------------


class TestHearingOrderInput:
    """引擎输入 wrapper 验证。"""

    def _make_graph(self) -> IssueDependencyGraph:
        return IssueDependencyGraph(
            graph_id="G-001",
            case_id="CASE-001",
            nodes=[],
            edges=[],
            topological_order=[],
            cycles=[],
            has_cycles=False,
            created_at="2026-01-01T00:00:00Z",
        )

    def test_empty_case_id_rejected(self):
        with pytest.raises(ValidationError):
            HearingOrderInput(
                case_id="",
                dependency_graph=self._make_graph(),
            )

    def test_default_issues_and_positions(self):
        inp = HearingOrderInput(
            case_id="CASE-001",
            dependency_graph=self._make_graph(),
        )
        assert inp.issues == []
        assert inp.party_positions == []


# ---------------------------------------------------------------------------
# HearingOrderResult 验证
# ---------------------------------------------------------------------------


class TestHearingOrderResult:
    """引擎输出 wrapper 验证。"""

    def test_valid_result(self):
        result = HearingOrderResult(
            order_id="ORD-001",
            case_id="CASE-001",
            phases=[],
            issue_presentation_order=[],
            total_estimated_duration_minutes=0,
            created_at="2026-01-01T00:00:00Z",
        )
        assert result.order_id == "ORD-001"

    def test_negative_total_duration_rejected(self):
        with pytest.raises(ValidationError):
            HearingOrderResult(
                order_id="ORD-001",
                case_id="CASE-001",
                phases=[],
                issue_presentation_order=[],
                total_estimated_duration_minutes=-1,
                created_at="2026-01-01T00:00:00Z",
            )
