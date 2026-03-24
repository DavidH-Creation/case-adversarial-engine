"""
报告生成引擎数据模型 — 与 JSON Schema 定义对齐。
Report generation engine data models — aligned with JSON Schema definitions.

所有模型均使用 Pydantic v2，字段定义严格匹配：
All models use Pydantic v2, strictly aligned with:
- schemas/reporting/report_artifact.schema.json
- schemas/case/issue_tree.schema.json
- schemas/case/evidence.schema.json
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 枚举类型 / Enum types
# ---------------------------------------------------------------------------


class StatementClass(str, Enum):
    """结论陈述分类，对应 docs/03_case_object_model.md statement_class 枚举。
    Statement classification per the case object model.
    """
    fact = "fact"           # 已证事实
    inference = "inference" # 推理结论
    assumption = "assumption"  # 假设前提


# ---------------------------------------------------------------------------
# 输入模型 / Input models
# ---------------------------------------------------------------------------


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
    """争点树输入 / IssueTree input, matching issue_tree.schema.json."""
    case_id: str = Field(..., min_length=1)
    run_id: Optional[str] = None
    job_id: Optional[str] = None
    issues: list[Issue]
    burdens: list[Burden]
    claim_issue_mapping: list[ClaimIssueMapping]
    defense_issue_mapping: list[DefenseIssueMapping]
    extraction_metadata: Optional[dict[str, Any]] = None


class EvidenceItem(BaseModel):
    """单条证据对象 / Single evidence item, matching evidence.schema.json."""
    evidence_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    owner_party_id: Optional[str] = None
    title: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    evidence_type: str
    target_fact_ids: list[str] = Field(default_factory=list)
    target_issue_ids: list[str] = Field(default_factory=list)
    access_domain: Optional[str] = None
    status: Optional[str] = None
    submitted_by_party_id: Optional[str] = None
    challenged_by_party_ids: list[str] = Field(default_factory=list)
    admissibility_notes: Optional[str] = None


class EvidenceIndex(BaseModel):
    """证据索引输入 / Evidence index input."""
    case_id: str
    evidence: list[EvidenceItem]
    extraction_metadata: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# 输出模型 / Output models
# ---------------------------------------------------------------------------


class KeyConclusion(BaseModel):
    """报告章节关键结论 / Key conclusion within a report section.

    合约约束 / Contract constraint:
    - supporting_evidence_ids 不能为空（citation_completeness = 100%）
    - statement_class 必须标注（fact / inference / assumption）
    """
    conclusion_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    statement_class: StatementClass
    supporting_evidence_ids: list[str] = Field(
        ...,
        description="至少一条支持该结论的证据 ID / At least one supporting evidence ID",
    )
    supporting_output_ids: list[str] = Field(default_factory=list)


class ReportSection(BaseModel):
    """报告章节 / Report section, matching the sections schema in report_artifact.schema.json."""
    section_id: str = Field(..., min_length=1)
    section_index: int = Field(..., ge=1)
    title: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1, description="章节正文 / Section body text")
    linked_issue_ids: list[str] = Field(default_factory=list)
    linked_output_ids: list[str] = Field(
        default_factory=list,
        description="回连推演输出 ID / Backlinks to AgentOutput IDs",
    )
    linked_evidence_ids: list[str] = Field(
        ...,
        description="章节引用的证据 ID 列表 / Evidence IDs cited in this section",
    )
    key_conclusions: list[KeyConclusion] = Field(default_factory=list)


class ReportArtifact(BaseModel):
    """诊断报告产物 / Diagnostic report artifact, matching report_artifact.schema.json.

    由 ReportGenerator 生成，必须满足以下合约：
    Generated by ReportGenerator, must satisfy:
    - citation_completeness = 100%
    - 覆盖所有顶层 Issue / Covers all root-level issues
    - summary ≤ 500 字 / Summary ≤ 500 characters
    - 零悬空引用 / Zero dangling references
    """
    report_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    summary: str = Field(
        ...,
        min_length=1,
        description="律师可在 5 分钟内读懂的报告摘要，≤500 字 / Lawyer-readable summary ≤500 chars",
    )
    sections: list[ReportSection]
    created_at: Optional[str] = None


# ---------------------------------------------------------------------------
# LLM 中间结构 / LLM intermediate structures
# ---------------------------------------------------------------------------


class LLMConclusionItem(BaseModel):
    """LLM 返回的单条关键结论（尚未分配 ID）。
    Single key conclusion as returned by LLM (before ID assignment).
    """
    text: str
    statement_class: str  # "fact" / "inference" / "assumption"
    supporting_evidence_ids: list[str] = Field(default_factory=list)


class LLMSectionItem(BaseModel):
    """LLM 返回的单个章节（尚未分配 ID）。
    Single section as returned by LLM (before ID assignment).
    """
    title: str
    body: str
    linked_issue_ids: list[str] = Field(default_factory=list)
    linked_evidence_ids: list[str] = Field(default_factory=list)
    key_conclusions: list[LLMConclusionItem] = Field(default_factory=list)


class LLMReportOutput(BaseModel):
    """LLM 返回的完整报告结构（尚未规范化）。
    Full report structure as returned by LLM (before normalization).
    """
    title: str
    summary: str
    sections: list[LLMSectionItem]
