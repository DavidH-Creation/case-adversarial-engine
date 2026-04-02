"""
Layer 1: 封面摘要层 / Cover Summary Layer.

V3.1 structure (perspective-independent):
  A. 中立结论摘要（一句话）
  B. 胜负手（1-2 most outcome-determinative evidence/issues）
  C. 阻断条件（which facts, if flipped, change the conclusion）
  D. 案件时间线（from TimelineEvent list, built externally）
  E. 证据优先级分层（from EvidencePriorityCard list, built externally）

Plaintiff/defendant perspective summaries have moved to Layer 3 exclusively.
"""

from __future__ import annotations

from engines.report_generation.v3.models import (
    CoverSummary,
    EvidencePriorityCard,
    Layer1Cover,
    SectionTag,
    TimelineEvent,
)
from engines.report_generation.v3.tag_system import format_tag


def build_layer1(
    *,
    adversarial_result,
    evidence_index,
    issue_tree,
    scenario_tree=None,
    exec_summary=None,
    action_rec=None,
    attack_chain=None,
    evidence_priorities: list[EvidencePriorityCard] | None = None,
    timeline: list[TimelineEvent] | None = None,
    perspective: str = "neutral",  # kept for API compat but no longer used
) -> Layer1Cover:
    """Build Layer 1 cover summary.

    Args:
        adversarial_result: AdversarialResult from debate
        evidence_index: EvidenceIndex
        issue_tree: IssueTree
        scenario_tree: ConditionalScenarioTree (optional)
        exec_summary: ExecutiveSummaryArtifact (optional, unused in V3.1)
        action_rec: ActionRecommendation (optional, unused in V3.1)
        attack_chain: OptimalAttackChain (optional)
        evidence_priorities: Pre-built evidence priority cards (optional)
        timeline: Pre-built timeline events (optional)
        perspective: Kept for API compat; no longer affects Layer 1 output.

    Returns:
        Layer1Cover
    """
    # A. Neutral conclusion
    neutral_conclusion = _build_neutral_conclusion(adversarial_result, issue_tree)

    # B. Winning move
    winning_move = _build_winning_move(adversarial_result, evidence_index, issue_tree, attack_chain)

    # C. Blocking conditions
    blocking_conditions = _build_blocking_conditions(adversarial_result, scenario_tree)

    cover = CoverSummary(
        neutral_conclusion=neutral_conclusion,
        winning_move=winning_move,
        blocking_conditions=blocking_conditions,
    )

    # D. Timeline (built externally, passed in)
    resolved_timeline: list[TimelineEvent] = timeline or []

    # E. Evidence priorities (built externally, passed in)
    resolved_priorities: list[EvidencePriorityCard] = evidence_priorities or []

    return Layer1Cover(
        cover_summary=cover,
        timeline=resolved_timeline,
        evidence_priorities=resolved_priorities,
        # Keep scenario_tree_summary empty -- blocking_conditions replaces it
        scenario_tree_summary="",
    )


def _build_neutral_conclusion(adversarial_result, issue_tree) -> str:
    """Build a one-sentence neutral conclusion."""
    if adversarial_result and adversarial_result.summary:
        assessment = adversarial_result.summary.overall_assessment
        if assessment:
            # Take first sentence only
            first_sentence = assessment.split("\u3002")[0] + "\u3002"
            if len(first_sentence) > 200:
                first_sentence = first_sentence[:200] + "..."
            return first_sentence

    # Fallback: count issues and summarize
    n_issues = len(issue_tree.issues)
    n_open = sum(1 for i in issue_tree.issues if hasattr(i, "status") and i.status.value == "open")
    return f"\u672c\u6848\u6d89\u53ca {n_issues} \u4e2a\u4e89\u70b9\uff0c\u5176\u4e2d {n_open} \u4e2a\u5c1a\u672a\u89e3\u51b3\uff0c\u53cc\u65b9\u5728\u6838\u5fc3\u4e8b\u5b9e\u8ba4\u5b9a\u4e0a\u5b58\u5728\u5206\u6b67\u3002"


