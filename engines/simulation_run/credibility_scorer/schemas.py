"""
credibility_scorer 引擎专用数据模型。
Engine-specific schemas for credibility_scorer.

共享类型从 engines.shared.models 导入；本模块只保留：
- CredibilityScorerInput：引擎输入 wrapper
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from engines.shared.models import (  # noqa: F401
    AmountCalculationReport,
    CredibilityDeduction,
    CredibilityScorecard,
    Evidence,
    Issue,
)


class CredibilityScorerInput(BaseModel):
    """
    CredibilityScorer 输入 wrapper。

    Args:
        case_id:        案件 ID
        run_id:         运行快照 ID
        amount_report:  P0.2 金额一致性报告（用于 CRED-01、CRED-03）
        evidence_list:  证据列表（用于 CRED-02、CRED-04、CRED-06）
        issue_list:     争点列表（用于 CRED-04、CRED-05）
    """
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    amount_report: AmountCalculationReport
    evidence_list: list[Evidence] = Field(default_factory=list)
    issue_list: list[Issue] = Field(default_factory=list)
