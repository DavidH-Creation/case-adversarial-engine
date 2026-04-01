"""
证据分类器 / Evidence Classifier.

包含两套分类系统：

1. [已废弃] 红绿灯系统 (Traffic Light) — classify_evidence_risk / classify_all_evidence
   问题：对抗辩论后所有证据均被质证，导致 14/16 条证据全部黄灯，零区分度。

2. [推荐] 优先级系统 (Priority) — classify_evidence_priority / classify_all_evidence_priority
   基于证据与争点树的结构关系确定优先级：
     核心证据 (core)     — 控制 L1（根）争点结果的关键证据
     辅助证据 (supporting) — 佐证核心证据或指向同一争点
     背景证据 (background) — 仅提供背景信息（身份证明、程序性文书）
"""

from __future__ import annotations

from engines.report_generation.v3.models import (
    EvidencePriority,
    EvidencePriorityCard,
    # Backward-compatible imports for traffic light system
    EvidenceRiskLevel,
    EvidenceTrafficLight,
)

# ============================================================================
# [DEPRECATED] Traffic Light System
# ============================================================================
#
# The traffic light classifier is DEPRECATED. It produces all-yellow results
# because any challenged evidence is capped at yellow (lines 86-92 of the
# original), and in real adversarial cases ALL evidence is challenged.
# Result: 14/16 evidence items are yellow with identical reason, zero
# discrimination value.
#
# Kept for backward compatibility — layer1_cover.py and
# evidence_battle_matrix.py still import these functions.
# ============================================================================

# Evidence types that are third-party verifiable
_GREEN_TYPES = {
    "documentary",  # 银行流水、合同原件、公证书
}

# Evidence types from screenshots or single-party sources
_YELLOW_TYPES = {
    "electronic_data",   # 微信截图、短信、App记录
    "witness_statement",  # 证人证言
}

# Evidence types that are inherently sensitive
_RED_TYPES = {
    "audio_visual",  # 录音录像（合法性常被质疑）
}

# Source keywords indicating third-party verification
_GREEN_SOURCE_KEYWORDS = {
    "银行", "bank", "公证", "notary", "法院", "court",
    "工商", "税务", "公安",
}

# Source keywords indicating single-party / screenshot
_YELLOW_SOURCE_KEYWORDS = {
    "微信", "wechat", "支付宝", "alipay", "短信", "sms",
    "截图", "screenshot", "朋友圈", "qq",
}


def classify_evidence_risk(
    evidence_id: str,
    title: str,
    evidence_type: str,
    source: str,
    *,
    is_copy_only: bool = False,
    is_challenged: bool = False,
    admissibility_score: float = 1.0,
) -> EvidenceTrafficLight:
    """Classify a single evidence item into the traffic light system.

    .. deprecated::
        Use :func:`classify_evidence_priority` instead. The traffic light
        system produces all-yellow results when evidence is challenged during
        adversarial debate (which is always the case in practice).

    Priority:
    1. Explicit red flags (copy-only, challenged, low admissibility) -> red
    2. Evidence type classification
    3. Source keyword matching
    4. Default -> yellow
    """
    reason_parts: list[str] = []

    # Priority 1: Explicit red flags
    if is_copy_only:
        return EvidenceTrafficLight(
            evidence_id=evidence_id,
            title=title,
            risk_level=EvidenceRiskLevel.red,
            reason="仅有复印件无原件",
        )

    if is_challenged and admissibility_score < 0.5:
        return EvidenceTrafficLight(
            evidence_id=evidence_id,
            title=title,
            risk_level=EvidenceRiskLevel.red,
            reason="证据已被质证且可采性评分低",
        )

    # Challenged evidence is yellow at best, regardless of type or source
    if is_challenged:
        return EvidenceTrafficLight(
            evidence_id=evidence_id,
            title=title,
            risk_level=EvidenceRiskLevel.yellow,
            reason=f"证据已被质证，最高黄灯（可采性: {admissibility_score:.0%}）",
        )

    if admissibility_score < 0.3:
        return EvidenceTrafficLight(
            evidence_id=evidence_id,
            title=title,
            risk_level=EvidenceRiskLevel.red,
            reason=f"可采性评分极低 ({admissibility_score:.0%})",
        )

    # Priority 2: Type-based classification
    ev_type_lower = evidence_type.lower()

    if ev_type_lower in _RED_TYPES:
        return EvidenceTrafficLight(
            evidence_id=evidence_id,
            title=title,
            risk_level=EvidenceRiskLevel.red,
            reason="录音/录像类证据，合法性常被质疑",
        )

    # Priority 3: Source keyword matching (overrides type if stronger signal)
    source_lower = (source + " " + title).lower()

    for kw in _GREEN_SOURCE_KEYWORDS:
        if kw in source_lower:
            reason_parts.append(f"来源含第三方关键词「{kw}」")
            return EvidenceTrafficLight(
                evidence_id=evidence_id,
                title=title,
                risk_level=EvidenceRiskLevel.green,
                reason="; ".join(reason_parts) or "第三方可核实来源",
            )

    if ev_type_lower in _GREEN_TYPES:
        return EvidenceTrafficLight(
            evidence_id=evidence_id,
            title=title,
            risk_level=EvidenceRiskLevel.green,
            reason="书证类型，通常第三方可核实",
        )

    for kw in _YELLOW_SOURCE_KEYWORDS:
        if kw in source_lower:
            reason_parts.append(f"来源含单方关键词「{kw}」")
            return EvidenceTrafficLight(
                evidence_id=evidence_id,
                title=title,
                risk_level=EvidenceRiskLevel.yellow,
                reason="; ".join(reason_parts) or "截图/单方来源",
            )

    if ev_type_lower in _YELLOW_TYPES:
        return EvidenceTrafficLight(
            evidence_id=evidence_id,
            title=title,
            risk_level=EvidenceRiskLevel.yellow,
            reason="电子数据/证人证言类型",
        )

    # Default: yellow (conservative)
    return EvidenceTrafficLight(
        evidence_id=evidence_id,
        title=title,
        risk_level=EvidenceRiskLevel.yellow,
        reason="无法确认第三方可核实性，默认黄灯",
    )