def _build_winning_move(
    adversarial_result,
    evidence_index,
    issue_tree,
    attack_chain=None,
) -> str:
    """Identify the winning move -- the evidence/issue most determining the case outcome.

    Strategy:
    1. Look at the favored side's strongest argument (first entry).
    2. Cross-reference cited evidence across strongest arguments.
    3. Format as: "证据名称 -- 简要说明为什么这是胜负手"

    Fallback: highest-weight issue from ranked_issues / issue_tree.
    """
    if not adversarial_result or not adversarial_result.summary:
        return _winning_move_from_issue_tree(issue_tree)

    summary = adversarial_result.summary
    assessment = summary.overall_assessment or ""

    # Determine which side is favored
    plaintiff_args = summary.plaintiff_strongest_arguments or []
    defendant_args = summary.defendant_strongest_defenses or []

    # Heuristic: if assessment mentions defendant/被告 favorably, lead with defense
    favored_args = plaintiff_args
    if any(kw in assessment for kw in ("被告占优", "被告有利", "defendant")):
        favored_args = defendant_args if defendant_args else plaintiff_args

    if not favored_args:
        favored_args = defendant_args

    if not favored_args:
        return _winning_move_from_issue_tree(issue_tree)

    top_arg = favored_args[0]
    position = getattr(top_arg, "position", "")
    issue_id = getattr(top_arg, "issue_id", "")

    # Try to find the most-cited evidence across top arguments
    evidence_title = _find_dominant_evidence(favored_args[:3], evidence_index)

    if evidence_title:
        return f"{evidence_title} \u2014\u2014 {position}"

    if issue_id and position:
        return f"[{issue_id}] {position}"

    return _winning_move_from_issue_tree(issue_tree)


def _find_dominant_evidence(
    top_args: list,
    evidence_index,
) -> str:
    """Find the evidence cited most frequently across the top arguments.

    Returns the evidence title, or empty string if none found.
    """
    evidence_counts: dict[str, int] = {}
    for arg in top_args:
        cited = getattr(arg, "cited_evidence_ids", None) or []
        for eid in cited:
            evidence_counts[eid] = evidence_counts.get(eid, 0) + 1

    if not evidence_counts:
        return ""

    top_eid = max(evidence_counts, key=evidence_counts.get)  # type: ignore[arg-type]

    # Resolve title from evidence_index
    for ev in evidence_index.evidence:
        if ev.evidence_id == top_eid:
            return ev.title
    return top_eid


def _winning_move_from_issue_tree(issue_tree) -> str:
    """Fallback: derive winning move from highest-priority issue."""
    if issue_tree and issue_tree.issues:
        top_issue = issue_tree.issues[0]
        return f"[{top_issue.issue_id}] {top_issue.title}"
    return "\uff08\u5f85\u5206\u6790\u80dc\u8d1f\u624b\uff09"


