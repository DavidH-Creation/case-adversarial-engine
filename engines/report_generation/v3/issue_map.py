"""
争点地图生成器 / Issue Map Generator.

为每个争点生成固定模板的卡片（树状结构）：
  争点 / 原告主张 / 被告主张 / 决定性证据 / 当前缺口 / 结果敏感度

完全中立，不偏向任何一方。
"""

from __future__ import annotations

from collections import defaultdict

from engines.report_generation.v3.models import IssueMapCard, SectionTag


# ---------------------------------------------------------------------------
# Action enum → human-readable mapping
# ---------------------------------------------------------------------------
_ACTION_LABEL: dict[str, str] = {
    "supplement_evidence": "建议补强证据",
    "reassess": "建议重新评估",
}

# Maximum number of L1 root issues before merging kicks in.
_MAX_ROOTS = 4

# Threshold for evidence-based merging (Jaccard overlap).
_EVIDENCE_OVERLAP_THRESHOLD = 0.30

# Maximum thesis length for child issues.
_CHILD_THESIS_MAX_LEN = 120

# If a thesis is reused across >= this many issues, truncate it.
_THESIS_REUSE_LIMIT = 3
_THESIS_TRUNCATE_LEN = 200


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two sets."""
    if not a and not b:
        return 0.0
    intersection = a & b
    union = a | b
    return len(intersection) / len(union) if union else 0.0


def _get_composite_score(issue) -> float:
    """Extract composite score with fallback."""
    score = getattr(issue, "composite_score", None)
    return float(score) if score is not None else 0.0


def _humanize_action(raw_value: str) -> str:
    """Convert internal enum value to plain-language gap description."""
    return _ACTION_LABEL.get(raw_value, raw_value)


def _clean_thesis(text: str) -> str:
    """Remove internal markers like [来源:对抗分析] from thesis text."""
    return text.replace("[来源:对抗分析] ", "").replace("[来源:对抗分析]", "")


def _truncate_thesis(text: str, max_len: int) -> str:
    """Truncate thesis to max_len, ending at a sentence boundary if possible."""
    if len(text) <= max_len:
        return text
    # Try to cut at the last sentence-ending punctuation within the limit.
    truncated = text[:max_len]
    for sep in ("。", "；", ".", ";"):
        idx = truncated.rfind(sep)
        if idx > max_len // 2:
            return truncated[: idx + 1]
    return truncated + "…"


def _deduplicate_thesis(
    thesis_map: dict[str, str],
    issue_ids: list[str],
) -> dict[str, str]:
    """Detect reused thesis paragraphs and truncate duplicates.

    If a thesis text (>200 chars) appears across 3+ issues, keep only
    the first occurrence at full length; subsequent ones are truncated.
    """
    if not thesis_map:
        return thesis_map

    # Count occurrences of each thesis text.
    text_to_ids: dict[str, list[str]] = defaultdict(list)
    for iid in issue_ids:
        text = thesis_map.get(iid, "")
        if text:
            text_to_ids[text].append(iid)

    result = dict(thesis_map)
    for text, ids in text_to_ids.items():
        if len(text) > _THESIS_TRUNCATE_LEN and len(ids) >= _THESIS_REUSE_LIMIT:
            # Keep the first occurrence full-length, truncate the rest.
            for iid in ids[1:]:
                result[iid] = _truncate_thesis(text, _CHILD_THESIS_MAX_LEN)

    return result


def _build_parent_children_map(issues) -> dict[str | None, list]:
    """Build a mapping from parent_issue_id → list of child issues."""
    children_map: dict[str | None, list] = defaultdict(list)
    for issue in issues:
        pid = getattr(issue, "parent_issue_id", None)
        children_map[pid].append(issue)
    return children_map


def _merge_roots(roots: list, all_issues: list) -> tuple[list, dict[str, str]]:
    """Merge related root issues when there are too many (>_MAX_ROOTS).

    Strategy:
    1. Group roots that share >50% of their evidence_ids (Jaccard).
    2. In each group, the highest-scored root becomes the representative.
    3. Other group members become its children (synthetic parent_issue_id).
    4. If still >_MAX_ROOTS, keep top N by composite_score.

    Returns:
        (new_roots, reparent_map) where reparent_map maps
        demoted_issue_id → new_parent_issue_id.
    """
    if len(roots) <= _MAX_ROOTS:
        return roots, {}

    # Build evidence sets for each root.
    evidence_sets: dict[str, set[str]] = {}
    for r in roots:
        eids = getattr(r, "evidence_ids", []) or []
        evidence_sets[r.issue_id] = set(eids)

    # Greedy grouping by evidence overlap.
    used: set[str] = set()
    groups: list[list] = []

    # Sort roots by composite_score descending so higher-scored roots
    # become group representatives first.
    sorted_roots = sorted(roots, key=_get_composite_score, reverse=True)

    for root in sorted_roots:
        if root.issue_id in used:
            continue
        group = [root]
        used.add(root.issue_id)
        for other in sorted_roots:
            if other.issue_id in used:
                continue
            overlap = _jaccard(
                evidence_sets.get(root.issue_id, set()),
                evidence_sets.get(other.issue_id, set()),
            )
            if overlap >= _EVIDENCE_OVERLAP_THRESHOLD:
                group.append(other)
                used.add(other.issue_id)
        groups.append(group)

    # Build merged roots and reparent map.
    new_roots: list = []
    reparent_map: dict[str, str] = {}

    for group in groups:
        # First element (highest score) is the representative root.
        representative = group[0]
        new_roots.append(representative)
        for member in group[1:]:
            reparent_map[member.issue_id] = representative.issue_id

    # If still too many, keep top N by composite_score.
    if len(new_roots) > _MAX_ROOTS:
        new_roots.sort(key=_get_composite_score, reverse=True)
        demoted = new_roots[_MAX_ROOTS:]
        new_roots = new_roots[:_MAX_ROOTS]
        # Demoted roots become children of the highest-scored remaining root.
        fallback_parent = new_roots[0].issue_id
        for d in demoted:
            reparent_map[d.issue_id] = fallback_parent

    return new_roots, reparent_map


def _compute_sensitivity(issue) -> str:
    """Determine outcome sensitivity string for an issue."""
    composite = getattr(issue, "composite_score", None)
    if composite is not None:
        if composite > 70:
            return "极高 — 该争点翻转将直接改变裁判结果"
        elif composite > 40:
            return "中等 — 该争点影响部分诉请金额或责任分配"
        else:
            return "较低 — 该争点对最终结果影响有限"

    outcome_impact = getattr(issue, "outcome_impact", None)
    if outcome_impact:
        impact_val = (
            outcome_impact.value if hasattr(outcome_impact, "value") else str(outcome_impact)
        )
        sensitivity_map = {
            "decisive": "极高 — 该争点翻转将直接改变裁判结果",
            "significant": "中等 — 该争点影响部分诉请金额或责任分配",
            "moderate": "中等 — 该争点影响部分诉请金额或责任分配",
            "marginal": "较低 — 该争点对最终结果影响有限",
        }
        return sensitivity_map.get(impact_val, "")

    return ""


def _collect_gaps(issue, attack_targets: dict[str, str]) -> list[str]:
    """Build current-gaps list for an issue, using plain language."""
    gaps: list[str] = []
    if issue.issue_id in attack_targets:
        gaps.append(f"被攻击点: {attack_targets[issue.issue_id]}")

    action = getattr(issue, "recommended_action", None)
    if action:
        raw = action.value if hasattr(action, "value") else str(action)
        label = _humanize_action(raw)
        if label != raw:
            # Only add recognized actions.
            gaps.append(label)
    return gaps


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_issue_map(
    issue_tree,
    adversarial_result=None,
    ranked_issues=None,
    attack_chain=None,
) -> list[IssueMapCard]:
    """Build tree-structured issue map cards.

    Algorithm:
    1. Build parent→children map from issue.parent_issue_id
    2. Identify L1 roots (parent_issue_id is None)
    3. If too many roots (>5), merge related issues heuristically
    4. Build cards with depth annotations
    5. Return ordered list: root card, then its children, then next root, etc.

    Args:
        issue_tree: IssueTree from pipeline
        adversarial_result: AdversarialResult for plaintiff/defendant arguments
        ranked_issues: IssueTree with ranking data (from IssueImpactRanker)
        attack_chain: OptimalAttackChain (optional)

    Returns:
        List of IssueMapCard in tree-walk order (parent, children, next parent …)
    """
    # ------------------------------------------------------------------
    # 1. Build adversarial thesis lookup maps
    # ------------------------------------------------------------------
    plaintiff_args: dict[str, str] = {}
    defendant_args: dict[str, str] = {}

    if adversarial_result and adversarial_result.summary:
        for arg in adversarial_result.summary.plaintiff_strongest_arguments or []:
            plaintiff_args[arg.issue_id] = f"{arg.position}: {arg.reasoning}"
        for arg in adversarial_result.summary.defendant_strongest_defenses or []:
            defendant_args[arg.issue_id] = f"{arg.position}: {arg.reasoning}"

    # Fall back to best arguments if summary is sparse.
    if adversarial_result:
        for arg in adversarial_result.plaintiff_best_arguments or []:
            if arg.issue_id not in plaintiff_args:
                plaintiff_args[arg.issue_id] = arg.position
        for arg in adversarial_result.defendant_best_defenses or []:
            if arg.issue_id not in defendant_args:
                defendant_args[arg.issue_id] = arg.position

    # ------------------------------------------------------------------
    # 2. Attack chain targets for gap analysis
    # ------------------------------------------------------------------
    attack_targets: dict[str, str] = {}
    if attack_chain:
        for node in getattr(attack_chain, "top_attacks", []):
            attack_targets[node.target_issue_id] = node.attack_description

    # ------------------------------------------------------------------
    # 3. Use ranked issues if available; build issue index
    # ------------------------------------------------------------------
    issues = ranked_issues.issues if ranked_issues else issue_tree.issues
    issue_index: dict[str, object] = {iss.issue_id: iss for iss in issues}
    all_issue_ids = [iss.issue_id for iss in issues]

    # ------------------------------------------------------------------
    # 4. Deduplicate thesis paragraphs
    # ------------------------------------------------------------------
    plaintiff_args = _deduplicate_thesis(plaintiff_args, all_issue_ids)
    defendant_args = _deduplicate_thesis(defendant_args, all_issue_ids)

    # ------------------------------------------------------------------
    # 5. Build parent→children map & identify roots
    # ------------------------------------------------------------------
    children_map = _build_parent_children_map(issues)

    roots = children_map.get(None, [])
    # Also treat issues whose parent_issue_id points to a non-existent
    # issue as roots (orphan recovery).
    for issue in issues:
        pid = getattr(issue, "parent_issue_id", None)
        if pid is not None and pid not in issue_index:
            roots.append(issue)

    # Sort roots by composite_score descending.
    roots.sort(key=_get_composite_score, reverse=True)

    # ------------------------------------------------------------------
    # 6. Merge roots if too many
    # ------------------------------------------------------------------
    roots, reparent_map = _merge_roots(roots, issues)

    # ------------------------------------------------------------------
    # 7. Build cards via DFS tree walk
    # ------------------------------------------------------------------
    cards: list[IssueMapCard] = []
    visited: set[str] = set()

    def _make_card(issue, depth: int, parent_id: str | None) -> None:
        if issue.issue_id in visited:
            return
        visited.add(issue.issue_id)

        # --- Thesis text ---
        p_thesis_raw = plaintiff_args.get(issue.issue_id, "")
        d_thesis_raw = defendant_args.get(issue.issue_id, "")

        # Clean internal markers.
        p_thesis_raw = _clean_thesis(p_thesis_raw)
        d_thesis_raw = _clean_thesis(d_thesis_raw)

        # For sub-issues, keep thesis shorter and more focused.
        if depth > 0:
            p_thesis_raw = _truncate_thesis(p_thesis_raw, _CHILD_THESIS_MAX_LEN)
            d_thesis_raw = _truncate_thesis(d_thesis_raw, _CHILD_THESIS_MAX_LEN)

        p_thesis = p_thesis_raw if p_thesis_raw else "（待补充原告主张）"
        d_thesis = d_thesis_raw if d_thesis_raw else "（待补充被告主张）"

        cards.append(
            IssueMapCard(
                issue_id=issue.issue_id,
                issue_title=issue.title,
                parent_issue_id=parent_id,
                depth=depth,
                plaintiff_thesis=p_thesis,
                defendant_thesis=d_thesis,
                decisive_evidence=(issue.evidence_ids[:5] if issue.evidence_ids else []),
                current_gaps=_collect_gaps(issue, attack_targets),
                outcome_sensitivity=_compute_sensitivity(issue),
                tag=SectionTag.inference,
            )
        )

        # Recurse into children (original children + reparented siblings).
        own_children = children_map.get(issue.issue_id, [])
        # Add issues that were reparented onto this root during merging.
        reparented_children = [
            issue_index[cid]
            for cid, pid in reparent_map.items()
            if pid == issue.issue_id and cid in issue_index
        ]
        all_children = own_children + reparented_children
        # Sort children by composite_score descending.
        all_children.sort(key=_get_composite_score, reverse=True)

        for child in all_children:
            _make_card(child, depth + 1, issue.issue_id)

    for root in roots:
        _make_card(root, depth=0, parent_id=None)

    # ------------------------------------------------------------------
    # 8. Catch any orphans not visited (defensive)
    # ------------------------------------------------------------------
    for issue in issues:
        if issue.issue_id not in visited:
            _make_card(issue, depth=0, parent_id=None)

    return cards
