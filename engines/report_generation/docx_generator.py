"""
通用 Word 文档报告生成器 — 对抗分析报告模板。
Reusable DOCX report generator for adversarial case analysis.

从 run_case.py 管道末端调用，接收结构化数据，生成统一格式的 Word 报告。
Zero hardcoded case-specific content — all data comes from parameters.

Usage:
    from engines.report_generation.docx_generator import generate_docx_report
    dest = generate_docx_report(
        output_dir=Path("outputs/20260329-123456"),
        case_data=case_data,          # YAML dict
        result=result_dict,           # AdversarialResult as dict
        issue_tree=issue_tree,        # IssueTree object (has .issues with .title, .issue_type)
        decision_tree=dt_dict,        # DecisionPathTree as dict (or None)
        attack_chain=ac_dict,         # OptimalAttackChain as dict (or None)
        exec_summary=es_dict,         # ExecutiveSummaryArtifact as dict (or None)
        amount_report=ar_dict,        # AmountCalculationReport as dict (or None)
    )
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.shared import Emu, RGBColor

from engines.shared.disclaimer_templates import DISCLAIMER_DOCX_BODY, DISCLAIMER_DOCX_TITLE
from engines.report_generation.risk_heatmap import build_risk_heatmap, RISK_LABEL_ZH, RiskLevel
from engines.report_generation.mediation_range import compute_mediation_range

# ---------------------------------------------------------------------------
# 样式常量 / Style constants
# ---------------------------------------------------------------------------
CLR_TITLE_DARK = RGBColor(0x1B, 0x3A, 0x5C)
CLR_BLUE = RGBColor(0x2E, 0x75, 0xB6)
CLR_RED = RGBColor(0xC0, 0x39, 0x2B)
CLR_GREEN = RGBColor(0x27, 0xAE, 0x60)
CLR_ORANGE = RGBColor(0xE6, 0x7E, 0x22)
CLR_BODY = RGBColor(0x1A, 0x1A, 0x1A)
CLR_GRAY = RGBColor(0x4A, 0x4A, 0x4A)

SZ_TITLE = 279_400  # ~22pt
SZ_SUBTITLE = 203_200  # ~16pt
SZ_AGENT_TITLE = 152_400  # ~12pt
SZ_SECTION_HDR = 139_700  # ~11pt
SZ_BODY = 133_350  # ~10.5pt
SZ_RISK = 120_650  # ~9.5pt
SZ_EVIDENCE = 114_300  # ~9pt
SZ_NORMAL = 127_000  # ~10pt
FONT_NAME = "Arial"
FONT_EAST_ASIA = "Microsoft YaHei"

# ---------------------------------------------------------------------------
# 翻译映射 / Translation maps
# ---------------------------------------------------------------------------
_ISSUE_TYPE_ZH: dict[str, str] = {
    "factual": "事实争点",
    "mixed": "混合争点",
    "legal": "法律争点",
    "procedural": "程序争点",
}

_ROUND_PHASE_ZH: dict[str, str] = {
    "claim": "首轮主张",
    "evidence": "证据整理",
    "rebuttal": "针对性反驳",
}


# ---------------------------------------------------------------------------
# 内部工具函数 / Internal helpers
# ---------------------------------------------------------------------------


def _add_run(
    para,
    text: str,
    *,
    bold: bool = False,
    size: int | None = None,
    color: RGBColor | None = None,
    italic: bool = False,
):
    """向段落追加一个格式化 run。"""
    run = para.add_run(text)
    run.font.name = FONT_NAME
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = rPr.makeelement(qn("w:rFonts"), {})
        rPr.insert(0, rFonts)
    rFonts.set(qn("w:eastAsia"), FONT_EAST_ASIA)
    if bold:
        run.font.bold = True
    if size:
        run.font.size = size
    if color:
        run.font.color.rgb = color
    if italic:
        run.font.italic = True
    return run


def _styled(
    doc, text: str, *, bold: bool = False, size: int = SZ_NORMAL, color: RGBColor = CLR_BODY
):
    """添加单 run 段落。"""
    p = doc.add_paragraph()
    _add_run(p, text, bold=bold, size=size, color=color)
    return p


def _bullet(doc, text: str, *, size: int = SZ_NORMAL, color: RGBColor = CLR_BODY):
    p = doc.add_paragraph()
    _add_run(p, "• " + text, size=size, color=color)
    return p


def _agent_color(role: str) -> RGBColor:
    if "plaintiff" in role:
        return CLR_BLUE
    if "defendant" in role:
        return CLR_RED
    return CLR_GREEN


def _set_table_font(table):
    for row in table.rows:
        for cell in row.cells:
            for para in cell.paragraphs:
                for run in para.runs:
                    run.font.name = FONT_NAME
                    run.font.size = SZ_NORMAL


def _build_party_zh(case_data: dict) -> dict[str, str]:
    """从 YAML case_data 动态构建 party_id → 中文名映射。"""
    mapping: dict[str, str] = {}
    parties = case_data.get("parties", {})
    for role_key, info in parties.items():
        pid = info.get("party_id", "")
        name = info.get("name", "")
        if not pid or not name:
            continue
        if "plaintiff" in role_key:
            mapping[pid] = f"原告{name}方"
        else:
            mapping[pid] = f"被告{name}方"
    return mapping


def _build_issue_info(issue_tree) -> dict[str, tuple[str, str]]:
    """从 IssueTree 对象构建 issue_id → (title, type_value) 映射。"""
    info: dict[str, tuple[str, str]] = {}
    if issue_tree is None:
        return info
    for iss in getattr(issue_tree, "issues", []):
        itype = (
            getattr(iss.issue_type, "value", str(iss.issue_type))
            if hasattr(iss, "issue_type")
            else ""
        )
        info[iss.issue_id] = (iss.title, itype)
    return info


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _is_uuid(s: str) -> bool:
    """Return True if s looks like a raw UUID string."""
    return bool(_UUID_RE.match(s))


def _filter_uuids(items: list[str]) -> list[str]:
    """Remove raw UUID strings from a list of text items."""
    return [item for item in items if not _is_uuid(item)]


# ---------------------------------------------------------------------------
# 公共 API / Public API
# ---------------------------------------------------------------------------


def generate_docx_report(
    *,
    output_dir: Path,
    case_data: dict,
    result: dict,
    issue_tree: Any = None,
    ranked_issues: Any = None,
    decision_tree: dict | None = None,
    attack_chain: dict | None = None,
    exec_summary: dict | None = None,
    amount_report: dict | None = None,
    action_rec: Any = None,
    document_drafts: list | None = None,
    filename: str | None = None,
) -> Path:
    """生成通用对抗分析 Word 报告。

    Args:
        output_dir:      输出目录
        case_data:       YAML 案件定义 dict（含 parties, summary, case_type 等）
        result:          AdversarialResult 序列化 dict
        issue_tree:      IssueTree 对象（可选，用于争点描述/类型）
        decision_tree:   DecisionPathTree 序列化 dict（可选）
        attack_chain:    OptimalAttackChain 序列��� dict（可选）
        exec_summary:    ExecutiveSummaryArtifact 序列化 dict（可选���
        amount_report:   AmountCalculationReport 序列化 dict（可选）
        filename:        自定义文件名（默认 "对抗分析报告.docx"）

    Returns:
        生成的 docx 文件路径
    """
    decision_tree = decision_tree or {}
    attack_chain = attack_chain or {}
    exec_summary = exec_summary or {}
    amount_report = amount_report or {}

    party_zh = _build_party_zh(case_data)
    issue_info = _build_issue_info(issue_tree)

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = FONT_NAME
    style.font.size = Emu(SZ_NORMAL)

    # ── 标题块 ──
    _render_title(doc, case_data, result)
    # ── 免责声明 ──
    _render_disclaimer(doc)
    # ── 行动优先级清单 ──
    _render_action_priority_list(doc, exec_summary, action_rec)
    # ── 案件摘要 ──
    _render_case_summary(doc, case_data, result)
    # ── 争点列表 ──
    _render_issue_table(doc, result, issue_info)
    # ── 三轮对抗 ──
    _render_debate_rounds(doc, result)
    # ── 证据冲突 ──
    _render_conflicts(doc, result)
    # ── AI 综合分析 ──
    _render_llm_summary(doc, result)
    # ── 证据缺失 ──
    _render_missing_evidence(doc, result, party_zh)
    # ─��� 争点影响排序 ──
    _render_issue_ranking(doc, exec_summary)
    # ── 风险热力图 ──
    _render_risk_heatmap(doc, ranked_issues)
    # ── 裁判路径树 ──
    _render_decision_tree(doc, decision_tree)
    # ── 调解区间 ──
    _render_mediation_range(doc, amount_report, decision_tree)
    # ── 攻击链 ──
    _render_attack_chain(doc, attack_chain, party_zh)
    # ── 对方策略预警 ──
    _render_opponent_strategy_warning(doc, result, attack_chain)
    # ── 行动建议 ���─
    _render_action_recommendations(doc, exec_summary)
    # ── 执行摘要 ──
    _render_executive_summary(doc, exec_summary, amount_report)
    # ── 文书草稿 ──
    if document_drafts:
        _render_document_drafts(doc, document_drafts)

    # 保存
    if filename is None:
        filename = "对抗分析报告.docx"
    dest = output_dir / filename
    doc.save(str(dest))
    return dest


# ---------------------------------------------------------------------------
# 各章节渲染函数 / Section renderers
# ---------------------------------------------------------------------------


def _render_disclaimer(doc):
    """免责声明块（首页标题后）。"""
    _styled(doc, DISCLAIMER_DOCX_TITLE, bold=True, size=SZ_SECTION_HDR, color=CLR_ORANGE)
    _styled(doc, DISCLAIMER_DOCX_BODY, size=SZ_NORMAL, color=CLR_GRAY)
    doc.add_paragraph()


def _render_title(doc, case_data: dict, result: dict):
    """封面标题块。"""
    case_id = result.get("case_id", "")
    # 从 case_id 提取简短标识，如 "case-civil-loan-wang-v-chen-zhuang-2025" → "对抗分析报告"
    p0 = doc.add_paragraph()
    _add_run(p0, "对抗分析报告", bold=True, size=SZ_TITLE, color=CLR_TITLE_DARK)

    # 副标题：从 summary 提取核心争议 或用当事人名
    parties = case_data.get("parties", {})
    p_name = parties.get("plaintiff", {}).get("name", "原告")
    d_name = parties.get("defendant", {}).get("name", "被告")
    subtitle = f"{p_name} 诉 {d_name}"
    # 如果 summary 里有核心争议，追加
    for row in case_data.get("summary", []):
        if isinstance(row, list) and len(row) >= 2 and "争议" in str(row[0]):
            subtitle = f"{row[1]}（{subtitle}）"
            break

    p1 = doc.add_paragraph()
    _add_run(p1, subtitle, size=SZ_SUBTITLE, color=CLR_BLUE)

    p2 = doc.add_paragraph()
    model = case_data.get("model", "")
    _add_run(p2, f"对抗分析报告  |  对抗引擎  |  {model}", size=SZ_NORMAL, color=CLR_GRAY)
    doc.add_paragraph()


def _render_case_summary(doc, case_data: dict, result: dict):
    """案件摘要表格。"""
    doc.add_heading("案件摘要", level=1)

    rows = [
        ("案件ID", result.get("case_id", "")),
        ("运行ID", result.get("run_id", "")),
    ]
    # 追加 YAML summary 表
    for item in case_data.get("summary", []):
        if isinstance(item, list) and len(item) >= 2:
            rows.append((str(item[0]), str(item[1])))

    table = doc.add_table(rows=len(rows), cols=2)
    table.style = "Light Grid Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (k, v) in enumerate(rows):
        table.rows[i].cells[0].text = k
        table.rows[i].cells[1].text = v
    _set_table_font(table)


def _render_issue_table(doc, result: dict, issue_info: dict[str, tuple[str, str]]):
    """争点列表表格。"""
    # 收集所有唯一 issue_id
    seen_ids: list[str] = []
    seen_set: set[str] = set()
    for r in result.get("rounds", []):
        for o in r.get("outputs", []):
            for iid in o.get("issue_ids", []):
                if iid not in seen_set:
                    seen_ids.append(iid)
                    seen_set.add(iid)

    conflict_ids = {c["issue_id"] for c in result.get("evidence_conflicts", [])}

    doc.add_heading(f"争点列表（{len(seen_ids)}个争���）", level=1)
    table = doc.add_table(rows=1, cols=4)
    table.style = "Light Grid Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = table.rows[0].cells
    hdr[0].text = "#"
    hdr[1].text = "争点"
    hdr[2].text = "类型"
    hdr[3].text = "状态"

    for idx, iid in enumerate(seen_ids, 1):
        row = table.add_row().cells
        num = iid.split("-")[-1] if "-" in iid else str(idx)
        row[0].text = num
        desc, itype = issue_info.get(iid, (iid, ""))
        row[1].text = desc
        row[2].text = _ISSUE_TYPE_ZH.get(itype, itype)
        row[3].text = "⚠ 冲突" if iid in conflict_ids else "✔"
    _set_table_font(table)


def _render_debate_rounds(doc, result: dict):
    """三轮对抗记录。"""
    doc.add_heading("三轮对抗记录", level=1)

    for r in result.get("rounds", []):
        rn = r["round_number"]
        phase = r["phase"]
        label = _ROUND_PHASE_ZH.get(phase, phase)
        doc.add_heading(f"第{rn}轮：{label}", level=2)

        for o in r["outputs"]:
            role = o["agent_role_code"]
            title_text = o.get("title", "")
            body = o.get("body", "")
            ev_cited = ", ".join(o.get("evidence_citations", []))

            if "plaintiff" in role:
                role_label = "[原告代理]"
            elif "defendant" in role:
                role_label = "[被告代理]"
            else:
                role_label = "[证据管理]"

            p = doc.add_paragraph()
            _add_run(
                p,
                f"{role_label} {title_text}",
                bold=True,
                size=SZ_AGENT_TITLE,
                color=_agent_color(role),
            )
            _styled(
                doc, body[:2000] + ("..." if len(body) > 2000 else ""), size=SZ_BODY, color=CLR_BODY
            )
            _styled(doc, f"引用证据: {ev_cited}", size=SZ_EVIDENCE, color=CLR_GRAY)

            risk_flags = o.get("risk_flags", [])
            if risk_flags:
                _styled(doc, "风险标记:", bold=True, size=SZ_RISK, color=CLR_ORANGE)
                for rf in risk_flags:
                    desc = rf.get("description", "")
                    flag_id = rf.get("flag_id", "")
                    prefix = "【本方薄弱点】" if flag_id.startswith("own-weakness-") else ""
                    _bullet(doc, prefix + desc, size=SZ_RISK, color=CLR_GRAY)

            doc.add_paragraph()


def _render_conflicts(doc, result: dict):
    """证据冲突分析。"""
    conflicts = result.get("evidence_conflicts", [])
    if not conflicts:
        return
    doc.add_heading(f"证据冲突分析（{len(conflicts)}条）", level=1)
    for c in conflicts:
        p = doc.add_paragraph()
        _add_run(p, f"[{c['issue_id']}] ", bold=True, size=SZ_SECTION_HDR, color=CLR_RED)
        doc.add_paragraph()
        _styled(doc, c["conflict_description"], size=SZ_NORMAL, color=CLR_BODY)


def _render_llm_summary(doc, result: dict):
    """AI 综合分析。"""
    summary = result.get("summary")
    if not summary:
        return

    doc.add_heading("AI综���分析", level=1)
    doc.add_heading("整体态势评估", level=2)
    overall = summary.get("overall_assessment", "")
    _styled(doc, overall, size=SZ_NORMAL, color=CLR_BODY)

    # 原告最强论点
    p_args = summary.get("plaintiff_strongest_arguments", [])
    if p_args:
        _styled(doc, "原告最强论点", bold=True, size=SZ_SECTION_HDR, color=CLR_BLUE)
        for a in p_args:
            p = doc.add_paragraph()
            _add_run(p, f"[{a['issue_id']}] ", bold=True, size=SZ_NORMAL, color=CLR_BLUE)
            _add_run(p, a.get("position", ""), size=SZ_NORMAL, color=CLR_BODY)
            reasoning = a.get("reasoning", "")
            if reasoning:
                _styled(doc, f"▶ {reasoning}", size=SZ_NORMAL, color=CLR_GRAY)

    # 被告最强抗辩
    d_args = summary.get("defendant_strongest_defenses", [])
    if d_args:
        _styled(doc, "被告最强抗辩", bold=True, size=SZ_SECTION_HDR, color=CLR_RED)
        for d in d_args:
            p = doc.add_paragraph()
            _add_run(p, f"[{d['issue_id']}] ", bold=True, size=SZ_NORMAL, color=CLR_RED)
            _add_run(p, d.get("position", ""), size=SZ_NORMAL, color=CLR_BODY)
            reasoning = d.get("reasoning", "")
            if reasoning:
                _styled(doc, f"▶ {reasoning}", size=SZ_NORMAL, color=CLR_GRAY)

    # 未解决争点
    unresolved = summary.get("unresolved_issues", [])
    if unresolved:
        _styled(doc, "关键未解决争点", bold=True, size=SZ_SECTION_HDR, color=CLR_BLUE)
        for u in unresolved:
            iid = u.get("issue_id", "")
            title = u.get("issue_title", "")
            why = u.get("why_unresolved", "")
            _bullet(doc, f"{iid} {title}：{why}", size=SZ_NORMAL, color=CLR_BODY)


def _render_missing_evidence(doc, result: dict, party_zh: dict[str, str]):
    """证据缺失报告。"""
    missing = result.get("missing_evidence_report", [])
    if not missing:
        return
    doc.add_heading("证据��失报告", level=1)
    for m in missing:
        raw_party = m.get("missing_for_party_id", "")
        party_name = party_zh.get(raw_party, raw_party)
        p = doc.add_paragraph()
        _add_run(
            p,
            f"[{m['issue_id']}] {party_name}: {m['description']}",
            bold=True,
            size=SZ_BODY,
            color=CLR_ORANGE,
        )


def _render_issue_ranking(doc, exec_summary: dict):
    """争点影响排序。"""
    doc.add_heading("争点影响排序", level=1)
    top5 = exec_summary.get("top5_decisive_issues", [])
    _styled(doc, "前五大决定性争点:", bold=True, size=SZ_SECTION_HDR, color=CLR_BLUE)
    visible = _filter_uuids(top5) if isinstance(top5, list) else []
    if visible:
        for iid in visible:
            _bullet(doc, iid, size=SZ_NORMAL, color=CLR_BODY)
    else:
        _styled(doc, "（暂无排序数据）", size=SZ_NORMAL, color=CLR_GRAY)


_PARTY_ZH = {"plaintiff": "原告", "defendant": "被告", "neutral": "中性"}


def _render_decision_tree(doc, decision_tree: dict):
    """裁判路径树。"""
    paths = decision_tree.get("paths", [])
    if not paths:
        doc.add_heading("裁判路径树", level=1)
        _styled(
            doc,
            "（本次运行未生成裁判路径，可能需重新运行庭后分析流程）",
            size=SZ_NORMAL,
            color=CLR_GRAY,
        )
        return

    doc.add_heading(f"裁判路径树（{len(paths)}条路径）", level=1)

    # --- 概率比较摘要 ---
    most_likely = decision_tree.get("most_likely_path")
    plaintiff_best = decision_tree.get("plaintiff_best_path")
    defendant_best = decision_tree.get("defendant_best_path")
    if most_likely or plaintiff_best or defendant_best:
        _styled(doc, "路径概率比较", bold=True, size=SZ_SECTION_HDR, color=CLR_BLUE)
        summary_fields = []
        if most_likely:
            summary_fields.append(("最可能路径", most_likely))
        if plaintiff_best:
            summary_fields.append(("原告最优路径", plaintiff_best))
        if defendant_best:
            summary_fields.append(("被告最优路径", defendant_best))
        for label, val in summary_fields:
            p = doc.add_paragraph()
            _add_run(p, f"{label}：", bold=True, size=SZ_RISK, color=CLR_GRAY)
            _add_run(p, val, size=SZ_RISK, color=CLR_BODY)
        doc.add_paragraph()

    # Sort paths by probability descending for display
    sorted_paths = sorted(paths, key=lambda x: x.get("probability", 0.5), reverse=True)

    for rank, path in enumerate(sorted_paths, start=1):
        pid = path.get("path_id", "")
        prob = path.get("probability", 0.5)
        party = _PARTY_ZH.get(path.get("party_favored", "neutral"), "中性")

        # Label most-likely path
        label_suffix = f"  【概率 {prob:.0%} · 有利方：{party}】"
        if pid == most_likely:
            label_suffix += "  ★ 最可能"

        _styled(doc, f"路径 {pid}{label_suffix}", bold=True, size=SZ_SECTION_HDR, color=CLR_BLUE)

        fields = [
            ("触发条件", path.get("trigger_condition", "")),
            ("触发争点", ", ".join(path.get("trigger_issue_ids", []))),
            ("关键证据", ", ".join(path.get("key_evidence_ids", []))),
            ("可能结果", path.get("possible_outcome", "")),
        ]
        ci = path.get("confidence_interval")
        if ci:
            lo = ci.get("lower", 0)
            hi = ci.get("upper", 0)
            fields.append(("置信区间", f"{lo:.0%} ~ {hi:.0%}"))
        rationale = path.get("probability_rationale", "")
        if rationale:
            fields.append(("概率依据", rationale))
        notes = path.get("path_notes", "")
        if notes:
            fields.append(("备注", notes))

        for field_label, val in fields:
            if not val:
                continue
            p = doc.add_paragraph()
            _add_run(p, f"{field_label}：", bold=True, size=SZ_RISK, color=CLR_GRAY)
            _add_run(p, val, size=SZ_RISK, color=CLR_BODY)
        doc.add_paragraph()

    blocking = decision_tree.get("blocking_conditions", [])
    if blocking:
        _styled(doc, "阻断条件", bold=True, size=SZ_SECTION_HDR, color=CLR_RED)
        for bc in blocking:
            _bullet(
                doc, f"{bc['condition_id']}: {bc['description']}", size=SZ_NORMAL, color=CLR_BODY
            )


def _render_attack_chain(doc, attack_chain: dict, party_zh: dict[str, str]):
    """对方最优攻击链。"""
    attacks = attack_chain.get("top_attacks", [])
    if not attacks:
        doc.add_heading("对方最优攻击链", level=1)
        _styled(
            doc,
            "（本次运行未生成攻击链，可能需重新运���庭后分析流程）",
            size=SZ_NORMAL,
            color=CLR_GRAY,
        )
        return

    doc.add_heading("对��最优攻击链", level=1)

    order = attack_chain.get("recommended_order", [])
    raw_party = attack_chain.get("owner_party_id", "")
    p = doc.add_paragraph()
    _add_run(p, "攻击方：", bold=True, size=SZ_BODY, color=CLR_RED)
    _add_run(p, party_zh.get(raw_party, raw_party), size=SZ_BODY, color=CLR_BODY)
    if order:
        p2 = doc.add_paragraph()
        _add_run(p2, "推荐顺序：", bold=True, size=SZ_BODY, color=CLR_RED)
        _add_run(p2, " → ".join(order), size=SZ_BODY, color=CLR_BODY)
    doc.add_paragraph()

    for node in attacks:
        nid = node.get("attack_node_id", "")
        _styled(doc, nid, bold=True, size=SZ_SECTION_HDR, color=CLR_RED)

        attack_fields = [
            ("目标争点", node.get("target_issue_id", "")),
            ("攻击论点", node.get("attack_description", "")),
            ("成功条件", node.get("success_conditions", "")),
            ("支撑证据", ", ".join(node.get("supporting_evidence_ids", []))),
            ("反制动作", node.get("counter_measure", "")),
            ("对方补证策略", node.get("adversary_pivot_strategy", "")),
        ]
        for label, val in attack_fields:
            if not val:
                continue
            p = doc.add_paragraph()
            _add_run(p, f"{label}：", bold=True, size=SZ_RISK, color=CLR_ORANGE)
            _add_run(p, val, size=SZ_RISK, color=CLR_BODY)
        doc.add_paragraph()


def _render_action_recommendations(doc, exec_summary: dict):
    """行动建议。"""
    doc.add_heading("行动建议", level=1)

    stable = exec_summary.get("current_most_stable_claim", "")
    _styled(doc, "最稳诉请版本：", bold=True, size=SZ_SECTION_HDR, color=CLR_GREEN)
    _styled(doc, stable if stable else "（暂无稳定诉请版本）", size=SZ_NORMAL, color=CLR_BODY)

    actions = exec_summary.get("top3_immediate_actions", [])
    if actions and actions != "未启用":
        _styled(doc, "前三项立即行动：", bold=True, size=SZ_SECTION_HDR, color=CLR_ORANGE)
        if isinstance(actions, list):
            for a in _filter_uuids(actions):
                _bullet(doc, a, size=SZ_NORMAL, color=CLR_BODY)
        else:
            _styled(doc, str(actions), size=SZ_NORMAL, color=CLR_GRAY)

    gaps = exec_summary.get("critical_evidence_gaps", [])
    if gaps and gaps != "未启用":
        _styled(doc, "关键缺证：", bold=True, size=SZ_SECTION_HDR, color=CLR_ORANGE)
        if isinstance(gaps, list):
            for g in _filter_uuids(gaps):
                _bullet(doc, g, size=SZ_NORMAL, color=CLR_BODY)
        else:
            _styled(doc, str(gaps), size=SZ_NORMAL, color=CLR_GRAY)


def _render_executive_summary(doc, exec_summary: dict, amount_report: dict):
    """执行摘要。"""
    doc.add_heading("执行摘要", level=1)

    sections = [
        ("前五大决定性争点", exec_summary.get("top5_decisive_issues", [])),
        ("前三项对方最优攻击", exec_summary.get("top3_adversary_optimal_attacks", [])),
    ]
    for label, val in sections:
        p = doc.add_paragraph()
        _add_run(p, f"{label}：", bold=True, size=SZ_SECTION_HDR, color=CLR_BLUE)
        if isinstance(val, list):
            for item in val:
                _bullet(doc, item, size=SZ_NORMAL, color=CLR_BODY)
        else:
            _styled(doc, str(val), size=SZ_NORMAL, color=CLR_BODY)

    # 金额一致性校验
    check = amount_report.get("consistency_check_result", {})
    verdict_block = check.get("verdict_block_active", False)
    n_conflicts = len(check.get("unresolved_conflicts", []))
    p = doc.add_paragraph()
    _add_run(p, "金额一致性校验：", bold=True, size=SZ_SECTION_HDR, color=CLR_BLUE)
    _add_run(
        p,
        f"阻断裁判={'是' if verdict_block else '否'}，未解决冲突={n_conflicts}条",
        size=SZ_NORMAL,
        color=CLR_RED if verdict_block else CLR_GREEN,
    )


# ---------------------------------------------------------------------------
# Unit 11: 报告增强 — 新增章节渲染函数
# ---------------------------------------------------------------------------

_RISK_COLOR: dict[str, RGBColor] = {
    "favorable": CLR_GREEN,
    "neutral": CLR_ORANGE,
    "unfavorable": CLR_RED,
}


def _render_action_priority_list(doc, exec_summary: dict | None, action_rec: Any | None):
    """行动优先级清单 — 你现在最该做的 3 件事。"""
    items: list[str] = []

    if exec_summary and isinstance(exec_summary.get("top3_immediate_actions"), list):
        items = exec_summary["top3_immediate_actions"][:3]
    elif action_rec is not None:
        # Fallback: derive from action_rec fields
        ev_prios = getattr(action_rec, "evidence_supplement_priorities", None)
        if ev_prios:
            items.append(f"补强证据: {ev_prios[0]}")
        amendments = getattr(action_rec, "recommended_claim_amendments", None)
        if amendments:
            items.append(f"调整诉请: {amendments[0].amendment_description}")
        abandons = getattr(action_rec, "claims_to_abandon", None)
        if abandons:
            items.append(f"考虑放弃: {abandons[0].abandon_reason}")

    if not items:
        return

    doc.add_heading("你现在最该做的 3 件事", level=1)
    visible = _filter_uuids(items)
    for i, item in enumerate(visible[:3], 1):
        p = doc.add_paragraph()
        _add_run(p, f"{i}. ", bold=True, size=SZ_SECTION_HDR, color=CLR_ORANGE)
        _add_run(p, item, size=SZ_BODY, color=CLR_BODY)
    doc.add_paragraph()


def _render_risk_heatmap(doc, ranked_issues: Any | None):
    """风险热力图表格。"""
    rows = build_risk_heatmap(ranked_issues)
    if not rows:
        return

    doc.add_heading(f"风险热力图（{len(rows)}个争点）", level=1)

    table = doc.add_table(rows=1, cols=6)
    table.style = "Light Grid Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = table.rows[0].cells
    hdr[0].text = "争点"
    hdr[1].text = "结果影响"
    hdr[2].text = "攻击强度"
    hdr[3].text = "证据强度"
    hdr[4].text = "风险等级"
    hdr[5].text = "建议行动"

    for row in rows:
        cells = table.add_row().cells
        cells[0].text = f"{row.issue_id}: {row.title[:20]}"
        cells[1].text = row.outcome_impact or "-"
        cells[2].text = row.attack_strength or "-"
        cells[3].text = row.evidence_strength or "-"
        label = RISK_LABEL_ZH.get(row.risk_level, "")
        cells[4].text = label
        # Color the risk cell
        color = _RISK_COLOR.get(row.risk_level.value, CLR_BODY)
        for para in cells[4].paragraphs:
            for run in para.runs:
                run.font.color.rgb = color
                run.font.bold = True
        cells[5].text = row.recommended_action or "-"

    _set_table_font(table)


def _render_mediation_range(doc, amount_report: dict | None, decision_tree: dict | None):
    """调解区间评估。"""
    med = compute_mediation_range(amount_report, decision_tree)
    if med is None:
        return

    doc.add_heading("调解区间评估", level=1)

    rows_data = [
        ("诉请总额", f"{med.total_claimed:,} 元"),
        ("可核实金额", f"{med.total_verified:,} 元"),
        ("最低可能", f"{med.min_amount:,} 元"),
        ("最高可能", f"{med.max_amount:,} 元"),
        ("建议调解点", f"{med.suggested_amount:,} 元"),
    ]

    table = doc.add_table(rows=len(rows_data), cols=2)
    table.style = "Light Grid Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (label, val) in enumerate(rows_data):
        table.rows[i].cells[0].text = label
        table.rows[i].cells[1].text = val
    _set_table_font(table)

    # Highlight the suggested amount row
    last_row = table.rows[-1]
    for cell in last_row.cells:
        for para in cell.paragraphs:
            for run in para.runs:
                run.font.bold = True
                run.font.color.rgb = CLR_GREEN

    _styled(doc, f"计算依据: {med.rationale}", size=SZ_RISK, color=CLR_GRAY)


def _render_opponent_strategy_warning(doc, result: dict, attack_chain: dict | None):
    """对方策略预警 — 被告核心抗辩 + 攻击路径预警。"""
    summary = result.get("summary")
    defenses = summary.get("defendant_strongest_defenses", []) if summary else []
    attacks = (attack_chain or {}).get("top_attacks", [])

    if not defenses and not attacks:
        return

    doc.add_heading("对方策略预警", level=1)

    if defenses:
        _styled(doc, "被告核心抗辩及应对建议", bold=True, size=SZ_SECTION_HDR, color=CLR_RED)
        for d in defenses:
            p = doc.add_paragraph()
            _add_run(p, f"[{d['issue_id']}] ", bold=True, size=SZ_NORMAL, color=CLR_RED)
            _add_run(p, d.get("position", ""), size=SZ_NORMAL, color=CLR_BODY)
            reasoning = d.get("reasoning", "")
            if reasoning:
                _styled(doc, f"对方论据: {reasoning}", size=SZ_RISK, color=CLR_GRAY)
            # Match counter_measure from attack_chain
            if attacks:
                target_id = d.get("issue_id", "")
                for node in attacks:
                    if node.get("target_issue_id") == target_id:
                        cm = node.get("counter_measure", "")
                        if cm:
                            _styled(doc, f"应对建议: {cm}", size=SZ_RISK, color=CLR_GREEN)
                        break
        doc.add_paragraph()

    if attacks:
        _styled(doc, "对方最优攻击路径预警", bold=True, size=SZ_SECTION_HDR, color=CLR_RED)
        for node in attacks:
            nid = node.get("attack_node_id", "")
            target = node.get("target_issue_id", "")
            desc = node.get("attack_description", "")
            p = doc.add_paragraph()
            _add_run(p, f"{nid} → {target}: ", bold=True, size=SZ_RISK, color=CLR_RED)
            _add_run(p, desc, size=SZ_RISK, color=CLR_BODY)

            cond = node.get("success_conditions", "")
            if cond:
                _styled(doc, f"成功条件: {cond}", size=SZ_RISK, color=CLR_GRAY)
            cm = node.get("counter_measure", "")
            if cm:
                _styled(doc, f"应对: {cm}", size=SZ_RISK, color=CLR_GREEN)
            pivot = node.get("adversary_pivot_strategy", "")
            if pivot:
                _styled(doc, f"对方可能转向: {pivot}", size=SZ_RISK, color=CLR_ORANGE)


# ---------------------------------------------------------------------------
# 文书草稿章节 / Document draft section renderers
# ---------------------------------------------------------------------------

_DOC_TYPE_ZH: dict[str, str] = {
    "pleading": "起诉状草稿",
    "defense": "答辩状草稿",
    "cross_exam": "质证意见草稿",
}


def _render_document_drafts(doc, document_drafts: list) -> None:
    """文书草稿章节 — 将 DocumentDraft 列表渲染为 DOCX 结构化章节。
    Document draft sections — renders a list of DocumentDraft objects into DOCX.

    每份文书草稿为独立一级标题，骨架字段按语义分组渲染。
    Each document draft gets its own top-level heading, skeleton fields rendered by group.
    """
    doc.add_heading("文书草稿", level=1)
    _styled(
        doc,
        "以下文书草稿由 AI 生成，仅供律师参考和编辑，不构成正式法律文件。",
        size=SZ_NORMAL,
        color=CLR_ORANGE,
    )
    doc.add_paragraph()

    for draft in document_drafts:
        doc_type = getattr(draft, "doc_type", "")
        case_type = getattr(draft, "case_type", "")
        heading_text = _DOC_TYPE_ZH.get(doc_type, doc_type)
        doc.add_heading(f"{heading_text}（{case_type}）", level=2)

        content = getattr(draft, "content", None)
        if content is None:
            _styled(doc, "（无内容）", size=SZ_NORMAL, color=CLR_GRAY)
            continue

        # 文档头
        header = getattr(content, "header", "")
        if header:
            _styled(doc, header, bold=True, size=SZ_SECTION_HDR, color=CLR_TITLE_DARK)

        # 按文书类型渲染各骨架字段
        if doc_type == "pleading":
            _render_list_section(doc, "事实陈述", getattr(content, "fact_narrative_items", []))
            _render_list_section(doc, "法律依据", getattr(content, "legal_claim_items", []))
            _render_list_section(doc, "诉讼请求", getattr(content, "prayer_for_relief_items", []))
            attack_basis = getattr(content, "attack_chain_basis", "unavailable")
            if attack_basis and attack_basis != "unavailable":
                _styled(doc, f"攻击链策略依据：{attack_basis}", size=SZ_NORMAL, color=CLR_BLUE)

        elif doc_type == "defense":
            _render_list_section(doc, "逐项否认", getattr(content, "denial_items", []))
            _render_list_section(doc, "实质性抗辩", getattr(content, "defense_claim_items", []))
            _render_list_section(doc, "反请求", getattr(content, "counter_prayer_items", []))

        elif doc_type == "cross_exam":
            items = getattr(content, "items", [])
            if items:
                doc.add_heading("逐证据质证意见", level=3)
                for item in items:
                    ev_id = getattr(item, "evidence_id", "")
                    opinion = getattr(item, "opinion_text", "")
                    p = doc.add_paragraph()
                    _add_run(p, f"[{ev_id}] ", bold=True, size=SZ_NORMAL, color=CLR_BLUE)
                    _add_run(p, opinion, size=SZ_NORMAL, color=CLR_BODY)
            else:
                _styled(doc, "（无证据需要质证）", size=SZ_NORMAL, color=CLR_GRAY)

        # 证据引用
        ev_cited = getattr(draft, "evidence_ids_cited", [])
        if ev_cited:
            p = doc.add_paragraph()
            _add_run(p, "引用证据：", bold=True, size=SZ_NORMAL, color=CLR_GRAY)
            _add_run(p, ", ".join(ev_cited), size=SZ_NORMAL, color=CLR_GRAY)

        doc.add_paragraph()


def _render_list_section(doc, label: str, items: list[str]) -> None:
    """渲染一个有序列表章节（标签 + 条目列表）。"""
    if not items:
        return
    doc.add_heading(label, level=3)
    for item in items:
        _bullet(doc, item, size=SZ_NORMAL, color=CLR_BODY)
