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

    # Build condition nodes from blocking conditions (sequential gates)
    blocking_nodes: list[str] = []
    for bc in (decision_tree.blocking_conditions or []):
        node_id = _next_id()
        nodes.append(ConditionalNode(
            node_id=node_id,
            condition=bc.description,
            related_evidence_ids=getattr(bc, "related_evidence_ids", []),
        ))
        blocking_nodes.append(node_id)

    # Build a proper binary tree from decision paths instead of a flat linked list.
    # Uses recursive binary partitioning: the middle path becomes the root,
    # left paths form the yes-subtree, right paths form the no-subtree.
    paths = list(decision_tree.paths or [])

    def _build_binary_subtree(path_list: list) -> Optional[str]:
        """Recursively build a balanced binary subtree from paths."""
        if not path_list:
            return None

        if len(path_list) == 1:
            p = path_list[0]
            node_id = _next_id()
            nodes.append(ConditionalNode(
                node_id=node_id,
                condition=p.trigger_condition,
                yes_outcome=p.possible_outcome,
                no_outcome="条件不成立，结果不确定",
                related_evidence_ids=p.key_evidence_ids or [],
            ))
            return node_id

        mid = len(path_list) // 2
        pivot = path_list[mid]
        left_paths = path_list[:mid]
        right_paths = path_list[mid + 1:]

        node_id = _next_id()

        # Build subtrees first so they get their node IDs
        yes_child = _build_binary_subtree(left_paths)
        no_child = _build_binary_subtree(right_paths)

        nodes.append(ConditionalNode(
            node_id=node_id,
            condition=pivot.trigger_condition,
            yes_outcome=pivot.possible_outcome if yes_child is None else None,
            yes_child_id=yes_child,
            no_child_id=no_child,
            no_outcome=None if no_child else "条件均不成立，结果不确定",
            related_evidence_ids=pivot.key_evidence_ids or [],
        ))
        return node_id

    path_root_id = _build_binary_subtree(paths)

    # Link blocking conditions to path tree
    if blocking_nodes:
        for i, bc_id in enumerate(blocking_nodes):
            for node in nodes:
                if node.node_id == bc_id:
                    node.yes_outcome = "存在阻断条件，无法形成稳定判断"
                    if i + 1 < len(blocking_nodes):
                        node.no_child_id = blocking_nodes[i + 1]
                    elif path_root_id:
                        node.no_child_id = path_root_id
                    else:
                        node.no_outcome = "无后续条件分支"
                    break

    # Determine root
    root_id = blocking_nodes[0] if blocking_nodes else (path_root_id or "")

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
