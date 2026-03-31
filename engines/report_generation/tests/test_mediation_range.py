"""
mediation_range 单元测试。
Tests for engines.report_generation.mediation_range module.

验证:
- Happy path: amount_report + decision_tree → [min, max, suggested]
- Happy path: 多条 claim → 金额正确求和
- Edge case: 无 amount_report → None
- Edge case: 空 claim_calculation_table → None
- Edge case: 无 confidence_interval → 使用默认 [30%, 90%]
- Edge case: calculated_amount 为 None → 使用 claimed_amount 作为 fallback
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from engines.report_generation.mediation_range import (
    MediationRange,
    compute_mediation_range,
    _aggregate_confidence,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(claimed: str, calculated: str | None = None) -> SimpleNamespace:
    """Create a mock ClaimCalculationEntry."""
    return SimpleNamespace(
        claim_id="claim-001",
        claim_type=SimpleNamespace(value="principal"),
        claimed_amount=Decimal(claimed),
        calculated_amount=Decimal(calculated) if calculated else None,
        delta=Decimal(claimed) - Decimal(calculated) if calculated else None,
        delta_explanation="",
    )


def _make_amount_report(entries: list) -> SimpleNamespace:
    """Create a mock AmountCalculationReport."""
    return SimpleNamespace(claim_calculation_table=entries)


def _make_decision_tree(confidence_intervals: list[tuple[float, float]]) -> SimpleNamespace:
    """Create a mock DecisionPathTree with confidence intervals."""
    paths = []
    for lo, hi in confidence_intervals:
        paths.append(
            SimpleNamespace(
                confidence_interval=SimpleNamespace(lower=lo, upper=hi),
            )
        )
    return SimpleNamespace(paths=paths)


# ---------------------------------------------------------------------------
# Test: compute_mediation_range
# ---------------------------------------------------------------------------


class TestComputeMediationRange:
    def test_happy_path_with_decision_tree(self) -> None:
        """amount_report + decision_tree → 正确的 [min, max, suggested]。"""
        report = _make_amount_report(
            [
                _make_entry("100000", "80000"),
            ]
        )
        tree = _make_decision_tree([(0.4, 0.8)])

        result = compute_mediation_range(report, tree)

        assert result is not None
        assert result.total_claimed == Decimal("100000")
        assert result.total_verified == Decimal("80000")
        # min = 80000 * 0.4 = 32000
        assert result.min_amount == Decimal("32000.00")
        # max = 80000 * 0.8 = 64000 (< 100000 claimed)
        assert result.max_amount == Decimal("64000.00")
        # suggested = (32000 + 64000) / 2 = 48000
        assert result.suggested_amount == Decimal("48000.00")
        assert result.confidence_lower == 0.4
        assert result.confidence_upper == 0.8

    def test_multiple_claims_summed(self) -> None:
        """多条 claim → 金额正确求和。"""
        report = _make_amount_report(
            [
                _make_entry("50000", "40000"),
                _make_entry("30000", "30000"),
            ]
        )
        tree = _make_decision_tree([(0.5, 0.9)])

        result = compute_mediation_range(report, tree)

        assert result is not None
        assert result.total_claimed == Decimal("80000")
        assert result.total_verified == Decimal("70000")
        # min = 70000 * 0.5 = 35000
        assert result.min_amount == Decimal("35000.00")
        # max = 70000 * 0.9 = 63000
        assert result.max_amount == Decimal("63000.00")

    def test_none_amount_report(self) -> None:
        """None amount_report → None。"""
        assert compute_mediation_range(None) is None

    def test_empty_table(self) -> None:
        """空 claim_calculation_table → None。"""
        report = _make_amount_report([])
        assert compute_mediation_range(report) is None

    def test_no_decision_tree_uses_default(self) -> None:
        """无 decision_tree → 使用默认 [30%, 90%]。"""
        report = _make_amount_report(
            [
                _make_entry("100000", "100000"),
            ]
        )
        result = compute_mediation_range(report, None)

        assert result is not None
        assert result.confidence_lower == 0.3
        assert result.confidence_upper == 0.9
        # min = 100000 * 0.3 = 30000
        assert result.min_amount == Decimal("30000.00")
        # max = min(100000 * 0.9, 100000) = 90000
        assert result.max_amount == Decimal("90000.00")

    def test_no_confidence_intervals_uses_default(self) -> None:
        """decision_tree 有 paths 但无 confidence_interval → 使用默认。"""
        report = _make_amount_report(
            [
                _make_entry("50000", "50000"),
            ]
        )
        tree = SimpleNamespace(
            paths=[
                SimpleNamespace(confidence_interval=None),
            ]
        )
        result = compute_mediation_range(report, tree)

        assert result is not None
        assert result.confidence_lower == 0.3
        assert result.confidence_upper == 0.9

    def test_calculated_none_uses_claimed_fallback(self) -> None:
        """calculated_amount 为 None → verified 使用 claimed 作为 fallback。"""
        report = _make_amount_report(
            [
                _make_entry("100000", None),
            ]
        )
        result = compute_mediation_range(report, None)

        assert result is not None
        assert result.total_verified == Decimal("100000")

    def test_max_capped_at_claimed(self) -> None:
        """max_amount 不超过 claimed 总额。"""
        report = _make_amount_report(
            [
                _make_entry("50000", "80000"),  # verified > claimed
            ]
        )
        tree = _make_decision_tree([(0.8, 1.0)])

        result = compute_mediation_range(report, tree)

        assert result is not None
        # max = min(80000 * 1.0, 50000) = 50000
        assert result.max_amount <= result.total_claimed

    def test_multiple_paths_averaged(self) -> None:
        """多条 paths → confidence intervals 取平均。"""
        report = _make_amount_report(
            [
                _make_entry("100000", "100000"),
            ]
        )
        tree = _make_decision_tree(
            [
                (0.2, 0.6),
                (0.4, 0.8),
                (0.6, 1.0),
            ]
        )
        result = compute_mediation_range(report, tree)

        assert result is not None
        assert abs(result.confidence_lower - 0.4) < 0.01
        assert abs(result.confidence_upper - 0.8) < 0.01

    def test_dict_input_supported(self) -> None:
        """Support dict-style input (as used in DOCX generator)。"""
        report = {
            "claim_calculation_table": [
                {"claimed_amount": "100000", "calculated_amount": "80000"},
            ]
        }
        tree = {
            "paths": [
                {"confidence_interval": {"lower": 0.3, "upper": 0.7}},
            ]
        }
        result = compute_mediation_range(report, tree)
        assert result is not None
        assert result.total_claimed == Decimal("100000")

    def test_rationale_populated(self) -> None:
        """rationale 字段包含关键信息。"""
        report = _make_amount_report(
            [
                _make_entry("100000", "80000"),
            ]
        )
        result = compute_mediation_range(report, None)
        assert result is not None
        assert "100000" in str(result.rationale) or "100,000" in result.rationale
        assert "80000" in str(result.rationale) or "80,000" in result.rationale


# ---------------------------------------------------------------------------
# Test: _aggregate_confidence
# ---------------------------------------------------------------------------


class TestAggregateConfidence:
    def test_none_tree(self) -> None:
        assert _aggregate_confidence(None) == (0.3, 0.9)

    def test_empty_paths(self) -> None:
        assert _aggregate_confidence(SimpleNamespace(paths=[])) == (0.3, 0.9)

    def test_single_interval(self) -> None:
        tree = _make_decision_tree([(0.5, 0.8)])
        assert _aggregate_confidence(tree) == (0.5, 0.8)
