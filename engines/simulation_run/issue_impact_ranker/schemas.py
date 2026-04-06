"""
issue_impact_ranker 引擎专用数据模型。
Engine-specific schemas for issue_impact_ranker.

共享类型从 engines.shared.models 导入；本模块只保留输入/输出 wrapper 和 LLM 中间模型。
Shared types imported from engines.shared.models; this module only keeps
input/output wrappers and LLM intermediate models.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from engines.shared.models import (  # noqa: F401
    AmountCalculationReport,
    AttackStrength,
    EvidenceIndex,
    EvidenceStrength,
    ImpactTarget,
    IssueTree,
    OutcomeImpact,
    RecommendedAction,
)


# ---------------------------------------------------------------------------
# LLM 中间模型 / LLM intermediate models
# ---------------------------------------------------------------------------


class LLMSingleIssueEvaluation(BaseModel):
    """LLM 对单个争点的评估输出（中间模型，由规则层进一步校验）。
    LLM evaluation output for a single issue (intermediate model, validated by rule layer).
    """

    issue_id: str = Field(..., min_length=1)
    outcome_impact: str = Field(default="")
    impact_targets: list[str] = Field(default_factory=list)
    proponent_evidence_strength: str = Field(default="")
    proponent_evidence_ids: list[str] = Field(
        default_factory=list,
        description="支撑 proponent_evidence_strength 评估的证据 ID",
    )
    opponent_attack_strength: str = Field(default="")
    opponent_attack_evidence_ids: list[str] = Field(
        default_factory=list,
        description="支撑 opponent_attack_strength 评估的证据 ID",
    )
    recommended_action: str = Field(default="")
    recommended_action_basis: str = Field(
        default="",
        description="建议行动依据说明（必须非空，否则规则层丢弃 recommended_action）",
    )
    recommended_action_evidence_ids: list[str] = Field(default_factory=list)
    # v2: 加权评分维度（default=0，容忍 LLM 不返回）
    importance_score: int = Field(default=0, description="争点关键程度 0-100")
    swing_score: int = Field(default=0, description="结论翻转摆幅 0-100")
    evidence_strength_gap: int = Field(default=0, description="主张方证据优势度 -100~+100")
    dependency_depth: int = Field(default=0, description="争点依赖层级 0=根争点")
    credibility_impact: int = Field(default=0, description="对整案可信度冲击 0-100")


class LLMIssueEvaluationOutput(BaseModel):
    """LLM 批量评估输出（中间模型）。LLM batch evaluation output (intermediate model)."""

    evaluations: list[LLMSingleIssueEvaluation]


# ---------------------------------------------------------------------------
# 引擎 I/O wrapper / Engine I/O wrappers
# ---------------------------------------------------------------------------


class IssueImpactRankerInput(BaseModel):
    """IssueImpactRanker 输入 wrapper。

    Args:
        case_id:                    案件 ID
        run_id:                     运行快照 ID（写入元信息）
        issue_tree:                 待评估的争点树
        evidence_index:             证据索引
        amount_calculation_report:  P0.2 产物（案件无金额数据时为 None）
        proponent_party_id:         主张方 party_id，对应 Burden.burden_party_id
    """

    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    issue_tree: IssueTree
    evidence_index: EvidenceIndex
    amount_calculation_report: Optional[AmountCalculationReport] = None
    proponent_party_id: str = Field(
        ...,
        min_length=1,
        description="主张方 party_id，以 Burden.burden_party_id 确定角色",
    )


class IssueImpactRankingResult(BaseModel):
    """争点影响排序结果产物。纳入 CaseWorkspace.artifact_index。
    Issue impact ranking result artifact.

    ranked_issue_tree:      issues 已按 outcome_impact DESC 排序并富化
    evaluation_metadata:    LLM 调用元信息（model/timestamp/评估数量）
    unevaluated_issue_ids:  未能评估或校验失败的争点 ID（供审计）
    created_at:             ISO-8601 时间戳
    """

    ranked_issue_tree: IssueTree
    evaluation_metadata: dict[str, Any] = Field(default_factory=dict)
    unevaluated_issue_ids: list[str] = Field(default_factory=list)
    created_at: str
