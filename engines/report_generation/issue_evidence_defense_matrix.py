"""
争点-证据-抗辩矩阵聚合模块。
Issue-Evidence-Defense Matrix aggregation module.

从 IssueTree × EvidenceIndex × DefenseChain 三个现有产物构建三维关联矩阵。
Builds a three-dimensional association matrix from IssueTree, EvidenceIndex, and DefenseChain.

纯数据变换，不调用 LLM。
Pure data transformation, no LLM calls.

Usage:
    from engines.report_generation.issue_evidence_defense_matrix import (
        build_issue_evidence_defense_matrix,
        render_matrix_markdown,
    )
    matrix = build_issue_evidence_defense_matrix(issue_tree, evidence_index, defense_chain)
    md = render_matrix_markdown(matrix)
"""

from __future__ import annotations

from typing import Any

from .schemas import IssueEvidenceDefenseMatrix, MatrixRow

# Impact sort order: lower number = higher priority in descending sort
_IMPACT_ORDER: dict[str, int] = {"high": 0, "medium": 1, "low": 2}


def build_issue_evidence_defense_matrix(
    issue_tree: Any,
    evidence_index: Any,
    defense_chain: Any = None,
) -> IssueEvidenceDefenseMatrix | None:
    """从 IssueTree × EvidenceIndex × DefenseChain 构建三维关联矩阵。

    Build a three-dimensional association matrix from IssueTree, EvidenceIndex,
    and (optionally) DefenseChain.

    Args:
        issue_tree: IssueTree object with .issues list
        evidence_index: EvidenceIndex object with .evidence list; each Evidence has
                        .evidence_id and .target_issue_ids
        defense_chain: PlaintiffDefenseChain object (optional) with .defense_points;
                       each DefensePoint has .point_id and .issue_id

    Returns:
        IssueEvidenceDefenseMatrix with rows sorted by issue_impact descending,
        or None if issue_tree is None or has no issues.
    """
    if issue_tree is None:
        return None

    issues = getattr(issue_tree, "issues", None)
    if not issues:
        return None

    # Build evidence lookup: issue_id → [evidence_id, ...]
    # Scan EvidenceIndex.evidence for each evidence's target_issue_ids
    evidence_by_issue: dict[str, list[str]] = {}
    if evidence_index is not None:
        for ev in getattr(evidence_index, "evidence", []):
            ev_id = getattr(ev, "evidence_id", None)
            if not ev_id:
                continue
            for iid in getattr(ev, "target_issue_ids", []):
                evidence_by_issue.setdefault(iid, []).append(ev_id)

    # Build defense lookup: issue_id → [point_id, ...]
    # Scan DefenseChain.defense_points
    defense_by_issue: dict[str, list[str]] = {}
    if defense_chain is not None:
        for dp in getattr(defense_chain, "defense_points", []):
            point_id = getattr(dp, "point_id", None)
            issue_id = getattr(dp, "issue_id", None)
            if point_id and issue_id:
                defense_by_issue.setdefault(issue_id, []).append(point_id)

    rows: list[MatrixRow] = []
    for iss in issues:
        issue_id = iss.issue_id
        issue_label = getattr(iss, "title", issue_id)
        impact = _safe_enum_value(getattr(iss, "outcome_impact", None))

        # Prefer EvidenceIndex cross-reference; fall back to Issue.evidence_ids
        ev_ids = evidence_by_issue.get(issue_id, [])
        if not ev_ids:
            ev_ids = list(getattr(iss, "evidence_ids", []))

        defense_ids = defense_by_issue.get(issue_id, [])
        has_unrebutted = len(ev_ids) > 0 and len(defense_ids) == 0

        rows.append(
            MatrixRow(
                issue_id=issue_id,
                issue_label=issue_label,
                issue_impact=impact,
                evidence_ids=ev_ids,
                defense_ids=defense_ids,
                evidence_count=len(ev_ids),
                has_unrebutted_evidence=has_unrebutted,
            )
        )

    # Sort by impact descending: high(0) > medium(1) > low(2) > unknown(99)
    rows.sort(key=lambda r: _IMPACT_ORDER.get(r.issue_impact, 99))

    return IssueEvidenceDefenseMatrix(
        rows=rows,
        total_issues=len(rows),
        issues_with_evidence=sum(1 for r in rows if r.evidence_count > 0),
    )


def render_matrix_markdown(matrix: IssueEvidenceDefenseMatrix) -> str:
    """渲染矩阵为 Markdown 表格。
    Render matrix as a Markdown table.

    Returns:
        Markdown string with header and table rows.
    """
    lines = [
        "## 争点-证据-抗辩矩阵 / Issue-Evidence-Defense Matrix",
        "",
        "| 争点 | 影响度 | 关联证据数 | 抗辩点数 | 未反驳 |",
        "|------|--------|-----------|---------|--------|",
    ]
    for row in matrix.rows:
        impact_display = row.issue_impact or "-"
        unrebutted = "是" if row.has_unrebutted_evidence else "否"
        lines.append(
            f"| {row.issue_label} | {impact_display} | {row.evidence_count} "
            f"| {len(row.defense_ids)} | {unrebutted} |"
        )
    return "\n".join(lines)


def _safe_enum_value(val: Any) -> str:
    """Extract .value from enum or return str; default to empty string."""
    if val is None:
        return ""
    return val.value if hasattr(val, "value") else str(val)
