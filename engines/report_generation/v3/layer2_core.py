"""
Layer 2: 中立对抗内核层 / Neutral Adversarial Core Layer.

完全中立，不受 --perspective 影响：
  2.1 事实底座 — 仅无争议客观事实
  2.2 争点地图 — 固定模板卡片
  2.3 证据作战矩阵 — 七问
  2.4 条件场景树 — 二元条件分支
"""

from __future__ import annotations

from engines.report_generation.v3.evidence_battle_matrix import build_evidence_battle_matrix
from engines.report_generation.v3.fact_base import extract_fact_base
from engines.report_generation.v3.issue_map import build_issue_map
from engines.report_generation.v3.models import (
    EvidenceRiskLevel,
    Layer2Core,
    SectionTag,
)
from engines.report_generation.v3.scenario_tree import (
    render_scenario_tree_text,
)
from engines.report_generation.v3.tag_system import format_tag


def build_layer2(
    *,
    issue_tree,
    evidence_index,
    adversarial_result=None,
    ranked_issues=None,
    attack_chain=None,
    scenario_tree=None,
) -> Layer2Core:
    """Build Layer 2 neutral adversarial core.

    All content in this layer is completely neutral and perspective-independent.
    The scenario_tree should be pre-built by the caller (report_writer) to
    avoid duplicate construction.
    """
    # 2.1 Fact base — adversarial_result used ONLY for dispute detection
    fact_base = extract_fact_base(issue_tree, evidence_index, adversarial_result)

    # 2.2 Issue map — presents BOTH sides neutrally with source attribution
    issue_map = build_issue_map(
        issue_tree, adversarial_result, ranked_issues, attack_chain
    )

    # 2.3 Evidence battle matrix — neutral analysis of evidence stability
    evidence_matrix = build_evidence_battle_matrix(
        evidence_index, issue_tree, attack_chain
    )

    # 2.4 Conditional scenario tree — pre-built, passed in from caller
    return Layer2Core(
        fact_base=fact_base,
        issue_map=issue_map,
        evidence_battle_matrix=evidence_matrix,
        scenario_tree=scenario_tree,
    )


def render_layer2_md(layer2: Layer2Core) -> list[str]:
    """Render Layer 2 as Markdown lines."""
    lines: list[str] = []

    # --- 2.1 Fact Base ---
    lines.append(f"# 二、中立对抗内核 {format_tag(SectionTag.fact)}")
    lines.append("")
    lines.append(f"## 2.1 事实底座 {format_tag(SectionTag.fact)}")
    lines.append("")
    if layer2.fact_base:
        lines.append("| # | 事实描述 | 来源证据 |")
        lines.append("|---|----------|----------|")
        for fb in layer2.fact_base:
            ev_refs = ", ".join(fb.source_evidence_ids[:3])
            lines.append(f"| {fb.fact_id} | {fb.description[:80]} | {ev_refs} |")
        lines.append("")
    else:
        lines.append("*暂无双方均认可的无争议事实。*")
        lines.append("")

    # --- 2.2 Issue Map ---
    lines.append(f"## 2.2 争点地图 {format_tag(SectionTag.inference)}")
    lines.append("")
    for card in layer2.issue_map:
        lines.append(f"### {card.issue_id}: {card.issue_title}")
        lines.append("")
        lines.append("| 字段 | 内容 |")
        lines.append("|------|------|")
        lines.append(f"| 原告主张 | {card.plaintiff_thesis} |")
        lines.append(f"| 被告主张 | {card.defendant_thesis} |")
        lines.append(
            f"| 决定性证据 | {', '.join(card.decisive_evidence) if card.decisive_evidence else '待补充'} |"
        )
        lines.append(
            f"| 当前缺口 | {'; '.join(card.current_gaps) if card.current_gaps else '暂无'} |"
        )
        lines.append(f"| 结果敏感度 | {card.outcome_sensitivity or '待评估'} |")
        lines.append("")

    # --- 2.3 Evidence Battle Matrix ---
    lines.append(f"## 2.3 证据作战矩阵 {format_tag(SectionTag.inference)}")
    lines.append("")

    _risk_emoji = {
        EvidenceRiskLevel.green: "🟢",
        EvidenceRiskLevel.yellow: "🟡",
        EvidenceRiskLevel.red: "🔴",
    }

    for card in layer2.evidence_battle_matrix:
        emoji = _risk_emoji.get(card.risk_level, "⚪")
        lines.append(f"### {card.evidence_id} {emoji}")
        lines.append("")
        lines.append("| 问题 | 分析 |")
        lines.append("|------|------|")
        lines.append(f"| 1. 这是什么证据 | {card.q1_what} |")
        lines.append(f"| 2. 证明什么命题 | {card.q2_proves} |")
        lines.append(f"| 3. 证明方向 | {card.q3_direction} |")
        lines.append(f"| 4. 四性风险 | {card.q4_risks} |")
        lines.append(f"| 5. 对方如何攻击 | {card.q5_opponent_attack} |")
        lines.append(f"| 6. 如何加固 | {card.q6_reinforce} |")
        lines.append(f"| 7. 失败影响 | {card.q7_failure_impact} |")
        lines.append("")

    # --- 2.4 Conditional Scenario Tree ---
    lines.append(f"## 2.4 条件场景树 {format_tag(SectionTag.inference)}")
    lines.append("")
    if layer2.scenario_tree:
        tree_text = render_scenario_tree_text(layer2.scenario_tree)
        if tree_text:
            lines.append("```")
            lines.append(tree_text)
            lines.append("```")
            lines.append("")
        else:
            lines.append("*场景树数据不足，无法渲染。*")
            lines.append("")
    else:
        lines.append("*暂无条件场景树数据。*")
        lines.append("")

    return lines
