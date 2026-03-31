"""
simulate_exclusion — 证据排除传播分析（规则层，不调用 LLM）。
Rules-based utility: propagates evidence exclusion through the analysis chain.

使用方法 / Usage:
    from engines.case_structuring.admissibility_evaluator import simulate_exclusion

    report = simulate_exclusion(
        evidence_id="ev-003",
        evidence_index=evidence_index,
        issue_tree=issue_tree,
        decision_path_tree=decision_path_tree,
        attack_chains=[plaintiff_chain, defendant_chain],
    )

合约保证 / Contract guarantees:
- 纯规则层，不修改任何输入对象（只读）
- 不调用 LLM，同步返回
- evidence_id 不存在时返回 severity=negligible 的空报告
- 各影响层独立计算，互不干扰
"""

from __future__ import annotations

from typing import Optional

from engines.shared.models import (
    DecisionPathTree,
    EvidenceIndex,
    IssueTree,
    OptimalAttackChain,
)

from .schemas import (
    ChainImpact,
    ExclusionSeverity,
    ImpactReport,
    IssueImpact,
    PathImpact,
)

# 严重程度优先级（数字越大越严重）
_SEVERITY_RANK: dict[ExclusionSeverity, int] = {
    "negligible": 0,
    "manageable": 1,
    "significant": 2,
    "case_breaking": 3,
}


