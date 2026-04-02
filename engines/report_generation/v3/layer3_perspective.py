"""
Layer 3: 角色化输出层 / Role-based Output Layer (V3.1).

--perspective 驱动的 *纯动作方案* 输出层：
  每个角色获得 5 个行动导向板块（不重述 Layer 1/2 分析）：
    1. 补证清单          evidence_supplement_checklist
    2. 质证要点          cross_examination_points
    3. 庭审发问          trial_questions
    4. 应对预案          contingency_plans
    5. 过度主张边界      over_assertion_boundaries
  另附 unified_electronic_evidence_strategy（直接透传 Layer 2，不重新生成）。
"""

from __future__ import annotations

from typing import Optional

from engines.report_generation.v3.models import (
    ConditionalScenarioTree,
    EvidenceBasicCard,
    Layer3Perspective,
    PerspectiveOutput,
    SectionTag,
)
from engines.report_generation.v3.tag_system import format_tag


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


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
    evidence_cards: Optional[list] = None,
    unified_electronic_strategy: str = "",
    scenario_tree: Optional[ConditionalScenarioTree] = None,
    perspective: str = "neutral",
) -> Layer3Perspective:
    """Build Layer 3 role-based action-oriented output.

    V3.1: all output is action items, NOT analytical observations.
    New optional params (evidence_cards, unified_electronic_strategy,
    scenario_tree) are backward-compatible — callers that omit them still work.
    """
    outputs: list[PerspectiveOutput] = []

    if perspective in ("plaintiff", "neutral"):
        outputs.append(
            _build_plaintiff_output(
                adversarial_result,
                action_rec,
                attack_chain,
                hearing_order,
                issue_tree=issue_tree,
                evidence_index=evidence_index,
                exec_summary=exec_summary,
                evidence_cards=evidence_cards,
                scenario_tree=scenario_tree,
                unified_electronic_strategy=unified_electronic_strategy,
            )
        )

    if perspective in ("defendant", "neutral"):
        outputs.append(
            _build_defendant_output(
                adversarial_result,
                attack_chain,
                defense_chain,
                action_rec,
                issue_tree=issue_tree,
                evidence_index=evidence_index,
                exec_summary=exec_summary,
                evidence_cards=evidence_cards,
                scenario_tree=scenario_tree,
                unified_electronic_strategy=unified_electronic_strategy,
            )
        )

    return Layer3Perspective(outputs=outputs)


# ---------------------------------------------------------------------------
# Plaintiff perspective — pure action items
# ---------------------------------------------------------------------------


def _build_plaintiff_output(
    adversarial_result,
    action_rec,
    attack_chain,
    hearing_order,
    *,
    issue_tree=None,
    evidence_index=None,
    exec_summary=None,
    evidence_cards: Optional[list] = None,
    scenario_tree: Optional[ConditionalScenarioTree] = None,
    unified_electronic_strategy: str = "",
) -> PerspectiveOutput:
    """Build plaintiff perspective output — 5 action-oriented sections."""
    output = PerspectiveOutput(
        perspective="plaintiff",
        unified_electronic_evidence_strategy=unified_electronic_strategy,
    )

    # --- 1. 补证清单 (evidence_supplement_checklist) -----------------------
    # Sources: action_rec.evidence_supplement_priorities + plaintiff's weak evidence
    _fill_supplement_checklist_plaintiff(output, action_rec, evidence_index, issue_tree)

    # --- 2. 质证要点 (cross_examination_points) ----------------------------
    # Target: defendant's evidence; attack via q4_best_attack
    _fill_cross_exam_plaintiff(output, evidence_cards, evidence_index)

    # --- 3. 庭审发问 (trial_questions) ------------------------------------
    # Sources: evidence_conflicts + issue gaps → questions to ask defendant
    _fill_trial_questions_plaintiff(output, adversarial_result, issue_tree)

    # --- 4. 应对预案 (contingency_plans) -----------------------------------
    # Source: scenario tree conditions
    _fill_contingency_plans(output, scenario_tree, perspective="plaintiff")

    # --- 5. 过度主张边界 (over_assertion_boundaries) -----------------------
    # Source: unresolved_issues + weak evidence indicators
    _fill_over_assertion_boundaries_plaintiff(
        output,
        adversarial_result,
        issue_tree,
        evidence_index,
    )

    return output


# ---------------------------------------------------------------------------
# Defendant perspective — pure action items
# ---------------------------------------------------------------------------


