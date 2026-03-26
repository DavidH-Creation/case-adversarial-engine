"""
共享数据模型 — 所有跨引擎 Pydantic 模型和枚举的单一来源。
Shared data models — single source of truth for all cross-engine Pydantic models and enums.

两层策略 / Two-tier strategy:
- Tier 1: JSON Schema 和引擎代码中都存在的稳定字段（required, typed, enforced）
- Tier 2: docs/03_case_object_model.md 中定义但代码尚未有的前瞻字段（Optional with defaults）

迁移规则 / Migration rule:
- 各引擎 schemas.py 删除重复类型，改从本模块导入
- 只保留 LLM 中间模型和引擎专用 wrapper
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Protocol, Union, runtime_checkable

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# 枚举类型 / Enumerations
# ---------------------------------------------------------------------------


class CaseType(str, Enum):
    """案件类型枚举（schema-level canonical）。"""
    civil = "civil"
    criminal = "criminal"
    admin = "admin"


class PromptProfile(str, Enum):
    """提示模板 key（engine-level）。NOT a CaseType value."""
    civil_loan = "civil_loan"


class AccessDomain(str, Enum):
    """证据可见域。"""
    owner_private = "owner_private"
    shared_common = "shared_common"
    admitted_record = "admitted_record"


class EvidenceStatus(str, Enum):
    """证据生命周期状态。"""
    private = "private"
    submitted = "submitted"
    challenged = "challenged"
    admitted_for_discussion = "admitted_for_discussion"


class EvidenceType(str, Enum):
    """证据类型枚举，对应《民事诉讼法》证据种类。"""
    documentary = "documentary"
    physical = "physical"
    witness_statement = "witness_statement"
    electronic_data = "electronic_data"
    expert_opinion = "expert_opinion"
    audio_visual = "audio_visual"
    other = "other"


class IssueType(str, Enum):
    """争点类型。"""
    factual = "factual"
    legal = "legal"
    procedural = "procedural"
    mixed = "mixed"


class IssueStatus(str, Enum):
    """争点当前状态。"""
    open = "open"
    resolved = "resolved"
    deferred = "deferred"


class PropositionStatus(str, Enum):
    """事实命题核实状态。"""
    unverified = "unverified"
    supported = "supported"
    contradicted = "contradicted"
    disputed = "disputed"


class BurdenStatus(str, Enum):
    """举证责任完成状态。"""
    met = "met"
    partially_met = "partially_met"
    not_met = "not_met"
    disputed = "disputed"


class StatementClass(str, Enum):
    """结论陈述分类。"""
    fact = "fact"
    inference = "inference"
    assumption = "assumption"


class WorkflowStage(str, Enum):
    """产品工作流阶段。"""
    case_structuring = "case_structuring"
    procedure_setup = "procedure_setup"
    simulation_run = "simulation_run"
    report_generation = "report_generation"
    interactive_followup = "interactive_followup"


class ProcedurePhase(str, Enum):
    """法律程序阶段。"""
    case_intake = "case_intake"
    element_mapping = "element_mapping"
    opening = "opening"
    evidence_submission = "evidence_submission"
    evidence_challenge = "evidence_challenge"
    judge_questions = "judge_questions"
    rebuttal = "rebuttal"
    output_branching = "output_branching"


class ChangeItemObjectType(str, Enum):
    """change_item 目标对象类型枚举。"""
    Party = "Party"
    Claim = "Claim"
    Defense = "Defense"
    Issue = "Issue"
    Evidence = "Evidence"
    Burden = "Burden"
    ProcedureState = "ProcedureState"
    AgentOutput = "AgentOutput"
    ReportArtifact = "ReportArtifact"


class DiffDirection(str, Enum):
    """差异方向枚举。"""
    strengthen = "strengthen"
    weaken = "weaken"
    neutral = "neutral"


class ScenarioStatus(str, Enum):
    """场景生命周期状态。"""
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class JobStatus(str, Enum):
    """长任务生命周期状态。对应 schemas/indexing.schema.json#/$defs/job_status。"""
    created = "created"
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


# ---------------------------------------------------------------------------
# 基础输入模型 / Basic input models
# ---------------------------------------------------------------------------


class RawMaterial(BaseModel):
    """原始案件材料段落，由调用方提供。"""
    source_id: str = Field(..., min_length=1, description="材料唯一标识符")
    text: str = Field(..., min_length=1, description="纯文本内容")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="开放元数据（document_type, date, submitter 等）",
    )


