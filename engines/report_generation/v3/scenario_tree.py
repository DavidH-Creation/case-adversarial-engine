"""
条件场景树构建器 / Conditional Scenario Tree Builder.

将现有的 DecisionPathTree（概率式）转换为条件触发式场景树（二元分支）。
不使用百分比概率，改用 if-then 条件判断。

每个节点是一个条件问题，分支为「是/否」两个方向，
最终叶节点给出可能的裁判结果。
"""

from __future__ import annotations

from typing import Optional

from engines.report_generation.v3.models import (
    ConditionalNode,
    ConditionalScenarioTree,
)


def build_scenario_tree_from_decision_paths(
    decision_tree,
    issue_tree,
    evidence_index,
) -> Optional[ConditionalScenarioTree]:
    """Convert a DecisionPathTree into a ConditionalScenarioTree.

    The conversion strategy:
    1. Each blocking_condition becomes a root-level condition node
    2. Each DecisionPath becomes a branch outcome, keyed by its trigger_condition
    3. Paths are chained via admissibility_gate → evidence condition nodes

    Args:
        decision_tree: DecisionPathTree from pipeline (may be None)
        issue_tree: IssueTree for issue context
        evidence_index: EvidenceIndex for evidence references

    Returns:
        ConditionalScenarioTree or None if no decision_tree provided
    """
    if decision_tree is None:
        return None

    nodes: list[ConditionalNode] = []
    node_counter = 0

    def _next_id() -> str:
        nonlocal node_counter
        node_counter += 1
        return f"COND-{node_counter:03d}"

    # Build condition nodes from blocking conditions first
    blocking_nodes: list[str] = []
    for bc in (decision_tree.blocking_conditions or []):
        node_id = _next_id()
        nodes.append(ConditionalNode(
            node_id=node_id,
            condition=bc.description,
            related_evidence_ids=getattr(bc, "related_evidence_ids", []),
        ))
        blocking_nodes.append(node_id)

    # Build leaf nodes from decision paths
    path_outcomes: list[tuple[str, str, str]] = []  # (node_id, trigger, outcome)
    for path in (decision_tree.paths or []):
        node_id = _next_id()
        nodes.append(ConditionalNode(
            node_id=node_id,
            condition=path.trigger_condition,
            yes_outcome=path.possible_outcome,
            no_outcome=None,  # will be linked to fallback or next path
            related_evidence_ids=path.key_evidence_ids or [],
        ))
        path_outcomes.append((node_id, path.trigger_condition, path.possible_outcome))

    # Link paths: chain them so that "no" on one path leads to the next path's condition
    for i in range(len(path_outcomes) - 1):
        current_id = path_outcomes[i][0]
        next_id = path_outcomes[i + 1][0]
        # Find the node and set its no_child_id
        for node in nodes:
            if node.node_id == current_id:
                node.no_child_id = next_id
                break

    # Last path's "no" gets a default unfavorable outcome
    if path_outcomes:
        last_id = path_outcomes[-1][0]
        for node in nodes:
            if node.node_id == last_id and node.no_outcome is None:
                node.no_outcome = "条件均不成立，结果不确定"
                break

    # Link blocking conditions to first path
    if blocking_nodes and path_outcomes:
        for i, bc_id in enumerate(blocking_nodes):
            for node in nodes:
                if node.node_id == bc_id:
                    # If blocking condition is met → uncertain; if not → proceed to paths
                    node.yes_outcome = "存在阻断条件，无法形成稳定判断"
                    if i + 1 < len(blocking_nodes):
                        node.no_child_id = blocking_nodes[i + 1]
                    else:
                        node.no_child_id = path_outcomes[0][0]
                    break

    # Determine root
    root_id = blocking_nodes[0] if blocking_nodes else (
        path_outcomes[0][0] if path_outcomes else ""
    )

    if not root_id:
        return None

    return ConditionalScenarioTree(
        tree_id=f"cst-{decision_tree.tree_id}" if hasattr(decision_tree, "tree_id") else "cst-001",
        case_id=decision_tree.case_id,
        root_node_id=root_id,
        nodes=nodes,
    )


def render_scenario_tree_text(tree: ConditionalScenarioTree) -> str:
    """Render a ConditionalScenarioTree as indented text for the cover summary.

    Output format (if-then, no percentages):
      录音是否被采信？
      ├── 是 → 借款合意是否成立？
      │   ├── 是 → 原告胜诉
      │   └── 否 → 驳回
      └── 否 → 其他条件...
    """
    if not tree or not tree.nodes:
        return ""

    node_map = {n.node_id: n for n in tree.nodes}

    def _render(node_id: str, indent: int = 0, is_last: bool = True) -> list[str]:
        node = node_map.get(node_id)
        if not node:
            return []

        prefix = ""
        if indent > 0:
            prefix = "│   " * (indent - 1) + ("└── " if is_last else "├── ")

        lines = [f"{prefix}{node.condition}"]

        # Yes branch
        yes_prefix = "│   " * indent + "├── "
        if node.yes_child_id and node.yes_child_id in node_map:
            lines.append(f"{yes_prefix}是 →")
            lines.extend(_render(node.yes_child_id, indent + 1, is_last=False))
        elif node.yes_outcome:
            lines.append(f"{yes_prefix}是 → {node.yes_outcome}")

        # No branch
        no_prefix = "│   " * indent + "└── "
        if node.no_child_id and node.no_child_id in node_map:
            lines.append(f"{no_prefix}否 →")
            lines.extend(_render(node.no_child_id, indent + 1, is_last=True))
        elif node.no_outcome:
            lines.append(f"{no_prefix}否 → {node.no_outcome}")

        return lines

    return "\n".join(_render(tree.root_node_id))


def render_scenario_tree_summary(tree: ConditionalScenarioTree) -> str:
    """Render a short if-then summary for Layer 1 cover."""
    if not tree or not tree.nodes:
        return "暂无条件场景分析"

    node_map = {n.node_id: n for n in tree.nodes}
    summaries: list[str] = []

    # Walk from root, collect first-level conditions
    root = node_map.get(tree.root_node_id)
    if not root:
        return "暂无条件场景分析"

    def _collect_leaf_outcomes(node_id: str, depth: int = 0) -> list[str]:
        if depth > 5:
            return []
        node = node_map.get(node_id)
        if not node:
            return []
        outcomes: list[str] = []
        if node.yes_outcome:
            outcomes.append(f"若{node.condition}成立 → {node.yes_outcome}")
        elif node.yes_child_id:
            outcomes.extend(_collect_leaf_outcomes(node.yes_child_id, depth + 1))
        if node.no_outcome:
            outcomes.append(f"若{node.condition}不成立 → {node.no_outcome}")
        elif node.no_child_id:
            outcomes.extend(_collect_leaf_outcomes(node.no_child_id, depth + 1))
        return outcomes

    summaries = _collect_leaf_outcomes(tree.root_node_id)
    return "；".join(summaries[:5]) if summaries else "暂无条件场景分析"
