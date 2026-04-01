"""
证据作战矩阵生成器 / Evidence Battle Matrix Generator.

V3.1 双层证据卡：
  - EvidenceBasicCard（4 字段）：所有辅助/背景证据
  - EvidenceKeyCard （6 字段）：核心证据额外含加固策略和失效影响

观测性阈值 (Observability Threshold):
  信息不足时不填套话，明确标注"信息不足，需查看原件后判断"。

统一电子证据策略 (Unified Electronic Strategy):
  公共补强动作（如"申请司法鉴定"）抽取到 unified_electronic_strategy，
  各卡片只保留差异化动作。

完全中立分析，无 LLM 调用。
"""

from __future__ import annotations

from collections import Counter
from typing import Union

from engines.report_generation.v3.evidence_classifier import (
    classify_evidence_priority,
    classify_evidence_risk,  # kept for backward compat
)
from engines.report_generation.v3.models import (
    EvidenceBasicCard,
    EvidenceBattleCard,  # kept for backward compat
    EvidenceKeyCard,
    EvidencePriority,
    SectionTag,
)

# ---------------------------------------------------------------------------
# Observability threshold
# ---------------------------------------------------------------------------

_INSUFFICIENT_MSG = "信息不足，需查看原件后判断"


def _has_sufficient_observability(evidence) -> bool:
    """Check if we have enough information to analyze this evidence in detail.

    Requires at least 2 positive signals out of 4 checks:
    - Has meaningful summary (not just title repeat)
    - Has specific source info
    - Has admissibility challenge data
    - Has authenticity risk data
    """
    checks = 0

    summary = getattr(evidence, "summary", "")
    title = getattr(evidence, "title", "")
    if summary and len(summary) > len(title) + 20:
        checks += 1

    source = getattr(evidence, "source", "")
    if source and len(source) > 5:
        checks += 1

    if getattr(evidence, "admissibility_challenges", []):
        checks += 1

    if getattr(evidence, "authenticity_risk", None):
        checks += 1

    return checks >= 2


# ---------------------------------------------------------------------------
# Q2: merged target (old Q2 proves + Q3 direction)
# ---------------------------------------------------------------------------


def _build_q2_target(evidence, issue_tree) -> str:
    """Build merged q2_target: target issues + fact proposition + owner."""
    owner = getattr(evidence, "owner_party_id", "")
    target_fact_ids = getattr(evidence, "target_fact_ids", [])
    target_issue_ids = getattr(evidence, "target_issue_ids", [])
    supports = getattr(evidence, "supports", [])

    # Collect all related issue IDs
    all_issue_ids = list(dict.fromkeys(target_issue_ids + supports))

    # Build target issues string
    if all_issue_ids:
        target_issues_str = ", ".join(all_issue_ids[:3])
        if len(all_issue_ids) > 3:
            target_issues_str += "等"
    else:
        target_issues_str = ""

    # Build fact proposition string
    if target_fact_ids:
        fact_proposition = ", ".join(target_fact_ids[:3])
    else:
        fact_proposition = "待明确"

    # Assemble
    parts = []
    if target_issues_str:
        parts.append(f"服务争点{target_issues_str}")
    parts.append(f"证明{fact_proposition}")
    if owner:
        parts.append(f"支持{owner}方")

    return "，".join(parts)


# ---------------------------------------------------------------------------
# Q3: key risk (replaces old Q4 four-dimensional risk)
# ---------------------------------------------------------------------------


def _build_key_risk(evidence) -> str:
    """Build key risk string from evidence fields.

    Returns empty string if no substantive risk identified (never returns
    boilerplate like '暂无明显风险').
    """
    risks: list[str] = []

    # Authenticity
    auth_risk = getattr(evidence, "authenticity_risk", None)
    if auth_risk:
        val = auth_risk.value if hasattr(auth_risk, "value") else str(auth_risk)
        if val != "none":
            risks.append(f"真实性: {val}")

    # Completeness (copy-only)
    if getattr(evidence, "is_copy_only", False):
        risks.append("完整性: 仅有复印件")

    # Relevance
    rel_score = getattr(evidence, "relevance_score", None)
    if rel_score:
        val = rel_score.value if hasattr(rel_score, "value") else str(rel_score)
        if val in ("low", "minimal"):
            risks.append(f"关联性: {val}")

    # Legality
    leg_risk = getattr(evidence, "legality_risk", None)
    if leg_risk:
        val = leg_risk.value if hasattr(leg_risk, "value") else str(leg_risk)
        if val != "none":
            risks.append(f"合法性: {val}")

    # Admissibility
    adm_score = getattr(evidence, "admissibility_score", 1.0)
    if adm_score < 0.7:
        risks.append(f"可采性评分: {adm_score:.0%}")

    challenges = getattr(evidence, "admissibility_challenges", [])
    if challenges:
        risks.append(f"质疑理由: {'; '.join(challenges[:2])}")

    return "; ".join(risks)