# ---------------------------------------------------------------------------
# 核心案件对象 / Core case objects
# ---------------------------------------------------------------------------


class Evidence(BaseModel):
    """结构化证据对象。Tier 1 字段对应 evidence.schema.json。"""
    evidence_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    owner_party_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    evidence_type: EvidenceType
    target_fact_ids: list[str] = Field(..., min_length=1)
    target_issue_ids: list[str] = Field(default_factory=list)
    access_domain: AccessDomain = AccessDomain.owner_private
    status: EvidenceStatus = EvidenceStatus.private
    submitted_by_party_id: Optional[str] = None
    challenged_by_party_ids: list[str] = Field(default_factory=list)
    admissibility_notes: Optional[str] = None


class FactProposition(BaseModel):
    """事实命题 — 连接证据与争点的桥梁。"""
    proposition_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    status: PropositionStatus = PropositionStatus.unverified
    linked_evidence_ids: list[str] = Field(default_factory=list)


class Issue(BaseModel):
    """争点对象。Tier 1 对应 issue.schema.json；Tier 2 为 docs/03 前瞻字段（Optional）。"""
    issue_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    issue_type: IssueType
    parent_issue_id: Optional[str] = None
    related_claim_ids: list[str] = Field(default_factory=list)
    related_defense_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    burden_ids: list[str] = Field(default_factory=list)
    fact_propositions: list[FactProposition] = Field(default_factory=list)
    status: IssueStatus = IssueStatus.open
    created_at: Optional[str] = None
    # Tier 2: docs/03 前瞻字段
    description: Optional[str] = None
    priority: Optional[str] = None


class Burden(BaseModel):
    """举证责任对象。canonical 字段名使用 burden_party_id（docs/03）。"""
    burden_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    issue_id: str = Field(..., min_length=1)
    burden_party_id: str = Field(..., min_length=1, description="承担举证责任的当事方 party_id")
    proof_standard: str = Field(default="")
    legal_basis: str = Field(default="")
    status: BurdenStatus = BurdenStatus.not_met
    # 向后兼容字段（引擎代码原有）
    description: Optional[str] = None
    # Tier 2: docs/03 前瞻字段
    burden_type: Optional[str] = None
    fact_proposition: Optional[str] = None
    shift_condition: Optional[str] = None


class Claim(BaseModel):
    """诉请对象。"""
    claim_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    owner_party_id: str = Field(..., min_length=1)
    case_type: str = Field(default="civil")
    title: str = Field(..., min_length=1)
    claim_text: str = Field(default="")
    claim_category: str = Field(default="")
    target_issue_ids: list[str] = Field(default_factory=list)
    supporting_fact_ids: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    status: str = Field(default="open")


class Defense(BaseModel):
    """抗辩对象。"""
    defense_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    owner_party_id: str = Field(..., min_length=1)
    against_claim_id: str = Field(..., min_length=1)
    defense_text: str = Field(default="")
    defense_category: str = Field(default="")
    target_issue_ids: list[str] = Field(default_factory=list)
    supporting_fact_ids: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    status: str = Field(default="open")


class Party(BaseModel):
    """案件参与主体。"""
    party_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    party_type: str = Field(..., min_length=1)
    role_code: str = Field(..., min_length=1)
    side: str = Field(..., min_length=1)
    case_type: str = Field(default="civil")
    access_domain_scope: list[str] = Field(default_factory=list)
    active: bool = True


# ---------------------------------------------------------------------------
# 聚合产物 / Aggregate artifacts
# ---------------------------------------------------------------------------


class ClaimIssueMapping(BaseModel):
    """诉请到争点的映射。"""
    claim_id: str = Field(..., min_length=1)
    issue_ids: list[str] = Field(..., min_length=1)


class DefenseIssueMapping(BaseModel):
    """抗辩到争点的映射。"""
    defense_id: str = Field(..., min_length=1)
    issue_ids: list[str] = Field(..., min_length=1)


class EvidenceIndex(BaseModel):
    """证据索引工作格式（非磁盘 artifact envelope）。"""
    case_id: str = Field(..., min_length=1)
    evidence: list[Evidence]
    extraction_metadata: Optional[dict[str, Any]] = None


