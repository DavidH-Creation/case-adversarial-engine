# engines/shared/tests/test_rule_config.py
"""RuleThresholds 单元测试。"""

from decimal import Decimal
import pytest
from engines.shared.rule_config import RuleThresholds


class TestRuleThresholdsDefaults:
    def test_default_values(self):
        cfg = RuleThresholds()
        assert cfg.prof_lender_min_cases == 3
        assert cfg.prof_lender_min_borrowers == 3
        assert cfg.prof_lender_max_span_months == 24
        assert cfg.false_litigation_ratio == Decimal("2.0")
        assert cfg.lpr_multiplier_cap == Decimal("4.0")

    def test_custom_overrides(self):
        cfg = RuleThresholds(prof_lender_min_cases=5, false_litigation_ratio=Decimal("3.0"))
        assert cfg.prof_lender_min_cases == 5
        assert cfg.false_litigation_ratio == Decimal("3.0")
        # other defaults unchanged
        assert cfg.prof_lender_min_borrowers == 3

    def test_validation_min_cases_positive(self):
        with pytest.raises(ValueError):
            RuleThresholds(prof_lender_min_cases=0)

    def test_validation_ratio_positive(self):
        with pytest.raises(ValueError):
            RuleThresholds(false_litigation_ratio=Decimal("0"))
