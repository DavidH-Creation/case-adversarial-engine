"""
证据风险红绿灯分类器 / Evidence Risk Traffic Light Classifier.

根据证据类型、来源和状态，将每条证据分类为：
  🟢 green  — 第三方可核实（银行流水、公证文书、法院认证文书）
  🟡 yellow — 截图/单方提供（微信截图、短信记录、社交媒体）
  🔴 red    — 争议+敏感（录音合法性存疑、复印件无原件、被质证的证据）

颜色仅代表证据稳定性，不代表对任何一方的立场。
"""

from __future__ import annotations

from engines.report_generation.v3.models import (
    EvidenceRiskLevel,
    EvidenceTrafficLight,
)

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

    Priority:
    1. Explicit red flags (copy-only, challenged, low admissibility) → red
    2. Evidence type classification
    3. Source keyword matching
    4. Default → yellow
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