# ---------------------------------------------------------------------------
# Q4: best attack (replaces old Q5 opponent attack)
# ---------------------------------------------------------------------------


def _build_best_attack(evidence, attack_chain=None) -> str:
    """Predict how opponent would attack this evidence.

    Returns empty string if no attack vector identified (never returns
    boilerplate like '对方攻击方向待分析').
    """
    attacks: list[str] = []

    # From attack chain
    if attack_chain:
        for node in getattr(attack_chain, "top_attacks", []):
            ev_ids = getattr(node, "supporting_evidence_ids", [])
            if evidence.evidence_id in ev_ids:
                attacks.append(node.attack_description)

    # From evidence's own attacked_by field
    attacked_by = getattr(evidence, "is_attacked_by", [])
    if attacked_by:
        attacks.append(f"被反驳证据: {', '.join(attacked_by[:3])}")

    # From vulnerability field
    vuln = getattr(evidence, "vulnerability", None)
    if vuln:
        val = vuln.value if hasattr(vuln, "value") else str(vuln)
        if val not in ("none", "low"):
            attacks.append(f"脆弱性: {val}")

    # Type-specific attack predictions
    ev_type = (
        evidence.evidence_type.value
        if hasattr(evidence.evidence_type, "value")
        else str(evidence.evidence_type)
    )
    if ev_type == "audio_visual":
        attacks.append("录音合法性质疑（是否经对方同意）")
    elif ev_type == "electronic_data":
        attacks.append("电子数据完整性质疑（是否篡改）")
    elif ev_type == "witness_statement":
        attacks.append("证人与当事人利害关系质疑")

    return "; ".join(attacks)


# ---------------------------------------------------------------------------
# Q5: reinforce strategy (key cards only)
# ---------------------------------------------------------------------------


def _build_reinforce_strategy(evidence) -> str:
    """Suggest how to reinforce this evidence.

    Returns empty string if no reinforcement needed (never returns
    boilerplate like '当前证据较稳固，保持现状').
    """
    strategies: list[str] = []

    ev_type = (
        evidence.evidence_type.value
        if hasattr(evidence.evidence_type, "value")
        else str(evidence.evidence_type)
    )

    if getattr(evidence, "is_copy_only", False):
        strategies.append("提供原件或经公证的副本")

    if ev_type == "electronic_data":
        strategies.append("申请司法鉴定确认数据完整性")
        strategies.append("提供平台后台数据佐证")
    elif ev_type == "audio_visual":
        strategies.append("提供录音完整版（不截取）")
        strategies.append("申请声纹鉴定")
    elif ev_type == "witness_statement":
        strategies.append("证人出庭作证")
        strategies.append("提供其他独立证人旁证")

    # From admissibility challenges
    challenges = getattr(evidence, "admissibility_challenges", [])
    if challenges:
        strategies.append(f"针对质疑准备反驳: {challenges[0]}")

    adm_score = getattr(evidence, "admissibility_score", 1.0)
    if adm_score < 0.7:
        strategies.append("提供补强证据提高可采性评分")

    return "; ".join(strategies)


# ---------------------------------------------------------------------------
# Q6: failure impact (key cards only)
# ---------------------------------------------------------------------------


def _build_failure_impact(evidence, issue_tree) -> str:
    """Describe what conclusions need recalculation if this evidence fails.

    Returns empty string if no impact identified (never returns boilerplate
    like '该证据失败对整体结论影响有限' or '影响范围待评估').
    """
    impacts: list[str] = []

    target_issues = getattr(evidence, "target_issue_ids", [])
    supports = getattr(evidence, "supports", [])
    affected_issues = list(set(target_issues + supports))

    if affected_issues:
        for issue in getattr(issue_tree, "issues", []):
            if issue.issue_id in affected_issues:
                impacts.append(
                    f"争点「{issue.title}」({issue.issue_id}) 结论需重新评估"
                )

    # Check exclusion impact
    excl = getattr(evidence, "exclusion_impact", None)
    if excl:
        impacts.append(f"排除影响: {excl}")

    return "; ".join(impacts)


# ---------------------------------------------------------------------------
# Unified electronic evidence strategy
# ---------------------------------------------------------------------------