def _build_defendant_output(
    adversarial_result,
    attack_chain,
    defense_chain,
    action_rec,
    *,
    issue_tree=None,
    evidence_index=None,
    exec_summary=None,
    evidence_cards: Optional[list] = None,
    scenario_tree: Optional[ConditionalScenarioTree] = None,
    unified_electronic_strategy: str = "",
) -> PerspectiveOutput:
    """Build defendant perspective output — 5 action-oriented sections."""
    output = PerspectiveOutput(
        perspective="defendant",
        unified_electronic_evidence_strategy=unified_electronic_strategy,
    )

    # --- 1. 补证清单 -------------------------------------------------------
    _fill_supplement_checklist_defendant(output, action_rec, evidence_index, issue_tree)

    # --- 2. 质证要点 -------------------------------------------------------
    # Target: plaintiff's evidence; attack via q4_best_attack
    _fill_cross_exam_defendant(output, evidence_cards, evidence_index)

    # --- 3. 庭审发问 -------------------------------------------------------
    # Questions to ask plaintiff / plaintiff witnesses
    _fill_trial_questions_defendant(output, adversarial_result, issue_tree)

    # --- 4. 应对预案 -------------------------------------------------------
    _fill_contingency_plans(output, scenario_tree, perspective="defendant")

    # --- 5. 过度主张边界 ---------------------------------------------------
    _fill_over_assertion_boundaries_defendant(
        output,
        adversarial_result,
        issue_tree,
        evidence_index,
    )

    return output


# ---------------------------------------------------------------------------
# Section builders — Plaintiff
# ---------------------------------------------------------------------------


def _fill_supplement_checklist_plaintiff(
    output: PerspectiveOutput,
    action_rec,
    evidence_index,
    issue_tree,
) -> None:
    """补证清单 for plaintiff: what concrete evidence to obtain."""
    # Primary source: action_rec.evidence_supplement_priorities
    if action_rec:
        for esp in (getattr(action_rec, "evidence_supplement_priorities", None) or [])[:5]:
            issue_ctx = _resolve_issue_title(str(getattr(esp, "issue_id", "")), issue_tree)
            desc = str(esp)
            if issue_ctx and issue_ctx not in desc:
                desc = f"针对{issue_ctx}：{desc}"
            output.evidence_supplement_checklist.append(desc)

    # Supplement from evidence_index: plaintiff evidence with low admissibility
    if evidence_index and len(output.evidence_supplement_checklist) < 3:
        for ev in evidence_index.evidence:
            owner = getattr(ev, "owner_party_id", "")
            adm = getattr(ev, "admissibility_score", 1.0)
            if "plaintiff" in owner.lower() or "原告" in owner:
                if adm < 0.7:
                    gap_str = (
                        f"针对{ev.title}（可采性{adm:.0%}）：补强{_evidence_reinforce_hint(ev)}"
                    )
                    output.evidence_supplement_checklist.append(gap_str)
            if len(output.evidence_supplement_checklist) >= 5:
                break


def _fill_cross_exam_plaintiff(
    output: PerspectiveOutput,
    evidence_cards: Optional[list],
    evidence_index,
) -> None:
    """质证要点 for plaintiff: challenge each defendant core evidence."""
    defendant_cards = _get_opponent_cards(
        evidence_cards,
        evidence_index,
        opponent_keywords=("defendant", "被告"),
    )
    for card in defendant_cards[:5]:
        attack = getattr(card, "q4_best_attack", "")
        title = _card_title(card, evidence_index)
        if attack:
            output.cross_examination_points.append(f"针对「{title}」：{attack}")


def _fill_trial_questions_plaintiff(
    output: PerspectiveOutput,
    adversarial_result,
    issue_tree,
) -> None:
    """庭审发问 for plaintiff: questions targeting defendant factual contradictions."""
    q_num = 0
    # From evidence_conflicts
    if adversarial_result:
        for conflict in (adversarial_result.evidence_conflicts or [])[:5]:
            q_num += 1
            issue_ctx = _resolve_issue_title(conflict.issue_id, issue_tree)
            desc = conflict.conflict_description
            output.trial_questions.append(
                f"问被告（{issue_ctx or conflict.issue_id}）：{desc}如何解释？"
            )

    # From issue tree gaps (issues with missing evidence on defendant side)
    if issue_tree and q_num < 3:
        for iss in issue_tree.issues:
            if q_num >= 5:
                break
            # Look for issues where defendant has burden but evidence is thin
            if _issue_has_defendant_burden(iss, issue_tree):
                q_num += 1
                output.trial_questions.append(f"问被告（{iss.title}）：请提供支持该抗辩的具体证据")


