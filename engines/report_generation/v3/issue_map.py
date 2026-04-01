"""
争点地图生成器 / Issue Map Generator.

为每个争点生成固定模板的卡片：
  争点 / 原告主张 / 被告主张 / 决定性证据 / 当前缺口 / 结果敏感度

完全中立，不偏向任何一方。
"""

from __future__ import annotations

from engines.report_generation.v3.models import IssueMapCard, SectionTag


def build_issue_map(
    issue_tree,
    adversarial_result=None,
    ranked_issues=None,
    attack_chain=None,
) -> list[IssueMapCard]:
    """Build issue map cards from pipeline data.

    Each card follows a fixed template:
    - issue_id + title
    - Plaintiff thesis (from claims / adversarial arguments)
    - Defendant thesis (from defenses / adversarial arguments)
    - Decisive evidence IDs
    - Current gaps
    - Outcome sensitivity

    Args:
        issue_tree: IssueTree from pipeline
        adversarial_result: AdversarialResult for plaintiff/defendant arguments
        ranked_issues: IssueTree with ranking data (from IssueImpactRanker)
        attack_chain: OptimalAttackChain (optional)

    Returns:
        List of IssueMapCard, one per issue
    """
    cards: list[IssueMapCard] = []

    # Build lookup maps from adversarial result.
    # Source: adversarial debate analysis — theses are presented neutrally
    # (both sides) with explicit source attribution.
    plaintiff_args: dict[str, str] = {}
    defendant_args: dict[str, str] = {}

    if adversarial_result and adversarial_result.summary:
        for arg in (adversarial_result.summary.plaintiff_strongest_arguments or []):
            plaintiff_args[arg.issue_id] = f"{arg.position}: {arg.reasoning}"
        for arg in (adversarial_result.summary.defendant_strongest_defenses or []):
            defendant_args[arg.issue_id] = f"{arg.position}: {arg.reasoning}"

    # Build from best arguments if summary is sparse
    if adversarial_result:
        for arg in (adversarial_result.plaintiff_best_arguments or []):
            if arg.issue_id not in plaintiff_args:
                plaintiff_args[arg.issue_id] = arg.position
        for arg in (adversarial_result.defendant_best_defenses or []):
            if arg.issue_id not in defendant_args:
                defendant_args[arg.issue_id] = arg.position

    # Attack chain targets for gap analysis
    attack_targets: dict[str, str] = {}
    if attack_chain:
        for node in getattr(attack_chain, "top_attacks", []):
            attack_targets[node.target_issue_id] = node.attack_description

    # Use ranked issues if available, otherwise original issue_tree
    issues = ranked_issues.issues if ranked_issues else issue_tree.issues

    for issue in issues:
        # Determine outcome sensitivity from ranking data
        sensitivity = ""
        if hasattr(issue, "composite_score") and issue.composite_score is not None:
            if issue.composite_score > 70:
                sensitivity = "极高 — 该争点翻转将直接改变裁判结果"
            elif issue.composite_score > 40:
                sensitivity = "中等 — 该争点影响部分诉请金额或责任分配"
            else:
                sensitivity = "较低 — 该争点对最终结果影响有限"
        elif hasattr(issue, "outcome_impact") and issue.outcome_impact:
            impact_val = issue.outcome_impact.value if hasattr(issue.outcome_impact, "value") else str(issue.outcome_impact)
            sensitivity_map = {
                "decisive": "极高 — 该争点翻转将直接改变裁判结果",
                "significant": "中等 — 该争点影响部分诉请金额或责任分配",
                "moderate": "中等 — 该争点影响部分诉请金额或责任分配",
                "marginal": "较低 — 该争点对最终结果影响有限",
            }
            sensitivity = sensitivity_map.get(impact_val, "")

        # Collect current gaps
        gaps: list[str] = []
        if issue.issue_id in attack_targets:
            gaps.append(f"被攻击点: {attack_targets[issue.issue_id]}")
        if hasattr(issue, "recommended_action") and issue.recommended_action:
            action_val = issue.recommended_action.value if hasattr(issue.recommended_action, "value") else str(issue.recommended_action)
            if action_val in ("supplement_evidence", "reassess"):
                gaps.append(f"建议行动: {action_val}")

        # Source-attribute theses: if from adversarial debate, mark as such
        p_thesis = plaintiff_args.get(issue.issue_id, "")
        d_thesis = defendant_args.get(issue.issue_id, "")
        p_thesis_attributed = (
            f"[来源:对抗分析] {p_thesis}" if p_thesis else "（待补充原告主张）"
        )
        d_thesis_attributed = (
            f"[来源:对抗分析] {d_thesis}" if d_thesis else "（待补充被告主张）"
        )

        cards.append(IssueMapCard(
            issue_id=issue.issue_id,
            issue_title=issue.title,
            plaintiff_thesis=p_thesis_attributed,
            defendant_thesis=d_thesis_attributed,
            decisive_evidence=issue.evidence_ids[:5] if issue.evidence_ids else [],
            current_gaps=gaps,
            outcome_sensitivity=sensitivity,
            tag=SectionTag.inference,
        ))

    return cards
