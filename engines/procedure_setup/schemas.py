"""
程序设置引擎数据模型 — 与 JSON Schema 定义及对象模型对齐。
Procedure setup engine data models — aligned with JSON Schema and the case object model.

所有模型均使用 Pydantic v2，字段定义严格匹配：
All models use Pydantic v2, strictly aligned with:
- docs/03_case_object_model.md (ProcedureState, CaseWorkspace)
- schemas/procedure/run.schema.json
- schemas/indexing.schema.json
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 枚举类型 / Enum types
# ---------------------------------------------------------------------------


class ProcedurePhase(str, Enum):
    """程序阶段枚举（来自 docs/03_case_object_model.md）。
    Procedure phase enum (from docs/03_case_object_model.md).
    """
    case_intake = "case_intake"
    element_mapping = "element_mapping"
    opening = "opening"
    evidence_submission = "evidence_submission"
    evidence_challenge = "evidence_challenge"
    judge_questions = "judge_questions"
    rebuttal = "rebuttal"
    output_branching = "output_branching"


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


class AccessDomain(str, Enum):
    """访问域枚举 / Access domain enum."""
    owner_private = "owner_private"
    shared_common = "shared_common"
    admitted_record = "admitted_record"


class EvidenceStatusValue(str, Enum):
    """证据状态枚举 / Evidence status enum."""
    private = "private"
    submitted = "submitted"
    challenged = "challenged"
    admitted_for_discussion = "admitted_for_discussion"


# ---------------------------------------------------------------------------
# 索引引用模型 / Index reference models
# ---------------------------------------------------------------------------


class MaterialRef(BaseModel):
    """材料索引引用 / Material index reference."""
    index_name: str = Field(default="material_index")
    object_type: str
    object_id: str = Field(..., min_length=1)
    storage_ref: str = Field(..., min_length=1)


class ArtifactRef(BaseModel):
    """产物索引引用 / Artifact index reference."""
    index_name: str = Field(default="artifact_index")
    object_type: str
    object_id: str = Field(..., min_length=1)
    storage_ref: str = Field(..., min_length=1)


class InputSnapshot(BaseModel):
    """运行输入快照 / Run input snapshot."""
    material_refs: list[MaterialRef] = Field(default_factory=list)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 引擎输入模型 / Engine input models
# ---------------------------------------------------------------------------


class PartyInfo(BaseModel):
    """当事人简要信息 / Summary party information for procedure setup.

    合约约束 / Contract constraint:
    - 仅用于程序设置阶段，提供角色与立场信息
    - Only used in procedure setup stage to supply role and side information
    """
    party_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    role_code: str = Field(..., min_length=1)
    side: str = Field(..., min_length=1)


class FactProposition(BaseModel):
    """事实命题 / Fact proposition within an Issue."""
    proposition_id: str
    text: str
    status: Optional[str] = None
    linked_evidence_ids: list[str] = Field(default_factory=list)


class Issue(BaseModel):
    """争点对象 / Issue object, matching issue.schema.json."""
    issue_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    issue_type: str
    parent_issue_id: Optional[str] = None
    related_claim_ids: list[str] = Field(default_factory=list)
    related_defense_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    burden_ids: list[str] = Field(default_factory=list)
    fact_propositions: list[FactProposition] = Field(default_factory=list)
    status: Optional[str] = None
    created_at: Optional[str] = None


class Burden(BaseModel):
    """举证责任对象 / Burden of proof object."""
    burden_id: str
    case_id: str
    issue_id: str
    bearer_party_id: str
    description: str
    proof_standard: Optional[str] = None
    legal_basis: Optional[str] = None
    status: Optional[str] = None


class ClaimIssueMapping(BaseModel):
    """诉请-争点映射 / Claim-to-issue mapping."""
    claim_id: str
    issue_ids: list[str]


class DefenseIssueMapping(BaseModel):
    """抗辩-争点映射 / Defense-to-issue mapping."""
    defense_id: str
    issue_ids: list[str]


class IssueTree(BaseModel):
    """争点树 / IssueTree input."""
    case_id: str = Field(..., min_length=1)
    run_id: Optional[str] = None
    job_id: Optional[str] = None
    issues: list[Issue]
    burdens: list[Burden]
    claim_issue_mapping: list[ClaimIssueMapping]
    defense_issue_mapping: list[DefenseIssueMapping]
    extraction_metadata: Optional[dict[str, Any]] = None


class ProcedureSetupInput(BaseModel):
    """程序设置引擎输入合约 / Procedure setup engine input contract.

    合约约束 / Contract constraint:
    - workspace_id 和 case_id 必须与 IssueTree.case_id 一致
    - workspace_id and case_id must match IssueTree.case_id
    - case_type 必须来自统一枚举：civil / criminal / admin
    - case_type must come from the canonical enum: civil / criminal / admin
    """
    workspace_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    case_type: str = Field(..., min_length=1)
    parties: list[PartyInfo]


# ---------------------------------------------------------------------------
# 引擎输出核心模型 / Engine output core models
# ---------------------------------------------------------------------------


class ProcedureState(BaseModel):
    """程序状态对象 / ProcedureState object, matching docs/03_case_object_model.md.

    合约约束 / Contract constraint:
    - phase 必须来自统一 ProcedurePhase 枚举
    - phase must come from the canonical ProcedurePhase enum
    - judge_questions 阶段不得包含 owner_private 读取域
    - judge_questions phase must not include owner_private in readable_access_domains
    - next_state_ids 为空时表示终止状态
    - Empty next_state_ids indicates a terminal state
    """
    state_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    phase: str  # ProcedurePhase 枚举值 / ProcedurePhase enum value
    round_index: int = Field(..., ge=0)
    allowed_role_codes: list[str] = Field(default_factory=list)
    readable_access_domains: list[str] = Field(default_factory=list)
    writable_object_types: list[str] = Field(default_factory=list)
    admissible_evidence_statuses: list[str] = Field(default_factory=list)
    open_issue_ids: list[str] = Field(default_factory=list)
    entry_conditions: list[str] = Field(default_factory=list)
    exit_conditions: list[str] = Field(default_factory=list)
    next_state_ids: list[str] = Field(default_factory=list)  # 空=终止 / empty=terminal


class ProcedureConfig(BaseModel):
    """程序配置 / Procedure configuration derived from case type.

    记录程序级参数，供下游工作流（simulation_run）引用。
    Stores procedure-level parameters referenced by downstream workflow stages.
    """
    case_type: str
    total_phases: int
    evidence_submission_deadline_days: int
    evidence_challenge_window_days: int
    max_rounds_per_phase: int
    applicable_laws: list[str] = Field(default_factory=list)


class TimelineEvent(BaseModel):
    """时间线事件 / Timeline event.

    合约约束 / Contract constraint:
    - event_id 在同一 case 内唯一
    - event_id must be unique within the same case
    - relative_day 从程序启动之日计算
    - relative_day is counted from the procedure start date
    """
    event_id: str = Field(..., min_length=1)
    event_type: str = Field(..., min_length=1)
    phase: str  # ProcedurePhase 枚举值 / ProcedurePhase enum value
    description: str = Field(..., min_length=1)
    relative_day: int = Field(..., ge=0)
    is_mandatory: bool = True


class Run(BaseModel):
    """执行快照 / Run execution snapshot, matching run.schema.json."""
    run_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    workspace_id: str = Field(..., min_length=1)
    scenario_id: Optional[str] = None
    trigger_type: str = Field(..., min_length=1)
    input_snapshot: InputSnapshot
    output_refs: list[ArtifactRef] = Field(default_factory=list)
    started_at: str
    finished_at: Optional[str] = None
    status: str


class ProcedureSetupResult(BaseModel):
    """程序设置结果 / Result returned by ProcedurePlanner.

    包含完整程序状态序列、程序配置、时间线事件和执行快照。
    Contains the complete procedure state sequence, config, timeline events, and Run.

    合约约束 / Contract constraint:
    - procedure_states 覆盖全部八个程序阶段
    - procedure_states covers all eight procedure phases
    - run.trigger_type 固定为 "procedure_setup"
    - run.trigger_type is fixed to "procedure_setup"
    """
    procedure_states: list[ProcedureState]
    procedure_config: ProcedureConfig
    timeline_events: list[TimelineEvent]
    run: Run


# ---------------------------------------------------------------------------
# LLM 中间结构 / LLM intermediate structures
# ---------------------------------------------------------------------------


class LLMProcedureState(BaseModel):
    """LLM 返回的单个程序状态（尚未规范化）。
    Single procedure state as returned by LLM (before normalization).
    """
    phase: str
    allowed_role_codes: list[str] = Field(default_factory=list)
    readable_access_domains: list[str] = Field(default_factory=list)
    writable_object_types: list[str] = Field(default_factory=list)
    admissible_evidence_statuses: list[str] = Field(default_factory=list)
    entry_conditions: list[str] = Field(default_factory=list)
    exit_conditions: list[str] = Field(default_factory=list)


class LLMProcedureConfig(BaseModel):
    """LLM 返回的程序配置（尚未规范化）。
    Procedure config as returned by LLM (before normalization).
    """
    evidence_submission_deadline_days: int = 15
    evidence_challenge_window_days: int = 10
    max_rounds_per_phase: int = 3
    applicable_laws: list[str] = Field(default_factory=list)


class LLMTimelineEvent(BaseModel):
    """LLM 返回的时间线事件（尚未规范化）。
    Timeline event as returned by LLM (before normalization).
    """
    event_type: str
    phase: str
    description: str
    relative_day: int = Field(default=0, ge=0)
    is_mandatory: bool = True


class LLMProcedureOutput(BaseModel):
    """LLM 返回的完整程序设置输出（尚未规范化）。
    Full procedure setup output as returned by LLM (before normalization).
    """
    procedure_config: LLMProcedureConfig
    procedure_states: list[LLMProcedureState]
    timeline_events: list[LLMTimelineEvent] = Field(default_factory=list)
