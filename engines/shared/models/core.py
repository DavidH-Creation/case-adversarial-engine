"""
核心枚举与基础类型 / Core enumerations and foundational types.

包含所有枚举、RawMaterial 输入模型，以及 LLMClient 协议定义。
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


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


class DisputeResolutionStatus(str, Enum):
    """争议解决状态。"""

    resolved = "resolved"
    unresolved = "unresolved"
    partially_resolved = "partially_resolved"


class OutcomeImpact(str, Enum):
    """争点对最终裁判结果的影响程度（P0.1）。"""

    high = "high"
    medium = "medium"
    low = "low"


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


class Perspective(str, Enum):
    """输出视角标注（v7）。每个 section/建议必须显式标注视角。"""

    neutral = "neutral"
    plaintiff = "plaintiff"
    defendant = "defendant"


class AdmissibilityStatus(str, Enum):
    """证据可采性状态（v7 可采性闸门）。"""

    clear = "clear"  # 证据可采性无争议
    uncertain = "uncertain"  # 可采性存疑
    weak = "weak"  # 可采性较弱，可能被排除
    excluded = "excluded"  # 已被排除


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


class BlockingConditionType(str, Enum):
    """阻断条件类型。"""

    amount_conflict = "amount_conflict"
    evidence_gap = "evidence_gap"
    procedure_unresolved = "procedure_unresolved"


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
# 基础设施协议 / Infrastructure protocol
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
