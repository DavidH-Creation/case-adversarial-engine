"""
Layer 1: 封面摘要层 / Cover Summary Layer.

决策者首页，极简：
  A. 中立结论摘要（一句话）
  B. 视角摘要（--perspective 驱动）
  C. 条件场景树摘要（if-then 格式，无百分比）
  D. 证据风险红绿灯
"""

from __future__ import annotations

from engines.report_generation.v3.evidence_classifier import classify_all_evidence
from engines.report_generation.v3.models import (
    CoverSummary,
    EvidenceRiskLevel,
    Layer1Cover,
    PerspectiveDefendantSummary,
    PerspectivePlaintiffSummary,
    SectionTag,
)
from engines.report_generation.v3.scenario_tree import render_scenario_tree_summary
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
    perspective: str = "neutral",
) -> Layer1Cover:
    """Build Layer 1 cover summary.

    Args:
        adversarial_result: AdversarialResult from debate
        evidence_index: EvidenceIndex
        issue_tree: IssueTree
        scenario_tree: ConditionalScenarioTree (optional)
        exec_summary: ExecutiveSummaryArtifact (optional)
        action_rec: ActionRecommendation (optional)
        attack_chain: OptimalAttackChain (optional)
        perspective: "plaintiff" / "defendant" / "neutral"

    Returns:
        Layer1Cover
    """
    # A. Neutral conclusion
    neutral_conclusion = _build_neutral_conclusion(adversarial_result, issue_tree)

    # B. Perspective summary
    plaintiff_summary = None
    defendant_summary = None

    if perspective in ("plaintiff", "neutral"):
        plaintiff_summary = _build_plaintiff_summary(
            adversarial_result, exec_summary, action_rec
        )

    if perspective in ("defendant", "neutral"):
        defendant_summary = _build_defendant_summary(
            adversarial_result, attack_chain, action_rec
        )

    cover = CoverSummary(
        neutral_conclusion=neutral_conclusion,
        plaintiff_summary=plaintiff_summary,
        defendant_summary=defendant_summary,
    )

    # C. Scenario tree summary
    tree_summary = ""
    if scenario_tree:
        tree_summary = render_scenario_tree_summary(scenario_tree)

    # D. Evidence traffic lights
    traffic_lights = classify_all_evidence(evidence_index.evidence)

    return Layer1Cover(
        cover_summary=cover,
        scenario_tree_summary=tree_summary,
        evidence_traffic_lights=traffic_lights,
    )


def _build_neutral_conclusion(adversarial_result, issue_tree) -> str:
    """Build a one-sentence neutral conclusion."""
    if adversarial_result and adversarial_result.summary:
        assessment = adversarial_result.summary.overall_assessment
        if assessment:
            # Take first sentence only
            first_sentence = assessment.split("。")[0] + "。"
            if len(first_sentence) > 200:
                first_sentence = first_sentence[:200] + "..."
            return first_sentence

    # Fallback: count issues and summarize
    n_issues = len(issue_tree.issues)
    n_open = sum(
        1 for i in issue_tree.issues
        if hasattr(i, "status") and i.status.value == "open"
    )
    return f"本案涉及 {n_issues} 个争点，其中 {n_open} 个尚未解决，双方在核心事实认定上存在分歧。"


def _build_plaintiff_summary(
    adversarial_result, exec_summary, action_rec,
) -> PerspectivePlaintiffSummary:
    """Build plaintiff perspective summary."""
    strengths: list[str] = []
    dangers: list[str] = []
    actions: list[str] = []

    # Strengths from adversarial result
    if adversarial_result and adversarial_result.summary:
        for arg in (adversarial_result.summary.plaintiff_strongest_arguments or [])[:3]:
            strengths.append(f"[{arg.issue_id}] {arg.position}")

    # Dangers from defendant's strongest defenses
    if adversarial_result and adversarial_result.summary:
        for d in (adversarial_result.summary.defendant_strongest_defenses or [])[:2]:
            dangers.append(f"[{d.issue_id}] {d.position}")

    # Actions from exec_summary or action_rec
    if exec_summary and isinstance(getattr(exec_summary, "top3_immediate_actions", None), list):
        actions = list(exec_summary.top3_immediate_actions[:3])
    elif action_rec:
        if getattr(action_rec, "evidence_supplement_priorities", None):
            actions.append(f"补强证据: {action_rec.evidence_supplement_priorities[0]}")
        if getattr(action_rec, "recommended_claim_amendments", None):
            am = action_rec.recommended_claim_amendments[0]
            actions.append(f"调整诉请: {am.amendment_description}")
        if getattr(action_rec, "claims_to_abandon", None):
            ab = action_rec.claims_to_abandon[0]
            actions.append(f"考虑放弃: {ab.abandon_reason}")

    # Ensure minimum entries
    if not strengths:
        strengths = ["（待分析原告优势）"]
    if not dangers:
        dangers = ["（待分析风险点）"]
    if not actions:
        actions = ["（待制定行动计划）"]

    return PerspectivePlaintiffSummary(
        top3_strengths=strengths[:3],
        top2_dangers=dangers[:2],
        top3_actions=actions[:3],
    )


