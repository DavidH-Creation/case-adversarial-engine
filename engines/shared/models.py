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
from decimal import Decimal
from enum import Enum
from typing import Any, Optional, Protocol, Union, runtime_checkable

from pydantic import BaseModel, Field, field_validator, model_validator


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
    labor_dispute = "labor_dispute"
    real_estate = "real_estate"


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


class ProcedureState(BaseModel):
    """程序阶段的访问控制状态 — v1.5 新增。

    当传递给 AccessController.filter_evidence_for_agent() 时，
    在角色级规则之上叠加阶段级过滤：
    - evidence.access_domain 必须在 readable_access_domains 内
    - evidence.status 必须在 admissible_evidence_statuses 内
    """
    phase: ProcedurePhase
    readable_access_domains: list[AccessDomain]
    admissible_evidence_statuses: list[EvidenceStatus]


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


class RiskImpactObject(str, Enum):
    """风险影响对象维度枚举。对应 docs/03_case_object_model.md risk_impact_object。"""
    win_rate = "win_rate"
    supported_amount = "supported_amount"
    trial_credibility = "trial_credibility"
    procedural_stability = "procedural_stability"
    evidence_supplement_cost = "evidence_supplement_cost"


class AgentRole(str, Enum):
    """代理角色编码。对应 docs/03_case_object_model.md Party.role_code 和 AgentOutput.agent_role_code。"""
    plaintiff_agent = "plaintiff_agent"
    defendant_agent = "defendant_agent"
    judge_agent = "judge_agent"
    evidence_manager = "evidence_manager"


class RepaymentAttribution(str, Enum):
    """还款归因类型 — 每笔还款必须唯一归因到某一类。"""
    principal = "principal"
    interest = "interest"
    penalty = "penalty"


class DisputeResolutionStatus(str, Enum):
    """争议解决状态。"""
    resolved = "resolved"
    unresolved = "unresolved"
    partially_resolved = "partially_resolved"


class ClaimType(str, Enum):
    """诉请类型 — 对应 ClaimCalculationEntry.claim_type。"""
    principal = "principal"
    interest = "interest"
    penalty = "penalty"
    attorney_fee = "attorney_fee"
    other = "other"


class OutcomeImpact(str, Enum):
    """争点对最终裁判结果的影响程度（P0.1）。"""
    high = "high"
    medium = "medium"
    low = "low"


class ImpactTarget(str, Enum):
    """争点影响的诉请对象（P0.1）。"""
    principal = "principal"
    interest = "interest"
    penalty = "penalty"
    attorney_fee = "attorney_fee"
    credibility = "credibility"


class EvidenceStrength(str, Enum):
    """主张方证据强度（P0.1）。"""
    strong = "strong"
    medium = "medium"
    weak = "weak"


class AttackStrength(str, Enum):
    """反对方攻击强度（P0.1）。"""
    strong = "strong"
    medium = "medium"
    weak = "weak"


class RecommendedAction(str, Enum):
    """系统建议行动（P0.1）。"""
    supplement_evidence = "supplement_evidence"
    amend_claim = "amend_claim"
    abandon = "abandon"
    explain_in_trial = "explain_in_trial"


class AuthenticityRisk(str, Enum):
    """证据真实性风险（P1.5）。"""
    high = "high"
    medium = "medium"
    low = "low"


class SupplementCost(str, Enum):
    """补证成本（P1.7）。"""
    high = "high"
    medium = "medium"
    low = "low"


class RelevanceScore(str, Enum):
    """证据关联性（P1.5）。"""
    strong = "strong"
    medium = "medium"
    weak = "weak"


class ProbativeValue(str, Enum):
    """证据证明力（P1.5）。"""
    strong = "strong"
    medium = "medium"
    weak = "weak"


class Vulnerability(str, Enum):
    """证据易受对方攻击的风险（P1.5）。"""
    high = "high"
    medium = "medium"
    low = "low"


class LegalityRisk(str, Enum):
    """证据合法性风险（v1.5 质证四维度之一）。"""
    high = "high"
    medium = "medium"
    low = "low"


class ContractValidity(str, Enum):
    """合同效力状态 — 影响利息计算标准。"""
    valid = "valid"
    disputed = "disputed"
    invalid = "invalid"


class IssueCategory(str, Enum):
    """争点分析类型（P1.6）。与 issue_type 并列，不替代。"""
    fact_issue = "fact_issue"
    legal_issue = "legal_issue"
    calculation_issue = "calculation_issue"
    procedure_credibility_issue = "procedure_credibility_issue"


class OutcomeImpactSize(str, Enum):
    """补证后对结果的影响大小（P1.7）。"""
    significant = "significant"
    moderate = "moderate"
    marginal = "marginal"