def classify_all_evidence(
    evidence_list: list,
) -> list[EvidenceTrafficLight]:
    """Classify all evidence items from an EvidenceIndex.

    .. deprecated::
        Use :func:`classify_all_evidence_priority` instead.

    Args:
        evidence_list: List of Evidence objects from engines.shared.models.

    Returns:
        List of EvidenceTrafficLight classifications.
    """
    results = []
    for ev in evidence_list:
        results.append(
            classify_evidence_risk(
                evidence_id=ev.evidence_id,
                title=ev.title,
                evidence_type=ev.evidence_type.value if hasattr(ev.evidence_type, "value") else str(ev.evidence_type),
                source=ev.source,
                is_copy_only=getattr(ev, "is_copy_only", False),
                is_challenged=bool(getattr(ev, "challenged_by_party_ids", [])),
                admissibility_score=getattr(ev, "admissibility_score", 1.0),
            )
        )
    return results


# ============================================================================
# Priority-Based Classification System (Recommended)
# ============================================================================

# Title keywords for background evidence detection
_IDENTITY_KEYWORDS = {"身份", "身份信息", "身份证", "户口", "户籍"}
_PROCEDURAL_KEYWORDS = {"起诉状", "答辩状", "受理通知", "传票", "送达"}
_COST_KEYWORDS = {"诉讼费", "受理费", "律师费", "鉴定费"}


def _get_l1_issue_ids(issue_tree) -> set[str]:
    """Extract L1 (root) issue IDs from an IssueTree.

    L1 issues are those where parent_issue_id is None, meaning they are
    top-level issues that directly control case outcomes.
    """
    issues = getattr(issue_tree, "issues", [])
    return {
        iss.issue_id
        for iss in issues
        if getattr(iss, "parent_issue_id", None) is None
    }


def _get_issue_title_map(issue_tree) -> dict[str, str]:
    """Build a mapping from issue_id to issue title."""
    issues = getattr(issue_tree, "issues", [])
    return {iss.issue_id: getattr(iss, "title", "") for iss in issues}


def _is_identity_document(title: str) -> bool:
    """Check if evidence title indicates an identity document."""
    return any(kw in title for kw in _IDENTITY_KEYWORDS)


def _is_procedural_document(evidence_type_str: str, title: str) -> bool:
    """Check if evidence is a procedural document (pleadings, service docs)."""
    if evidence_type_str == "documentary":
        return any(kw in title for kw in _PROCEDURAL_KEYWORDS)
    return False


def _targets_only_cost_issues(
    target_issue_ids: list[str],
    issue_title_map: dict[str, str],
) -> bool:
    """Check if evidence only targets cost/fee-related issues."""
    if not target_issue_ids:
        return False
    return all(
        any(kw in issue_title_map.get(iid, "") for kw in _COST_KEYWORDS)
        for iid in target_issue_ids
    )


