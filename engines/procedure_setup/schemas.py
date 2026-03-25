"""
程序设置引擎数据模型。
Procedure setup engine data models.

共享类型从 engines.shared.models 导入；本模块只保留程序阶段专用类型和 LLM 中间结构。
Shared types imported from engines.shared.models; only procedure-specific types and LLM intermediate structures kept here.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

# 从共享模块导入所有共享类型（re-exported for backward compat）
from engines.shared.models import (  # noqa: F401
    AccessDomain,
    ArtifactRef,
    Burden,
    ClaimIssueMapping,
    DefenseIssueMapping,
    EvidenceStatus as EvidenceStatusValue,  # backward compat alias
    EvidenceStatus,
    FactProposition,
    InputSnapshot,
    Issue,
    IssueTree,
    MaterialRef,
    ProcedurePhase,
    Run,
)

# 全局阶段顺序 / Canonical phase order
PHASE_ORDER: list[str] = [
    ProcedurePhase.case_intake.value,
    ProcedurePhase.element_mapping.value,
    ProcedurePhase.opening.value,
    ProcedurePhase.evidence_submission.value,
    ProcedurePhase.evidence_challenge.value,
    ProcedurePhase.judge_questions.value,
    ProcedurePhase.rebuttal.value,
    ProcedurePhase.output_branching.value,
]


# ---------------------------------------------------------------------------
# 引擎输入模型 / Engine input models
# ---------------------------------------------------------------------------


class PartyInfo(BaseModel):
    """当事人简要信息（仅用于程序设置阶段）。"""
    party_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    role_code: str = Field(..., min_length=1)
    side: str = Field(..., min_length=1)


class ProcedureSetupInput(BaseModel):
    """程序设置引擎输入合约。"""
    workspace_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    case_type: str = Field(..., min_length=1)
    parties: list[PartyInfo]


# ---------------------------------------------------------------------------
# 引擎输出核心模型 / Engine output core models
# ---------------------------------------------------------------------------


class ProcedureState(BaseModel):
    """程序状态对象，matching docs/03_case_object_model.md."""
    state_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    phase: str  # ProcedurePhase 枚举值
    round_index: int = Field(..., ge=0)
    allowed_role_codes: list[str] = Field(default_factory=list)
    readable_access_domains: list[str] = Field(default_factory=list)
    writable_object_types: list[str] = Field(default_factory=list)
    admissible_evidence_statuses: list[str] = Field(default_factory=list)
    open_issue_ids: list[str] = Field(default_factory=list)
    entry_conditions: list[str] = Field(default_factory=list)
    exit_conditions: list[str] = Field(default_factory=list)
    next_state_ids: list[str] = Field(default_factory=list)


class ProcedureConfig(BaseModel):
    """程序配置（记录程序级参数，供下游引用）。"""
    case_type: str
    total_phases: int
    evidence_submission_deadline_days: int
    evidence_challenge_window_days: int
    max_rounds_per_phase: int
    applicable_laws: list[str] = Field(default_factory=list)


class TimelineEvent(BaseModel):
    """时间线事件。"""
    event_id: str = Field(..., min_length=1)
    event_type: str = Field(..., min_length=1)
    phase: str
    description: str = Field(..., min_length=1)
    relative_day: int = Field(..., ge=0)
    is_mandatory: bool = True


class ProcedureSetupResult(BaseModel):
    """程序设置结果。"""
    procedure_states: list[ProcedureState]
    procedure_config: ProcedureConfig
    timeline_events: list[TimelineEvent]
    run: Run


# ---------------------------------------------------------------------------
# LLM 中间结构 / LLM intermediate structures
# ---------------------------------------------------------------------------


class LLMProcedureState(BaseModel):
    """LLM 返回的单个程序状态（尚未规范化）。"""
    phase: str
    allowed_role_codes: list[str] = Field(default_factory=list)
    readable_access_domains: list[str] = Field(default_factory=list)
    writable_object_types: list[str] = Field(default_factory=list)
    admissible_evidence_statuses: list[str] = Field(default_factory=list)
    entry_conditions: list[str] = Field(default_factory=list)
    exit_conditions: list[str] = Field(default_factory=list)


class LLMProcedureConfig(BaseModel):
    """LLM 返回的程序配置（尚未规范化）。"""
    evidence_submission_deadline_days: int = 15
    evidence_challenge_window_days: int = 10
    max_rounds_per_phase: int = 3
    applicable_laws: list[str] = Field(default_factory=list)


class LLMTimelineEvent(BaseModel):
    """LLM 返回的时间线事件（尚未规范化）。"""
    event_type: str
    phase: str
    description: str
    relative_day: int = Field(default=0, ge=0)
    is_mandatory: bool = True


class LLMProcedureOutput(BaseModel):
    """LLM 返回的完整程序设置输出（尚未规范化）。"""
    procedure_config: LLMProcedureConfig
    procedure_states: list[LLMProcedureState]
    timeline_events: list[LLMTimelineEvent] = Field(default_factory=list)
