"""
admissibility_evaluator 引擎专用数据模型。
Engine-specific schemas for admissibility_evaluator.

共享类型从 engines.shared.models 导入；本模块只保留 LLM 中间模型、引擎 I/O wrapper 和
simulate_exclusion 输出类型（ImpactReport）。
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from engines.shared.models import (  # noqa: F401
    DecisionPathTree,
    EvidenceIndex,
    IssueTree,
    OptimalAttackChain,
)


# ---------------------------------------------------------------------------
# LLM 中间模型 / LLM intermediate models
# ---------------------------------------------------------------------------


class LLMAdmissibilityItem(BaseModel):
    """LLM 输出的单条证据可采性评估（中间模型，由规则层进一步校验）。"""

    evidence_id: str = Field(default="")
    admissibility_score: float = Field(default=1.0)  # 规则层校验 0.0–1.0
    admissibility_challenges: list[str] = Field(default_factory=list)
    exclusion_impact: Optional[str] = None  # 排除后对案件的影响


class LLMAdmissibilityOutput(BaseModel):
    """LLM 批量输出（中间模型）。"""

    evidence_assessments: list[LLMAdmissibilityItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 引擎 I/O wrapper / Engine I/O wrapper
# ---------------------------------------------------------------------------


class AdmissibilityEvaluatorInput(BaseModel):
    """AdmissibilityEvaluator 输入 wrapper。

    Args:
        case_id:        案件 ID
        run_id:         运行快照 ID（写入产物元信息）
        evidence_index: 待评估的完整证据索引
    """

    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    evidence_index: EvidenceIndex


# ---------------------------------------------------------------------------
# ImpactReport — simulate_exclusion 输出类型
# ---------------------------------------------------------------------------

ExclusionSeverity = Literal["case_breaking", "significant", "manageable", "negligible"]


class IssueImpact(BaseModel):
    """单争点受排除证据影响的评估。"""

    issue_id: str = Field(..., min_length=1)
    issue_title: str = Field(default="")
    loses_primary_evidence: bool = Field(
        default=False,
        description="该争点是否因此失去其主要证据支撑（证据仅有此一份或此为最强支撑）",
    )
    remaining_evidence_ids: list[str] = Field(
        default_factory=list,
        description="排除后该争点剩余的证据 ID 列表",
    )
    impact_severity: ExclusionSeverity = Field(
        default="negligible",
        description="排除对该争点的影响严重程度",
    )


class PathImpact(BaseModel):
    """单裁判路径受排除证据影响的评估。"""

    path_id: str = Field(..., min_length=1)
    becomes_nonviable: bool = Field(
        default=False,
        description="该路径是否因证据排除而不可行（证据在 admissibility_gate 中）",
    )
    impact_description: str = Field(default="")


class ChainImpact(BaseModel):
    """单攻击链受排除证据影响的评估。"""

    chain_id: str = Field(..., min_length=1)
    owner_party_id: str = Field(default="")
    broken_attack_node_ids: list[str] = Field(
        default_factory=list,
        description="失去证据支撑的攻击节点 ID 列表",
    )
    impact_description: str = Field(default="")


class ImpactReport(BaseModel):
    """simulate_exclusion 输出：单份证据被排除后对全链路的影响报告。"""

    excluded_evidence_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    affected_issues: list[IssueImpact] = Field(default_factory=list)
    affected_paths: list[PathImpact] = Field(default_factory=list)
    affected_chains: list[ChainImpact] = Field(default_factory=list)
    overall_severity: ExclusionSeverity = Field(
        default="negligible",
        description="整体排除影响严重程度：case_breaking > significant > manageable > negligible",
    )
    summary: str = Field(default="")
