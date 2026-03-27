"""
evidence_gap_roi_ranker 引擎专用数据模型。
Engine-specific schemas for evidence_gap_roi_ranker.

共享类型从 engines.shared.models 导入；本模块只保留：
- EvidenceGapDescriptor：调用方提供的单条缺证项描述符（不含 roi_rank）
- EvidenceGapRankerInput：排序器输入 wrapper
- EvidenceGapRankingResult：排序结果产物
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from engines.shared.models import (  # noqa: F401
    EvidenceGapItem,
    OutcomeImpactSize,
    PracticallyObtainable,
    SupplementCost,
)


class EvidenceGapDescriptor(BaseModel):
    """
    单条缺证项描述符 — 调用方提供的结构化缺证信息（不含 roi_rank）。

    roi_rank 由 EvidenceGapROIRanker 按规则层自动计算后填入 EvidenceGapItem。

    Args:
        gap_id:                  缺证项唯一标识
        related_issue_id:        关联争点 ID（必须绑定）
        gap_description:         缺证说明文字
        supplement_cost:         预计补证成本（high/medium/low）
        outcome_impact_size:     补证后对结果的影响大小（significant/moderate/marginal）
        practically_obtainable:  现实可取得性（yes/no/uncertain）
        alternative_evidence_paths: 替代证据路径说明列表
    """
    gap_id: str = Field(..., min_length=1, description="缺证项唯一标识")
    related_issue_id: str = Field(..., min_length=1, description="关联争点 ID，必须绑定")
    gap_description: str = Field(..., min_length=1, description="缺证说明")
    supplement_cost: SupplementCost
    outcome_impact_size: OutcomeImpactSize
    practically_obtainable: PracticallyObtainable
    alternative_evidence_paths: list[str] = Field(
        default_factory=list, description="替代证据路径说明"
    )


class EvidenceGapRankerInput(BaseModel):
    """
    EvidenceGapROIRanker 输入 wrapper。

    Args:
        case_id:    案件 ID
        run_id:     运行快照 ID（写入产物元信息）
        gap_items:  缺证项描述符列表（调用方提供，可为空）
    """
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    gap_items: list[EvidenceGapDescriptor] = Field(
        default_factory=list, description="缺证项描述符列表"
    )


class EvidenceGapRankingResult(BaseModel):
    """
    缺证 ROI 排序结果产物。纳入 CaseWorkspace.artifact_index。

    ranked_items:  已按 ROI 规则排序并分配 roi_rank 的 EvidenceGapItem 列表（roi_rank=1 优先）
    created_at:    ISO-8601 时间戳
    """
    case_id: str
    run_id: str
    ranked_items: list[EvidenceGapItem] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
