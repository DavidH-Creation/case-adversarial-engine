"""
Layer 2: 中立对抗内核层 / Neutral Adversarial Core Layer.

完全中立，不受 --perspective 影响：
  2.1 事实底座 — 仅无争议客观事实
  2.2 争点地图 — 固定模板卡片
  2.3 证据作战矩阵 — 七问
  2.4 条件场景树 — 二元条件分支
"""

from __future__ import annotations

from engines.report_generation.v3.evidence_battle_matrix import (
    build_evidence_battle_matrix,
    build_evidence_cards,
)
from engines.report_generation.v3.fact_base import extract_fact_base
from engines.report_generation.v3.issue_map import build_issue_map
from engines.report_generation.v3.models import (
    EvidenceBasicCard,
    EvidenceKeyCard,
    EvidenceRiskLevel,
    Layer2Core,
    SectionTag,
)
from engines.report_generation.v3.scenario_tree import (
    render_scenario_tree_text,
)
from engines.report_generation.v3.tag_system import format_tag, humanize_text


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

    # 2.3 Evidence cards (dual-tier) + unified electronic strategy
    evidence_cards, unified_electronic_strategy = build_evidence_cards(
        evidence_index, issue_tree, attack_chain
    )

    # 2.3b DEPRECATED: old battle matrix for backward compat
    evidence_matrix = build_evidence_battle_matrix(
        evidence_index, issue_tree, attack_chain
    )

    # 2.4 Conditional scenario tree — pre-built, passed in from caller
    return Layer2Core(
        fact_base=fact_base,
        issue_map=issue_map,
        evidence_cards=evidence_cards,
        unified_electronic_strategy=unified_electronic_strategy,
        evidence_battle_matrix=evidence_matrix,
        scenario_tree=scenario_tree,
    )


def _h(text: str, ctx: dict[str, str] | None) -> str:
    """Humanize text if context is available, otherwise return as-is."""
    if ctx:
        return humanize_text(text, ctx)
    return text


def _h_list(items: list[str], ctx: dict[str, str] | None) -> list[str]:
    """Humanize a list of strings."""
    return [_h(item, ctx) for item in items]


