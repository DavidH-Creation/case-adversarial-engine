"""
V3 四层报告主生成器 / V3 4-Layer Report Writer.

替代 scripts/run_case.py 中的 _write_md() 函数。
生成完整的四层结构化 Markdown 报告。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

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
from engines.report_generation.v3.tag_system import format_tag, humanize_text


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
    """Build the complete 4-layer report data structure.

    Args:
        adversarial_result: AdversarialResult from debate engine
        issue_tree: IssueTree from case structuring
        evidence_index: EvidenceIndex from case structuring
        case_data: Raw YAML case data dict
        ranked_issues: IssueTree with ranking data (optional)
        decision_tree: DecisionPathTree (optional, converted to conditional tree)
        attack_chain: OptimalAttackChain (optional)
        defense_chain: DefenseChain (optional)
        action_rec: ActionRecommendation (optional)
        exec_summary: ExecutiveSummaryArtifact (optional)
        amount_report: AmountCalculationReport (optional)
        hearing_order: HearingOrder (optional)
        perspective: "plaintiff" / "defendant" / "neutral"

    Returns:
        FourLayerReport
    """
    from engines.report_generation.v3.scenario_tree import (
        build_scenario_tree_from_decision_paths,
    )

    # Build conditional scenario tree ONCE and share across layers
    scenario_tree = build_scenario_tree_from_decision_paths(
        decision_tree, issue_tree, evidence_index
    )

    # Build timeline ONCE and share across Layer 1 and Layer 4
    timeline_events = auto_generate_timeline(
        case_data, evidence_index=evidence_index, issue_tree=issue_tree,
    )

    # Build evidence priorities ONCE and share across layers
    evidence_priorities = classify_all_evidence_priority(
        evidence_index.evidence if evidence_index else [],
        issue_tree,
        ranked_issues=ranked_issues,
    )

    # Build each layer
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
        case_id=adversarial_result.case_id if adversarial_result else case_data.get("case_id", "unknown"),
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
    """Write the 4-layer report as a Markdown file.

    This is the V3 replacement for the old _write_md() function.

    Args:
        out: Output directory path
        report: FourLayerReport data structure
        case_data: Raw YAML case data dict
        no_redact: If True, skip PII redaction

    Returns:
        Path to the written report file
    """
    from engines.shared.disclaimer_templates import DISCLAIMER_MD
    from engines.shared.pii_redactor import redact_text

    # Collect party names for redaction whitelist
    party_names: list[str] = []
    for _role, info in case_data.get("parties", {}).items():
        name = info.get("name", "")
        if name:
            party_names.append(name)

    perspective_label = {
        "plaintiff": "原告视角",
        "defendant": "被告视角",
        "neutral": "中立双视角",
    }.get(report.perspective, "中立双视角")

    p = out / "report.md"
    lines: list[str] = [
        DISCLAIMER_MD,
        "",
        "# " + case_data.get("case_type", "civil_loan").replace("_", " ").title() + " — 案件诊断报告",
        "",
        f"**Case ID**: {report.case_id}  |  **Run ID**: {report.run_id}",
        f"**Generated**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**视角**: {perspective_label}",
        f"**报告版本**: V3 四层架构",
        "",
        "---",
        "",
        f"# 一、封面摘要 {format_tag(SectionTag.fact)}",
        "",
    ]

    # Layer 1
    lines.extend(render_layer1_md(report.layer1, report.perspective))
    lines.append("---")
    lines.append("")

    # Build humanize context from report data for ID→label conversion
    humanize_ctx: dict[str, str] = {}
    for card in report.layer2.issue_map:
        humanize_ctx[card.issue_id] = card.issue_title
    for ecard in report.layer2.evidence_cards:
        if isinstance(ecard, EvidenceBasicCard):
            humanize_ctx[ecard.evidence_id] = ecard.q1_what[:30] if ecard.q1_what else ""

    # Layer 2
    lines.extend(render_layer2_md(report.layer2, humanize_ctx=humanize_ctx))
    lines.append("---")
    lines.append("")

    # Layer 3
    lines.extend(render_layer3_md(report.layer3, report.perspective))
    lines.append("---")
    lines.append("")

    # Layer 4
    lines.extend(render_layer4_md(report.layer4))

    content = "\n".join(lines)
    # Humanize internal IDs throughout the report (especially Layer 4 appendix)
    content = humanize_text(content, context=humanize_ctx)
    if not no_redact:
        content = redact_text(content, party_names=party_names or None)
    p.write_text(content, encoding="utf-8")
    return p
