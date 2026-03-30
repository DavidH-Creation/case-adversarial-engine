"""
hearing_order 引擎专用数据模型。
Engine-specific schemas for hearing_order.

共享类型从 engines.shared.models 导入；本模块只保留引擎 I/O wrapper。
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from engines.shared.models import Issue, OutcomeImpact  # noqa: F401

from engines.simulation_run.issue_dependency_graph.schemas import (  # noqa: F401
    IssueDependencyGraph,
)


# ---------------------------------------------------------------------------
# 输出结构模型 / Output structure models
# ---------------------------------------------------------------------------


class HearingPhase(BaseModel):
    """庭审阶段。

    Args:
        phase_id:                       阶段唯一标识（如 "phase-1"）
        phase_name:                     阶段名称（如 "程序性事项"）
        issue_ids:                      本阶段涵盖的争点 ID 列表（按建议顺序）
        estimated_duration_minutes:     本阶段预估庭审时长（分钟）
        phase_rationale:                阶段划分依据说明
    """
    phase_id: str = Field(..., min_length=1)
    phase_name: str = Field(..., min_length=1)
    issue_ids: list[str] = Field(default_factory=list)
    estimated_duration_minutes: int = Field(ge=0)
    phase_rationale: str = Field(default="")


class IssueTimeEstimate(BaseModel):
    """单个争点的庭审时间预估。"""
    issue_id: str = Field(..., min_length=1)
    estimated_minutes: int = Field(ge=1)
    rationale: str = Field(default="")


# ---------------------------------------------------------------------------
# 引擎 I/O wrapper / Engine I/O wrappers
# ---------------------------------------------------------------------------


class PartyPosition(BaseModel):
    """当事方庭审立场（用于争点优先级判断）。

    Args:
        party_id:       当事方 ID
        role:           角色（"plaintiff" / "defendant"）
        priority_issue_ids: 该方希望优先审理的争点 ID 列表
    """
    party_id: str = Field(..., min_length=1)
    role: str = Field(..., pattern=r"^(plaintiff|defendant)$")
    priority_issue_ids: list[str] = Field(default_factory=list)


class HearingOrderInput(BaseModel):
    """HearingOrderGenerator 输入 wrapper。

    Args:
        case_id:            案件 ID
        dependency_graph:   争点依赖图（由 IssueDependencyGraphGenerator 生成）
        issues:             含 P0.1 富化字段的争点列表
        party_positions:    当事方庭审立场列表（可选）
    """
    case_id: str = Field(..., min_length=1)
    dependency_graph: IssueDependencyGraph
    issues: list[Issue] = Field(default_factory=list)
    party_positions: list[PartyPosition] = Field(default_factory=list)


class HearingOrderResult(BaseModel):
    """庭审顺序建议产物。

    合约保证：
    - issue_presentation_order 包含所有输入争点（无遗漏）
    - phases 中的 issue_ids 与 issue_presentation_order 一一对应
    - total_estimated_duration_minutes == sum(phase.estimated_duration_minutes)

    Args:
        order_id:                           产物唯一标识
        case_id:                            案件 ID
        phases:                             庭审阶段列表（按顺序）
        issue_presentation_order:           全量争点建议出庭顺序（issue_id 列表）
        issue_time_estimates:               每个争点的庭审时间预估
        total_estimated_duration_minutes:   全程预估庭审时长（分钟）
        ordering_rationale:                 整体排序依据说明
        metadata:                           构建元信息
        created_at:                         ISO-8601 时间戳
    """
    order_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    phases: list[HearingPhase]
    issue_presentation_order: list[str] = Field(
        description="全量争点建议出庭顺序（issue_id 列表）"
    )
    issue_time_estimates: list[IssueTimeEstimate] = Field(default_factory=list)
    total_estimated_duration_minutes: int = Field(ge=0)
    ordering_rationale: str = Field(default="")
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
