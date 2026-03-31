# engines/shared/rule_config.py
"""
集中式规则阈值配置 — 所有确定性规则的可调参数。
Centralized rule thresholds — configurable parameters for all deterministic rules.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class RuleThresholds(BaseModel):
    """规则引擎阈值配置。构造 Calculator/Scorer 时注入，测试时可覆盖。

    Args:
        prof_lender_min_cases:      职业放贷人：最低诉讼案件数
        prof_lender_min_borrowers:  职业放贷人：最低不同借款人数
        prof_lender_max_span_months: 职业放贷人：统计时间窗口（月）
        false_litigation_ratio:     虚假诉讼预警：起诉金额/可核实交付 比值上限
        lpr_multiplier_cap:         合同无效时 LPR 倍数上限
    """

    prof_lender_min_cases: int = Field(default=3, gt=0)
    prof_lender_min_borrowers: int = Field(default=3, gt=0)
    prof_lender_max_span_months: int = Field(default=24, gt=0)
    false_litigation_ratio: Decimal = Field(default=Decimal("2.0"), gt=0)
    lpr_multiplier_cap: Decimal = Field(default=Decimal("4.0"), gt=0)
