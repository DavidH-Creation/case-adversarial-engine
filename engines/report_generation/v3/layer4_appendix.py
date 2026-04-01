"""
Layer 4: 附录层 / Appendix Layer.

始终相同，不受 --perspective 影响：
  - 三轮对抗辩论完整记录
  - 证据索引表
  - 案件时间线
  - 术语表
  - 金额计算明细
"""

from __future__ import annotations

from engines.report_generation.v3.models import Layer4Appendix, SectionTag
from engines.report_generation.v3.tag_system import format_tag


def build_layer4(
    *,
    adversarial_result,
    evidence_index,
    issue_tree,
    amount_report=None,
    case_data: dict | None = None,
) -> Layer4Appendix:
    """Build Layer 4 appendix.

    All content in this layer is perspective-independent.
    """
    # Adversarial transcripts
    transcripts_md = _render_adversarial_transcripts(adversarial_result)

    # Evidence index
    evidence_md = _render_evidence_index(evidence_index)

    # Timeline
    timeline_md = _render_timeline(case_data or {})

    # Amount calculation
    amount_md = _render_amount_calculation(amount_report)

    return Layer4Appendix(
        adversarial_transcripts_md=transcripts_md,
        evidence_index_md=evidence_md,
        timeline_md=timeline_md,
        glossary_md=_render_glossary(),
        amount_calculation_md=amount_md,
    )


def _render_adversarial_transcripts(adversarial_result) -> str:
    """Render full 3-round adversarial debate transcripts."""
    if not adversarial_result:
        return "*暂无对抗辩论记录。*"

    lines: list[str] = []
    for rs in adversarial_result.rounds:
        lines.append(f"### Round {rs.round_number} ({rs.phase.value})")
        lines.append("")
        for o in rs.outputs:
            lines.append(f"**{o.agent_role_code}** — {o.title}")
            lines.append("")
            lines.append(o.body)
            lines.append("")
            lines.append(f"*引用证据*: {', '.join(o.evidence_citations)}")
            lines.append("")
            lines.append("---")
            lines.append("")
    return "\n".join(lines)


def _render_evidence_index(evidence_index) -> str:
    """Render evidence index table."""
    lines: list[str] = []
    lines.append("| 编号 | 标题 | 类型 | 提交方 | 状态 |")
    lines.append("|------|------|------|--------|------|")
    for ev in evidence_index.evidence:
        ev_type = ev.evidence_type.value if hasattr(ev.evidence_type, "value") else str(ev.evidence_type)
        status = ev.status.value if hasattr(ev.status, "value") else str(ev.status)
        lines.append(
            f"| {ev.evidence_id} | {ev.title[:40]} | {ev_type} | {ev.owner_party_id} | {status} |"
        )
    return "\n".join(lines)


def _render_timeline(case_data: dict) -> str:
    """Render case timeline from case_data events."""
    events = case_data.get("timeline", [])
    if not events:
        return "*暂无时间线数据。*"

    lines: list[str] = []
    lines.append("| 日期 | 事件 |")
    lines.append("|------|------|")
    for event in events:
        if isinstance(event, dict):
            lines.append(f"| {event.get('date', '?')} | {event.get('description', '?')} |")
        elif isinstance(event, (list, tuple)) and len(event) >= 2:
            lines.append(f"| {event[0]} | {event[1]} |")
    return "\n".join(lines)


def _render_amount_calculation(amount_report) -> str:
    """Render amount calculation details."""
    if not amount_report:
        return "*暂无金额计算明细。*"

    lines: list[str] = []
    lines.append("| 项目 | 金额 | 说明 |")
    lines.append("|------|------|------|")

    # Handle AmountCalculationReport fields
    if hasattr(amount_report, "total_principal"):
        lines.append(
            f"| 借款本金 | {amount_report.total_principal:,} 元 | 核实本金总额 |"
        )
    if hasattr(amount_report, "total_interest"):
        lines.append(
            f"| 利息 | {amount_report.total_interest:,} 元 | 计算利息总额 |"
        )
    if hasattr(amount_report, "total_claimed"):
        lines.append(
            f"| 诉请总额 | {amount_report.total_claimed:,} 元 | 原告主张金额 |"
        )
    if hasattr(amount_report, "verified_amount"):
        lines.append(
            f"| 可核实金额 | {amount_report.verified_amount:,} 元 | 有证据支撑的金额 |"
        )

    return "\n".join(lines) if len(lines) > 2 else "*暂无金额计算明细。*"


def _render_glossary() -> str:
    """Render glossary of legal terms used in the report."""
    terms = [
        ("争点", "双方在事实或法律适用上存在分歧的焦点问题"),
        ("举证责任", "当事人应当对其主张的事实承担提供证据并加以证明的责任"),
        ("质证", "对对方提交的证据进行审查、核实、反驳的诉讼行为"),
        ("书证", "以文字、符号、图形等记载或表示的内容来证明案件事实的证据"),
        ("电子数据", "通过电子邮件、聊天记录、电子交易记录等形成的信息数据"),
        ("证明力", "证据对待证事实的证明价值和说服力"),
        ("可采性", "证据是否符合法定条件，能否被法庭采纳使用"),
        ("借款合意", "借贷双方就借款事项达成的一致意思表示"),
    ]
    lines: list[str] = []
    lines.append("| 术语 | 解释 |")
    lines.append("|------|------|")
    for term, explanation in terms:
        lines.append(f"| {term} | {explanation} |")
    return "\n".join(lines)


def render_layer4_md(layer4: Layer4Appendix) -> list[str]:
    """Render Layer 4 as Markdown lines."""
    lines: list[str] = []
    lines.append(f"# 四、附录 {format_tag(SectionTag.fact)}")
    lines.append("")

    # Adversarial transcripts
    lines.append("## 4.1 三轮对抗辩论记录")
    lines.append("")
    lines.append(layer4.adversarial_transcripts_md)
    lines.append("")

    # Evidence index
    lines.append("## 4.2 证据索引")
    lines.append("")
    lines.append(layer4.evidence_index_md)
    lines.append("")

    # Timeline
    lines.append("## 4.3 案件时间线")
    lines.append("")
    lines.append(layer4.timeline_md)
    lines.append("")

    # Amount calculation
    if layer4.amount_calculation_md and "暂无" not in layer4.amount_calculation_md:
        lines.append("## 4.4 金额计算明细")
        lines.append("")
        lines.append(layer4.amount_calculation_md)
        lines.append("")

    # Glossary
    lines.append("## 4.5 术语表")
    lines.append("")
    lines.append(layer4.glossary_md)
    lines.append("")

    return lines