def simulate_exclusion(
    evidence_id: str,
    evidence_index: EvidenceIndex,
    issue_tree: Optional[IssueTree] = None,
    decision_path_tree: Optional[DecisionPathTree] = None,
    attack_chains: Optional[list[OptimalAttackChain]] = None,
) -> ImpactReport:
    """模拟将指定证据排除后对全链路的影响。

    Args:
        evidence_id:        被排除的证据 ID
        evidence_index:     当前证据索引（用于查找证据元信息）
        issue_tree:         争点树（可选；若提供则分析争点层影响）
        decision_path_tree: 裁判路径树（可选；若提供则分析路径层影响）
        attack_chains:      攻击链列表（可选；若提供则分析攻击链层影响）

    Returns:
        ImpactReport，包含各层影响评估和整体严重程度
    """
    case_id = evidence_index.case_id

    # 验证目标证据存在
    target_ev = next(
        (ev for ev in evidence_index.evidence if ev.evidence_id == evidence_id),
        None,
    )
    if target_ev is None:
        return ImpactReport(
            excluded_evidence_id=evidence_id,
            case_id=case_id,
            summary=f"证据 {evidence_id} 在证据索引中未找到，无影响。",
        )

    # 计算各层影响
    issue_impacts = _analyze_issue_impacts(evidence_id, evidence_index, issue_tree)
    path_impacts = _analyze_path_impacts(evidence_id, decision_path_tree)
    chain_impacts = _analyze_chain_impacts(evidence_id, attack_chains)

    # 汇总整体严重程度
    overall_severity = _compute_overall_severity(issue_impacts, path_impacts, chain_impacts)

    summary = _build_summary(
        evidence_id, target_ev.title, issue_impacts, path_impacts, chain_impacts, overall_severity
    )

    return ImpactReport(
        excluded_evidence_id=evidence_id,
        case_id=case_id,
        affected_issues=issue_impacts,
        affected_paths=path_impacts,
        affected_chains=chain_impacts,
        overall_severity=overall_severity,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# 内部分析函数
# ---------------------------------------------------------------------------


def _analyze_issue_impacts(
    evidence_id: str,
    evidence_index: EvidenceIndex,
    issue_tree: Optional[IssueTree],
) -> list[IssueImpact]:
    """分析争点层影响：哪些争点依赖该证据，排除后剩余证据情况。"""
    if issue_tree is None:
        return []

    impacts: list[IssueImpact] = []

    # 构建争点的支撑证据集合（从 evidence_index 的 target_issue_ids 反查）
    issue_to_evidence: dict[str, list[str]] = {}
    for ev in evidence_index.evidence:
        for iid in ev.target_issue_ids:
            issue_to_evidence.setdefault(iid, []).append(ev.evidence_id)

    for issue in issue_tree.issues:
        # 合并来源：issue.evidence_ids + 反查索引
        all_ev_ids = set(issue.evidence_ids) | set(issue_to_evidence.get(issue.issue_id, []))

        if evidence_id not in all_ev_ids:
            continue  # 该争点不依赖此证据

        remaining = sorted(all_ev_ids - {evidence_id})
        loses_primary = len(all_ev_ids) == 1 or _is_primary_evidence(
            evidence_id, issue, evidence_index
        )

        severity: ExclusionSeverity
        if loses_primary and not remaining:
            severity = "case_breaking"
        elif loses_primary:
            severity = "significant"
        elif len(remaining) <= 1:
            severity = "manageable"
        else:
            severity = "negligible"

        impacts.append(
            IssueImpact(
                issue_id=issue.issue_id,
                issue_title=issue.title,
                loses_primary_evidence=loses_primary,
                remaining_evidence_ids=remaining,
                impact_severity=severity,
            )
        )

    return impacts


def _is_primary_evidence(
    evidence_id: str,
    issue,  # Issue
    evidence_index: EvidenceIndex,
) -> bool:
    """判断 evidence_id 是否为该争点的主要证据（admissibility_score 最高者）。"""
    all_ev_ids = set(issue.evidence_ids)
    for ev in evidence_index.evidence:
        if issue.issue_id in ev.target_issue_ids:
            all_ev_ids.add(ev.evidence_id)

    if len(all_ev_ids) <= 1:
        return True  # 唯一证据即为主要证据

    # 找到当前证据的 admissibility_score
    ev_scores: dict[str, float] = {}
    for ev in evidence_index.evidence:
        if ev.evidence_id in all_ev_ids:
            ev_scores[ev.evidence_id] = ev.admissibility_score

    target_score = ev_scores.get(evidence_id, 1.0)
    max_score = max(ev_scores.values()) if ev_scores else 0.0

    return target_score >= max_score


def _analyze_path_impacts(
    evidence_id: str,
    decision_path_tree: Optional[DecisionPathTree],
) -> list[PathImpact]:
    """分析路径层影响：admissibility_gate 中包含该证据的路径变为不可行。"""
    if decision_path_tree is None:
        return []

    impacts: list[PathImpact] = []

    for path in decision_path_tree.paths:
        in_gate = evidence_id in path.admissibility_gate
        in_key_evidence = evidence_id in path.key_evidence_ids

        if not (in_gate or in_key_evidence):
            continue

        becomes_nonviable = in_gate  # gate 中的证据排除必然使路径不可行

        if becomes_nonviable:
            desc = f"路径 {path.path_id} 的前提条件证据 {evidence_id} 被排除，路径不可行。" + (
                f" 降级路径: {path.fallback_path_id}" if path.fallback_path_id else ""
            )
        else:
            desc = f"路径 {path.path_id} 的关键证据 {evidence_id} 被排除，路径仍可行但证明力减弱。"

        impacts.append(
            PathImpact(
                path_id=path.path_id,
                becomes_nonviable=becomes_nonviable,
                impact_description=desc,
            )
        )

    return impacts


def _analyze_chain_impacts(
    evidence_id: str,
    attack_chains: Optional[list[OptimalAttackChain]],
) -> list[ChainImpact]:
    """分析攻击链层影响：哪些攻击节点依赖该证据。"""
    if not attack_chains:
        return []

    impacts: list[ChainImpact] = []

    for chain in attack_chains:
        broken_nodes: list[str] = []
        for node in chain.top_attacks:
            if evidence_id in node.supporting_evidence_ids:
                broken_nodes.append(node.attack_node_id)

        if not broken_nodes:
            continue

        desc = (
            f"攻击链 {chain.chain_id}（{chain.owner_party_id}）中"
            f" {len(broken_nodes)} 个攻击节点失去证据支撑: {', '.join(broken_nodes)}。"
        )

        impacts.append(
            ChainImpact(
                chain_id=chain.chain_id,
                owner_party_id=chain.owner_party_id,
                broken_attack_node_ids=broken_nodes,
                impact_description=desc,
            )
        )

    return impacts


def _compute_overall_severity(
    issue_impacts: list[IssueImpact],
    path_impacts: list[PathImpact],
    chain_impacts: list[ChainImpact],
) -> ExclusionSeverity:
    """汇总各层影响，计算整体严重程度。"""
    max_rank = 0

    for ii in issue_impacts:
        max_rank = max(max_rank, _SEVERITY_RANK[ii.impact_severity])

    for pi in path_impacts:
        if pi.becomes_nonviable:
            max_rank = max(max_rank, _SEVERITY_RANK["significant"])

    if chain_impacts:
        # 任意攻击链受影响 → 至少 manageable
        max_rank = max(max_rank, _SEVERITY_RANK["manageable"])

    # 多条路径不可行 → 升级为 case_breaking
    nonviable_count = sum(1 for pi in path_impacts if pi.becomes_nonviable)
    if nonviable_count >= 2:
        max_rank = max(max_rank, _SEVERITY_RANK["case_breaking"])

    rank_to_severity: dict[int, ExclusionSeverity] = {v: k for k, v in _SEVERITY_RANK.items()}
    return rank_to_severity[max_rank]


def _build_summary(
    evidence_id: str,
    evidence_title: str,
    issue_impacts: list[IssueImpact],
    path_impacts: list[PathImpact],
    chain_impacts: list[ChainImpact],
    overall_severity: ExclusionSeverity,
) -> str:
    """构建人类可读的影响摘要。"""
    parts: list[str] = [
        f"排除证据「{evidence_title}」({evidence_id}) 的影响分析（整体严重程度: {overall_severity}）：",
    ]

    if issue_impacts:
        loses_primary = [ii for ii in issue_impacts if ii.loses_primary_evidence]
        parts.append(
            f"争点层：{len(issue_impacts)} 个争点受影响"
            + (f"，其中 {len(loses_primary)} 个失去主要证据支撑" if loses_primary else "")
            + "。"
        )

    if path_impacts:
        nonviable = [pi for pi in path_impacts if pi.becomes_nonviable]
        parts.append(
            f"路径层：{len(path_impacts)} 条路径受影响"
            + (f"，其中 {len(nonviable)} 条不可行" if nonviable else "")
            + "。"
        )

    if chain_impacts:
        total_broken = sum(len(ci.broken_attack_node_ids) for ci in chain_impacts)
        parts.append(
            f"攻击链层：{len(chain_impacts)} 条攻击链受影响，共 {total_broken} 个攻击节点失去支撑。"
        )

    if not (issue_impacts or path_impacts or chain_impacts):
        parts.append("未发现对争点、路径或攻击链的影响。")

    return " ".join(parts)
