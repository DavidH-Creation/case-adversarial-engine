"""
角色化视角模块 — 纯数据变换，不调用 LLM。
Perspective summary module — pure data transformation, no LLM calls.

从现有产物（对抗结果、裁判路径树、争点树等）聚合角色化视角卡片，
并渲染为报告 Layer 1 Block B 和 Layer 3 的 Markdown。

Aggregates a perspective card from existing artifacts (adversarial result,
decision path tree, issue tree) and renders Layer 1 Block B and Layer 3.
"""

from __future__ import annotations

from typing import Any

from .schemas import Perspective, PerspectiveCard

# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

_MAX_STRENGTHS = 3
_MAX_DANGERS = 2
_MAX_ACTIONS = 3
_MAX_PATHS = 5


def build_perspective_card(
    perspective: Perspective,
    adversarial_result: Any,
    decision_path_tree: Any = None,
    action_recommendations: list | None = None,
    missing_evidence_report: list | None = None,
    issue_tree: Any = None,
) -> PerspectiveCard:
    """Build a perspective card from existing artifacts.

    Args:
        perspective:            Perspective enum (PLAINTIFF / DEFENDANT / JUDGE / NEUTRAL)
        adversarial_result:     AdversarialResult (or None-safe Any with .summary)
        decision_path_tree:     Optional DecisionPathTree with .paths list
        action_recommendations: Optional list with .role attribute per item
        missing_evidence_report: Optional list with .missing_for_party_id attribute
        issue_tree:             Optional IssueTree with .issues list

    Returns:
        PerspectiveCard with up to 3 strengths, 2 dangers, 3 priority actions,
        and relevant path IDs.
    """
    summary = getattr(adversarial_result, "summary", None) if adversarial_result else None
    paths: list = _get_paths(decision_path_tree)

    if perspective == Perspective.PLAINTIFF:
        return _build_plaintiff_card(
            summary, paths, action_recommendations, missing_evidence_report
        )
    elif perspective == Perspective.DEFENDANT:
        return _build_defendant_card(summary, paths, action_recommendations)
    else:
        # JUDGE and NEUTRAL share the neutral card
        return _build_neutral_card(summary, paths, issue_tree)


# ---------------------------------------------------------------------------
# Per-perspective builders
# ---------------------------------------------------------------------------


def _build_plaintiff_card(
    summary: Any,
    paths: list,
    action_recommendations: list | None,
    missing_evidence_report: list | None,
) -> PerspectiveCard:
    # top_strengths: plaintiff_strongest_arguments[:3] → position text
    strengths = []
    for arg in _safe_list(getattr(summary, "plaintiff_strongest_arguments", [])):
        strengths.append(getattr(arg, "position", str(arg)))
        if len(strengths) >= _MAX_STRENGTHS:
            break

    # top_dangers: defendant-favored paths sorted by key_evidence count desc
    danger_paths = sorted(
        [p for p in paths if _safe_str(getattr(p, "party_favored", "")) == "defendant"],
        key=lambda p: -len(getattr(p, "key_evidence_ids", [])),
    )
    dangers = []
    for p in danger_paths[:_MAX_DANGERS]:
        outcome = getattr(p, "possible_outcome", "") or getattr(p, "trigger_condition", "")
        dangers.append(f"[路径 {getattr(p, 'path_id', '?')}] {outcome}")

    # priority_actions: action_recommendations where role=="plaintiff"
    actions = _filter_actions(action_recommendations, "plaintiff")

    # relevant_paths: plaintiff-favored path IDs
    relevant = [
        getattr(p, "path_id", "")
        for p in paths
        if _safe_str(getattr(p, "party_favored", "")) == "plaintiff"
    ][:_MAX_PATHS]

    return PerspectiveCard(
        perspective=Perspective.PLAINTIFF,
        top_strengths=strengths,
        top_dangers=dangers,
        priority_actions=actions,
        relevant_paths=relevant,
    )


