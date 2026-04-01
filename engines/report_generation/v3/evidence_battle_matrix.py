"""
证据作战矩阵生成器 / Evidence Battle Matrix Generator.

为每条证据生成「七问」卡片：
  1. 这是什么证据
  2. 证明什么命题
  3. 证明方向（支持谁）
  4. 真实性/完整性/关联性/合法性风险
  5. 对方如何攻击
  6. 如何加固
  7. 若此证据失败，哪些结论需重新计算

完全中立分析，颜色仅代表证据稳定性。
"""

from __future__ import annotations

from engines.report_generation.v3.evidence_classifier import classify_evidence_risk
from engines.report_generation.v3.models import EvidenceBattleCard, SectionTag


def _get_proof_direction(evidence, issue_tree) -> str:
    """Determine which side the evidence supports."""
    owner = getattr(evidence, "owner_party_id", "")
    supports = getattr(evidence, "supports", [])
    if supports:
        return f"支持 {owner} 方在争点 {', '.join(supports[:3])} 上的主张"
    target_issues = getattr(evidence, "target_issue_ids", [])
    if target_issues:
        return f"关联争点 {', '.join(target_issues[:3])}，由 {owner} 方提交"
    return f"由 {owner} 方提交"


def _get_risk_assessment(evidence) -> str:
    """Build risk assessment string from evidence fields."""
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

    return "; ".join(risks) if risks else "暂无明显风险"


def _get_opponent_attack(evidence, attack_chain=None) -> str:
    """Predict how opponent would attack this evidence."""
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
    ev_type = evidence.evidence_type.value if hasattr(evidence.evidence_type, "value") else str(evidence.evidence_type)
    if ev_type == "audio_visual":
        attacks.append("录音合法性质疑（是否经对方同意）")
    elif ev_type == "electronic_data":
        attacks.append("电子数据完整性质疑（是否篡改）")
    elif ev_type == "witness_statement":
        attacks.append("证人与当事人利害关系质疑")

    return "; ".join(attacks) if attacks else "对方攻击方向待分析"


def _get_reinforce_strategy(evidence) -> str:
    """Suggest how to reinforce this evidence."""
    strategies: list[str] = []

    ev_type = evidence.evidence_type.value if hasattr(evidence.evidence_type, "value") else str(evidence.evidence_type)

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

    return "; ".join(strategies) if strategies else "当前证据较稳固，保持现状"


def _get_failure_impact(evidence, issue_tree) -> str:
    """Describe what conclusions need recalculation if this evidence fails."""
    impacts: list[str] = []

    target_issues = getattr(evidence, "target_issue_ids", [])
    supports = getattr(evidence, "supports", [])
    affected_issues = list(set(target_issues + supports))

    if not affected_issues:
        return "该证据失败对整体结论影响有限"

    for issue in issue_tree.issues:
        if issue.issue_id in affected_issues:
            impacts.append(f"争点「{issue.title}」({issue.issue_id}) 结论需重新评估")

    # Check exclusion impact
    excl = getattr(evidence, "exclusion_impact", None)
    if excl:
        impacts.append(f"排除影响: {excl}")

    return "; ".join(impacts) if impacts else "影响范围待评估"


def build_evidence_battle_matrix(
    evidence_index,
    issue_tree,
    attack_chain=None,
) -> list[EvidenceBattleCard]:
    """Build 7-question battle cards for all evidence.

    Args:
        evidence_index: EvidenceIndex from pipeline
        issue_tree: IssueTree for issue context
        attack_chain: OptimalAttackChain (optional)

    Returns:
        List of EvidenceBattleCard, one per evidence piece
    """
    cards: list[EvidenceBattleCard] = []

    for ev in evidence_index.evidence:
        ev_type_str = ev.evidence_type.value if hasattr(ev.evidence_type, "value") else str(ev.evidence_type)

        # Classify risk level
        traffic_light = classify_evidence_risk(
            evidence_id=ev.evidence_id,
            title=ev.title,
            evidence_type=ev_type_str,
            source=ev.source,
            is_copy_only=getattr(ev, "is_copy_only", False),
            is_challenged=bool(getattr(ev, "challenged_by_party_ids", [])),
            admissibility_score=getattr(ev, "admissibility_score", 1.0),
        )

        cards.append(EvidenceBattleCard(
            evidence_id=ev.evidence_id,
            q1_what=f"{ev.title} — {ev_type_str}类证据。{ev.summary[:150]}",
            q2_proves=f"证明事实: {', '.join(ev.target_fact_ids[:3])}" if ev.target_fact_ids else "待明确证明命题",
            q3_direction=_get_proof_direction(ev, issue_tree),
            q4_risks=_get_risk_assessment(ev),
            q5_opponent_attack=_get_opponent_attack(ev, attack_chain),
            q6_reinforce=_get_reinforce_strategy(ev),
            q7_failure_impact=_get_failure_impact(ev, issue_tree),
            risk_level=traffic_light.risk_level,
            tag=SectionTag.inference,
        ))

    return cards
