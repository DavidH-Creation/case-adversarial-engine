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

import re

from engines.report_generation.v3.models import Layer4Appendix, SectionTag, TimelineEvent
from engines.report_generation.v3.tag_system import format_tag

# ---------------------------------------------------------------------------
# Date extraction regexes
# ---------------------------------------------------------------------------

_DATE_CN_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
_DATE_ISO_RE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_TIME_CN_RE = re.compile(r"(\d{1,2})[时:](\d{1,2})[分]?")


# ---------------------------------------------------------------------------
# Timeline auto-generation
# ---------------------------------------------------------------------------


def _extract_date_from_match(
    match: re.Match, pattern_type: str,
) -> str:
    """Normalize a date regex match to YYYY-MM-DD format."""
    year, month, day = match.group(1), match.group(2), match.group(3)
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _extract_events_from_text(
    text: str,
    source: str,
    disputed: bool = False,
) -> list[TimelineEvent]:
    """Extract timeline events from a text string using date regexes.

    For each date found, take up to 30 chars before and after the match
    as context to form the event description.
    """
    if not text:
        return []

    events: list[TimelineEvent] = []
    seen_positions: set[int] = set()

    for pattern, ptype in [(_DATE_CN_RE, "cn"), (_DATE_ISO_RE, "iso")]:
        for m in pattern.finditer(text):
            # Deduplicate overlapping matches at same position
            if m.start() in seen_positions:
                continue
            seen_positions.add(m.start())

            date_str = _extract_date_from_match(m, ptype)

            # Extract surrounding context (30 chars each side)
            ctx_start = max(0, m.start() - 30)
            ctx_end = min(len(text), m.end() + 30)
            context = text[ctx_start:ctx_end].strip()
            # Clean up: collapse whitespace, remove newlines
            context = re.sub(r"\s+", " ", context)

            # Check for time pattern immediately after the date
            time_suffix = ""
            after_date = text[m.end() : m.end() + 10]
            time_match = _TIME_CN_RE.search(after_date)
            if time_match:
                hour, minute = int(time_match.group(1)), int(time_match.group(2))
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    time_suffix = f" {hour:02d}:{minute:02d}"

            events.append(
                TimelineEvent(
                    date=date_str + time_suffix,
                    event=context,
                    source=source,
                    disputed=disputed,
                ),
            )

    return events


