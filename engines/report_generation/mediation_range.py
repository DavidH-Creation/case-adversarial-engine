"""
调解区间计算 — 基于金额报告和裁判路径树估算和解建议金额范围。
Mediation range calculator — estimates settlement range from amount report + decision tree.

纯计算模块，不调用 LLM。

Usage:
    from engines.report_generation.mediation_range import compute_mediation_range, MediationRange
    result = compute_mediation_range(amount_report, decision_tree)
    # result: MediationRange or None
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass
class MediationRange:
    """调解区间计算结果。"""
    total_claimed: Decimal        # 诉请总额
    total_verified: Decimal       # 可核实总额
    min_amount: Decimal           # 最低可能（基于最不利路径）
    max_amount: Decimal           # 最高可能（基于最有利路径）
    suggested_amount: Decimal     # 建议调解点
    confidence_lower: float       # 综合置信度下界
    confidence_upper: float       # 综合置信度上界
    rationale: str                # 计算依据说明


def compute_mediation_range(
    amount_report: Any,
    decision_tree: Any = None,
) -> MediationRange | None:
    """Compute mediation/settlement range.

    Algorithm:
    1. Sum claimed_amount and calculated_amount from claim_calculation_table
    2. Use decision_tree confidence_intervals to weight the range
    3. min = verified × avg_lower_confidence
    4. max = verified × avg_upper_confidence (capped at claimed)
    5. suggested = (min + max) / 2

    Args:
        amount_report: AmountCalculationReport object or dict with claim_calculation_table
        decision_tree: DecisionPathTree object or dict with paths[].confidence_interval (optional)

    Returns:
        MediationRange or None if amount_report is unavailable or has no entries.
    """
    if amount_report is None:
        return None

    # Support both object and dict access
    table = _get_attr_or_key(amount_report, "claim_calculation_table")
    if not table:
        return None

    # Sum claimed and verified amounts
    total_claimed = Decimal("0")
    total_verified = Decimal("0")
    for entry in table:
        claimed = _decimal_val(entry, "claimed_amount")
        calculated = _decimal_val(entry, "calculated_amount")
        total_claimed += claimed
        if calculated is not None:
            total_verified += calculated
        else:
            # If not calculable, use claimed as fallback for verified
            total_verified += claimed

    if total_claimed <= 0:
        return None

    # Extract confidence intervals from decision tree
    avg_lower, avg_upper = _aggregate_confidence(decision_tree)

    # Calculate range
    min_amount = total_verified * Decimal(str(avg_lower))
    max_amount = total_verified * Decimal(str(avg_upper))

    # Ensure min <= max
    if min_amount > max_amount:
        min_amount, max_amount = max_amount, min_amount

    # Cap both at total_claimed
    min_amount = min(min_amount, total_claimed)
    max_amount = min(max_amount, total_claimed)

    suggested = (min_amount + max_amount) / 2

    # Quantize to 2 decimal places
    q = Decimal("0.01")
    min_amount = min_amount.quantize(q)
    max_amount = max_amount.quantize(q)
    suggested = suggested.quantize(q)

    # Build rationale
    parts = [f"诉请总额 {total_claimed:,} 元"]
    if total_verified != total_claimed:
        parts.append(f"可核实金额 {total_verified:,} 元")
    parts.append(f"综合置信区间 {avg_lower:.0%}~{avg_upper:.0%}")
    rationale = "；".join(parts)

    return MediationRange(
        total_claimed=total_claimed,
        total_verified=total_verified,
        min_amount=min_amount,
        max_amount=max_amount,
        suggested_amount=suggested,
        confidence_lower=avg_lower,
        confidence_upper=avg_upper,
        rationale=rationale,
    )


def _aggregate_confidence(decision_tree: Any) -> tuple[float, float]:
    """Extract and average confidence intervals from decision tree paths.

    Returns (avg_lower, avg_upper). Defaults to (0.3, 0.9) if no intervals available.
    """
    if decision_tree is None:
        return (0.3, 0.9)

    paths = _get_attr_or_key(decision_tree, "paths")
    if not paths:
        return (0.3, 0.9)

    lowers: list[float] = []
    uppers: list[float] = []

    for path in paths:
        ci = _get_attr_or_key(path, "confidence_interval")
        if ci is None:
            continue
        lo = _get_attr_or_key(ci, "lower")
        hi = _get_attr_or_key(ci, "upper")
        if lo is not None and hi is not None:
            lowers.append(float(lo))
            uppers.append(float(hi))

    if not lowers:
        return (0.3, 0.9)

    return (sum(lowers) / len(lowers), sum(uppers) / len(uppers))


def _get_attr_or_key(obj: Any, key: str) -> Any:
    """Get value from object attribute or dict key."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _decimal_val(entry: Any, key: str) -> Decimal | None:
    """Extract a Decimal value from entry (object or dict)."""
    val = _get_attr_or_key(entry, key)
    if val is None:
        return None
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val))
    except Exception:
        return None
