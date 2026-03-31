"""
action_recommender 引擎专用数据模型。
Engine-specific schemas for action_recommender.

共享类型从 engines.shared.models 导入；本模块只保留：
- ActionRecommenderInput：引擎输入 wrapper
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from typing import Optional

from engines.shared.models import (  # noqa: F401
    ActionRecommendation,
    AmountCalculationReport,
    ClaimAbandonSuggestion,
    ClaimAmendmentSuggestion,
    DecisionPathTree,
    EvidenceGapItem,
    EvidenceIndex,
    Issue,
    TrialExplanationPriority,
)


class ActionRecommenderInput(BaseModel):
    """
    ActionRecommender 输入 wrapper。

    Args:
        case_id:                    案件 ID
        run_id:                     运行快照 ID
        issue_list:                 含 P0.1 扩展字段的争点列表（可为空）
        evidence_gap_list:          含 roi_rank 的缺证项列表（来自 P1.7，可为空）
        amount_calculation_report:  P0.2 金额一致性报告
        decision_path_tree:         P0.3 裁判路径树（v7 新增，用于推荐-路径对齐）
    """

    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    issue_list: list[Issue] = Field(default_factory=list, description="含 P0.1 扩展字段的争点列表")
    evidence_gap_list: list[EvidenceGapItem] = Field(
        default_factory=list, description="含 roi_rank 的缺证项列表（来自 P1.7）"
    )
    amount_calculation_report: AmountCalculationReport
    proponent_party_id: str = Field(
        default="", description="主张方 party_id（用于 party-specific 建议）"
    )
    evidence_index: Optional[EvidenceIndex] = Field(
        default=None, description="证据索引（LLM 策略层需要，纯规则层可省略）"
    )
    decision_path_tree: Optional[DecisionPathTree] = Field(
        default=None,
        description="v7: P0.3 裁判路径树，用于推荐一致性校验和行动对齐",
    )
