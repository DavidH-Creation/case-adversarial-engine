"""
风险热力图数据生成 — 基于争点排序结果计算每个争点的风险等级。
Risk heatmap data generator — computes risk level per issue from ranking results.

纯计算模块，不调用 LLM。

Usage:
    from engines.report_generation.risk_heatmap import build_risk_heatmap, RiskLevel
    rows = build_risk_heatmap(ranked_issues)
    # rows: list[HeatmapRow] or None
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engines.shared.models import IssueTree


class RiskLevel(str, Enum):
    """争点风险等级 / Issue risk level."""

    favorable = "favorable"  # 🟢 我方有利
    neutral = "neutral"  # 🟡 中性/不确定
    unfavorable = "unfavorable"  # 🔴 我方不利


# Emoji mapping for Markdown rendering
RISK_EMOJI: dict[RiskLevel, str] = {
    RiskLevel.favorable: "🟢",
    RiskLevel.neutral: "🟡",
    RiskLevel.unfavorable: "🔴",
}

# Chinese labels
RISK_LABEL_ZH: dict[RiskLevel, str] = {
    RiskLevel.favorable: "有利",
    RiskLevel.neutral: "中性",
    RiskLevel.unfavorable: "不利",
}


@dataclass
class HeatmapRow:
    """热力图单行数据。"""

    issue_id: str
    title: str
    outcome_impact: str  # high / medium / low
    attack_strength: str  # strong / medium / weak
    evidence_strength: str  # strong / medium / weak
    risk_level: RiskLevel
    recommended_action: str  # supplement_evidence / amend_claim / abandon / explain_in_trial


def _classify_risk(outcome_impact: str, attack_strength: str, evidence_strength: str) -> RiskLevel:
    """Classify risk based on impact × attack × evidence dimensions.

    Rules:
    - unfavorable: high impact + strong attack, OR any impact + strong attack + weak evidence
    - favorable: low/medium impact + weak attack, OR any impact + weak attack + strong evidence
    - neutral: everything else
    """
    if outcome_impact == "high" and attack_strength == "strong":
        return RiskLevel.unfavorable
    if attack_strength == "strong" and evidence_strength == "weak":
        return RiskLevel.unfavorable
    if outcome_impact == "high" and evidence_strength == "weak":
        return RiskLevel.unfavorable

    if attack_strength == "weak" and evidence_strength == "strong":
        return RiskLevel.favorable
    if outcome_impact == "low" and attack_strength == "weak":
        return RiskLevel.favorable
    if outcome_impact == "medium" and attack_strength == "weak" and evidence_strength != "weak":
        return RiskLevel.favorable

    return RiskLevel.neutral


def build_risk_heatmap(ranked_issues: Any) -> list[HeatmapRow] | None:
    """Build risk heatmap rows from IssueImpactRankingResult.ranked_issue_tree (or IssueTree).

    Args:
        ranked_issues: object with .issues attribute where each issue has
                       outcome_impact, opponent_attack_strength, proponent_evidence_strength

    Returns:
        List of HeatmapRow, or None if no ranked issues available.
    """
    if ranked_issues is None:
        return None

    issues = getattr(ranked_issues, "issues", None)
    if not issues:
        return None

    rows: list[HeatmapRow] = []
    for iss in issues:
        impact = _safe_enum_value(getattr(iss, "outcome_impact", None))
        attack = _safe_enum_value(getattr(iss, "opponent_attack_strength", None))
        evidence = _safe_enum_value(getattr(iss, "proponent_evidence_strength", None))
        action = _safe_enum_value(getattr(iss, "recommended_action", None))

        risk = _classify_risk(impact, attack, evidence)
        rows.append(
            HeatmapRow(
                issue_id=iss.issue_id,
                title=getattr(iss, "title", iss.issue_id),
                outcome_impact=impact,
                attack_strength=attack,
                evidence_strength=evidence,
                risk_level=risk,
                recommended_action=action,
            )
        )

    return rows if rows else None


def _safe_enum_value(val: Any) -> str:
    """Extract .value from enum or return str; default to empty string."""
    if val is None:
        return ""
    return val.value if hasattr(val, "value") else str(val)