def _build_defendant_summary(
    adversarial_result, attack_chain, action_rec,
) -> PerspectiveDefendantSummary:
    """Build defendant perspective summary."""
    defenses: list[str] = []
    supplement: list[str] = []
    attack_order: list[str] = []

    # Defenses from adversarial result
    if adversarial_result and adversarial_result.summary:
        for d in (adversarial_result.summary.defendant_strongest_defenses or [])[:3]:
            defenses.append(f"[{d.issue_id}] {d.position}")

    # Plaintiff's likely supplementation from action_rec
    if action_rec and getattr(action_rec, "evidence_supplement_priorities", None):
        for esp in action_rec.evidence_supplement_priorities[:3]:
            supplement.append(str(esp))

    # Optimal attack order from attack_chain
    if attack_chain:
        order = getattr(attack_chain, "recommended_order", [])
        if order:
            attack_order = list(order[:5])
        for node in getattr(attack_chain, "top_attacks", [])[:3]:
            if not attack_order:
                attack_order.append(f"{node.target_issue_id}: {node.attack_description}")

    # Ensure minimum entries
    if not defenses:
        defenses = ["（待分析被告防线）"]
    if not supplement:
        supplement = ["（待预测原告补强方向）"]
    if not attack_order:
        attack_order = ["（待制定攻击顺序）"]

    return PerspectiveDefendantSummary(
        top3_defenses=defenses[:3],
        plaintiff_likely_supplement=supplement[:3],
        optimal_attack_order=attack_order[:3],
    )


def render_layer1_md(layer1: Layer1Cover, perspective: str = "neutral") -> list[str]:
    """Render Layer 1 as Markdown lines."""
    lines: list[str] = []

    # A. Neutral conclusion
    lines.append(f"## A. 中立结论摘要 {format_tag(SectionTag.fact)}")
    lines.append("")
    lines.append(f"> {layer1.cover_summary.neutral_conclusion}")
    lines.append("")

    # B. Perspective summary
    if perspective == "plaintiff" and layer1.cover_summary.plaintiff_summary:
        ps = layer1.cover_summary.plaintiff_summary
        lines.append(f"## B. 原告视角摘要 {format_tag(SectionTag.recommendation)}")
        lines.append("")
        lines.append("### 三大优势")
        for i, s in enumerate(ps.top3_strengths, 1):
            lines.append(f"{i}. {s}")
        lines.append("")
        lines.append("### 两大危险")
        for i, d in enumerate(ps.top2_dangers, 1):
            lines.append(f"{i}. {d}")
        lines.append("")
        lines.append("### 三项立即行动")
        for i, a in enumerate(ps.top3_actions, 1):
            lines.append(f"{i}. {a}")
        lines.append("")

    elif perspective == "defendant" and layer1.cover_summary.defendant_summary:
        ds = layer1.cover_summary.defendant_summary
        lines.append(f"## B. 被告视角摘要 {format_tag(SectionTag.recommendation)}")
        lines.append("")
        lines.append("### 三大防线")
        for i, d in enumerate(ds.top3_defenses, 1):
            lines.append(f"{i}. {d}")
        lines.append("")
        lines.append("### 原告可能补强方向")
        for i, s in enumerate(ds.plaintiff_likely_supplement, 1):
            lines.append(f"{i}. {s}")
        lines.append("")
        lines.append("### 最优攻击顺序")
        for i, a in enumerate(ds.optimal_attack_order, 1):
            lines.append(f"{i}. {a}")
        lines.append("")

    else:
        # neutral: show both sides
        if layer1.cover_summary.plaintiff_summary:
            ps = layer1.cover_summary.plaintiff_summary
            lines.append(f"## B-1. 原告视角 {format_tag(SectionTag.recommendation)}")
            lines.append("")
            for i, s in enumerate(ps.top3_strengths, 1):
                lines.append(f"- 优势{i}: {s}")
            for i, d in enumerate(ps.top2_dangers, 1):
                lines.append(f"- 危险{i}: {d}")
            lines.append("")

        if layer1.cover_summary.defendant_summary:
            ds = layer1.cover_summary.defendant_summary
            lines.append(f"## B-2. 被告视角 {format_tag(SectionTag.recommendation)}")
            lines.append("")
            for i, d in enumerate(ds.top3_defenses, 1):
                lines.append(f"- 防线{i}: {d}")
            lines.append("")

    # C. Scenario tree summary
    if layer1.scenario_tree_summary:
        lines.append(f"## C. 条件场景摘要 {format_tag(SectionTag.inference)}")
        lines.append("")
        lines.append(layer1.scenario_tree_summary)
        lines.append("")

    # D. Evidence traffic lights
    if layer1.evidence_traffic_lights:
        lines.append(f"## D. 证据风险红绿灯 {format_tag(SectionTag.fact)}")
        lines.append("")
        lines.append("| 证据 | 标题 | 风险 | 理由 |")
        lines.append("|------|------|------|------|")
        _emoji = {
            EvidenceRiskLevel.green: "🟢",
            EvidenceRiskLevel.yellow: "🟡",
            EvidenceRiskLevel.red: "🔴",
        }
        for tl in layer1.evidence_traffic_lights:
            emoji = _emoji.get(tl.risk_level, "⚪")
            lines.append(
                f"| {tl.evidence_id} | {tl.title[:30]} | {emoji} | {tl.reason} |"
            )
        lines.append("")

    return lines