class PracticallyObtainable(str, Enum):
    """证据现实可取得性（P1.7）。"""
    yes = "yes"
    no = "no"
    uncertain = "uncertain"


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
    admissibility_risk: Optional[str] = None  # P1 新增：可采性风险说明（如来源争议、取证程序瑕疵等）
    # P1.5: 证据权重评分扩展字段（向后兼容，全部 Optional）
    authenticity_risk: Optional[AuthenticityRisk] = None
    relevance_score: Optional[RelevanceScore] = None
    probative_value: Optional[ProbativeValue] = None
    legality_risk: Optional[LegalityRisk] = None
    vulnerability: Optional[Vulnerability] = None
    evidence_weight_scored: bool = False
    # P2.9: 可信度折损扩展字段（向后兼容，Optional/默认值）
    is_copy_only: bool = Field(default=False, description="关键证据仅有复印件无原件（CRED-02）")
    # 可采性门控扩展字段（向后兼容，全部有默认值）
    admissibility_score: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="证据可采性评分 (1.0=完全可采, 0.0=被排除；由 AdmissibilityEvaluator 填充)",
    )
    admissibility_challenges: list[str] = Field(
        default_factory=list,
        description="证据被质疑可采性的理由列表（如录音合法性、传闻规则等）",
    )
    exclusion_impact: Optional[str] = Field(
        default=None,
        description="该证据被排除后对案件的影响描述（由 AdmissibilityEvaluator 填充）",
    )


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
    # P0.1: 争点影响排序扩展字段（向后兼容，全部 Optional）
    outcome_impact: Optional[OutcomeImpact] = None
    impact_targets: list[ImpactTarget] = Field(default_factory=list)
    proponent_evidence_strength: Optional[EvidenceStrength] = None
    opponent_attack_strength: Optional[AttackStrength] = None
    recommended_action: Optional[RecommendedAction] = None
    recommended_action_basis: Optional[str] = None  # recommended_action 的依据说明
    # P0.1 v2: 加权评分维度（向后兼容，全部 Optional）
    importance_score: Optional[int] = Field(
        default=None, ge=0, le=100, description="争点对最终裁判的关键程度 (0-100)"
    )
    swing_score: Optional[int] = Field(
        default=None, ge=0, le=100, description="争点结论翻转对结果的摆幅 (0-100)"
    )
    evidence_strength_gap: Optional[int] = Field(
        default=None, ge=-100, le=100,
        description="主张方证据强度减去反对方攻击强度 (-100 to +100)",
    )
    dependency_depth: Optional[int] = Field(
        default=None, ge=0, description="0=根争点，1+=依赖上游争点"
    )
    credibility_impact: Optional[int] = Field(
        default=None, ge=0, le=100, description="对整案可信度的冲击 (0-100)"
    )
    composite_score: Optional[float] = Field(
        default=None, description="加权综合分（规则层计算，越高越重要）"
    )
    # P1.6: 争点类型分类扩展字段（向后兼容，Optional）
    issue_category: Optional[IssueCategory] = None
    # P1 新增：争点依赖关系（上游争点 issue_id 列表；空列表表示根争点）
    depends_on: list[str] = Field(default_factory=list)


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


class LitigationHistory(BaseModel):
    """当事人近期放贷诉讼统计 — 职业放贷人检测输入。"""
    lending_case_count: int = Field(default=0, ge=0, description="近期放贷诉讼数")
    distinct_borrower_count: int = Field(default=0, ge=0, description="不同借款人数")
    total_lending_amount: Decimal = Field(default=Decimal("0"), ge=0, description="累计放贷金额")
    time_span_months: int = Field(default=0, ge=0, description="统计时间跨度（月）")
    uniform_contract_detected: bool = Field(default=False, description="借条格式是否雷同")


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
    # v1.5 bugfix: 职业放贷人检测扩展字段
    litigation_history: Optional[LitigationHistory] = None


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


class RiskFlag(BaseModel):
    """风险标记结构体。对应 docs/03_case_object_model.md RiskFlag。

    constraints:
    - flag_id:               非空
    - description:           非空（对应原 str 内容，保持语义兼容）
    - impact_objects:        impact_objects_scored=True 时必须非空
    - impact_objects_scored: False 表示过渡期自动升级的旧数据
    """
    flag_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    impact_objects: list[RiskImpactObject] = Field(default_factory=list)
    impact_objects_scored: bool = Field(default=True)

    @model_validator(mode="after")
    def _check_impact_objects_when_scored(self) -> "RiskFlag":
        if self.impact_objects_scored and len(self.impact_objects) == 0:
            raise ValueError(
                "impact_objects must not be empty when impact_objects_scored=True; "
                "set impact_objects_scored=False for legacy-migrated data"
            )
        return self


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
    risk_flags: list[RiskFlag] = Field(
        default_factory=list,
        description="风险标记列表。v1.5 起只接受 RiskFlag 对象，不再接受 str。",
    )
    created_at: str


# ---------------------------------------------------------------------------
# 金额计算层 / Amount calculation layer  (P0.2)
# ---------------------------------------------------------------------------


class LoanTransaction(BaseModel):
    """放款流水记录。每笔放款对应一条。"""
    tx_id: str = Field(..., min_length=1, description="流水唯一标识")
    date: str = Field(..., min_length=1, description="放款日期，格式 YYYY-MM-DD")
    amount: Decimal = Field(..., gt=0, description="放款金额，必须大于零")
    evidence_id: str = Field(..., min_length=1, description="关联放款凭证 evidence_id")
    principal_base_contribution: bool = Field(
        ..., description="是否计入本金基数；True 表示该笔放款为主张本金的组成部分"
    )


