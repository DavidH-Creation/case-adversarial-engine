"""
证据作战矩阵 — 7问分析模块。
Evidence Battle Matrix — 7-question analysis per evidence piece.

每条证据评估7个核心问题：
1. 证明目标  (target issue labels)
2. 提交方    (owner party)
3. 可采性    (admissibility status)
4. 对方质疑  (opposition challenges)
5. 补强证据数 (corroboration count)
6. 稳定性    (traffic light: green/yellow/red)
7. 路径依赖数 (path dependency count)

纯数据变换，不调用 LLM。
Pure data transformation, no LLM calls.
"""

from __future__ import annotations

from typing import Any

from .schemas import EvidenceBattleMatrix, EvidenceBattleRow

# ---------------------------------------------------------------------------
# 稳定性交通灯 / Stability traffic light
# ---------------------------------------------------------------------------

_RED_ADMISSIBILITY = frozenset({"excluded"})
_YELLOW_ADMISSIBILITY = frozenset({"uncertain", "weak"})
_YELLOW_EVIDENCE_TYPES = frozenset({"witness_statement", "audio_visual"})
_RED_AUTH_RISK = frozenset({"high"})


def _evidence_stability_light(ev: Any) -> str:
    """Return '🟢 绿' / '🟡 黄' / '🔴 红' based on evidence stability signals."""
    admissibility_status = _safe_value(getattr(ev, "admissibility_status", None))
    authenticity_risk = _safe_value(getattr(ev, "authenticity_risk", None))
    is_attacked_by: list = getattr(ev, "is_attacked_by", []) or []
    evidence_type = _safe_value(getattr(ev, "evidence_type", None))

    # Red: explicitly excluded, high authenticity risk, or actively attacked
    if admissibility_status in _RED_ADMISSIBILITY:
        return "🔴 红"
    if authenticity_risk in _RED_AUTH_RISK:
        return "🔴 红"
    if is_attacked_by:
        return "🔴 红"

    # Yellow: screenshot-like types or uncertain/weak admissibility
    if evidence_type in _YELLOW_EVIDENCE_TYPES:
        return "🟡 黄"
    if admissibility_status in _YELLOW_ADMISSIBILITY:
        return "🟡 黄"

    # Green: third-party verifiable (documentary, electronic, physical, etc.)
    return "🟢 绿"