def auto_generate_timeline(
    case_data: dict,
    evidence_index=None,
    issue_tree=None,
) -> list[TimelineEvent]:
    """Auto-generate case timeline from all available sources.

    Sources (in priority order):
    1. case_data["timeline"] -- explicit timeline entries
    2. case_data["summary"] -- extract dates via regex
    3. Evidence summaries -- extract dates via regex
    4. Evidence titles -- extract dates via regex
    5. Evidence metadata -- transfer dates, filing dates

    Returns a sorted, deduplicated list of :class:`TimelineEvent`.
    If fewer than 5 events are found, generic placeholder events
    (e.g. filing date) are appended from ``case_data``.
    """
    events: list[TimelineEvent] = []

    # ----- Source 1: explicit timeline entries -----
    raw_timeline = case_data.get("timeline", [])
    for entry in raw_timeline:
        if isinstance(entry, dict):
            events.append(
                TimelineEvent(
                    date=entry.get("date", ""),
                    event=entry.get("description", entry.get("event", "")),
                    source="case_data",
                    disputed=bool(entry.get("disputed", False)),
                ),
            )
        elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
            events.append(
                TimelineEvent(
                    date=str(entry[0]),
                    event=str(entry[1]),
                    source="case_data",
                ),
            )

    # ----- Source 2: case_data summary text -----
    summary_text = case_data.get("summary", "")
    if isinstance(summary_text, list):
        summary_text = "\n".join(str(s) for s in summary_text)
    if summary_text:
        events.extend(
            _extract_events_from_text(summary_text, source="case_data"),
        )

    # ----- Sources 3-5: evidence index -----
    if evidence_index is not None:
        ev_list = getattr(evidence_index, "evidence", [])
        for ev in ev_list:
            ev_id = getattr(ev, "evidence_id", "unknown")
            is_disputed = bool(getattr(ev, "challenged_by_party_ids", None))

            # Source 3: evidence summary
            ev_summary = getattr(ev, "summary", "")
            if ev_summary:
                events.extend(
                    _extract_events_from_text(ev_summary, source=ev_id, disputed=is_disputed),
                )

            # Source 4: evidence title
            ev_title = getattr(ev, "title", "")
            if ev_title:
                events.extend(
                    _extract_events_from_text(ev_title, source=ev_id, disputed=is_disputed),
                )

    # ----- Deduplication -----
    seen: set[tuple[str, str]] = set()
    unique_events: list[TimelineEvent] = []
    for evt in events:
        # Dedup key: (date, first 20 chars of event text)
        key = (evt.date, evt.event[:20])
        if key not in seen:
            seen.add(key)
            unique_events.append(evt)

    # ----- Sort by date ascending (YYYY-MM-DD string sort) -----
    unique_events.sort(key=lambda e: e.date)

    # ----- Ensure minimum 5 entries -----
    if len(unique_events) < 5:
        # Try to add generic events from case_data metadata
        filing_date = case_data.get("filing_date", "")
        if filing_date and ("filing_date", filing_date[:20]) not in seen:
            unique_events.append(
                TimelineEvent(
                    date=filing_date,
                    event="案件立案",
                    source="case_data",
                ),
            )
            seen.add(("filing_date", filing_date[:20]))

        acceptance_date = case_data.get("acceptance_date", "")
        if acceptance_date and ("acceptance_date", acceptance_date[:20]) not in seen:
            unique_events.append(
                TimelineEvent(
                    date=acceptance_date,
                    event="法院受理",
                    source="case_data",
                ),
            )
            seen.add(("acceptance_date", acceptance_date[:20]))

        hearing_date = case_data.get("hearing_date", "")
        if hearing_date and ("hearing_date", hearing_date[:20]) not in seen:
            unique_events.append(
                TimelineEvent(
                    date=hearing_date,
                    event="开庭审理",
                    source="case_data",
                ),
            )
            seen.add(("hearing_date", hearing_date[:20]))

        mediation_date = case_data.get("mediation_date", "")
        if mediation_date and ("mediation_date", mediation_date[:20]) not in seen:
            unique_events.append(
                TimelineEvent(
                    date=mediation_date,
                    event="调解",
                    source="case_data",
                ),
            )
            seen.add(("mediation_date", mediation_date[:20]))

        judgment_date = case_data.get("judgment_date", "")
        if judgment_date and ("judgment_date", judgment_date[:20]) not in seen:
            unique_events.append(
                TimelineEvent(
                    date=judgment_date,
                    event="判决下达",
                    source="case_data",
                ),
            )
            seen.add(("judgment_date", judgment_date[:20]))

        # Re-sort after adding generic events
        unique_events.sort(key=lambda e: e.date)

    return unique_events


# ---------------------------------------------------------------------------
# Layer 4 builder
# ---------------------------------------------------------------------------


def build_layer4(
    *,
    adversarial_result,
    evidence_index,
    issue_tree,
    amount_report=None,
    case_data: dict | None = None,
    timeline_events: list[TimelineEvent] | None = None,
) -> Layer4Appendix:
    """Build Layer 4 appendix.

    All content in this layer is perspective-independent.

    If *timeline_events* is provided, those events are rendered directly.
    Otherwise, :func:`auto_generate_timeline` is called to extract events
    from *case_data* and *evidence_index*.
    """
    cd = case_data or {}

    # Adversarial transcripts
    transcripts_md = _render_adversarial_transcripts(adversarial_result)

    # Evidence index
    evidence_md = _render_evidence_index(evidence_index)

    # Timeline — use provided events or auto-generate
    if timeline_events is None:
        timeline_events = auto_generate_timeline(
            cd,
            evidence_index=evidence_index,
            issue_tree=issue_tree,
        )
    timeline_md = _render_timeline(cd, timeline_events=timeline_events)

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


def _render_timeline(
    case_data: dict,
    timeline_events: list[TimelineEvent] | None = None,
) -> str:
    """Render case timeline.

    When *timeline_events* are provided (auto-generated or explicit),
    render a richer table with source and disputed columns.  Otherwise
    fall back to the original ``case_data["timeline"]`` dict/tuple format.
    """
    # ----- New path: structured TimelineEvent objects -----
    if timeline_events:
        lines: list[str] = [
            "| 日期 | 事件 | 来源 | 争议 |",
            "|------|------|------|------|",
        ]
        for evt in timeline_events:
            disputed_marker = "\u26a0\ufe0f" if evt.disputed else ""
            lines.append(
                f"| {evt.date} | {evt.event} | {evt.source} | {disputed_marker} |",
            )
        return "\n".join(lines)

    # ----- Legacy fallback: raw case_data dicts/tuples -----
    events = case_data.get("timeline", [])
    if not events:
        return "*暂无时间线数据。*"

    lines = [
        "| 日期 | 事件 |",
        "|------|------|",
    ]
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