def _fill_over_assertion_boundaries_plaintiff(
    output: PerspectiveOutput,
    adversarial_result,
    issue_tree,
    evidence_index,
) -> None:
    """过度主张边界 for plaintiff: what NOT to over-claim."""
    if adversarial_result:
        for issue_id in (adversarial_result.unresolved_issues or [])[:3]:
            issue_title = _resolve_issue_title(issue_id, issue_tree)
            reason = _weak_evidence_reason(issue_id, evidence_index, "plaintiff")
            output.over_assertion_boundaries.append(
                f"不建议在{issue_title or issue_id}上过度主张"
                + (f"，因为{reason}" if reason else "，该争点尚未闭合")
            )

    # Also flag claims_to_abandon from action_rec
    if not output.over_assertion_boundaries:
        # Fallback: any issue with high dispute_ratio evidence
        if evidence_index:
            for ev in evidence_index.evidence:
                owner = getattr(ev, "owner_party_id", "")
                if "plaintiff" in owner.lower() or "原告" in owner:
                    dr = getattr(ev, "dispute_ratio", None)
                    if dr is not None and dr > 0.6:
                        output.over_assertion_boundaries.append(
                            f"不建议过度依赖{ev.title}（争议比{dr:.0%}），需准备替代方案"
                        )
                if len(output.over_assertion_boundaries) >= 3:
                    break


# ---------------------------------------------------------------------------
# Section builders — Defendant
# ---------------------------------------------------------------------------


def _fill_supplement_checklist_defendant(
    output: PerspectiveOutput,
    action_rec,
    evidence_index,
    issue_tree,
) -> None:
    """补证清单 for defendant: evidence to gather for defense."""
    # From action_rec — predict what plaintiff will supplement, then pre-empt
    if action_rec:
        for esp in (getattr(action_rec, "evidence_supplement_priorities", None) or [])[:3]:
            issue_ctx = _resolve_issue_title(str(getattr(esp, "issue_id", "")), issue_tree)
            output.evidence_supplement_checklist.append(
                f"针对{issue_ctx or '相关争点'}：预判原告将补强{esp}，应提前准备反证"
            )

    # Defendant's own weak evidence needing supplementation
    if evidence_index and len(output.evidence_supplement_checklist) < 3:
        for ev in evidence_index.evidence:
            owner = getattr(ev, "owner_party_id", "")
            adm = getattr(ev, "admissibility_score", 1.0)
            if "defendant" in owner.lower() or "被告" in owner:
                if adm < 0.7:
                    gap_str = (
                        f"针对{ev.title}（可采性{adm:.0%}）：补强{_evidence_reinforce_hint(ev)}"
                    )
                    output.evidence_supplement_checklist.append(gap_str)
            if len(output.evidence_supplement_checklist) >= 5:
                break


def _fill_cross_exam_defendant(
    output: PerspectiveOutput,
    evidence_cards: Optional[list],
    evidence_index,
) -> None:
    """质证要点 for defendant: challenge each plaintiff core evidence."""
    plaintiff_cards = _get_opponent_cards(
        evidence_cards,
        evidence_index,
        opponent_keywords=("plaintiff", "原告"),
    )
    for card in plaintiff_cards[:5]:
        attack = getattr(card, "q4_best_attack", "")
        title = _card_title(card, evidence_index)
        if attack:
            output.cross_examination_points.append(f"针对「{title}」：{attack}")


def _fill_trial_questions_defendant(
    output: PerspectiveOutput,
    adversarial_result,
    issue_tree,
) -> None:
    """庭审发问 for defendant: questions targeting plaintiff factual contradictions."""
    q_num = 0
    if adversarial_result:
        for conflict in (adversarial_result.evidence_conflicts or [])[:5]:
            q_num += 1
            issue_ctx = _resolve_issue_title(conflict.issue_id, issue_tree)
            desc = conflict.conflict_description
            output.trial_questions.append(
                f"问原告（{issue_ctx or conflict.issue_id}）：{desc}如何解释？"
            )

    # From issue tree: issues where plaintiff has burden but evidence is weak
    if issue_tree and q_num < 3:
        for iss in issue_tree.issues:
            if q_num >= 5:
                break
            if _issue_has_plaintiff_burden(iss, issue_tree):
                q_num += 1
                output.trial_questions.append(f"问原告（{iss.title}）：请提供支持该主张的直接证据")


