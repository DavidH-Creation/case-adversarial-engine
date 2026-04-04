"""V3 four-layer report builder and Markdown writer."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import uuid

from engines.report_generation.v3.evidence_classifier import classify_all_evidence_priority
from engines.report_generation.v3.layer1_cover import build_layer1, render_layer1_md
from engines.report_generation.v3.layer2_core import build_layer2, render_layer2_md
from engines.report_generation.v3.layer3_perspective import build_layer3, render_layer3_md
from engines.report_generation.v3.layer4_appendix import (
    auto_generate_timeline,
    build_layer4,
    render_layer4_md,
)
from engines.report_generation.v3.models import EvidenceBasicCard, FourLayerReport, SectionTag
from engines.report_generation.v3.render_contract import lint_markdown_render_contract
from engines.report_generation.v3.tag_system import (
    build_humanize_context,
    format_tag,
    humanize_text,
)


def build_four_layer_report(
    *,
    adversarial_result,
    issue_tree,
    evidence_index,
    case_data: dict,
    ranked_issues=None,
    decision_tree=None,
    attack_chain=None,
    defense_chain=None,
    action_rec=None,
    exec_summary=None,
    amount_report=None,
    hearing_order=None,
    perspective: str = "neutral",
) -> FourLayerReport:
    """Build the complete four-layer report data structure."""
    from engines.report_generation.v3.scenario_tree import (
        build_scenario_tree_from_decision_paths,
    )

    scenario_tree = build_scenario_tree_from_decision_paths(
        decision_tree,
        issue_tree,
        evidence_index,
    )
    timeline_events = auto_generate_timeline(
        case_data,
        evidence_index=evidence_index,
        issue_tree=issue_tree,
    )
    evidence_priorities = classify_all_evidence_priority(
        evidence_index.evidence if evidence_index else [],
        issue_tree,
        ranked_issues=ranked_issues,
    )

    layer1 = build_layer1(
        adversarial_result=adversarial_result,
        evidence_index=evidence_index,
        issue_tree=issue_tree,
        scenario_tree=scenario_tree,
        exec_summary=exec_summary,
        action_rec=action_rec,
        attack_chain=attack_chain,
        evidence_priorities=evidence_priorities,
        timeline=timeline_events,
        perspective=perspective,
    )
    layer2 = build_layer2(
        issue_tree=issue_tree,
        evidence_index=evidence_index,
        adversarial_result=adversarial_result,
        ranked_issues=ranked_issues,
        attack_chain=attack_chain,
        scenario_tree=scenario_tree,
    )
    layer3 = build_layer3(
        adversarial_result=adversarial_result,
        issue_tree=issue_tree,
        evidence_index=evidence_index,
        action_rec=action_rec,
        attack_chain=attack_chain,
        defense_chain=defense_chain,
        exec_summary=exec_summary,
        hearing_order=hearing_order,
        evidence_cards=layer2.evidence_cards,
        unified_electronic_strategy=layer2.unified_electronic_strategy,
        scenario_tree=scenario_tree,
        perspective=perspective,
    )
    layer4 = build_layer4(
        adversarial_result=adversarial_result,
        evidence_index=evidence_index,
        issue_tree=issue_tree,
        amount_report=amount_report,
        case_data=case_data,
        timeline_events=timeline_events,
    )

    return FourLayerReport(
        report_id=f"rpt-v3-{uuid.uuid4().hex[:12]}",
        case_id=adversarial_result.case_id
        if adversarial_result
        else case_data.get("case_id", "unknown"),
        run_id=adversarial_result.run_id if adversarial_result else f"run-{uuid.uuid4().hex[:8]}",
        perspective=perspective,
        layer1=layer1,
        layer2=layer2,
        layer3=layer3,
        layer4=layer4,
    )


def write_v3_report_md(
    out: Path,
    report: FourLayerReport,
    case_data: dict,
    *,
    no_redact: bool = False,
) -> Path:
    """Write the four-layer report as a Markdown file."""
    from engines.shared.disclaimer_templates import DISCLAIMER_MD
    from engines.shared.pii_redactor import redact_text

    party_names = [
        info.get("name", "")
        for info in case_data.get("parties", {}).values()
        if info.get("name", "")
    ]

    perspective_label = {
        "plaintiff": "原告视角",
        "defendant": "被告视角",
        "neutral": "中立双视角",
    }.get(report.perspective, "中立双视角")

    output_path = out / "report.md"
    lines: list[str] = [
        DISCLAIMER_MD,
        "",
        "# "
        + case_data.get("case_type", "civil_loan").replace("_", " ").title()
        + " - 案件诊断报告",
        "",
        f"**Case ID**: {report.case_id}  |  **Run ID**: {report.run_id}",
        f"**Generated**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**视角**: {perspective_label}",
        "**报告版本**: V3 四层架构",
        "",
        "---",
        "",
        f"# 一、封面摘要 {format_tag(SectionTag.fact)}",
        "",
    ]

    lines.extend(render_layer1_md(report.layer1, report.perspective))
    lines.extend(["---", ""])

    humanize_ctx = build_humanize_context()
    for card in report.layer2.issue_map:
        humanize_ctx[card.issue_id] = card.issue_title
    for evidence_card in report.layer2.evidence_cards:
        if isinstance(evidence_card, EvidenceBasicCard):
            title = evidence_card.q1_what[:30] if evidence_card.q1_what else ""
            if title:
                humanize_ctx[evidence_card.evidence_id] = title

    lines.extend(render_layer2_md(report.layer2, humanize_ctx=humanize_ctx))
    lines.extend(["---", ""])
    lines.extend(render_layer3_md(report.layer3, report.perspective))
    lines.extend(["---", ""])
    lines.extend(render_layer4_md(report.layer4))

    content = "\n".join(lines)
    content = _fill_empty_major_sections(content)
    content = humanize_text(content, context=humanize_ctx)
    if not no_redact:
        content = redact_text(content, party_names=party_names or None)
    lint_markdown_render_contract(content)

    output_path.write_text(content, encoding="utf-8")
    return output_path


def _fill_empty_major_sections(content: str) -> str:
    """Insert controlled fallbacks when a level-2 section would otherwise be empty."""
    headings = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", content))
    if not headings:
        return content

    parts: list[str] = []
    cursor = 0
    for index, match in enumerate(headings):
        section_start = match.start()
        body_start = match.end()
        next_start = headings[index + 1].start() if index + 1 < len(headings) else len(content)

        parts.append(content[cursor:section_start])

        title = match.group(1).strip()
        body = content[body_start:next_start]
        if body.strip():
            parts.append(content[section_start:next_start])
        else:
            fallback = _section_fallback(title)
            parts.append(content[section_start:body_start] + "\n" + fallback + "\n")
        cursor = next_start

    parts.append(content[cursor:])
    return "".join(parts)


def _section_fallback(title: str) -> str:
    fallback_map = {
        "争点地图": "*暂无争点地图数据。*",
        "三轮对抗辩论记录": "*暂无对抗辩论记录。*",
        "证据索引": "*暂无证据索引数据。*",
        "案件时间线": "*暂无时间线数据。*",
        "术语表": "*暂无术语表。*",
        "Decision Path Tree": "*No decision path tree available.*",
        "Action Recommendations": "*No action recommendations available.*",
    }
    for key, fallback in fallback_map.items():
        if key in title:
            return fallback
    return "*暂无可展示内容。*"