def _build_defendant_card(
    summary: Any,
    paths: list,
    action_recommendations: list | None,
) -> PerspectiveCard:
    # top_strengths: defendant_strongest_defenses[:3] → position text
    strengths = []
    for arg in _safe_list(getattr(summary, "defendant_strongest_defenses", [])):
        strengths.append(getattr(arg, "position", str(arg)))
        if len(strengths) >= _MAX_STRENGTHS:
            break

    # top_dangers: plaintiff-favored paths (what plaintiff can prove) sorted by evidence count
    danger_paths = sorted(
        [p for p in paths if _safe_str(getattr(p, "party_favored", "")) == "plaintiff"],
        key=lambda p: -len(getattr(p, "key_evidence_ids", [])),
    )
    dangers = []
    for p in danger_paths[:_MAX_DANGERS]:
        outcome = getattr(p, "possible_outcome", "") or getattr(p, "trigger_condition", "")
        dangers.append(f"[路径 {getattr(p, 'path_id', '?')}] {outcome}")

    # priority_actions: action_recommendations where role=="defendant"
    actions = _filter_actions(action_recommendations, "defendant")

    # relevant_paths: defendant-favored path IDs
    relevant = [
        getattr(p, "path_id", "")
        for p in paths
        if _safe_str(getattr(p, "party_favored", "")) == "defendant"
    ][:_MAX_PATHS]

    return PerspectiveCard(
        perspective=Perspective.DEFENDANT,
        top_strengths=strengths,
        top_dangers=dangers,
        priority_actions=actions,
        relevant_paths=relevant,
    )


