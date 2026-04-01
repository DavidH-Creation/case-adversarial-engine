"""
Layer 3: 角色化输出层 / Role-based Output Layer.

--perspective 驱动的策略输出层：
  plaintiff: 三大诉请、攻击链预警、补强清单、庭审顺序、应放弃诉请
  defendant: 三大防线、原告补强预测、优先质证目标、应提动议、过度主张警告
  neutral (default): 双方均等展示
"""

from __future__ import annotations

from engines.report_generation.v3.models import (
    Layer3Perspective,
    PerspectiveOutput,
    SectionTag,
)
from engines.report_generation.v3.tag_system import format_tag


def build_layer3(
    *,
    adversarial_result,
    issue_tree,
    evidence_index,
    action_rec=None,
    attack_chain=None,
    defense_chain=None,
    exec_summary=None,
    hearing_order=None,
    perspective: str = "neutral",
) -> Layer3Perspective:
    """Build Layer 3 role-based output.

    The perspective flag completely changes what is shown:
    - plaintiff: offense strategy
    - defendant: defense strategy
    - neutral: both sides equally
    """
    outputs: list[PerspectiveOutput] = []

    if perspective in ("plaintiff", "neutral"):
        outputs.append(_build_plaintiff_output(
            adversarial_result, action_rec, attack_chain, hearing_order,
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            exec_summary=exec_summary,
        ))

    if perspective in ("defendant", "neutral"):
        outputs.append(_build_defendant_output(
            adversarial_result, attack_chain, defense_chain, action_rec,
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            exec_summary=exec_summary,
        ))

    return Layer3Perspective(outputs=outputs)


def _build_plaintiff_output(
    adversarial_result, action_rec, attack_chain, hearing_order,
    *, issue_tree=None, evidence_index=None, exec_summary=None,
) -> PerspectiveOutput:
    """Build plaintiff perspective output."""
    output = PerspectiveOutput(perspective="plaintiff")

    # Top claims
    if adversarial_result and adversarial_result.summary:
        for arg in (adversarial_result.summary.plaintiff_strongest_arguments or [])[:3]:
            ev_str = ", ".join(arg.supporting_evidence_ids[:3]) if hasattr(arg, "supporting_evidence_ids") else ""
            output.top_claims.append(
                f"[{arg.issue_id}] {arg.position}" + (f" (证据: {ev_str})" if ev_str else "")
            )

    # Defendant attack chain warnings
    if attack_chain:
        for node in getattr(attack_chain, "top_attacks", [])[:5]:
            warning = f"{node.target_issue_id}: {node.attack_description}"
            if node.counter_measure:
                warning += f" → 应对: {node.counter_measure}"
            output.defendant_attack_chains.append(warning)

    # Evidence to supplement — ground with actual evidence from evidence_index
    if action_rec:
        for esp in (getattr(action_rec, "evidence_supplement_priorities", None) or [])[:5]:
            output.evidence_to_supplement.append(str(esp))
    elif evidence_index:
        # Fallback: identify weak evidence that needs supplementation
        for ev in evidence_index.evidence:
            adm = getattr(ev, "admissibility_score", 1.0)
            if adm < 0.7 and getattr(ev, "owner_party_id", "") != "":
                output.evidence_to_supplement.append(
                    f"{ev.evidence_id}: {ev.title}（可采性 {adm:.0%}，需补强）"
                )
            if len(output.evidence_to_supplement) >= 5:
                break

    # Trial sequence
    if hearing_order:
        for item in (getattr(hearing_order, "hearing_items", None) or [])[:5]:
            output.trial_sequence.append(
                f"{getattr(item, 'order', '?')}. {getattr(item, 'description', str(item))}"
            )

    # Claims to abandon — ground with issue_tree data
    if action_rec:
        for ab in (getattr(action_rec, "claims_to_abandon", None) or []):
            output.claims_to_abandon.append(
                f"{ab.claim_id}: {ab.abandon_reason}"
            )

    # Ground with exec_summary immediate actions if available
    if exec_summary and not output.evidence_to_supplement:
        for action in (getattr(exec_summary, "top3_immediate_actions", None) or [])[:3]:
            output.evidence_to_supplement.append(str(action))

    return output