def _safe_value(val: Any) -> str:
    """Extract .value from enum or return str; default ''."""
    if val is None:
        return ""
    return val.value if hasattr(val, "value") else str(val)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_evidence_battle_matrix(
    evidence_index: Any,
    issue_tree: Any = None,
    decision_path_tree: Any = None,
) -> EvidenceBattleMatrix | None:
    """Build a 7-question evidence battle matrix.

    Args:
        evidence_index:   EvidenceIndex with .evidence list
        issue_tree:       Optional IssueTree to resolve issue titles
        decision_path_tree: Optional DecisionPathTree to count path dependencies

    Returns:
        EvidenceBattleMatrix, or None if evidence_index is None/empty.
    """
    if evidence_index is None:
        return None

    evidences = getattr(evidence_index, "evidence", None)
    if not evidences:
        return None

    # Build issue title lookup: issue_id → title
    issue_titles: dict[str, str] = {}
    if issue_tree is not None:
        for iss in getattr(issue_tree, "issues", []):
            iid = getattr(iss, "issue_id", None)
            title = getattr(iss, "title", iid) or iid
            if iid:
                issue_titles[iid] = title

    # Build path dependency lookup: evidence_id → count of paths citing it
    path_dep: dict[str, int] = {}
    if decision_path_tree is not None:
        for path in getattr(decision_path_tree, "paths", []):
            for ev_id in getattr(path, "key_evidence_ids", []):
                path_dep[ev_id] = path_dep.get(ev_id, 0) + 1

    # Build corroboration lookup:
    # For each target issue, collect all evidence IDs → corroboration = how many
    # other evidences share at least one common target issue.
    issue_to_ev_ids: dict[str, list[str]] = {}
    for ev in evidences:
        ev_id = getattr(ev, "evidence_id", None)
        if not ev_id:
            continue
        for iid in getattr(ev, "target_issue_ids", []):
            issue_to_ev_ids.setdefault(iid, []).append(ev_id)

    def _corroboration_count(ev: Any) -> int:
        """Count other evidences sharing at least one target issue."""
        ev_id = getattr(ev, "evidence_id", "")
        seen: set[str] = set()
        for iid in getattr(ev, "target_issue_ids", []):
            for other_id in issue_to_ev_ids.get(iid, []):
                if other_id != ev_id:
                    seen.add(other_id)
        return len(seen)

    rows: list[EvidenceBattleRow] = []
    green_count = yellow_count = red_count = 0

    for ev in evidences:
        ev_id = getattr(ev, "evidence_id", "") or ""
        ev_title = getattr(ev, "title", ev_id) or ev_id

        # Column 1: target issue labels
        target_labels = [
            issue_titles.get(iid, iid)
            for iid in getattr(ev, "target_issue_ids", [])
        ]

        # Column 2: owner party
        owner = getattr(ev, "owner_party_id", "") or ""

        # Column 3: admissibility status
        admissibility = _safe_value(getattr(ev, "admissibility_status", None))

        # Column 4: opposition challenges
        challenges: list[str] = list(getattr(ev, "admissibility_challenges", []) or [])

        # Column 5: corroboration
        corroboration = _corroboration_count(ev)

        # Column 6: stability traffic light
        light = _evidence_stability_light(ev)

        # Column 7: path dependency
        path_dep_count = path_dep.get(ev_id, 0)

        rows.append(
            EvidenceBattleRow(
                evidence_id=ev_id,
                evidence_title=ev_title,
                target_issue_labels=target_labels,
                owner=owner,
                admissibility=admissibility,
                opposition_challenges=challenges,
                corroboration_count=corroboration,
                stability_light=light,
                path_dependency_count=path_dep_count,
            )
        )

        if "🟢" in light:
            green_count += 1
        elif "🟡" in light:
            yellow_count += 1
        else:
            red_count += 1

    return EvidenceBattleMatrix(
        rows=rows,
        total_evidence=len(rows),
        green_count=green_count,
        yellow_count=yellow_count,
        red_count=red_count,
    )


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def render_evidence_battle_matrix_markdown(matrix: EvidenceBattleMatrix) -> str:
    """Render the evidence battle matrix as a 7-column Markdown table.

    Columns:
        证据 | 证明目标 | 提交方 | 可采性 | 对方质疑 | 补强 | 稳定性 | 路径依赖
    """
    lines = [
        "## 证据作战矩阵 / Evidence Battle Matrix",
        "",
        f"共 {matrix.total_evidence} 条证据  "
        f"🟢 {matrix.green_count}  🟡 {matrix.yellow_count}  🔴 {matrix.red_count}",
        "",
        "| 证据 | 证明目标 | 提交方 | 可采性 | 对方质疑 | 补强 | 稳定性 | 路径依赖 |",
        "|------|---------|--------|--------|---------|------|--------|---------|",
    ]

    for row in matrix.rows:
        issues_cell = "、".join(row.target_issue_labels) if row.target_issue_labels else "-"
        challenges_cell = "；".join(row.opposition_challenges) if row.opposition_challenges else "无"
        admissibility_cell = row.admissibility or "-"
        corroboration_cell = str(row.corroboration_count) if row.corroboration_count else "0"
        path_cell = str(row.path_dependency_count) if row.path_dependency_count else "0"
        owner_cell = row.owner or "-"

        lines.append(
            f"| {row.evidence_title} "
            f"| {issues_cell} "
            f"| {owner_cell} "
            f"| {admissibility_cell} "
            f"| {challenges_cell} "
            f"| {corroboration_cell} "
            f"| {row.stability_light} "
            f"| {path_cell} |"
        )

    return "\n".join(lines)