class IssueTree(BaseModel):
    """争点树产物，对应 schemas/case/issue_tree.schema.json。"""
    case_id: str = Field(..., min_length=1)
    run_id: Optional[str] = None
    job_id: Optional[str] = None
    issues: list[Issue] = Field(default_factory=list)
    burdens: list[Burden] = Field(default_factory=list)
    claim_issue_mapping: list[ClaimIssueMapping] = Field(default_factory=list)
    defense_issue_mapping: list[DefenseIssueMapping] = Field(default_factory=list)
    extraction_metadata: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# 报告层 / Report layer
# ---------------------------------------------------------------------------


class KeyConclusion(BaseModel):
    """报告章节关键结论。"""
    conclusion_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    statement_class: StatementClass
    supporting_evidence_ids: list[str] = Field(
        ..., description="至少一条支持该结论的证据 ID"
    )
    supporting_output_ids: list[str] = Field(default_factory=list)


class ReportSection(BaseModel):
    """报告章节。"""
    section_id: str = Field(..., min_length=1)
    section_index: int = Field(..., ge=1)
    title: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    linked_issue_ids: list[str] = Field(default_factory=list)
    linked_output_ids: list[str] = Field(default_factory=list)
    linked_evidence_ids: list[str] = Field(
        ..., description="章节引用的证据 ID 列表"
    )
    key_conclusions: list[KeyConclusion] = Field(default_factory=list)


class ReportArtifact(BaseModel):
    """诊断报告产物。"""
    report_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    sections: list[ReportSection]
    created_at: Optional[str] = None
    # Tier 2: docs/03 前瞻字段
    linked_output_ids: list[str] = Field(default_factory=list)
    linked_evidence_ids: list[str] = Field(default_factory=list)
    extraction_metadata: Optional[dict[str, Any]] = None


class InteractionTurn(BaseModel):
    """单次追问记录。"""
    turn_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    report_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    turn_index: Optional[int] = None
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    issue_ids: list[str] = Field(...)
    evidence_ids: list[str] = Field(...)
    statement_class: StatementClass
    created_at: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# 场景层 / Scenario layer
# ---------------------------------------------------------------------------


class ChangeItem(BaseModel):
    """单条变量注入。"""
    target_object_type: ChangeItemObjectType
    target_object_id: str = Field(..., min_length=1)
    field_path: str = Field(..., min_length=1)
    old_value: Any = None
    new_value: Any = None


class DiffEntry(BaseModel):
    """单争点差异条目。NO affected_party_ids per spec."""
    issue_id: str = Field(..., min_length=1)
    impact_description: str = Field(..., min_length=1)
    direction: DiffDirection


class Scenario(BaseModel):
    """场景对象。NO separate DiffSummary wrapper per spec."""
    scenario_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    baseline_run_id: str = Field(..., min_length=1)
    change_set: list[ChangeItem]
    diff_summary: Union[str, list[DiffEntry]] = Field(...)
    affected_issue_ids: list[str] = Field(default_factory=list)
    affected_evidence_ids: list[str] = Field(default_factory=list)
    status: ScenarioStatus


# ---------------------------------------------------------------------------
# 索引引用模型 / Index reference models
# ---------------------------------------------------------------------------


class MaterialRef(BaseModel):
    """材料索引引用。"""
    index_name: str = Field(default="material_index")
    object_type: str
    object_id: str = Field(..., min_length=1)
    storage_ref: str = Field(..., min_length=1)


class ArtifactRef(BaseModel):
    """产物索引引用。"""
    index_name: str = Field(default="artifact_index")
    object_type: str
    object_id: str = Field(..., min_length=1)
    storage_ref: str = Field(..., min_length=1)