def _build_defendant_output(
    adversarial_result, attack_chain, defense_chain, action_rec,
    *, issue_tree=None, evidence_index=None, exec_summary=None,
) -> PerspectiveOutput:
    """Build defendant perspective output."""
    output = PerspectiveOutput(perspective="defendant")

    # Top defenses
    if adversarial_result and adversarial_result.summary:
        for d in (adversarial_result.summary.defendant_strongest_defenses or [])[:3]:
            ev_str = ", ".join(d.supporting_evidence_ids[:3]) if hasattr(d, "supporting_evidence_ids") else ""
            output.top_defenses.append(
                f"[{d.issue_id}] {d.position}" + (f" (证据: {ev_str})" if ev_str else "")
            )

    # Plaintiff supplement prediction
    if action_rec:
        for esp in (getattr(action_rec, "evidence_supplement_priorities", None) or [])[:3]:
            output.plaintiff_supplement_prediction.append(
                f"原告可能补强: {esp}"
            )

    # Evidence to challenge first — ground with evidence_index
    if attack_chain:
        order = getattr(attack_chain, "recommended_order", [])
        for target_id in order[:3]:
            for node in getattr(attack_chain, "top_attacks", []):
                if node.target_issue_id == target_id:
                    output.evidence_to_challenge_first.append(
                        f"{target_id}: {node.attack_description}"
                    )
                    break
    elif evidence_index:
        # Fallback: identify opponent evidence with low admissibility to challenge
        for ev in evidence_index.evidence:
            adm = getattr(ev, "admissibility_score", 1.0)
            if adm < 0.7:
                output.evidence_to_challenge_first.append(
                    f"{ev.evidence_id}: {ev.title}（可采性 {adm:.0%}，优先质证）"
                )
            if len(output.evidence_to_challenge_first) >= 3:
                break

    # Defense chain motions
    if defense_chain:
        for step in (getattr(defense_chain, "defense_steps", None) or [])[:3]:
            output.motions_to_file.append(
                f"{getattr(step, 'step_id', '?')}: {getattr(step, 'description', str(step))}"
            )

    # Over-assertion warnings — ground with issue_tree data
    if adversarial_result:
        for issue_id in (adversarial_result.unresolved_issues or [])[:3]:
            # Enrich with issue title from issue_tree
            issue_title = ""
            if issue_tree:
                for iss in issue_tree.issues:
                    if iss.issue_id == issue_id:
                        issue_title = f"「{iss.title}」"
                        break
            output.over_assertion_warnings.append(
                f"争点 {issue_id}{issue_title} 尚未解决，避免过度主张"
            )

    return output


def render_layer3_md(layer3: Layer3Perspective, perspective: str = "neutral") -> list[str]:
    """Render Layer 3 as Markdown lines."""
    lines: list[str] = []
    lines.append(f"# 三、角色化输出 {format_tag(SectionTag.recommendation)}")
    lines.append("")

    for output in layer3.outputs:
        if output.perspective == "plaintiff":
            lines.append(f"## 原告策略 {format_tag(SectionTag.recommendation)}")
            lines.append("")

            if output.top_claims:
                lines.append("### 三大诉请")
                for i, c in enumerate(output.top_claims, 1):
                    lines.append(f"{i}. {c}")
                lines.append("")

            if output.defendant_attack_chains:
                lines.append(f"### 被告攻击链预警 {format_tag(SectionTag.inference)}")
                for w in output.defendant_attack_chains:
                    lines.append(f"- {w}")
                lines.append("")

            if output.evidence_to_supplement:
                lines.append(f"### 需补强证据清单 {format_tag(SectionTag.recommendation)}")
                for i, e in enumerate(output.evidence_to_supplement, 1):
                    lines.append(f"{i}. {e}")
                lines.append("")

            if output.trial_sequence:
                lines.append(f"### 庭审举证顺序建议 {format_tag(SectionTag.recommendation)}")
                for s in output.trial_sequence:
                    lines.append(f"- {s}")
                lines.append("")

            if output.claims_to_abandon:
                lines.append(f"### 应放弃的诉请 {format_tag(SectionTag.opinion)}")
                for a in output.claims_to_abandon:
                    lines.append(f"- {a}")
                lines.append("")

        elif output.perspective == "defendant":
            lines.append(f"## 被告策略 {format_tag(SectionTag.recommendation)}")
            lines.append("")

            if output.top_defenses:
                lines.append("### 三大防线")
                for i, d in enumerate(output.top_defenses, 1):
                    lines.append(f"{i}. {d}")
                lines.append("")

            if output.plaintiff_supplement_prediction:
                lines.append(f"### 原告可能补强方向 {format_tag(SectionTag.inference)}")
                for p in output.plaintiff_supplement_prediction:
                    lines.append(f"- {p}")
                lines.append("")

            if output.evidence_to_challenge_first:
                lines.append(f"### 优先质证目标 {format_tag(SectionTag.recommendation)}")
                for i, e in enumerate(output.evidence_to_challenge_first, 1):
                    lines.append(f"{i}. {e}")
                lines.append("")

            if output.motions_to_file:
                lines.append(f"### 应提交的动议 {format_tag(SectionTag.recommendation)}")
                for m in output.motions_to_file:
                    lines.append(f"- {m}")
                lines.append("")

            if output.over_assertion_warnings:
                lines.append(f"### 过度主张警告 {format_tag(SectionTag.opinion)}")
                for w in output.over_assertion_warnings:
                    lines.append(f"- {w}")
                lines.append("")

    return lines
