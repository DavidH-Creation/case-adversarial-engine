"""
争点抽取引擎数据模型。
Issue extractor engine data models.

共享类型从 engines.shared.models 导入；本模块只保留：
- 引擎专用 ExtractionMetadata（含 total_claims_processed 等统计字段）
- LLM 中间模型（LLMFactProposition, LLMIssueItem, LLMBurdenItem 等）
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

# 从共享模块导入所有共享类型 / Import all shared types (re-exported for backward compat)
from engines.shared.models import (  # noqa: F401
    Burden,
    BurdenStatus,
    ClaimIssueMapping,
    DefenseIssueMapping,
    EvidenceType,
    FactProposition,
    Issue,
    IssueStatus,
    IssueTree,
    IssueType,
    PropositionStatus,
)


# ---------------------------------------------------------------------------
# 引擎专用元信息 / Engine-specific extraction metadata
# ---------------------------------------------------------------------------


class ExtractionMetadata(BaseModel):
    """争点抽取过程元信息（含业务统计字段）。
    Issue extraction metadata with domain-specific statistics.
    """
    total_claims_processed: int = 0
    total_defenses_processed: int = 0
    total_evidence_referenced: int = 0
    extraction_timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        description="ISO 8601 格式时间戳",
    )


# ---------------------------------------------------------------------------
# LLM 中间结构 / LLM intermediate structures
# ---------------------------------------------------------------------------


class LLMFactProposition(BaseModel):
    """LLM 返回的事实命题（尚未分配ID）。"""
    text: str = ""
    status: str = "unverified"
    linked_evidence_ids: list[str] = Field(default_factory=list)


class LLMIssueItem(BaseModel):
    """LLM 返回的单个争点（使用临时ID引用）。"""
    tmp_id: str = Field(default="", description="临时ID，供本次输出内部引用")
    title: str = ""
    issue_type: str = "factual"
    parent_tmp_id: Optional[str] = None
    related_claim_ids: list[str] = Field(default_factory=list)
    related_defense_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    fact_propositions: list[LLMFactProposition] = Field(default_factory=list)


class LLMBurdenItem(BaseModel):
    """LLM 返回的举证责任（引用临时争点ID）。"""
    issue_tmp_id: str = ""
    burden_party_id: str = ""
    description: str = ""
    proof_standard: str = ""
    legal_basis: str = ""


class LLMClaimMapping(BaseModel):
    """LLM 返回的诉请→临时争点ID映射。"""
    claim_id: str = ""
    issue_tmp_ids: list[str] = Field(default_factory=list)


class LLMDefenseMapping(BaseModel):
    """LLM 返回的抗辩→临时争点ID映射。"""
    defense_id: str = ""
    issue_tmp_ids: list[str] = Field(default_factory=list)


class LLMExtractionOutput(BaseModel):
    """LLM 提取的完整结构化输出。
    临时ID由 IssueExtractor._build_issue_tree 替换为正式ID。
    """
    issues: list[LLMIssueItem] = Field(default_factory=list)
    burdens: list[LLMBurdenItem] = Field(default_factory=list)
    claim_issue_mapping: list[LLMClaimMapping] = Field(default_factory=list)
    defense_issue_mapping: list[LLMDefenseMapping] = Field(default_factory=list)