class RepaymentTransaction(BaseModel):
    """还款流水记录。每笔还款对应一条，必须唯一归因。"""
    tx_id: str = Field(..., min_length=1, description="流水唯一标识")
    date: str = Field(..., min_length=1, description="还款日期，格式 YYYY-MM-DD")
    amount: Decimal = Field(..., gt=0, description="还款金额，必须大于零")
    evidence_id: str = Field(..., min_length=1, description="关联还款凭证 evidence_id")
    attributed_to: Optional[RepaymentAttribution] = Field(
        None, description="归因类型；None 表示尚未归因（触发 all_repayments_attributed=False）"
    )
    attribution_basis: str = Field(default="", description="归因依据说明")


class DisputedAmountAttribution(BaseModel):
    """争议款项归因记录。记录原被告对同一笔款项的不同立场。"""
    item_id: str = Field(..., min_length=1, description="争议条目唯一标识")
    amount: Decimal = Field(..., gt=0, description="争议金额")
    dispute_description: str = Field(..., min_length=1, description="争议说明")
    plaintiff_attribution: str = Field(default="", description="原告立场")
    defendant_attribution: str = Field(default="", description="被告立场")
    resolution_status: DisputeResolutionStatus = DisputeResolutionStatus.unresolved


class ClaimCalculationEntry(BaseModel):
    """诉请计算表中的单行记录。"""
    claim_id: str = Field(..., min_length=1, description="关联 Claim.claim_id")
    claim_type: ClaimType
    claimed_amount: Decimal = Field(..., ge=0, description="诉请金额（由调用方提供）")
    calculated_amount: Optional[Decimal] = Field(
        None, description="系统可复算金额；None 表示该类型无法从流水确定性计算"
    )
    delta: Optional[Decimal] = Field(
        None, description="claimed_amount - calculated_amount；None 当 calculated_amount 为 None"
    )
    delta_explanation: str = Field(default="", description="差值说明")


class AmountConflict(BaseModel):
    """金额口径冲突记录。每个未解释冲突对应一条。"""
    conflict_id: str = Field(..., min_length=1, description="冲突唯一标识")
    conflict_description: str = Field(..., min_length=1, description="冲突描述")
    amount_a: Decimal = Field(..., description="第一种口径的金额")
    amount_b: Decimal = Field(..., description="第二种口径的金额")
    source_a_evidence_id: str = Field(default="", description="口径 A 的证据来源")
    source_b_evidence_id: str = Field(default="", description="口径 B 的证据来源")
    resolution_note: str = Field(default="", description="解释说明；空字符串表示无解释")


class AmountConsistencyCheck(BaseModel):
    """五条硬校验规则的聚合结果。"""
    principal_base_unique: bool = Field(
        ..., description="本金基数是否唯一确定：无未解决的本金口径冲突"
    )
    all_repayments_attributed: bool = Field(
        ..., description="每笔还款是否唯一归因：所有 RepaymentTransaction.attributed_to 非 None"
    )
    text_table_amount_consistent: bool = Field(
        ..., description="文本与表格金额是否一致：所有可复算诉请的 delta == 0"
    )
    duplicate_interest_penalty_claim: bool = Field(
        ..., description="是否存在利息/违约金重复请求：同类型诉请出现超过一条"
    )
    claim_total_reconstructable: bool = Field(
        ..., description="诉请总额是否可从流水复算：所有可复算诉请的 delta 均为零"
    )
    unresolved_conflicts: list[AmountConflict] = Field(
        default_factory=list,
        description="未解释的金额口径冲突列表；非空时触发 verdict_block_active"
    )
    verdict_block_active: bool = Field(
        ..., description="系统是否因未解释冲突阻断稳定裁判判断；硬规则：unresolved_conflicts 非空时必须为 True"
    )
    claim_delivery_ratio_normal: bool = Field(
        default=True,
        description="起诉金额与可核实交付金额比值是否正常（ratio <= 阈值）",
    )

    @model_validator(mode="after")
    def _enforce_verdict_block_rule(self) -> "AmountConsistencyCheck":
        """硬规则：unresolved_conflicts 非空时 verdict_block_active 必须为 True。"""
        if self.unresolved_conflicts and not self.verdict_block_active:
            raise ValueError(
                "verdict_block_active 必须为 True 当 unresolved_conflicts 非空"
            )
        return self


