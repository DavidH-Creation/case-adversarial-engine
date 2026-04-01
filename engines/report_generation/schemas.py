"""
报告生成引擎数据模型。
Report generation engine data models.

共享类型从 engines.shared.models 导入；本模块只保留 LLM 中间结构。
Shared types imported from engines.shared.models; only LLM intermediate structures kept here.
"""

from __future__ import annotations

from enum import Enum
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


# ---------------------------------------------------------------------------
# 争点-证据-抗辩矩阵 / Issue-Evidence-Defense Matrix
# ---------------------------------------------------------------------------


class MatrixRow(BaseModel):
    """矩阵单行：一个争点及其关联证据和抗辩点。
    Matrix row: one issue with associated evidence IDs and defense point IDs.
    """

    issue_id: str
    issue_label: str
    issue_impact: str = ""  # high / medium / low / ""
    evidence_ids: list[str] = Field(default_factory=list)
    defense_ids: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    has_unrebutted_evidence: bool = False


class IssueEvidenceDefenseMatrix(BaseModel):
    """争点-证据-抗辩三维关联矩阵。
    Three-dimensional association matrix: IssueTree × EvidenceIndex × DefenseChain.

    rows 按 issue_impact 降序排列（high > medium > low）。
    Rows sorted by issue_impact descending (high > medium > low).
    """

    rows: list[MatrixRow] = Field(default_factory=list)
    total_issues: int = 0
    issues_with_evidence: int = 0


# ---------------------------------------------------------------------------
# 证据作战矩阵 / Evidence Battle Matrix (7-question per evidence, Layer 2.3)
# ---------------------------------------------------------------------------


class EvidenceBattleRow(BaseModel):
    """证据作战矩阵单行：一条证据与7个核心问题的答案。
    One evidence piece evaluated across 7 fixed questions.
    """

    evidence_id: str
    evidence_title: str
    target_issue_labels: list[str] = Field(default_factory=list)
    owner: str = ""                      # owner_party_id
    admissibility: str = ""             # admissibility_status.value
    opposition_challenges: list[str] = Field(default_factory=list)
    corroboration_count: int = 0        # count of evidences sharing same target issues
    stability_light: str = ""           # 🟢 绿 / 🟡 黄 / 🔴 红
    path_dependency_count: int = 0      # count of decision paths citing this evidence


class EvidenceBattleMatrix(BaseModel):
    """证据作战矩阵：每条证据7问分析。
    Evidence battle matrix: 7-question analysis per evidence piece.
    """

    rows: list[EvidenceBattleRow] = Field(default_factory=list)
    total_evidence: int = 0
    green_count: int = 0
    yellow_count: int = 0
    red_count: int = 0


# ---------------------------------------------------------------------------
# 角色化视角 / Perspective (F1)
# ---------------------------------------------------------------------------


class Perspective(str, Enum):
    """报告视角 / Report perspective."""

    PLAINTIFF = "plaintiff"
    DEFENDANT = "defendant"
    JUDGE = "judge"
    NEUTRAL = "neutral"


class PerspectiveCard(BaseModel):
    """角色化视角卡片（Layer 1 Block B + Layer 3 的数据源）。
    Perspective card: data source for Layer 1 Block B and Layer 3 role output.
    """

    perspective: Perspective
    top_strengths: list[str] = Field(default_factory=list)   # max 3
    top_dangers: list[str] = Field(default_factory=list)     # max 2
    priority_actions: list[str] = Field(default_factory=list)  # max 3
    relevant_paths: list[str] = Field(default_factory=list)  # path_ids


# ---------------------------------------------------------------------------
# 结构化输出路径 / Structured outcome paths
# ---------------------------------------------------------------------------


class OutcomePathType(str, Enum):
    """结构化输出路径类型 / Outcome path type."""

    WIN = "WIN"
    LOSE = "LOSE"
    MEDIATION = "MEDIATION"
    SUPPLEMENT = "SUPPLEMENT"


class OutcomePath(BaseModel):
    """单条结构化输出路径。
    Structured outcome path (pure aggregation, no LLM).
    """

    path_type: OutcomePathType
    trigger_conditions: list[str] = Field(default_factory=list)
    key_actions: list[str] = Field(default_factory=list)
    required_evidence_ids: list[str] = Field(default_factory=list)
    risk_points: list[str] = Field(default_factory=list)
    source_artifact: str = Field(default="")


class CaseOutcomePaths(BaseModel):
    """四路径结构化输出聚合。
    Aggregated 4-path outcome structure for a case.
    """

    win_path: OutcomePath
    lose_path: OutcomePath
    mediation_path: OutcomePath
    supplement_path: OutcomePath


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