def _build_blocking_conditions(
    adversarial_result,
    scenario_tree=None,
) -> list[str]:
    """Identify blocking conditions -- facts that if flipped would change the conclusion.

    Strategy:
    1. From scenario_tree: each root condition is a potential blocking condition.
    2. From adversarial_result.unresolved_issues: unresolved issues are blocking.
    3. Format as natural language: "若X被推翻/排除，则Y"

    Returns 2-4 conditions max.
    """
    conditions: list[str] = []

    # Source 1: scenario tree root conditions
    if scenario_tree and getattr(scenario_tree, "nodes", None):
        root_id = getattr(scenario_tree, "root_node_id", None)
        nodes_by_id = {n.node_id: n for n in scenario_tree.nodes}

        # Collect root and immediate children conditions
        visit_ids = [root_id] if root_id else []
        if root_id and root_id in nodes_by_id:
            root_node = nodes_by_id[root_id]
            if root_node.yes_child_id:
                visit_ids.append(root_node.yes_child_id)
            if root_node.no_child_id:
                visit_ids.append(root_node.no_child_id)

        for nid in visit_ids:
            if nid not in nodes_by_id:
                continue
            node = nodes_by_id[nid]
            cond = node.condition
            yes_out = node.yes_outcome or ""
            no_out = node.no_outcome or ""

            if yes_out and no_out:
                conditions.append(
                    f"\u82e5\u201c{cond}\u201d\u6210\u7acb\uff0c\u5219{yes_out}\uff1b"
                    f"\u5426\u5219{no_out}"
                )
            elif cond:
                conditions.append(
                    f"\u82e5\u201c{cond}\u201d\u88ab\u63a8\u7ffb\uff0c\u5219\u7ed3\u8bba\u53ef\u80fd\u53cd\u8f6c"
                )

            if len(conditions) >= 4:
                break

    # Source 2: unresolved issues from adversarial result
    if adversarial_result and len(conditions) < 4:
        unresolved = getattr(adversarial_result, "unresolved_issues", None) or []
        for issue in unresolved:
            desc = ""
            if isinstance(issue, str):
                desc = issue
            elif hasattr(issue, "description"):
                desc = issue.description
            elif hasattr(issue, "issue_id"):
                desc = str(issue.issue_id)

            if desc:
                conditions.append(
                    f"\u82e5\u201c{desc}\u201d\u5f97\u5230\u89e3\u51b3\uff0c\u5219\u7ed3\u8bba\u53ef\u80fd\u53d8\u5316"
                )

            if len(conditions) >= 4:
                break

    if not conditions:
        conditions.append("\uff08\u5f85\u8bc6\u522b\u963b\u65ad\u6761\u4ef6\uff09")

    return conditions[:4]


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def render_layer1_md(layer1: Layer1Cover, perspective: str = "neutral") -> list[str]:
    """Render Layer 1 as Markdown lines.

    The ``perspective`` parameter is kept for API compatibility but no longer
    affects Layer 1 output (which is always perspective-independent in V3.1).
    """
    lines: list[str] = []

    # A. Neutral conclusion
    lines.append(f"## A. \u4e2d\u7acb\u7ed3\u8bba\u6458\u8981 {format_tag(SectionTag.inference)}")
    lines.append("")
    lines.append(f"> {layer1.cover_summary.neutral_conclusion}")
    lines.append("")

    # B. Winning move
    lines.append(f"## B. \u80dc\u8d1f\u624b {format_tag(SectionTag.inference)}")
    lines.append("")
    lines.append(layer1.cover_summary.winning_move or "\uff08\u5f85\u5206\u6790\uff09")
    lines.append("")

    # C. Blocking conditions
    lines.append(f"## C. \u963b\u65ad\u6761\u4ef6 {format_tag(SectionTag.assumption)}")
    lines.append("")
    if layer1.cover_summary.blocking_conditions:
        for i, cond in enumerate(layer1.cover_summary.blocking_conditions, 1):
            lines.append(f"{i}. {cond}")
    else:
        lines.append("\uff08\u65e0\u963b\u65ad\u6761\u4ef6\uff09")
    lines.append("")

    # D. Timeline
    lines.append(f"## D. \u6848\u4ef6\u65f6\u95f4\u7ebf {format_tag(SectionTag.fact)}")
    lines.append("")
    if layer1.timeline:
        lines.append("| \u65e5\u671f | \u4e8b\u4ef6 | \u6765\u6e90 | \u4e89\u8bae |")
        lines.append("|------|------|------|------|")
        for ev in layer1.timeline:
            disputed_marker = "\u26a0\ufe0f" if ev.disputed else ""
            source = ev.source or "\u2014"
            lines.append(f"| {ev.date} | {ev.event} | {source} | {disputed_marker} |")
    else:
        lines.append("\uff08\u65e0\u65f6\u95f4\u7ebf\u6570\u636e\uff09")
    lines.append("")

    # E. Evidence priorities
    lines.append(f"## E. \u8bc1\u636e\u4f18\u5148\u7ea7 {format_tag(SectionTag.inference)}")
    lines.append("")
    if layer1.evidence_priorities:
        lines.append("| \u8bc1\u636e | \u5c42\u7ea7 | \u7406\u7531 |")
        lines.append("|------|------|------|")
        for card in layer1.evidence_priorities:
            lines.append(f"| {card.title} | {card.priority.value} | {card.reason} |")
    else:
        lines.append("\uff08\u65e0\u8bc1\u636e\u4f18\u5148\u7ea7\u6570\u636e\uff09")
    lines.append("")

    return lines