def _fill_over_assertion_boundaries_defendant(
    output: PerspectiveOutput,
    adversarial_result,
    issue_tree,
    evidence_index,
) -> None:
    """过度主张边界 for defendant: what NOT to over-claim."""
    if adversarial_result:
        for issue_id in (adversarial_result.unresolved_issues or [])[:3]:
            issue_title = _resolve_issue_title(issue_id, issue_tree)
            reason = _weak_evidence_reason(issue_id, evidence_index, "defendant")
            output.over_assertion_boundaries.append(
                f"不建议在{issue_title or issue_id}上过度主张"
                + (f"，因为{reason}" if reason else "，该争点尚未闭合")
            )

    if not output.over_assertion_boundaries:
        if evidence_index:
            for ev in evidence_index.evidence:
                owner = getattr(ev, "owner_party_id", "")
                if "defendant" in owner.lower() or "被告" in owner:
                    dr = getattr(ev, "dispute_ratio", None)
                    if dr is not None and dr > 0.6:
                        output.over_assertion_boundaries.append(
                            f"不建议过度依赖{ev.title}（争议比{dr:.0%}），需准备替代方案"
                        )
                if len(output.over_assertion_boundaries) >= 3:
                    break


# ---------------------------------------------------------------------------
# Shared section builder — contingency plans
# ---------------------------------------------------------------------------


def _fill_contingency_plans(
    output: PerspectiveOutput,
    scenario_tree: Optional[ConditionalScenarioTree],
    perspective: str,
) -> None:
    """应对预案 from scenario tree: if-then contingencies."""
    if not scenario_tree or not scenario_tree.nodes:
        return

    node_map = {n.node_id: n for n in scenario_tree.nodes}

    def _collect_contingencies(
        node_id: str,
        depth: int = 0,
    ) -> list[str]:
        if depth > 4:
            return []
        node = node_map.get(node_id)
        if not node:
            return []

        items: list[str] = []
        if node.yes_outcome and node.no_outcome:
            items.append(f"若{node.condition} → {node.yes_outcome}；否则 → {node.no_outcome}")
        elif node.yes_outcome:
            items.append(f"若{node.condition} → {node.yes_outcome}")
        elif node.no_outcome:
            items.append(f"若{node.condition}不成立 → {node.no_outcome}")

        # Recurse into children
        if node.yes_child_id:
            items.extend(_collect_contingencies(node.yes_child_id, depth + 1))
        if node.no_child_id:
            items.extend(_collect_contingencies(node.no_child_id, depth + 1))
        return items

    contingencies = _collect_contingencies(scenario_tree.root_node_id)
    for c in contingencies[:5]:
        output.contingency_plans.append(c)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_issue_title(issue_id: str, issue_tree) -> str:
    """Look up issue title from issue_tree by ID."""
    if not issue_tree or not issue_id:
        return ""
    for iss in issue_tree.issues:
        if iss.issue_id == issue_id:
            return f"「{iss.title}」"
    return ""


def _get_opponent_cards(
    evidence_cards: Optional[list],
    evidence_index,
    opponent_keywords: tuple[str, ...],
) -> list:
    """Return evidence cards belonging to the opponent party.

    Uses evidence_index to look up owner_party_id for each card.
    Prioritizes core-priority cards.
    """
    if not evidence_cards:
        return []

    # Build lookup: evidence_id -> owner_party_id
    owner_map: dict[str, str] = {}
    if evidence_index:
        for ev in evidence_index.evidence:
            owner_map[ev.evidence_id] = getattr(ev, "owner_party_id", "")

    opponent_cards = []
    for card in evidence_cards:
        eid = getattr(card, "evidence_id", "")
        owner = owner_map.get(eid, "").lower()
        if any(kw in owner for kw in opponent_keywords):
            opponent_cards.append(card)

    # Sort: core evidence first
    from engines.report_generation.v3.models import EvidencePriority

    def _priority_sort(c: EvidenceBasicCard) -> int:
        p = getattr(c, "priority", EvidencePriority.supporting)
        if p == EvidencePriority.core:
            return 0
        if p == EvidencePriority.supporting:
            return 1
        return 2

    opponent_cards.sort(key=_priority_sort)
    return opponent_cards


def _card_title(card, evidence_index) -> str:
    """Get a human-readable title for an evidence card."""
    eid = getattr(card, "evidence_id", "")
    # Try to get title from evidence_index
    if evidence_index:
        for ev in evidence_index.evidence:
            if ev.evidence_id == eid:
                return ev.title
    # Fallback: q1_what or evidence_id
    return getattr(card, "q1_what", eid) or eid


def _evidence_reinforce_hint(ev) -> str:
    """Generate a hint on how to reinforce weak evidence."""
    notes = getattr(ev, "admissibility_notes", "") or ""
    risk = getattr(ev, "admissibility_risk", "") or ""
    if "原件" in notes or "原件" in risk:
        return "原件核实或公证"
    if "录音" in notes or "录音" in risk:
        return "录音合法性鉴定或补充其他佐证"
    if "截图" in notes or "截图" in risk:
        return "完整数据导出或公证保全"
    if notes:
        return f"补强方向：{notes[:30]}"
    return "补充佐证材料"