def _extract_unified_electronic_strategy(
    all_electronic_strategies: list[str],
) -> tuple[str, set[str]]:
    """Identify common electronic evidence reinforcement actions.

    Args:
        all_electronic_strategies: List of full strategy strings from
            electronic_data evidence items.

    Returns:
        Tuple of (unified_strategy_text, common_actions_set).
        - unified_strategy_text: Human-readable summary of common actions.
        - common_actions_set: Set of individual action strings that are common
          (appear 3+ times or appear in majority if <6 items).
    """
    if not all_electronic_strategies:
        return "", set()

    # Split each strategy string into individual actions
    action_counter: Counter[str] = Counter()
    for strategy_str in all_electronic_strategies:
        for action in strategy_str.split("; "):
            action = action.strip()
            if action:
                action_counter[action] += 1

    # Threshold: 3+ occurrences, or majority if fewer than 6 electronic items
    threshold = min(3, max(1, len(all_electronic_strategies) // 2 + 1))
    common_actions = {
        action for action, count in action_counter.items() if count >= threshold
    }

    if not common_actions:
        return "", set()

    unified_text = "电子证据统一补强策略: " + "; ".join(sorted(common_actions))
    return unified_text, common_actions


def _remove_common_actions(strategy_str: str, common_actions: set[str]) -> str:
    """Remove common actions from a per-evidence strategy string.

    Returns the remaining differential actions, or empty string if all
    actions were common.
    """
    if not common_actions or not strategy_str:
        return strategy_str

    remaining = [
        action.strip()
        for action in strategy_str.split("; ")
        if action.strip() and action.strip() not in common_actions
    ]
    return "; ".join(remaining)


# ---------------------------------------------------------------------------
# Main entry point: build_evidence_cards
# ---------------------------------------------------------------------------


def build_evidence_cards(
    evidence_index,
    issue_tree,
    attack_chain=None,
) -> tuple[list[Union[EvidenceBasicCard, EvidenceKeyCard]], str]:
    """Build dual-tier evidence cards with observability threshold.

    For each evidence item:
    - Classifies priority via evidence_classifier.classify_evidence_priority
    - Core evidence -> EvidenceKeyCard (6 fields)
    - Supporting/Background evidence -> EvidenceBasicCard (4 fields)

    Applies observability threshold: when insufficient metadata exists,
    fields are filled with an explicit "information insufficient" message
    rather than boilerplate.

    Electronic evidence reinforcement strategies that appear across multiple
    items are extracted into a unified strategy string.

    Args:
        evidence_index: EvidenceIndex from pipeline.
        issue_tree: IssueTree for issue context.
        attack_chain: OptionalAttackChain (optional).

    Returns:
        Tuple of (cards, unified_electronic_strategy).
        - cards: Mix of EvidenceBasicCard and EvidenceKeyCard.
        - unified_electronic_strategy: Common reinforcement actions for
          electronic evidence, or empty string if not applicable.
    """
    cards: list[Union[EvidenceBasicCard, EvidenceKeyCard]] = []

    # First pass: collect all electronic evidence strategies for unification
    electronic_strategies: list[str] = []
    evidence_data: list[
        tuple  # (ev, priority_card, ev_type_str, q1, q2, q3_risk, q4_attack, q5_reinforce, q6_impact, observable)
    ] = []

    for ev in evidence_index.evidence:
        ev_type_str = (
            ev.evidence_type.value
            if hasattr(ev.evidence_type, "value")
            else str(ev.evidence_type)
        )

        priority_card = classify_evidence_priority(ev, issue_tree)
        observable = _has_sufficient_observability(ev)

        # Q1: what is this evidence
        summary_snippet = getattr(ev, "summary", "")[:150]
        q1_what = f"{ev.title} — {ev_type_str}类证据。{summary_snippet}"

        # Q2: merged target
        q2_target = _build_q2_target(ev, issue_tree)

        # Q3: key risk
        if observable:
            q3_key_risk = _build_key_risk(ev)
            if not q3_key_risk:
                q3_key_risk = ""
        else:
            q3_key_risk = _INSUFFICIENT_MSG

        # Q4: best attack
        if observable:
            q4_best_attack = _build_best_attack(ev, attack_chain)
            if not q4_best_attack:
                q4_best_attack = ""
        else:
            q4_best_attack = _INSUFFICIENT_MSG

        # Q5: reinforce (only used for key cards, but compute for electronic extraction)
        if observable:
            q5_reinforce = _build_reinforce_strategy(ev)
        else:
            q5_reinforce = _INSUFFICIENT_MSG

        # Q6: failure impact (only used for key cards)
        if observable:
            q6_failure_impact = _build_failure_impact(ev, issue_tree)
            if not q6_failure_impact:
                q6_failure_impact = ""
        else:
            q6_failure_impact = _INSUFFICIENT_MSG

        # Collect electronic strategies for unification
        if ev_type_str == "electronic_data" and q5_reinforce and q5_reinforce != _INSUFFICIENT_MSG:
            electronic_strategies.append(q5_reinforce)

        evidence_data.append((
            ev, priority_card, ev_type_str,
            q1_what, q2_target, q3_key_risk, q4_best_attack,
            q5_reinforce, q6_failure_impact, observable,
        ))

    # Extract unified electronic strategy
    unified_strategy, common_actions = _extract_unified_electronic_strategy(
        electronic_strategies
    )

    # Second pass: build cards, removing common electronic actions from per-card strategies
    for (
        ev, priority_card, ev_type_str,
        q1_what, q2_target, q3_key_risk, q4_best_attack,
        q5_reinforce, q6_failure_impact, observable,
    ) in evidence_data:
        priority = priority_card.priority

        # Remove common electronic actions from per-card reinforce strategy
        if ev_type_str == "electronic_data" and common_actions and q5_reinforce != _INSUFFICIENT_MSG:
            q5_reinforce = _remove_common_actions(q5_reinforce, common_actions)

        if priority == EvidencePriority.core:
            cards.append(EvidenceKeyCard(
                evidence_id=ev.evidence_id,
                q1_what=q1_what,
                q2_target=q2_target,
                q3_key_risk=q3_key_risk,
                q4_best_attack=q4_best_attack,
                q5_reinforce=q5_reinforce,
                q6_failure_impact=q6_failure_impact,
                priority=priority,
                tag=SectionTag.inference,
            ))
        else:
            cards.append(EvidenceBasicCard(
                evidence_id=ev.evidence_id,
                q1_what=q1_what,
                q2_target=q2_target,
                q3_key_risk=q3_key_risk,
                q4_best_attack=q4_best_attack,
                priority=priority,
                tag=SectionTag.inference,
            ))

    return cards, unified_strategy


# ---------------------------------------------------------------------------
# DEPRECATED: backward-compatible wrapper
# ---------------------------------------------------------------------------


def build_evidence_battle_matrix(
    evidence_index,
    issue_tree,
    attack_chain=None,
) -> list[EvidenceBattleCard]:
    """DEPRECATED: Use build_evidence_cards() instead.

    Kept for backward compatibility. Converts dual-tier cards back to the
    old 7-question EvidenceBattleCard format.
    """
    cards: list[EvidenceBattleCard] = []

    for ev in evidence_index.evidence:
        ev_type_str = (
            ev.evidence_type.value
            if hasattr(ev.evidence_type, "value")
            else str(ev.evidence_type)
        )

        # Classify risk level (old traffic light system)
        traffic_light = classify_evidence_risk(
            evidence_id=ev.evidence_id,
            title=ev.title,
            evidence_type=ev_type_str,
            source=ev.source,
            is_copy_only=getattr(ev, "is_copy_only", False),
            is_challenged=bool(getattr(ev, "challenged_by_party_ids", [])),
            admissibility_score=getattr(ev, "admissibility_score", 1.0),
        )

        # Build old-style proof direction
        owner = getattr(ev, "owner_party_id", "")
        supports = getattr(ev, "supports", [])
        target_issues = getattr(ev, "target_issue_ids", [])
        if supports:
            q3_direction = f"支持 {owner} 方在争点 {', '.join(supports[:3])} 上的主张"
        elif target_issues:
            q3_direction = f"关联争点 {', '.join(target_issues[:3])}，由 {owner} 方提交"
        else:
            q3_direction = f"由 {owner} 方提交"

        # Build old-style risk assessment
        risk_str = _build_key_risk(ev)

        # Build old-style opponent attack
        attack_str = _build_best_attack(ev, attack_chain)

        # Build old-style reinforce
        reinforce_str = _build_reinforce_strategy(ev)

        # Build old-style failure impact
        impact_str = _build_failure_impact(ev, issue_tree)

        cards.append(EvidenceBattleCard(
            evidence_id=ev.evidence_id,
            q1_what=f"{ev.title} — {ev_type_str}类证据。{getattr(ev, 'summary', '')[:150]}",
            q2_proves=(
                f"证明事实: {', '.join(ev.target_fact_ids[:3])}"
                if getattr(ev, "target_fact_ids", [])
                else "待明确证明命题"
            ),
            q3_direction=q3_direction,
            q4_risks=risk_str or "暂无明显风险",
            q5_opponent_attack=attack_str or "对方攻击方向待分析",
            q6_reinforce=reinforce_str or "当前证据较稳固，保持现状",
            q7_failure_impact=impact_str or "该证据失败对整体结论影响有限",
            risk_level=traffic_light.risk_level,
            tag=SectionTag.inference,
        ))

    return cards