def render_layer2_md(
    layer2: Layer2Core,
    *,
    humanize_ctx: dict[str, str] | None = None,
) -> list[str]:
    """Render Layer 2 as Markdown lines.

    Args:
        layer2: The Layer2Core model containing all layer 2 data.
        humanize_ctx: Optional dict mapping raw IDs to human-readable titles.
            When provided, all internal IDs (issue-xxx-001, evidence-plaintiff-003,
            etc.) are converted to human-readable Chinese labels.
    """
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
            fact_id = _h(fb.fact_id, humanize_ctx)
            desc = _h(fb.description[:80], humanize_ctx)
            ev_refs = ", ".join(_h_list(fb.source_evidence_ids[:3], humanize_ctx))
            lines.append(f"| {fact_id} | {desc} | {ev_refs} |")
        lines.append("")
    else:
        lines.append("*暂无双方均认可的无争议事实。*")
        lines.append("")

    # --- 2.2 Issue Map (tree hierarchy) ---
    lines.append(f"## 2.2 争点地图 {format_tag(SectionTag.inference)}")
    lines.append("")
    for card in layer2.issue_map:
        title = _h(card.issue_title, humanize_ctx)
        sensitivity = card.outcome_sensitivity or "待评估"

        if card.depth == 0:
            # Root issue (L1): full card with table
            lines.append(f"### {title} ⚡{sensitivity}")
            lines.append("")
            lines.append("| 字段 | 内容 |")
            lines.append("|------|------|")
            lines.append(
                f"| 原告主张 | {_h(card.plaintiff_thesis, humanize_ctx)} |"
            )
            lines.append(
                f"| 被告主张 | {_h(card.defendant_thesis, humanize_ctx)} |"
            )
            decisive = (
                ", ".join(_h_list(card.decisive_evidence, humanize_ctx))
                if card.decisive_evidence
                else "待补充"
            )
            lines.append(f"| 决定性证据 | {decisive} |")
            gaps = (
                "; ".join(_h_list(card.current_gaps, humanize_ctx))
                if card.current_gaps
                else "暂无"
            )
            lines.append(f"| 当前缺口 | {gaps} |")
            lines.append("")
        else:
            # Child issue (L2+): compact blockquote format
            lines.append(f"> **子争点**: {title} ⚡{sensitivity}")
            lines.append(">")
            lines.append(
                f"> 原告: {_h(card.plaintiff_thesis, humanize_ctx)} / "
                f"被告: {_h(card.defendant_thesis, humanize_ctx)}"
            )
            if card.current_gaps:
                gaps = "; ".join(_h_list(card.current_gaps, humanize_ctx))
                lines.append(f"> 缺口: {gaps}")
            lines.append("")

    # --- 2.3 Evidence Analysis ---
    lines.append(f"## 2.3 证据作战矩阵 {format_tag(SectionTag.inference)}")
    lines.append("")

    # 2.3a Unified electronic evidence strategy (if present)
    if layer2.unified_electronic_strategy:
        lines.append("#### 统一电子证据补强策略")
        lines.append("")
        lines.append(_h(layer2.unified_electronic_strategy, humanize_ctx))
        lines.append("")

    # 2.3b Dual-tier evidence cards (V3.1 path)
    if layer2.evidence_cards:
        # Separate key (core) cards from basic (supporting/background) cards
        key_cards: list[EvidenceKeyCard] = []
        basic_cards: list[EvidenceBasicCard] = []
        for card in layer2.evidence_cards:
            if isinstance(card, EvidenceKeyCard):
                key_cards.append(card)
            else:
                basic_cards.append(card)

        # --- Key evidence cards (full 6-field table each) ---
        if key_cards:
            lines.append("### 核心证据详析")
            lines.append("")
            for card in key_cards:
                ev_name = _h(card.evidence_id, humanize_ctx)
                lines.append(f"#### {ev_name} — 核心证据")
                lines.append("")
                lines.append("| 字段 | 分析 |")
                lines.append("|------|------|")
                lines.append(f"| ① 内容 | {_h(card.q1_what, humanize_ctx)} |")
                lines.append(
                    f"| ② 服务争点 | {_h(card.q2_target, humanize_ctx)} |"
                )
                lines.append(
                    f"| ③ 关键风险 | {_h(card.q3_key_risk, humanize_ctx)} |"
                )
                lines.append(
                    f"| ④ 对方最佳攻击点 | {_h(card.q4_best_attack, humanize_ctx)} |"
                )
                lines.append(
                    f"| ⑤ 如何加固 | {_h(card.q5_reinforce, humanize_ctx)} |"
                )
                lines.append(
                    f"| ⑥ 失效影响 | {_h(card.q6_failure_impact, humanize_ctx)} |"
                )
                lines.append("")

        # --- Basic evidence cards (compact summary table) ---
        if basic_cards:
            lines.append("### 辅助/背景证据概览")
            lines.append("")
            lines.append("| 证据 | 层级 | 服务争点 | 关键风险 | 对方最佳攻击点 |")
            lines.append("|------|------|----------|----------|----------------|")
            for card in basic_cards:
                ev_name = _h(card.evidence_id, humanize_ctx)
                priority = card.priority.value
                target = _h(card.q2_target, humanize_ctx)
                risk = _h(card.q3_key_risk, humanize_ctx)
                attack = _h(card.q4_best_attack, humanize_ctx)
                lines.append(
                    f"| {ev_name} | {priority} | {target} | {risk} | {attack} |"
                )
            lines.append("")

    elif layer2.evidence_battle_matrix:
        # 2.3c FALLBACK: old 7-question battle matrix (backward compat)
        _risk_emoji = {
            EvidenceRiskLevel.green: "🟢",
            EvidenceRiskLevel.yellow: "🟡",
            EvidenceRiskLevel.red: "🔴",
        }

        for card in layer2.evidence_battle_matrix:
            emoji = _risk_emoji.get(card.risk_level, "⚪")
            ev_name = _h(card.evidence_id, humanize_ctx)
            lines.append(f"### {ev_name} {emoji}")
            lines.append("")
            lines.append("| 问题 | 分析 |")
            lines.append("|------|------|")
            lines.append(f"| 1. 这是什么证据 | {_h(card.q1_what, humanize_ctx)} |")
            lines.append(f"| 2. 证明什么命题 | {_h(card.q2_proves, humanize_ctx)} |")
            lines.append(f"| 3. 证明方向 | {_h(card.q3_direction, humanize_ctx)} |")
            lines.append(f"| 4. 四性风险 | {_h(card.q4_risks, humanize_ctx)} |")
            lines.append(
                f"| 5. 对方如何攻击 | {_h(card.q5_opponent_attack, humanize_ctx)} |"
            )
            lines.append(f"| 6. 如何加固 | {_h(card.q6_reinforce, humanize_ctx)} |")
            lines.append(
                f"| 7. 失败影响 | {_h(card.q7_failure_impact, humanize_ctx)} |"
            )
            lines.append("")
    else:
        lines.append("*暂无证据分析数据。*")
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
