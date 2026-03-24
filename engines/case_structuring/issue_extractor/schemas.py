"""
Pydantic 数据模型 — 与 JSON Schema 定义对齐。
Pydantic data models — aligned with JSON Schema definitions.

所有模型均使用 Pydantic v2，字段定义严格匹配
schemas/case/issue.schema.json 和 schemas/case/issue_tree.schema.json。
All models use Pydantic v2, aligned with issue.schema.json and issue_tree.schema.json.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 枚举类型 / Enumerations
# ---------------------------------------------------------------------------


class IssueType(str, Enum):
    """争点类型。Issue type enum.

    对应 issue.schema.json 中的 issue_type 枚举。
    Maps to the issue_type enum in issue.schema.json.
    """

    factual = "factual"        # 事实争点
    legal = "legal"            # 法律争点
    procedural = "procedural"  # 程序争点
    mixed = "mixed"            # 混合争点


class IssueStatus(str, Enum):
    """争点当前状态。Current status of an issue."""

    open = "open"
    resolved = "resolved"
    deferred = "deferred"


class PropositionStatus(str, Enum):
    """事实命题核实状态。Verification status of a fact proposition."""

    unverified = "unverified"
    supported = "supported"
    contradicted = "contradicted"
    disputed = "disputed"


class BurdenStatus(str, Enum):
    """举证责任完成状态。Status of burden of proof fulfillment."""

    met = "met"
    partially_met = "partially_met"
    not_met = "not_met"
    disputed = "disputed"


# ---------------------------------------------------------------------------
# 核心数据模型 / Core data models
# ---------------------------------------------------------------------------


class FactProposition(BaseModel):
    """
    事实命题 — 连接证据与争点的桥梁。
    Fact proposition — bridges evidence to issues.

    对应 issue.schema.json 中 fact_propositions 数组的元素结构。
    Corresponds to elements of fact_propositions array in issue.schema.json.
    """

    proposition_id: str = Field(..., min_length=1, description="事实命题唯一ID / Unique proposition ID")
    text: str = Field(..., min_length=1, description="命题文本 / Proposition text")
    status: PropositionStatus = PropositionStatus.unverified
    linked_evidence_ids: list[str] = Field(
        default_factory=list,
        description="支持或反驳该命题的证据ID列表 / Evidence IDs supporting or contradicting",
    )


class Issue(BaseModel):
    """
    争点对象，对应 schemas/case/issue.schema.json。
    Issue object, aligned with schemas/case/issue.schema.json.

    使用 parent_issue_id 表示层级关系（平铺列表，非嵌套JSON）。
    Hierarchy expressed via parent_issue_id (flat list, not nested JSON).
    """

    issue_id: str = Field(..., min_length=1, description="争点唯一ID / Unique issue ID")
    case_id: str = Field(..., min_length=1, description="所属案件ID / Owning case ID")
    title: str = Field(..., min_length=1, description="争点标题 / Issue title")
    issue_type: IssueType
    parent_issue_id: Optional[str] = Field(
        None,
        description="父争点ID，顶层争点为 null / Parent issue ID; null for root issues",
    )
    related_claim_ids: list[str] = Field(default_factory=list, description="关联诉请ID列表")
    related_defense_ids: list[str] = Field(default_factory=list, description="关联抗辩ID列表")
    evidence_ids: list[str] = Field(default_factory=list, description="关联证据ID列表")
    burden_ids: list[str] = Field(default_factory=list, description="关联举证责任ID列表")
    fact_propositions: list[FactProposition] = Field(
        default_factory=list,
        description="围绕该争点需判断的事实命题 / Fact propositions to be adjudicated",
    )
    status: IssueStatus = IssueStatus.open
    created_at: Optional[str] = Field(None, description="ISO 8601 datetime string")


class Burden(BaseModel):
    """
    举证责任对象，对应 docs/03_case_object_model.md 中的 Burden 定义。
    Burden of proof object, per Burden definition in docs/03_case_object_model.md.
    """

    burden_id: str = Field(..., min_length=1, description="举证责任唯一ID / Unique burden ID")
    case_id: str = Field(..., min_length=1)
    issue_id: str = Field(..., min_length=1, description="关联争点ID / Associated issue ID")
    bearer_party_id: str = Field(
        ..., min_length=1, description="承担举证责任的当事方 / Party bearing the burden"
    )
    description: str = Field(..., min_length=1, description="举证责任描述 / Burden description")
    proof_standard: str = Field(default="", description="证明标准 / Proof standard")
    legal_basis: str = Field(default="", description="法律依据 / Legal basis")
    status: BurdenStatus = BurdenStatus.not_met


class ClaimIssueMapping(BaseModel):
    """诉请到争点的映射。Mapping from a claim to its associated issues.

    合约约束：每个 Claim 至少映射一个 Issue。
    Contract constraint: each Claim must map to at least one Issue.
    """

    claim_id: str = Field(..., min_length=1)
    issue_ids: list[str] = Field(
        ..., min_length=1, description="至少映射一个争点 / Must reference at least one issue"
    )


class DefenseIssueMapping(BaseModel):
    """抗辩到争点的映射。Mapping from a defense to its associated issues.

    合约约束：每个 Defense 至少映射一个 Issue。
    Contract constraint: each Defense must map to at least one Issue.
    """

    defense_id: str = Field(..., min_length=1)
    issue_ids: list[str] = Field(
        ..., min_length=1, description="至少映射一个争点 / Must reference at least one issue"
    )


class ExtractionMetadata(BaseModel):
    """提取过程元信息，对应 issue_tree.schema.json 的 extraction_metadata 字段。
    Extraction process metadata, aligned with extraction_metadata in issue_tree.schema.json.
    """

    total_claims_processed: int = 0
    total_defenses_processed: int = 0
    total_evidence_referenced: int = 0
    extraction_timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        description="ISO 8601 格式时间戳 / ISO 8601 timestamp",
    )


class IssueTree(BaseModel):
    """
    争点树产物，对应 schemas/case/issue_tree.schema.json。
    IssueTree artifact, aligned with schemas/case/issue_tree.schema.json.

    由 IssueExtractor 生成，包含提取的争点、举证责任和映射关系。
    Generated by IssueExtractor; contains issues, burdens, and mappings.
    """

    case_id: str = Field(..., min_length=1)
    run_id: Optional[str] = None
    job_id: Optional[str] = None
    issues: list[Issue] = Field(default_factory=list)
    burdens: list[Burden] = Field(default_factory=list)
    claim_issue_mapping: list[ClaimIssueMapping] = Field(default_factory=list)
    defense_issue_mapping: list[DefenseIssueMapping] = Field(default_factory=list)
    extraction_metadata: Optional[ExtractionMetadata] = None


# ---------------------------------------------------------------------------
# LLM 返回的中间结构（解析 LLM JSON 输出用）
# LLM intermediate structures (for parsing LLM JSON output before ID assignment)
# ---------------------------------------------------------------------------


class LLMFactProposition(BaseModel):
    """LLM 返回的事实命题（尚未分配ID）。LLM-returned fact proposition before ID assignment."""

    text: str = ""
    status: str = "unverified"
    linked_evidence_ids: list[str] = Field(default_factory=list)


class LLMIssueItem(BaseModel):
    """LLM 返回的单个争点（使用临时ID引用）。LLM-returned issue item using temporary IDs."""

    tmp_id: str = Field(default="", description="临时ID，供本次输出内部引用 / Temp ID for internal cross-reference")
    title: str = ""
    issue_type: str = "factual"
    parent_tmp_id: Optional[str] = None
    related_claim_ids: list[str] = Field(default_factory=list)
    related_defense_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    fact_propositions: list[LLMFactProposition] = Field(default_factory=list)


class LLMBurdenItem(BaseModel):
    """LLM 返回的举证责任（引用临时争点ID）。LLM-returned burden item referencing temp issue ID."""

    issue_tmp_id: str = ""
    bearer_party_id: str = ""
    description: str = ""
    proof_standard: str = ""
    legal_basis: str = ""


class LLMClaimMapping(BaseModel):
    """LLM 返回的诉请→临时争点ID映射。LLM-returned claim-to-temp-issue mapping."""

    claim_id: str = ""
    issue_tmp_ids: list[str] = Field(default_factory=list)


class LLMDefenseMapping(BaseModel):
    """LLM 返回的抗辩→临时争点ID映射。LLM-returned defense-to-temp-issue mapping."""

    defense_id: str = ""
    issue_tmp_ids: list[str] = Field(default_factory=list)


class LLMExtractionOutput(BaseModel):
    """LLM 提取的完整结构化输出。Complete structured LLM extraction output.

    临时ID由 IssueExtractor._build_issue_tree 替换为正式ID。
    Temp IDs are replaced with proper IDs in IssueExtractor._build_issue_tree.
    """

    issues: list[LLMIssueItem] = Field(default_factory=list)
    burdens: list[LLMBurdenItem] = Field(default_factory=list)
    claim_issue_mapping: list[LLMClaimMapping] = Field(default_factory=list)
    defense_issue_mapping: list[LLMDefenseMapping] = Field(default_factory=list)