def _weak_evidence_reason(issue_id: str, evidence_index, party_keyword: str) -> str:
    """Find reason why a party's evidence is weak for a given issue."""
    if not evidence_index or not issue_id:
        return ""
    for ev in evidence_index.evidence:
        owner = getattr(ev, "owner_party_id", "").lower()
        target_issues = getattr(ev, "target_issue_ids", [])
        if party_keyword in owner and issue_id in target_issues:
            adm = getattr(ev, "admissibility_score", 1.0)
            if adm < 0.7:
                return f"关键证据「{ev.title}」可采性仅{adm:.0%}"
            dr = getattr(ev, "dispute_ratio", None)
            if dr is not None and dr > 0.5:
                return f"关键证据「{ev.title}」争议比高达{dr:.0%}"
    return ""


def _issue_has_defendant_burden(issue, issue_tree) -> bool:
    """Check if an issue has defendant burden of proof (heuristic)."""
    if not issue_tree:
        return False
    for burden in getattr(issue_tree, "burdens", []):
        if burden.issue_id == issue.issue_id:
            party = getattr(burden, "burden_party_id", "")
            if "defendant" in party.lower() or "被告" in party:
                return True
    return False


def _issue_has_plaintiff_burden(issue, issue_tree) -> bool:
    """Check if an issue has plaintiff burden of proof (heuristic)."""
    if not issue_tree:
        return False
    for burden in getattr(issue_tree, "burdens", []):
        if burden.issue_id == issue.issue_id:
            party = getattr(burden, "burden_party_id", "")
            if "plaintiff" in party.lower() or "原告" in party:
                return True
    return False


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------


def render_layer3_md(layer3: Layer3Perspective, perspective: str = "neutral") -> list[str]:
    """Render Layer 3 as Markdown lines — V3.1 action-oriented sections."""
    lines: list[str] = []
    lines.append(f"# 三、角色化输出 {format_tag(SectionTag.recommendation)}")
    lines.append("")

    for output in layer3.outputs:
        if output.perspective == "plaintiff":
            lines.extend(
                _render_perspective_md(
                    output,
                    title="原告策略「建议」",
                    ask_target="被告",
                )
            )
        elif output.perspective == "defendant":
            lines.extend(
                _render_perspective_md(
                    output,
                    title="被告策略「建议」",
                    ask_target="原告",
                )
            )

    return lines


def _render_perspective_md(
    output: PerspectiveOutput,
    title: str,
    ask_target: str,
) -> list[str]:
    """Render a single perspective's 5 action sections."""
    lines: list[str] = []
    lines.append(f"## {title}")
    lines.append("")

    # 1. 补证清单
    if output.evidence_supplement_checklist:
        lines.append(f"### 补证清单 {format_tag(SectionTag.recommendation)}")
        for i, item in enumerate(output.evidence_supplement_checklist, 1):
            lines.append(f"{i}. {item}")
        lines.append("")

    # 2. 质证要点
    if output.cross_examination_points:
        lines.append(f"### 质证要点 {format_tag(SectionTag.recommendation)}")
        for i, item in enumerate(output.cross_examination_points, 1):
            lines.append(f"{i}. {item}")
        lines.append("")

    # 3. 庭审发问
    if output.trial_questions:
        lines.append(f"### 庭审发问 {format_tag(SectionTag.recommendation)}")
        for i, item in enumerate(output.trial_questions, 1):
            lines.append(f"{i}. {item}")
        lines.append("")

    # 4. 应对预案
    if output.contingency_plans:
        lines.append(f"### 应对预案 {format_tag(SectionTag.inference)}")
        for i, item in enumerate(output.contingency_plans, 1):
            lines.append(f"{i}. {item}")
        lines.append("")

    # 5. 过度主张边界
    if output.over_assertion_boundaries:
        lines.append(f"### 过度主张边界 {format_tag(SectionTag.opinion)}")
        for i, item in enumerate(output.over_assertion_boundaries, 1):
            lines.append(f"{i}. {item}")
        lines.append("")

    # 统一电子证据补强策略 (passthrough from Layer 2)
    if output.unified_electronic_evidence_strategy:
        lines.append(f"### 电子证据补强策略 {format_tag(SectionTag.recommendation)}")
        lines.append("")
        lines.append(output.unified_electronic_evidence_strategy)
        lines.append("")

    return lines
