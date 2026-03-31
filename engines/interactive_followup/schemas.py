"""
交互追问引擎数据模型。
Interactive followup engine data models.

共享类型从 engines.shared.models 导入；本模块只保留追问会话专用类型和 LLM 中间结构。
Shared types imported from engines.shared.models; only followup session types and LLM intermediate structures kept here.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

# 从共享模块导入所有共享类型（re-exported for backward compat）
from engines.shared.models import (  # noqa: F401
    Burden,
    ClaimIssueMapping,
    DefenseIssueMapping,
    EvidenceIndex,
    Evidence as EvidenceItem,  # backward compat alias
    Evidence,
    EvidenceStatus,
    EvidenceType,
    FactProposition,
    InteractionTurn,
    Issue,
    IssueTree,
    KeyConclusion,
    ReportArtifact,
    ReportSection,
    StatementClass,
)


# ---------------------------------------------------------------------------
# LLM 中间结构 / LLM intermediate structures
# ---------------------------------------------------------------------------


class LLMCitationItem(BaseModel):
    """LLM 返回的单条证据引用。"""

    evidence_id: str
    quote: Optional[str] = None


class LLMFollowupOutput(BaseModel):
    """LLM 返回的追问响应（尚未规范化）。"""

    answer: str = Field(..., min_length=1)
    issue_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    statement_class: str = Field(default="inference")
    citations: list[LLMCitationItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 追问会话高层模型 / Higher-level followup session models
# ---------------------------------------------------------------------------


class Citation(BaseModel):
    """规范化的证据引用。"""

    evidence_id: str = Field(..., min_length=1)
    quote: Optional[str] = None
    relevance: Optional[str] = None


class FollowupQuestion(BaseModel):
    """追问输入包装。"""

    question: str = Field(..., min_length=1)
    hint_issue_ids: list[str] = Field(default_factory=list)


class FollowupAnswer(BaseModel):
    """追问回答中间模型（在规范化为 InteractionTurn 前的内部表示）。"""

    answer: str = Field(..., min_length=1)
    issue_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    statement_class: StatementClass = StatementClass.inference
    citations: list[Citation] = Field(default_factory=list)


class SessionState(BaseModel):
    """多轮追问会话状态。"""

    session_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    report_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    turns: list[InteractionTurn] = Field(default_factory=list)
    created_at: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

    @property
    def turn_count(self) -> int:
        """当前会话已完成的追问轮数。"""
        return len(self.turns)
