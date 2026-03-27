"""
executive_summary_generator 引擎专用数据模型。
Engine-specific schemas for executive_summary_generator.

共享类型从 engines.shared.models 导入；本模块只保留：
- ExecutiveSummaryGeneratorInput：引擎输入 wrapper
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from engines.shared.models import (  # noqa: F401
    ActionRecommendation,
    AmountCalculationReport,
    EvidenceGapItem,
    ExecutiveSummaryArtifact,
    Issue,
    OptimalAttackChain,
)


class ExecutiveSummaryGeneratorInput(BaseModel):
    """
    ExecutiveSummaryGenerator 输入 wrapper。

    Args:
        case_id:                  案件 ID
        run_id:                   运行快照 ID
        issue_list:               含 P0.1 扩展字段的争点列表（可为空）
        optimal_attack_chains:    P0.4 最优攻击链列表（传入对方的链，可为空）
        amount_calculation_report: P0.2 金额一致性报告
        action_recommendation:    P1.8 行动建议产物（可为 None，缺失时降级）
        evidence_gap_list:        P1.7 缺证 ROI 排序列表（可为 None，缺失时降级）
    """
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    issue_list: list[Issue] = Field(
        default_factory=list,
        description="含 P0.1 扩展字段的争点列表",
    )
    optimal_attack_chains: list[OptimalAttackChain] = Field(
        default_factory=list,
        description="P0.4 最优攻击链列表（通常为对方的链）",
    )
    amount_calculation_report: AmountCalculationReport
    action_recommendation: Optional[ActionRecommendation] = Field(
        default=None,
        description="P1.8 行动建议产物；None 时 top3_immediate_actions 降级为 '未启用'",
    )
    evidence_gap_list: Optional[list[EvidenceGapItem]] = Field(
        default=None,
        description="P1.7 缺证 ROI 列表；None 时 critical_evidence_gaps 降级为 '未启用'",
    )
