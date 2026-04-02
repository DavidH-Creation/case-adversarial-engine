"""
结构化输出路径聚合 — 从三个来源产物构建 CaseOutcomePaths。
Outcome path aggregator — builds CaseOutcomePaths from DecisionPathTree,
MediationRange, and EvidenceGapRankingResult.

纯计算模块，不调用 LLM。

Usage:
    from engines.report_generation.outcome_paths import (
        build_case_outcome_paths,
        render_outcome_paths_md_lines,
    )
    paths = build_case_outcome_paths(decision_tree, mediation_range, gap_result)
    lines = render_outcome_paths_md_lines(paths)
"""

from __future__ import annotations

from typing import Any

from .schemas import CaseOutcomePaths, OutcomePath, OutcomePathType

_INSUFFICIENT = ["insufficient_data"]


def build_case_outcome_paths(
    decision_tree: Any = None,
    mediation_range: Any = None,
    gap_result: Any = None,
    *,
    verdict_block_active: bool = False,
) -> CaseOutcomePaths:
    """Aggregate source artifacts into CaseOutcomePaths.

    Args:
        decision_tree: DecisionPathTree object (or None). Provides WIN/LOSE paths.
        mediation_range: MediationRange dataclass (or None). Provides MEDIATION path.
        gap_result: EvidenceGapRankingResult object (or None). Provides SUPPLEMENT path.
        verdict_block_active: When True, WIN/LOSE paths omit numeric confidence data.

    Returns:
        CaseOutcomePaths with all four paths populated.
        Missing sources produce paths with trigger_conditions=["insufficient_data"].
    """
    return CaseOutcomePaths(
        win_path=_build_win_path(decision_tree, verdict_block_active),
        lose_path=_build_lose_path(decision_tree, verdict_block_active),
        mediation_path=_build_mediation_path(mediation_range),
        supplement_path=_build_supplement_path(gap_result),
    )


def render_outcome_paths_md_lines(paths: CaseOutcomePaths) -> list[str]:
    """Render CaseOutcomePaths as Markdown lines for report output.

    Args:
        paths: CaseOutcomePaths aggregation result.

    Returns:
        List of Markdown-formatted strings.
    """
    lines: list[str] = ["## 结构化输出路径 / Case Outcome Paths", ""]

    _PATH_LABELS = {
        OutcomePathType.WIN: "✅ 胜诉路径 (WIN)",
        OutcomePathType.LOSE: "❌ 败诉路径 (LOSE)",
        OutcomePathType.MEDIATION: "🤝 调解路径 (MEDIATION)",
        OutcomePathType.SUPPLEMENT: "📋 补证路径 (SUPPLEMENT)",
    }

    for path in [paths.win_path, paths.lose_path, paths.mediation_path, paths.supplement_path]:
        label = _PATH_LABELS.get(path.path_type, path.path_type.value)
        lines.append(f"### {label}")
        lines.append("")

        if path.trigger_conditions:
            lines.append("**触发条件 / Trigger Conditions:**")
            for cond in path.trigger_conditions:
                lines.append(f"- {cond}")
            lines.append("")

        if path.key_actions:
            lines.append("**关键行动 / Key Actions:**")
            for action in path.key_actions:
                lines.append(f"- {action}")
            lines.append("")

        if path.required_evidence_ids:
            lines.append(
                f"**所需证据 / Required Evidence:** {', '.join(path.required_evidence_ids)}"
            )
            lines.append("")

        if path.risk_points:
            lines.append("**风险提示 / Risk Points:**")
            for rp in path.risk_points:
                lines.append(f"- {rp}")
            lines.append("")

        if path.source_artifact:
            lines.append(f"*来源产物 / Source: `{path.source_artifact}`*")
            lines.append("")

    return lines


# ---------------------------------------------------------------------------
# Internal path builders
# ---------------------------------------------------------------------------