class AmountCalculationReport(BaseModel):
    """金额/诉请一致性硬校验报告。P0.2 产物，纳入 CaseWorkspace.artifact_index。"""
    report_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    loan_transactions: list[LoanTransaction] = Field(
        ..., description="放款流水表"
    )
    repayment_transactions: list[RepaymentTransaction] = Field(
        ..., description="还款流水表"
    )
    disputed_amount_attributions: list[DisputedAmountAttribution] = Field(
        default_factory=list, description="争议款项归因表"
    )
    claim_calculation_table: list[ClaimCalculationEntry] = Field(
        ..., description="诉请计算表"
    )
    consistency_check_result: AmountConsistencyCheck = Field(
        ..., description="一致性校验结果（五条硬规则）"
    )
    interest_recalculation: Optional["InterestRecalculation"] = Field(
        default=None, description="合同无效/争议时的利息重算记录"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


class InterestRecalculation(BaseModel):
    """利息重算记录 — 合同无效时的利率切换结果。

    注：interest_amount 字段为单期概念金额（principal × rate），用于对比利率切换
    前后的差额比例。如需精算利息金额，下游应结合实际借贷期限重新计算。
    """
    original_rate: Decimal = Field(..., description="原合同约定利率")
    effective_rate: Decimal = Field(..., description="重算后适用利率")
    rate_basis: str = Field(..., min_length=1, description="利率依据（如 LPR、LPR*4）")
    contract_validity: ContractValidity
    original_interest_amount: Decimal = Field(..., description="单期概念利息 = principal × original_rate")
    recalculated_interest_amount: Decimal = Field(..., description="单期概念利息 = principal × effective_rate")
    delta: Decimal = Field(..., description="利息差额 = original - recalculated（同期比较）")


# ---------------------------------------------------------------------------
# 裁判路径树 / Decision path tree  (P0.3)
# ---------------------------------------------------------------------------


class BlockingConditionType(str, Enum):
    """阻断条件类型。"""
    amount_conflict = "amount_conflict"
    evidence_gap = "evidence_gap"
    procedure_unresolved = "procedure_unresolved"


class ConfidenceInterval(BaseModel):
    """置信度区间。仅在 verdict_block_active=False 时允许填写。"""
    lower: float = Field(..., ge=0.0, le=1.0, description="置信度区间下界 [0,1]")
    upper: float = Field(..., ge=0.0, le=1.0, description="置信度区间上界 [0,1]")

    @model_validator(mode="after")
    def _lower_le_upper(self) -> "ConfidenceInterval":
        if self.lower > self.upper:
            raise ValueError(f"lower ({self.lower}) must be <= upper ({self.upper})")
        return self


class PathRankingItem(BaseModel):
    """路径概率排序条目。DecisionPathTree.path_ranking 列表元素。"""
    path_id: str = Field(..., min_length=1, description="路径 ID")
    probability: float = Field(..., ge=0.0, le=1.0, description="路径触发概率")
    party_favored: str = Field(..., description="对哪方有利：plaintiff / defendant / neutral")
    key_conditions: list[str] = Field(
        default_factory=list, description="触发本路径需满足的关键条件（文字描述列表）"
    )


class DecisionPath(BaseModel):
    """单条裁判路径。"""
    path_id: str = Field(..., min_length=1)
    trigger_condition: str = Field(..., min_length=1, description="触发本路径的关键条件描述")
    trigger_issue_ids: list[str] = Field(default_factory=list, description="触发条件关联的争点 ID 列表")
    key_evidence_ids: list[str] = Field(
        default_factory=list,
        description="本路径依赖的关键证据 ID 列表（仅含支持本路径结论的证据）",
    )
    counter_evidence_ids: list[str] = Field(
        default_factory=list,
        description="与本路径结论相悖的证据 ID 列表（反驳/对立证据，不得与 key_evidence_ids 重叠）",
    )
    possible_outcome: str = Field(..., min_length=1, description="可能的裁判结果描述")
    confidence_interval: Optional[ConfidenceInterval] = Field(
        default=None, description="置信度区间；verdict_block_active=True 时必须为 None"
    )
    path_notes: str = Field(default="", description="路径备注")
    # v1.5: 路径可执行化扩展字段
    admissibility_gate: list[str] = Field(
        default_factory=list,
        description="本路径成立前提：哪些证据必须被法庭采信（evidence_id 列表）",
    )
    result_scope: list[str] = Field(
        default_factory=list,
        description="裁判范围标签：principal/interest/liability_allocation 等",
    )
    fallback_path_id: Optional[str] = Field(
        default=None, description="本路径失败时降级到哪条路径的 path_id"
    )
    # v1.6: 概率评分
    probability: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="路径触发概率（0-1），基于证据支撑度、阻断条件可满足性及法律先例对齐度",
    )
    probability_rationale: str = Field(
        default="", description="概率评估依据（支撑证据质量、阻断条件满足情况等）"
    )
    party_favored: str = Field(
        default="neutral",
        description="本路径结果对哪方有利：plaintiff / defendant / neutral",
    )


class BlockingCondition(BaseModel):
    """阻断稳定判断的条件。"""
    condition_id: str = Field(..., min_length=1)
    condition_type: BlockingConditionType
    description: str = Field(..., min_length=1)
    linked_issue_ids: list[str] = Field(default_factory=list)
    linked_evidence_ids: list[str] = Field(default_factory=list)