def classify_evidence_priority(
    evidence,
    issue_tree,
    *,
    ranked_issues=None,
) -> EvidencePriorityCard:
    """Classify a single evidence item into priority tiers.

    Deterministic, rule-based classification — no LLM calls.

    Classification logic:
    1. Identify L1 (root) issues: issues where parent_issue_id is None
    2. Background: identity docs, procedural docs, or evidence targeting
       only cost/fee issues, or evidence with no target_issue_ids
    3. Core: evidence whose target_issue_ids overlap with L1 issue IDs
       AND (admissibility_score >= 0.5 OR no challenged_by_party_ids)
    4. Supporting: everything else — targets same issues as core evidence
       but doesn't directly control L1 outcomes, or has admissibility < 0.5

    Args:
        evidence: Evidence object from shared models
        issue_tree: IssueTree for L1 issue identification
        ranked_issues: Optional ranked IssueTree (unused currently, reserved
            for future composite_score-based tie-breaking)

    Returns:
        EvidencePriorityCard with priority tier and reasoning.
    """
    ev_id = evidence.evidence_id
    ev_title = evidence.title
    ev_type_str = (
        evidence.evidence_type.value
        if hasattr(evidence.evidence_type, "value")
        else str(evidence.evidence_type)
    )
    target_issue_ids: list[str] = getattr(evidence, "target_issue_ids", [])
    admissibility: float = getattr(evidence, "admissibility_score", 1.0)
    challenged: list[str] = getattr(evidence, "challenged_by_party_ids", [])

    l1_ids = _get_l1_issue_ids(issue_tree)
    issue_title_map = _get_issue_title_map(issue_tree)

    # --- Background checks (applied first to filter out noise) ---

    # Identity documents
    if _is_identity_document(ev_title):
        return EvidencePriorityCard(
            evidence_id=ev_id,
            title=ev_title,
            priority=EvidencePriority.background,
            reason="身份证明类文书，仅提供背景信息",
            target_l1_issue_ids=[],
            admissibility_score=admissibility,
        )

    # Procedural documents
    if _is_procedural_document(ev_type_str, ev_title):
        return EvidencePriorityCard(
            evidence_id=ev_id,
            title=ev_title,
            priority=EvidencePriority.background,
            reason="程序性文书（起诉状/答辩状等），不直接影响争点裁判",
            target_l1_issue_ids=[],
            admissibility_score=admissibility,
        )

    # No target issues at all
    if not target_issue_ids:
        return EvidencePriorityCard(
            evidence_id=ev_id,
            title=ev_title,
            priority=EvidencePriority.background,
            reason="未关联任何争点，仅作为背景参考",
            target_l1_issue_ids=[],
            admissibility_score=admissibility,
        )

    # Only targets cost/fee issues
    if _targets_only_cost_issues(target_issue_ids, issue_title_map):
        return EvidencePriorityCard(
            evidence_id=ev_id,
            title=ev_title,
            priority=EvidencePriority.background,
            reason="仅关联诉讼费/鉴定费等费用争点，非实体争议",
            target_l1_issue_ids=[],
            admissibility_score=admissibility,
        )

    # --- Core vs. Supporting ---

    overlapping_l1 = sorted(set(target_issue_ids) & l1_ids)
    is_admissible = admissibility >= 0.5 or not challenged

    if overlapping_l1 and is_admissible:
        # Core: directly targets L1 issues with sufficient admissibility
        l1_titles = [issue_title_map.get(iid, iid) for iid in overlapping_l1]
        return EvidencePriorityCard(
            evidence_id=ev_id,
            title=ev_title,
            priority=EvidencePriority.core,
            reason=f"直接关联 L1 争点: {', '.join(l1_titles)}",
            target_l1_issue_ids=overlapping_l1,
            admissibility_score=admissibility,
        )

    if overlapping_l1 and not is_admissible:
        # Targets L1 issues but admissibility is too low — demote to supporting
        l1_titles = [issue_title_map.get(iid, iid) for iid in overlapping_l1]
        return EvidencePriorityCard(
            evidence_id=ev_id,
            title=ev_title,
            priority=EvidencePriority.supporting,
            reason=(
                f"关联 L1 争点（{', '.join(l1_titles)}）但可采性不足"
                f"（{admissibility:.0%}），降为辅助证据"
            ),
            target_l1_issue_ids=overlapping_l1,
            admissibility_score=admissibility,
        )

    # Does not target any L1 issue directly — supporting
    targeted_titles = [
        issue_title_map.get(iid, iid) for iid in target_issue_ids[:3]
    ]
    suffix = "等" if len(target_issue_ids) > 3 else ""
    return EvidencePriorityCard(
        evidence_id=ev_id,
        title=ev_title,
        priority=EvidencePriority.supporting,
        reason=f"关联子争点: {', '.join(targeted_titles)}{suffix}，佐证上级争点",
        target_l1_issue_ids=[],
        admissibility_score=admissibility,
    )


def classify_all_evidence_priority(
    evidence_list: list,
    issue_tree,
    *,
    ranked_issues=None,
) -> list[EvidencePriorityCard]:
    """Classify all evidence items into priority tiers.

    Args:
        evidence_list: List of Evidence objects from engines.shared.models.
        issue_tree: IssueTree for L1 issue identification.
        ranked_issues: Optional ranked IssueTree (reserved for future use).

    Returns:
        List of EvidencePriorityCard classifications, in the same order as
        the input list.
    """
    return [
        classify_evidence_priority(
            ev,
            issue_tree,
            ranked_issues=ranked_issues,
        )
        for ev in evidence_list
    ]
