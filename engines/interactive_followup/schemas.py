"""
交互追问引擎数据模型 — 与 JSON Schema 定义对齐。
Interactive followup engine data models — aligned with JSON Schema definitions.

所有模型均使用 Pydantic v2，字段定义严格匹配：
All models use Pydantic v2, strictly aligned with:
- docs/03_case_object_model.md (InteractionTurn)
- schemas/reporting/report_artifact.schema.json
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 从 report_generation 复用的输入模型 / Re-exported input models
# ---------------------------------------------------------------------------

from engines.report_generation.schemas import (  # noqa: F401
    EvidenceIndex,
    EvidenceItem,
    FactProposition,
    Issue,
    IssueTree,
    ReportArtifact,
    ReportSection,
    KeyConclusion,
    StatementClass,
    Burden,
    ClaimIssueMapping,
    DefenseIssueMapping,
)


# ---------------------------------------------------------------------------
# 交互追问核心对象 / Core interactive followup objects
# ---------------------------------------------------------------------------


class InteractionTurn(BaseModel):
    """单次追问记录 / Single interaction turn record.

    合约约束 / Contract constraints (from docs/03_case_object_model.md):
    - issue_ids 不能为空 / issue_ids cannot be empty
    - evidence_ids 必须是报告已引用证据的子集 / evidence_ids must be subset of report evidence
    - answer 中的事实性断言必须有对应 evidence_id / factual claims must cite evidence
    """

    turn_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    report_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    turn_index: Optional[int] = Field(
        default=None,
        description="本轮在会话中的序号（1-based）/ Turn index in session (1-based)",
    )
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    issue_ids: list[str] = Field(
        ...,
        description="本轮追问绑定的争点 ID 列表，不能为空 / Bound issue IDs, must be non-empty",
    )
    evidence_ids: list[str] = Field(
        ...,
        description="本轮追问引用的证据 ID 列表 / Evidence IDs cited in this turn",
    )
    statement_class: StatementClass = Field(
        ...,
        description="回答陈述分类 / Answer statement classification",
    )
    created_at: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# LLM 中间结构 / LLM intermediate structures
# ---------------------------------------------------------------------------


class LLMCitationItem(BaseModel):
    """LLM 返回的单条证据引用。
    Single evidence citation as returned by LLM.
    """

    evidence_id: str
    quote: Optional[str] = None  # 引用的具体文本片段（可选）


class LLMFollowupOutput(BaseModel):
    """LLM 返回的追问响应（尚未规范化）。
    Followup response as returned by LLM (before normalization).
    """

    answer: str = Field(..., min_length=1)
    issue_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    statement_class: str = Field(
        default="inference",
        description="fact / inference / assumption",
    )
    citations: list[LLMCitationItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 追问会话高层模型 / Higher-level followup session models
# ---------------------------------------------------------------------------


class Citation(BaseModel):
    """规范化的证据引用 / Normalized evidence citation.

    与 LLMCitationItem 的区别：Citation 是对外输出的规范形式。
    Unlike LLMCitationItem, Citation is the normalized output form.
    """

    evidence_id: str = Field(..., min_length=1)
    quote: Optional[str] = None
    relevance: Optional[str] = None  # 引用相关性说明 / Relevance note


class FollowupQuestion(BaseModel):
    """追问输入包装 / Followup question input wrapper.

    封装用户追问及其上下文提示。
    Wraps the user question and optional context hints.
    """

    question: str = Field(..., min_length=1, description="用户追问文本 / User question text")
    hint_issue_ids: list[str] = Field(
        default_factory=list,
        description="问题可能相关的争点 ID 提示（可选）/ Hint issue IDs for relevance",
    )


class FollowupAnswer(BaseModel):
    """追问回答中间模型 / Followup answer intermediate model.

    由引擎生成，在规范化为 InteractionTurn 前的内部表示。
    Internal representation before normalization to InteractionTurn.
    """

    answer: str = Field(..., min_length=1)
    issue_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    statement_class: StatementClass = StatementClass.inference
    citations: list[Citation] = Field(default_factory=list)


class SessionState(BaseModel):
    """多轮追问会话状态 / Multi-turn followup session state.

    追踪一次完整的追问会话（绑定到特定报告）。
    Tracks a complete followup session bound to a specific report.
    """

    session_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    report_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    turns: list[InteractionTurn] = Field(default_factory=list)
    created_at: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

    @property
    def turn_count(self) -> int:
        """当前会话已完成的追问轮数 / Number of completed turns in this session."""
        return len(self.turns)