class DecisionPathTree(BaseModel):
    """裁判路径树。P0.3 产物，纳入 CaseWorkspace.artifact_index（由调用方负责注册，同 P0.1/P0.2）。
    替代 AdversarialSummary.overall_assessment 的段落式综合评估。
    overall_assessment 的汇总填充（各路径 possible_outcome 摘要）由调用方负责，不在本模块实现。
    """
    tree_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    paths: list[DecisionPath] = Field(default_factory=list, description="裁判路径列表（建议 3-6 条）")
    blocking_conditions: list[BlockingCondition] = Field(
        default_factory=list, description="当前阻断稳定判断的条件列表"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    # v1.6: 路径概率比较结果
    most_likely_path: Optional[str] = Field(
        default=None, description="概率最高的路径 ID"
    )
    plaintiff_best_path: Optional[str] = Field(
        default=None, description="对原告最有利的路径 ID（plaintiff_favored 路径中概率最高）"
    )
    defendant_best_path: Optional[str] = Field(
        default=None, description="对被告最有利的路径 ID（defendant_favored 路径中概率最高）"
    )
    path_ranking: list[PathRankingItem] = Field(
        default_factory=list, description="路径按概率降序排列的排名列表"
    )


# ---------------------------------------------------------------------------
# P0.4：最强攻击链
# ---------------------------------------------------------------------------


class AttackNode(BaseModel):
    """单个攻击节点。OptimalAttackChain.top_attacks 列表元素（规则层保证恰好 3 个）。"""
    attack_node_id: str = Field(..., min_length=1, description="攻击节点唯一标识")
    target_issue_id: str = Field(..., min_length=1, description="攻击目标争点 ID")
    attack_description: str = Field(..., min_length=1, description="攻击论点描述")
    success_conditions: str = Field(default="", description="攻击成功条件")
    supporting_evidence_ids: list[str] = Field(
        ..., min_length=1, description="支撑此攻击点的证据 ID 列表（不得为空）"
    )
    counter_measure: str = Field(default="", description="我方对此攻击点的反制动作")
    adversary_pivot_strategy: str = Field(
        default="", description="对方补证后我方策略切换说明"
    )


class OptimalAttackChain(BaseModel):
    """某一方的最优攻击顺序与反制准备。P0.4 产物，纳入 CaseWorkspace.artifact_index。
    为原告和被告各生成一份。
    """
    chain_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    owner_party_id: str = Field(..., min_length=1, description="生成方当事人 ID")
    top_attacks: list[AttackNode] = Field(
        default_factory=list,
        description="最优攻击点，规则层保证恰好 3 个；LLM 失败时为空列表",
    )
    recommended_order: list[str] = Field(
        default_factory=list,
        description="推荐攻击顺序（有序 attack_node_id 列表），与 top_attacks 完全对应",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


# ---------------------------------------------------------------------------
# P1.7：缺证 ROI 排序 / Evidence gap ROI ranking
# ---------------------------------------------------------------------------


class EvidenceGapItem(BaseModel):
    """缺证项及其补证价值评估。P1.7 产物，纳入 CaseWorkspace.artifact_index。

    roi_rank 由规则层（EvidenceGapROIRanker）自动计算，调用方不得手动赋值。
    """
    gap_id: str = Field(..., min_length=1, description="缺证项唯一标识")
    case_id: str = Field(..., min_length=1, description="案件 ID")
    run_id: str = Field(..., min_length=1, description="运行快照 ID")
    related_issue_id: str = Field(..., min_length=1, description="关联争点 ID，必须绑定")
    gap_description: str = Field(..., min_length=1, description="缺证说明")
    supplement_cost: SupplementCost = Field(..., description="预计补证成本")
    outcome_impact_size: OutcomeImpactSize = Field(..., description="补证后预计对结果的影响大小")
    practically_obtainable: PracticallyObtainable = Field(..., description="现实中是否可取得")
    alternative_evidence_paths: list[str] = Field(
        default_factory=list, description="替代证据路径说明"
    )
    roi_rank: int = Field(..., ge=1, description="ROI 排序序号（规则层自动计算，1=最高优先）")


# ---------------------------------------------------------------------------
# P1.8：行动建议引擎 / Action recommendation  (P1.8)
# ---------------------------------------------------------------------------


class ClaimAmendmentSuggestion(BaseModel):
    """建议修改诉请条目（P1.8）。P2.11 实装后，同一 original_claim_id 的详细替代方案由
    AlternativeClaimSuggestion 提供并替代本条目。

    Args:
        suggestion_id:                  建议条目唯一标识
        original_claim_id:              关联原始 Claim.claim_id
        amendment_description:          建议修改方向（简要，不含完整替代文本）
        amendment_reason_issue_id:      修改依据绑定争点 ID（零容忍空值）
        amendment_reason_evidence_ids:  修改依据关联证据 ID 列表（可为空列表）
    """
    suggestion_id: str = Field(..., min_length=1)
    original_claim_id: str = Field(..., min_length=1)
    amendment_description: str = Field(..., min_length=1, description="简要修改方向")
    amendment_reason_issue_id: str = Field(..., min_length=1, description="修改依据争点 ID（零容忍空值）")
    amendment_reason_evidence_ids: list[str] = Field(
        default_factory=list, description="修改依据关联证据 ID 列表"
    )


class ClaimAbandonSuggestion(BaseModel):
    """建议放弃诉请条目（P1.8）。每条必须绑定 issue_id 和放弃理由——零容忍。

    Args:
        suggestion_id:           建议条目唯一标识
        claim_id:                建议放弃的 Claim.claim_id
        abandon_reason:          放弃理由（非空）
        abandon_reason_issue_id: 放弃依据争点 ID（零容忍空值）
    """
    suggestion_id: str = Field(..., min_length=1)
    claim_id: str = Field(..., min_length=1)
    abandon_reason: str = Field(..., min_length=1, description="放弃理由（零容忍空值）")
    abandon_reason_issue_id: str = Field(..., min_length=1, description="放弃依据争点 ID（零容忍空值）")


class TrialExplanationPriority(BaseModel):
    """庭审中优先解释事项（P1.8）。每条必须绑定 issue_id——零容忍。

    Args:
        priority_id:      条目唯一标识
        issue_id:         绑定争点 ID（零容忍空值）
        explanation_text: 需解释的事项描述（非空）
    """
    priority_id: str = Field(..., min_length=1)
    issue_id: str = Field(..., min_length=1, description="绑定争点 ID（零容忍空值）")
    explanation_text: str = Field(..., min_length=1, description="庭审解释事项说明")


class StrategicRecommendation(BaseModel):
    """案型适配的策略性建议（P1.8 v2）。由 LLM 策略层生成。"""
    recommendation_text: str = Field(..., min_length=1, description="策略建议文本")
    target_party: str = Field(
        ..., min_length=1, description="建议针对的当事方类型：plaintiff / defendant"
    )
    linked_issue_ids: list[str] = Field(default_factory=list, description="建议关联的争点 ID")
    priority: int = Field(default=1, ge=1, le=5, description="优先级 1-5, 1=最高")
    rationale: str = Field(default="", description="策略依据说明")


class PartyActionPlan(BaseModel):
    """单方行动计划（P1.8 v2）。聚合规则层结构行动和 LLM 策略建议。"""
    party_type: str = Field(..., min_length=1, description="plaintiff / defendant")
    structural_actions: list[str] = Field(
        default_factory=list, description="来自规则层的行动 ID 列表"
    )
    strategic_recommendations: list[StrategicRecommendation] = Field(
        default_factory=list, description="来自 LLM 的策略性建议"
    )


class ActionRecommendation(BaseModel):
    """行动建议产物（P1.8）。纳入 CaseWorkspace.artifact_index。

    在 report_generation 阶段由 ActionRecommender 生成，依赖 P0.1 争点分析和 P1.7 ROI 排序结果。

    Args:
        recommendation_id:              产物唯一标识
        case_id:                        案件 ID
        run_id:                         运行快照 ID
        recommended_claim_amendments:   建议修改诉请条目列表（ClaimAmendmentSuggestion[]）
        evidence_supplement_priorities: 建议补强证据的 gap_id 列表（按 ROI 排序）
        trial_explanation_priorities:   庭审优先解释事项列表（每条绑定 issue_id）
        claims_to_abandon:              建议放弃诉请条目列表（ClaimAbandonSuggestion[]）
        created_at:                     ISO-8601 时间戳（自动生成）
    """
    recommendation_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    recommended_claim_amendments: list[ClaimAmendmentSuggestion] = Field(default_factory=list)
    evidence_supplement_priorities: list[str] = Field(
        default_factory=list, description="gap_id 列表，按 ROI 降序排列（roi_rank=1 在前）"
    )
    trial_explanation_priorities: list[TrialExplanationPriority] = Field(default_factory=list)
    claims_to_abandon: list[ClaimAbandonSuggestion] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    # P1.8 v2: 案型适配扩展字段（向后兼容，全部 Optional）
    plaintiff_action_plan: Optional[PartyActionPlan] = None
    defendant_action_plan: Optional[PartyActionPlan] = None
    case_dispute_category: Optional[str] = Field(
        default=None,
        description="案件争议类别: amount_dispute / borrower_identity / contract_validity / ...",
    )
    strategic_headline: Optional[str] = Field(
        default=None, description="核心策略一句话（替代 amount-centric 最稳诉请）"
    )


# ---------------------------------------------------------------------------
# 可信度折损模型 / Credibility Scorecard  (P2.9)
# ---------------------------------------------------------------------------


class CredibilityDeduction(BaseModel):
    """单条可信度扣分项。由规则层生成，不允许 LLM 修改。"""
    deduction_id: str = Field(..., min_length=1, description="扣分项唯一 ID")
    rule_id: str = Field(..., min_length=1, description="触发规则编号，如 CRED-01")
    rule_description: str = Field(..., min_length=1, description="规则描述")
    deduction_points: int = Field(..., lt=0, description="扣分分值（负整数）")
    trigger_evidence_ids: list[str] = Field(
        default_factory=list, description="触发该规则的证据 ID 列表"
    )
    trigger_issue_ids: list[str] = Field(
        default_factory=list, description="触发该规则的争点 ID 列表"
    )


class CredibilityScorecard(BaseModel):
    """案件整体可信度折损评分卡。P2.9 产物，纳入 CaseWorkspace.artifact_index。

    base_score 固定为 100，final_score = base_score + sum(d.deduction_points)。
    final_score < 60 时，report_engine 须在报告显著位置标注可信度警告。
    """
    scorecard_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    base_score: int = Field(default=100, description="基础分（满分 100）")
    deductions: list[CredibilityDeduction] = Field(
        default_factory=list, description="触发的扣分项列表"
    )
    final_score: int = Field(..., description="最终得分 = base_score + sum(deduction_points)")
    summary: str = Field(..., min_length=1, description="可信度摘要说明")

    @model_validator(mode="after")
    def _validate_final_score(self) -> "CredibilityScorecard":
        """硬规则：final_score 必须等于 base_score + sum(deduction_points)。"""
        expected = self.base_score + sum(d.deduction_points for d in self.deductions)
        if self.final_score != expected:
            raise ValueError(
                f"final_score ({self.final_score}) 必须等于 "
                f"base_score + sum(deductions) ({expected})"
            )
        return self

# P2.11：替代主张自动生成 / Alternative claim generation  (P2.11)
# ---------------------------------------------------------------------------


class AlternativeClaimSuggestion(BaseModel):
    """替代主张建议（P2.11）。当原主张不稳定时自动生成更稳固的替代版本。

    触发条件（规则层，不调用 LLM）：
    1. Issue.recommended_action = amend_claim
    2. Issue.proponent_evidence_strength = weak 且 opponent_attack_strength = strong
    3. ClaimCalculationEntry.delta 绝对值超过 claimed_amount × 10%

    合约保证：
    - instability_issue_ids 非空（零容忍空列表）——min_length=1 强制
    - instability_evidence_ids 允许为空（Issue 本身可能无证据 ID，设计决策：绑定关系
      通过字段存在性体现，而非强制非空）
    - alternative_claim_text 必须具体可执行（非泛化建议）
    - supporting_evidence_ids 来自触发该建议的争点 evidence_ids

    Args:
        suggestion_id:            建议唯一标识
        case_id:                  案件 ID
        run_id:                   运行快照 ID
        original_claim_id:        关联原始 Claim.claim_id
        instability_reason:       不稳定原因文本（绑定 instability_issue_ids 和 instability_evidence_ids）
        instability_issue_ids:    原因绑定争点 ID 列表（非空，零容忍）
        instability_evidence_ids: 原因绑定证据 ID 列表（可为空列表，见合约保证说明）
        alternative_claim_text:   替代主张文本（具体可执行，非泛化）
        stability_rationale:      替代主张更稳固的理由
        supporting_evidence_ids:  支持替代主张的证据 ID 列表
        created_at:               ISO-8601 时间戳（自动生成）
    """
    suggestion_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    original_claim_id: str = Field(..., min_length=1, description="关联原始 Claim.claim_id")
    instability_reason: str = Field(..., min_length=1, description="原主张不稳定原因文本")
    instability_issue_ids: list[str] = Field(
        ..., min_length=1, description="绑定争点 ID 列表（零容忍空列表）"
    )
    instability_evidence_ids: list[str] = Field(
        default_factory=list, description="绑定证据 ID 列表（可为空，争点无证据时为空列表）"
    )
    alternative_claim_text: str = Field(
        ..., min_length=1, description="替代主张文本（具体可执行，不允许泛化建议）"
    )
    stability_rationale: str = Field(..., min_length=1, description="替代主张更稳固的理由")
    supporting_evidence_ids: list[str] = Field(
        default_factory=list, description="支持替代主张的证据 ID 列表"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


# ---------------------------------------------------------------------------
# P2.12：双层输出 / Executive summary artifact  (P2.12)
# ---------------------------------------------------------------------------


class ConfidenceMetrics(BaseModel):
    """执行摘要置信度指标（P2 结构化输出）。

    Args:
        overall_confidence:     整体置信度（0.0-1.0）
        evidence_completeness:  证据完整度（0.0-1.0）
        legal_clarity:          法律适用清晰度（0.0-1.0）
    """
    overall_confidence: float = Field(
        ge=0.0, le=1.0, description="整体置信度（基于证据充分性和法律依据清晰度）"
    )
    evidence_completeness: float = Field(
        ge=0.0, le=1.0, description="证据完整度（已有证据覆盖争点的比例）"
    )
    legal_clarity: float = Field(
        ge=0.0, le=1.0, description="法律适用清晰度（适用法条明确程度）"
    )


class ExecutiveSummaryStructuredOutput(BaseModel):
    """执行摘要结构化 JSON 输出（P2 双层输出）。

    与现有叙述性输出并存，提供机器可读的结构化摘要。

    Args:
        case_overview:          案件概述（1-3 句话的文字摘要）
        key_findings:           关键发现列表（每条为 1 句话的具体发现）
        risk_assessment:        风险评估摘要（指明主要风险点）
        recommended_actions:    建议行动列表（具体可执行，按优先级排序）
        confidence_metrics:     置信度指标
    """
    case_overview: str = Field(..., min_length=1, description="案件概述文本")
    key_findings: list[str] = Field(
        default_factory=list, description="关键发现列表（每条一句话）"
    )
    risk_assessment: str = Field(default="", description="风险评估摘要")
    recommended_actions: list[str] = Field(
        default_factory=list, description="建议行动列表（按优先级排序）"
    )
    confidence_metrics: ConfidenceMetrics


class ExecutiveSummaryArtifact(BaseModel):
    """一页式执行摘要（P2.12）。附加产物，不替代长报告 ReportArtifact。

    聚合 P0.1-P1.8 全量产物中的关键决策信息。P1.7/P1.8 缺失时对应字段降级为 "未启用"。

    合约保证：
    - top5_decisive_issues 最多 5 条（Issue 数不足时小于 5 条）
    - top3_immediate_actions 为 list 时：list 长度 ≤ 3；action_recommendation_id 必须非 None
    - top3_adversary_optimal_attacks 最多 3 条（AttackChain top_attacks 不足时可更少）
    - adversary_attack_chain_id 非空（P0.4 必须实现）
    - amount_report_id 非空（P0.2 必须实现）
    - critical_evidence_gaps 为 list 时：list 长度 ≤ 3

    Args:
        summary_id:                      产物唯一标识
        case_id:                         案件 ID
        run_id:                          运行快照 ID
        top5_decisive_issues:            Top5 决定性争点 issue_id 列表（按 outcome_impact 排序）
        top3_immediate_actions:          Top3 立即行动 suggestion_id/gap_id 列表，或 "未启用"
        action_recommendation_id:        绑定的 ActionRecommendation.recommendation_id（可回连）
        top3_adversary_optimal_attacks:  Top3 对方最优攻击 attack_node_id 列表
        adversary_attack_chain_id:       绑定的 OptimalAttackChain.chain_id（可回连）
        current_most_stable_claim:       最稳诉请版本说明文本（绑定 amount_report_id）
        amount_report_id:                绑定的 AmountCalculationReport.report_id（可回连）
        critical_evidence_gaps:          Top3 关键缺证 gap_id 列表（按 roi_rank 排序），或 "未启用"
        created_at:                      ISO-8601 时间戳（自动生成）
    """
    summary_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    top5_decisive_issues: list[str] = Field(
        ..., max_length=5, description="Top5 决定性争点 issue_id 列表（按 outcome_impact 排序，最多 5 条）"
    )
    top3_immediate_actions: Union[list[str], str] = Field(
        ...,
        description="Top3 立即行动 suggestion_id/gap_id 列表（最多 3 条），或 '未启用'（P1.8 缺失）",
    )
    action_recommendation_id: Optional[str] = Field(
        default=None,
        description="绑定的 ActionRecommendation.recommendation_id；top3_immediate_actions 为 list 时必须非 None",
    )
    top3_adversary_optimal_attacks: list[str] = Field(
        ..., max_length=3, description="Top3 对方最优攻击 attack_node_id 列表（最多 3 条）"
    )
    adversary_attack_chain_id: str = Field(
        ..., min_length=1, description="绑定的 OptimalAttackChain.chain_id（可回连）"
    )
    current_most_stable_claim: str = Field(
        ..., min_length=1, description="最稳诉请版本说明文本（绑定 amount_report_id）"
    )
    amount_report_id: str = Field(
        ..., min_length=1, description="绑定的 AmountCalculationReport.report_id（可回连）"
    )
    critical_evidence_gaps: Union[list[str], str] = Field(
        ...,
        description="Top3 关键缺证 gap_id 列表（最多 3 条，按 roi_rank 排序），或 '未启用'（P1.7 缺失）",
    )
    structured_output: Optional[ExecutiveSummaryStructuredOutput] = Field(
        default=None,
        description="P2 结构化 JSON 输出（与叙述性输出并存，机器可读）",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    @model_validator(mode="after")
    def _check_traceability(self) -> "ExecutiveSummaryArtifact":
        """硬规则：list 字段长度约束 + traceability。

        1. top3_immediate_actions 为列表时：长度 ≤ 3，action_recommendation_id 必须非 None
        2. critical_evidence_gaps 为列表时：长度 ≤ 3
        """
        if isinstance(self.top3_immediate_actions, list):
            if len(self.top3_immediate_actions) > 3:
                raise ValueError(
                    f"top3_immediate_actions list must have at most 3 items, "
                    f"got {len(self.top3_immediate_actions)}"
                )
            if self.action_recommendation_id is None:
                raise ValueError(
                    "action_recommendation_id must be set when top3_immediate_actions is a list"
                )
        if isinstance(self.critical_evidence_gaps, list) and len(self.critical_evidence_gaps) > 3:
            raise ValueError(
                f"critical_evidence_gaps list must have at most 3 items, "
                f"got {len(self.critical_evidence_gaps)}"
            )
        return self
