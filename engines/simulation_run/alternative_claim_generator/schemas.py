"""
alternative_claim_generator 引擎专用数据模型。
Engine-specific schemas for alternative_claim_generator.

共享类型从 engines.shared.models 导入；本模块只保留：
- AlternativeClaimGeneratorInput：引擎输入 wrapper
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from engines.shared.models import (  # noqa: F401
    AlternativeClaimSuggestion,
    AmountCalculationReport,
    AttackStrength,
    EvidenceStrength,
    Issue,
    RecommendedAction,
)


class AlternativeClaimGeneratorInput(BaseModel):
    """
    AlternativeClaimGenerator 输入 wrapper。

    Args:
        case_id:        案件 ID
        run_id:         运行快照 ID
        issue_list:     含 P0.1 扩展字段的争点列表（可为空）
        amount_report:  P0.2 金额一致性报告（含 ClaimCalculationEntry.delta）
    """

    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    issue_list: list[Issue] = Field(default_factory=list, description="含 P0.1 扩展字段的争点列表")
    amount_report: AmountCalculationReport
