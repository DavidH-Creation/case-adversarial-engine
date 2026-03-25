"""
报告生成引擎数据模型。
Report generation engine data models.

共享类型从 engines.shared.models 导入；本模块只保留 LLM 中间结构。
Shared types imported from engines.shared.models; only LLM intermediate structures kept here.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

# 从共享模块导入所有共享类型（re-exported for backward compat）
from engines.shared.models import (  # noqa: F401
    Burden,
    BurdenStatus,
    ClaimIssueMapping,
    DefenseIssueMapping,
    EvidenceIndex,
    EvidenceStatus,
    EvidenceType,
    Evidence as EvidenceItem,  # backward compat alias
    Evidence,
    FactProposition,
    Issue,
    IssueStatus,
    IssueTree,
    IssueType,
    KeyConclusion,
    PropositionStatus,
    ReportArtifact,
    ReportSection,
    StatementClass,
)


# ---------------------------------------------------------------------------
# LLM 中间结构 / LLM intermediate structures
# ---------------------------------------------------------------------------


class LLMConclusionItem(BaseModel):
    """LLM 返回的单条关键结论（尚未分配 ID）。"""
    text: str
    statement_class: str  # "fact" / "inference" / "assumption"
    supporting_evidence_ids: list[str] = Field(default_factory=list)


class LLMSectionItem(BaseModel):
    """LLM 返回的单个章节（尚未分配 ID）。"""
    title: str
    body: str
    linked_issue_ids: list[str] = Field(default_factory=list)
    linked_evidence_ids: list[str] = Field(default_factory=list)
    key_conclusions: list[LLMConclusionItem] = Field(default_factory=list)


class LLMReportOutput(BaseModel):
    """LLM 返回的完整报告结构（尚未规范化）。"""
    title: str
    summary: str
    sections: list[LLMSectionItem]