class InputSnapshot(BaseModel):
    """运行输入快照。"""
    material_refs: list[MaterialRef] = Field(default_factory=list)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 基础设施 / Infrastructure
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMClient(Protocol):
    """LLM 客户端协议 — 单一定义来源。"""

    async def create_message(
        self,
        *,
        system: str,
        user: str,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        """发送消息并返回文本响应。"""
        ...


class ExtractionMetadata(BaseModel):
    """提取过程元信息，prompt_profile 持久化于此以支持重放。"""
    model_used: str = Field(default="")
    temperature: float = Field(default=0.0)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    prompt_profile: str = Field(default="")
    prompt_version: str = Field(default="")
    total_tokens: int = Field(default=0)


class Run(BaseModel):
    """执行快照，对应 schemas/procedure/run.schema.json。
    output_refs 接受 material_ref | artifact_ref（per B7 schema fix）。
    """
    run_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    workspace_id: str = Field(..., min_length=1)
    scenario_id: Optional[str] = None
    trigger_type: str = Field(..., min_length=1)
    input_snapshot: InputSnapshot
    output_refs: list[Union[MaterialRef, ArtifactRef]] = Field(default_factory=list)
    started_at: str
    finished_at: Optional[str] = None
    status: str


# ---------------------------------------------------------------------------
# 长任务层 / Long-running job layer
# ---------------------------------------------------------------------------


class JobError(BaseModel):
    """长任务结构化错误。对应 schemas/indexing.schema.json#/$defs/job_error。"""
    code: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    details: Optional[dict[str, Any]] = None


class Job(BaseModel):
    """长任务状态与进度追踪。对应 schemas/procedure/job.schema.json。

    model_validator 强制以下 invariants：
    - created:   progress=0.0, result_ref=null, error=null
    - pending:   0 <= progress < 1, result_ref=null, error=null
    - running:   0 <= progress < 1, result_ref=null, error=null
    - completed: progress=1.0, result_ref≠null, error=null
    - failed:    progress < 1, result_ref=null, error≠null
    - cancelled: progress < 1, result_ref=null, error=null
    """
    job_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    workspace_id: str = Field(..., min_length=1)
    job_type: str = Field(..., min_length=1)
    job_status: JobStatus
    progress: float = Field(..., ge=0.0, le=1.0)
    message: Optional[str] = None
    result_ref: Optional[ArtifactRef] = None
    error: Optional[JobError] = None
    created_at: str
    updated_at: str

    @model_validator(mode="after")
    def _validate_status_invariants(self) -> "Job":
        s = self.job_status
        p = self.progress
        r = self.result_ref
        e = self.error

        if s == JobStatus.created:
            if p != 0.0:
                raise ValueError("created job must have progress=0.0")
            if r is not None:
                raise ValueError("created job must have result_ref=null")
            if e is not None:
                raise ValueError("created job must have error=null")

        elif s in (JobStatus.pending, JobStatus.running):
            if p >= 1.0:
                raise ValueError(f"{s.value} job progress must be < 1.0")
            if r is not None:
                raise ValueError(f"{s.value} job must have result_ref=null")
            if e is not None:
                raise ValueError(f"{s.value} job must have error=null")

        elif s == JobStatus.completed:
            if p != 1.0:
                raise ValueError("completed job must have progress=1.0")
            if r is None:
                raise ValueError("completed job must have a valid result_ref")
            if e is not None:
                raise ValueError("completed job must have error=null")

        elif s == JobStatus.failed:
            if p >= 1.0:
                raise ValueError("failed job progress must be < 1.0")
            if r is not None:
                raise ValueError("failed job must have result_ref=null")
            if e is None:
                raise ValueError("failed job must have a structured error")

        elif s == JobStatus.cancelled:
            if p >= 1.0:
                raise ValueError("cancelled job progress must be < 1.0")
            if r is not None:
                raise ValueError("cancelled job must have result_ref=null")
            if e is not None:
                raise ValueError("cancelled job must have error=null")

        return self


# ---------------------------------------------------------------------------
# 对抗层 / Adversarial layer
# ---------------------------------------------------------------------------


class AgentOutput(BaseModel):
    """角色在某一程序回合的规范化输出。对应 docs/03_case_object_model.md AgentOutput。

    constraints（由 Field 约束强制）：
    - issue_ids:          非空（至少绑定一个争点）
    - evidence_citations: 非空（所有关键结论必须引用具体证据 ID）
    - round_index:        >= 0
    """
    output_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    state_id: str = Field(..., min_length=1)
    phase: ProcedurePhase
    round_index: int = Field(..., ge=0)
    agent_role_code: str = Field(..., min_length=1)
    owner_party_id: str = Field(..., min_length=1)
    issue_ids: list[str] = Field(
        ..., min_length=1, description="必须非空；每条输出都必须绑定至少一个争点"
    )
    title: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    evidence_citations: list[str] = Field(
        ..., min_length=1, description="必须非空；所有关键结论必须引用具体证据 ID"
    )
    statement_class: StatementClass
    risk_flags: list[str] = Field(
        default_factory=list,
        description="风险标记列表（自由字符串，如'越权风险'/'引用不足'/'程序冲突'）",
    )
    created_at: str
