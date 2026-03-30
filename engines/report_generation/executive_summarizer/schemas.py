"""
executive_summarizer 引擎专用数据模型。
Engine-specific schemas for executive_summarizer.

共享类型从 engines.shared.models 导入；本模块只保留引擎 I/O wrapper。
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from engines.shared.models import (  # noqa: F401
    ActionRecommendation,
    AmountCalculationReport,
    DecisionPathTree,
    EvidenceGapItem,
    ExecutiveSummaryArtifact,
    Issue,
    OptimalAttackChain,
)


class ExecutiveSummarizerInput(BaseModel):
    """
    ExecutiveSummarizer 输入 wrapper。

    Args:
        case_id:                    案件 ID
        run_id:                     运行快照 ID
        issue_list:                 含 P0.1 扩展字段的争点列表（按 outcome_impact 排序）
        adversary_attack_chain:     P0.4 对方最优攻击链（可为空 OptimalAttackChain）
        amount_calculation_report:  P0.2 金额一致性报告（必须）
        action_recommendation:      P1.8 行动建议产物（可选，None 时降级为"未启用"）
        evidence_gap_items:         P1.7 缺证项列表（可选，None 时降级为"未启用"）
        decision_path_tree:         P0.3 裁判路径树（v7 新增，用于诉请拆分和内部决策摘要）
    """
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    issue_list: list[Issue] = Field(default_factory=list)
    adversary_attack_chain: OptimalAttackChain
    amount_calculation_report: AmountCalculationReport
    action_recommendation: Optional[ActionRecommendation] = None
    evidence_gap_items: Optional[list[EvidenceGapItem]] = None
    decision_path_tree: Optional[DecisionPathTree] = Field(
        default=None,
        description="v7: P0.3 裁判路径树，用于诉请拆分（一-2）和内部决策摘要（二-3）",
    )
