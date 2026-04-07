"""
分析层模型 / Analysis layer models.

包含核心案件对象、报告产物、对抗层和所有分析结果模型。
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional, Union

from pydantic import BaseModel, Field, model_validator

from engines.shared.models.core import (
    AccessDomain,
    AdmissibilityStatus,
    AgentRole,
    AttackStrength,
    AuthenticityRisk,
    BurdenStatus,
    EvidenceStatus,
    EvidenceStrength,
    EvidenceType,
    ImpactTarget,
    IssueCategory,
    IssueStatus,
    IssueType,
    LegalityRisk,
    OutcomeImpact,
    OutcomeImpactSize,
    Perspective,
    PracticallyObtainable,
    ProbativeValue,
    ProcedurePhase,
    PropositionStatus,
    RecommendedAction,
    RelevanceScore,
    RiskImpactObject,
    StatementClass,
    SupplementCost,
    Vulnerability,
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
    admissibility_risk: Optional[str] = (
        None  # P1 新增：可采性风险说明（如来源争议、取证程序瑕疵等）
    )
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
        default=1.0,
        ge=0.0,
        le=1.0,
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
    # v7: 证据关联与对抗扩展字段
    admissibility_status: AdmissibilityStatus = Field(
        default=AdmissibilityStatus.clear,
        description="可采性状态枚举：clear/uncertain/weak/excluded（v7 可采性闸门）",
    )
    supports: list[str] = Field(
        default_factory=list,
        description="该证据支持的争点 issue_id 列表（正向关联）",
    )
    is_attacked_by: list[str] = Field(
        default_factory=list,
        description="攻击/反驳该证据的其他证据 evidence_id 列表",
    )
    stability_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="证据稳定性 (0-1)：即使被质证也不容易崩的程度。区别于 probative_value(冲击力)。"
        "stability_score 优先于 probative_value 参与排序。",
    )
    support_strength: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="证据支撑强度 (0-1)：表面直观说服力。",
    )
    counter_evidence_strength: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="对立证据强度 (0-1)：反驳该证据的力度。",
    )
    dispute_ratio: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="争议比 (0-1)：counter_evidence_strength / (support_strength + counter_evidence_strength)。"
        "高值表明该证据被强反证、排序时应自动降权。",
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
        default=None,
        ge=-100,
        le=100,
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
    # v7: 真正决定裁判的子问题（二-2）
    decisive_sub_question: Optional[str] = Field(
        default=None,
        description="真正决定裁判结果的核心子问题（如'借款合意是否成立'），由 LLM 评估填充",
    )


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


# LitigationHistory has been physically isolated to engines.shared.models.civil_loan
# (Unit 22 Phase B). It is re-exported below for backward compatibility, and
# Party.litigation_history is now typed as a neutral dict[str, Any] so that the
# generic case-object layer no longer carries民间借贷-specific fields.
from engines.shared.models.civil_loan import LitigationHistory  # noqa: F401  (re-export)


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
    # v1.5 bugfix: 职业放贷人检测扩展字段（Unit 22 Phase B 起改为 dict 以
    # 移除对 civil_loan 模型的硬依赖；调用方按 dict[str, Any] 读写，必要时
    # 通过 LitigationHistory.model_validate / model_dump 转换）
    litigation_history: Optional[dict[str, Any]] = None


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
    supporting_evidence_ids: list[str] = Field(..., description="至少一条支持该结论的证据 ID")
    supporting_output_ids: list[str] = Field(default_factory=list)


class ReportSection(BaseModel):
    """报告章节。v7 起每个 section 必须标注视角、置信度和依赖。"""

    section_id: str = Field(..., min_length=1)
    section_index: int = Field(..., ge=1)
    title: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    linked_issue_ids: list[str] = Field(default_factory=list)
    linked_output_ids: list[str] = Field(default_factory=list)
    linked_evidence_ids: list[str] = Field(..., description="章节引用的证据 ID 列表")
    key_conclusions: list[KeyConclusion] = Field(default_factory=list)
    # v7: section 顶部元数据
    perspective: Perspective = Field(
        default=Perspective.neutral,
        description="本 section 的视角：neutral=中立评估, plaintiff=原告策略, defendant=被告策略",
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="本 section 结论置信度 (0-1)",
    )
    section_depends_on: list[str] = Field(
        default_factory=list,
        description="本 section 依赖的其他 section_id 列表（用于一致性校验的拓扑排序）",
    )


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
    amendment_reason_issue_id: str = Field(
        ..., min_length=1, description="修改依据争点 ID（零容忍空值）"
    )
    amendment_reason_evidence_ids: list[str] = Field(
        default_factory=list, description="修改依据关联证据 ID 列表"
    )
    # v1.5: 路径-行动连接（medium closed loop）
    impacted_path_ids: list[str] = Field(
        default_factory=list,
        description="本建议影响的裁判路径 ID 列表（来自 P0.3 DecisionPath.path_id）",
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
    abandon_reason_issue_id: str = Field(
        ..., min_length=1, description="放弃依据争点 ID（零容忍空值）"
    )
    # v1.5: 路径-行动连接（medium closed loop）
    impacted_path_ids: list[str] = Field(
        default_factory=list,
        description="本建议影响的裁判路径 ID 列表（来自 P0.3 DecisionPath.path_id）",
    )


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
    # v1.5: 路径-行动连接（medium closed loop）
    impacted_path_ids: list[str] = Field(
        default_factory=list,
        description="本庭审事项影响的裁判路径 ID 列表（来自 P0.3 DecisionPath.path_id）",
    )


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


# ---------------------------------------------------------------------------
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
# v7：诉请拆分 / Claim decomposition  (修订清单 一-2)
# ---------------------------------------------------------------------------


class ClaimDecomposition(BaseModel):
    """拆分后的诉请结构（v7）。替代原 current_most_stable_claim 单一 str 字段。

    三个字段对应修订清单一-2 的要求：
    - formal_claim:            正式诉请金额（原告实际起诉数额）
    - fallback_anchor:         保底锚点/最有把握主张（路径树最现实路径支持的金额）
    - expected_recovery_range: 预期回收区间 [lower, upper]

    合约保证：
    - fallback_anchor <= formal_claim（路径树显示仅部分支持时自动下调）
    - expected_recovery_range.lower <= expected_recovery_range.upper
    """

    formal_claim: Decimal = Field(..., ge=0, description="正式诉请金额（原告实际起诉数额）")
    fallback_anchor: Decimal = Field(
        ..., ge=0, description="保底锚点：最有把握获得支持的金额（不高于 formal_claim）"
    )
    expected_recovery_lower: Decimal = Field(..., ge=0, description="预期回收区间下界")
    expected_recovery_upper: Decimal = Field(..., ge=0, description="预期回收区间上界")
    decomposition_rationale: str = Field(
        default="", description="拆分依据说明（路径树哪条路径支持哪部分金额）"
    )

    @model_validator(mode="after")
    def _validate_ranges(self) -> "ClaimDecomposition":
        if self.fallback_anchor > self.formal_claim:
            raise ValueError(
                f"fallback_anchor ({self.fallback_anchor}) 不得大于 "
                f"formal_claim ({self.formal_claim})"
            )
        if self.expected_recovery_lower > self.expected_recovery_upper:
            raise ValueError(
                f"expected_recovery_lower ({self.expected_recovery_lower}) 不得大于 "
                f"expected_recovery_upper ({self.expected_recovery_upper})"
            )
        return self


# ---------------------------------------------------------------------------
# v7：内部决策版本 / Internal decision summary  (修订清单 二-3)
# ---------------------------------------------------------------------------


class InternalDecisionSummary(BaseModel):
    """内部决策版本摘要（v7）。不对外展示，仅供律师/内部团队决策使用。

    包含：最可能输赢方向、最现实可回收金额、最先该补哪条证据。
    """

    most_likely_winner: str = Field(
        ..., description="最可能胜诉方：plaintiff / defendant / uncertain"
    )
    most_likely_winner_rationale: str = Field(default="", description="判断依据")
    realistic_recovery_amount: Optional[Decimal] = Field(
        default=None, ge=0, description="最现实可回收金额"
    )
    priority_evidence_to_supplement: Optional[str] = Field(
        default=None, description="最先应补强的证据 gap_id"
    )
    priority_supplement_rationale: str = Field(default="", description="补证优先理由")


# ---------------------------------------------------------------------------
# v7：一致性校验结果 / Consistency check result  (修订清单 一-3, 三, 四)
# ---------------------------------------------------------------------------


class ConsistencyCheckResult(BaseModel):
    """输出前一致性校验结果（v7）。附加在最终输出末尾。

    校验维度（修订清单四）：
    1. perspective_consistent:    视角一致性（同 section 不混用中立+一方策略）
    2. recommendation_consistent: 推荐一致性（推荐与路径树判断对齐）
    3. admissibility_gate_passed: 可采性闸门（程序性争点不因内容严重就置顶）
    4. strong_argument_demoted:   强论点降权（被强反证的证据已降权）
    5. action_stance_aligned:     行动建议对齐（建议方向与整体态势匹配）
    """

    overall_pass: bool = Field(..., description="全部校验通过为 True")
    perspective_consistent: bool = Field(default=True)
    recommendation_consistent: bool = Field(default=True)
    admissibility_gate_passed: bool = Field(default=True)
    strong_argument_demoted: bool = Field(default=True)
    action_stance_aligned: bool = Field(default=True)
    failures: list[str] = Field(
        default_factory=list,
        description="失败原因列表（why_fail）",
    )
    sections_to_regenerate: list[str] = Field(
        default_factory=list,
        description="因一致性检查失败需要重生成的 section_id 列表",
    )


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
    legal_clarity: float = Field(ge=0.0, le=1.0, description="法律适用清晰度（适用法条明确程度）")


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
    key_findings: list[str] = Field(default_factory=list, description="关键发现列表（每条一句话）")
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
    - amount_report_id 可为 None（amount_calculation_report 缺失时降级）
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
        strategic_summary:               核心策略摘要（来自 strategic_headline），无策略层时为 None
        amount_report_id:                绑定的 AmountCalculationReport.report_id（可回连）
        critical_evidence_gaps:          Top3 关键缺证 gap_id 列表（按 roi_rank 排序），或 "未启用"
        created_at:                      ISO-8601 时间戳（自动生成）
    """

    summary_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    top5_decisive_issues: list[str] = Field(
        ...,
        max_length=5,
        description="Top5 决定性争点 issue_id 列表（按 outcome_impact 排序，最多 5 条）",
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
    defense_chain_id: Optional[str] = Field(
        default=None,
        description="绑定的 PlaintiffDefenseChain.chain_id（可回连），防御链未启用时为 None",
    )
    # v7: 拆分后的诉请结构（替代原 current_most_stable_claim 单一 str）
    claim_decomposition: Optional[ClaimDecomposition] = Field(
        default=None,
        description="v7 诉请拆分：formal_claim + fallback_anchor + expected_recovery_range",
    )
    current_most_stable_claim: str = Field(
        default="",
        description="[已废弃] v6 最稳诉请文本，向后兼容保留。v7 起使用 claim_decomposition。",
    )
    strategic_summary: Optional[str] = Field(
        default=None,
        description="核心策略一句话摘要（来自 ActionRecommendation.strategic_headline + 金额附注），无策略层时为 None",
    )
    amount_report_id: Optional[str] = Field(
        default=None, description="绑定的 AmountCalculationReport.report_id（可回连，amount_calculation_report 缺失时为 None）"
    )
    critical_evidence_gaps: Union[list[str], str] = Field(
        ...,
        description="Top3 关键缺证 gap_id 列表（最多 3 条，按 roi_rank 排序），或 '未启用'（P1.7 缺失）",
    )
    structured_output: Optional[ExecutiveSummaryStructuredOutput] = Field(
        default=None,
        description="P2 结构化 JSON 输出（与叙述性输出并存，机器可读）",
    )
    # v7: 最终建议区固定输出字段（修订清单三）
    primary_risk: Optional[str] = Field(
        default=None,
        description="当前案件主要风险点（一句话）",
    )
    next_best_action: Optional[str] = Field(
        default=None,
        description="下一步最优行动建议（一句话）",
    )
    # v7: 内部决策版本（修订清单二-3）
    internal_decision_summary: Optional[InternalDecisionSummary] = Field(
        default=None,
        description="内部决策版本摘要：最可能输赢方向、最现实可回收金额、最先该补哪条证据",
    )
    # v7: 一致性校验结果（修订清单三末尾 + 四）
    consistency_check: Optional[ConsistencyCheckResult] = Field(
        default=None,
        description="输出前自动校验结果：pass/fail + why_fail + sections_to_regenerate",
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