def _build_win_path(decision_tree: Any, verdict_block_active: bool) -> OutcomePath:
    """Build WIN path from plaintiff-favored DecisionPath entries."""
    if decision_tree is None:
        return OutcomePath(
            path_type=OutcomePathType.WIN,
            trigger_conditions=["insufficient_data"],
            source_artifact="",
        )

    paths = _get_attr(decision_tree, "paths") or []
    win_paths = [p for p in paths if _get_str(p, "party_favored") == "plaintiff"]

    trigger_conditions = [cond for p in win_paths if (cond := _get_str(p, "trigger_condition"))]
    required_evidence_ids = list(
        {eid for p in win_paths for eid in (_get_attr(p, "key_evidence_ids") or [])}
    )

    risk_points: list[str] = []

    if not trigger_conditions:
        trigger_conditions = ["insufficient_data"]

    return OutcomePath(
        path_type=OutcomePathType.WIN,
        trigger_conditions=trigger_conditions,
        key_actions=[],
        required_evidence_ids=required_evidence_ids,
        risk_points=risk_points,
        source_artifact="decision_path_tree",
    )


def _build_lose_path(decision_tree: Any, verdict_block_active: bool) -> OutcomePath:
    """Build LOSE path from defendant-favored DecisionPath entries."""
    if decision_tree is None:
        return OutcomePath(
            path_type=OutcomePathType.LOSE,
            trigger_conditions=["insufficient_data"],
            source_artifact="",
        )

    paths = _get_attr(decision_tree, "paths") or []
    lose_paths = [p for p in paths if _get_str(p, "party_favored") == "defendant"]

    trigger_conditions = [cond for p in lose_paths if (cond := _get_str(p, "trigger_condition"))]
    required_evidence_ids = list(
        {eid for p in lose_paths for eid in (_get_attr(p, "counter_evidence_ids") or [])}
    )

    risk_points: list[str] = []

    if not trigger_conditions:
        trigger_conditions = ["insufficient_data"]

    return OutcomePath(
        path_type=OutcomePathType.LOSE,
        trigger_conditions=trigger_conditions,
        key_actions=[],
        required_evidence_ids=required_evidence_ids,
        risk_points=risk_points,
        source_artifact="decision_path_tree",
    )


def _build_mediation_path(mediation_range: Any) -> OutcomePath:
    """Build MEDIATION path from MediationRange dataclass."""
    if mediation_range is None:
        return OutcomePath(
            path_type=OutcomePathType.MEDIATION,
            trigger_conditions=["insufficient_data"],
            source_artifact="",
        )

    min_amt = _get_attr(mediation_range, "min_amount")
    max_amt = _get_attr(mediation_range, "max_amount")
    suggested = _get_attr(mediation_range, "suggested_amount")
    rationale = _get_str(mediation_range, "rationale")

    key_actions: list[str] = []
    if min_amt is not None and max_amt is not None:
        key_actions.append(f"建议调解区间：{min_amt:,}~{max_amt:,} 元")
    if suggested is not None:
        key_actions.append(f"建议调解点：{suggested:,} 元")

    trigger_conditions = [rationale] if rationale else ["insufficient_data"]

    return OutcomePath(
        path_type=OutcomePathType.MEDIATION,
        trigger_conditions=trigger_conditions,
        key_actions=key_actions,
        required_evidence_ids=[],
        risk_points=[],
        source_artifact="mediation_range",
    )


def _build_supplement_path(gap_result: Any) -> OutcomePath:
    """Build SUPPLEMENT path from top-3 EvidenceGapItem entries."""
    if gap_result is None:
        return OutcomePath(
            path_type=OutcomePathType.SUPPLEMENT,
            trigger_conditions=["insufficient_data"],
            source_artifact="",
        )

    ranked_items = _get_attr(gap_result, "ranked_items") or []
    sorted_items = sorted(ranked_items, key=lambda x: getattr(x, "roi_rank", 999))
    top3 = sorted_items[:3]

    key_actions = [desc for item in top3 if (desc := _get_str(item, "gap_description"))]
    required_evidence_ids = [gap_id for item in top3 if (gap_id := _get_str(item, "gap_id"))]

    return OutcomePath(
        path_type=OutcomePathType.SUPPLEMENT,
        trigger_conditions=[],
        key_actions=key_actions,
        required_evidence_ids=required_evidence_ids,
        risk_points=[],
        source_artifact="evidence_gap_ranker",
    )


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _get_attr(obj: Any, key: str) -> Any:
    """Get attribute or dict key; returns None if missing."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _get_str(obj: Any, key: str) -> str:
    """Get attribute as string; returns empty string if missing or None."""
    val = _get_attr(obj, key)
    if val is None:
        return ""
    return val if isinstance(val, str) else str(val)