def _build_neutral_card(
    summary: Any,
    paths: list,
    issue_tree: Any,
) -> PerspectiveCard:
    # top_strengths: top 1 plaintiff argument + top 1 defendant argument
    strengths = []
    for arg in _safe_list(getattr(summary, "plaintiff_strongest_arguments", []))[:1]:
        strengths.append(f"[原告] {getattr(arg, 'position', str(arg))}")
    for arg in _safe_list(getattr(summary, "defendant_strongest_defenses", []))[:1]:
        strengths.append(f"[被告] {getattr(arg, 'position', str(arg))}")

    # top_dangers: top contested open issues (outcome_impact=high, status=open)
    dangers = []
    for iss in _safe_list(getattr(issue_tree, "issues", []) if issue_tree else []):
        impact = _safe_str(getattr(iss, "outcome_impact", ""))
        status = _safe_str(getattr(iss, "status", ""))
        if impact == "high" and status == "open":
            title = getattr(iss, "title", getattr(iss, "issue_id", "?"))
            dangers.append(title)
            if len(dangers) >= _MAX_DANGERS:
                break

    # priority_actions: unresolved issue titles (from summary or issue_tree)
    actions: list[str] = []
    for detail in _safe_list(getattr(summary, "unresolved_issues", []))[:_MAX_ACTIONS]:
        title = getattr(detail, "issue_title", getattr(detail, "issue_id", str(detail)))
        actions.append(f"待决争点: {title}")

    # relevant_paths: all path IDs
    relevant = [getattr(p, "path_id", "") for p in paths][:_MAX_PATHS]

    return PerspectiveCard(
        perspective=Perspective.JUDGE,
        top_strengths=strengths,
        top_dangers=dangers,
        priority_actions=actions,
        relevant_paths=relevant,
    )


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def render_layer1_block_b(card: PerspectiveCard) -> str:
    """Render the cover summary perspective card (Layer 1 Block B).

    Returns a compact perspective-tagged section (no long paragraphs).
    """
    perspective_label = {
        Perspective.PLAINTIFF: "原告视角 / Plaintiff Perspective",
        Perspective.DEFENDANT: "被告视角 / Defendant Perspective",
        Perspective.JUDGE: "法官视角 / Judge Perspective",
        Perspective.NEUTRAL: "中立视角 / Neutral Perspective",
    }.get(card.perspective, str(card.perspective))

    lines = [
        f"### {perspective_label}",
        "",
    ]

    if card.top_strengths:
        lines.append("**优势 / Strengths:**")
        for s in card.top_strengths:
            lines.append(f"- {s}")
        lines.append("")

    if card.top_dangers:
        lines.append("**风险 / Dangers:**")
        for d in card.top_dangers:
            lines.append(f"- {d}")
        lines.append("")

    if card.priority_actions:
        lines.append("**优先行动 / Priority Actions:**")
        for a in card.priority_actions:
            lines.append(f"- {a}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_layer3(card: PerspectiveCard, perspective: Perspective) -> str:
    """Render the full role-based output section (Layer 3).

    Returns a full-section Markdown string.
    """
    perspective_header = {
        Perspective.PLAINTIFF: "## Layer 3: 原告角色化输出 / Plaintiff Role Output",
        Perspective.DEFENDANT: "## Layer 3: 被告角色化输出 / Defendant Role Output",
        Perspective.JUDGE: "## Layer 3: 法官视角输出 / Judge Perspective Output",
        Perspective.NEUTRAL: "## Layer 3: 中立视角输出 / Neutral Perspective Output",
    }.get(perspective, "## Layer 3: 角色化输出 / Role Output")

    lines = [perspective_header, ""]

    if card.top_strengths:
        strength_title = {
            Perspective.PLAINTIFF: "### 核心主张 / Core Claims",
            Perspective.DEFENDANT: "### 核心抗辩 / Core Defenses",
            Perspective.JUDGE: "### 双方最强论点 / Strongest Arguments Per Side",
            Perspective.NEUTRAL: "### 核心论点 / Core Arguments",
        }.get(perspective, "### 核心优势 / Core Strengths")
        lines.append(strength_title)
        for s in card.top_strengths:
            lines.append(f"- {s}")
        lines.append("")

    if card.top_dangers:
        danger_title = {
            Perspective.PLAINTIFF: "### 对方攻击链 / Defendant Attack Chains",
            Perspective.DEFENDANT: "### 原告补强风险 / Plaintiff Supplement Risks",
            Perspective.JUDGE: "### 关键争议点 / Key Contested Issues",
            Perspective.NEUTRAL: "### 主要风险 / Main Risks",
        }.get(perspective, "### 风险点 / Risk Points")
        lines.append(danger_title)
        for d in card.top_dangers:
            lines.append(f"- {d}")
        lines.append("")

    if card.priority_actions:
        action_title = {
            Perspective.PLAINTIFF: "### 优先行动 / Priority Actions",
            Perspective.DEFENDANT: "### 优先行动 / Priority Actions",
            Perspective.JUDGE: "### 待决事项 / Unresolved Matters",
            Perspective.NEUTRAL: "### 优先行动 / Priority Actions",
        }.get(perspective, "### 优先行动 / Priority Actions")
        lines.append(action_title)
        for a in card.priority_actions:
            lines.append(f"- {a}")
        lines.append("")

    if card.relevant_paths:
        lines.append("### 相关裁判路径 / Relevant Decision Paths")
        lines.append(", ".join(card.relevant_paths))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_paths(decision_path_tree: Any) -> list:
    if decision_path_tree is None:
        return []
    return list(getattr(decision_path_tree, "paths", []) or [])


def _safe_list(val: Any) -> list:
    if val is None:
        return []
    return list(val)


def _safe_str(val: Any) -> str:
    if val is None:
        return ""
    return val.value if hasattr(val, "value") else str(val)


def _filter_actions(action_recommendations: list | None, role: str) -> list[str]:
    """Extract action text for a given role from action_recommendations."""
    if not action_recommendations:
        return []
    results = []
    for item in action_recommendations:
        item_role = _safe_str(getattr(item, "role", ""))
        if item_role == role:
            text = getattr(item, "action", getattr(item, "description", str(item)))
            results.append(text)
            if len(results) >= _MAX_ACTIONS:
                break
    return results
