"""
IssueDependencyGraphGenerator — 争点依赖图构建器（P2）。
Issue Dependency Graph Generator (P2).

职责 / Responsibilities:
1. 接收争点列表，读取每个 Issue 的 depends_on 字段（由另一任务添加）
2. 构建有向无环图（DAG），过滤非法引用（unknown issue_id）
3. Kahn 算法拓扑排序，确定分析顺序（被依赖方先分析）
4. 检测环路（拓扑排序后仍有剩余节点即存在环）
5. 对环路记录 warning 并排除环路节点（不抛异常）

合约保证 / Contract guarantees:
- 空争点列表直接返回空图
- depends_on 引用不存在的 issue_id 被过滤并记录 warning
- topological_order 仅含无环节点（环路节点单独记录在 cycles 中）
- 不调用 LLM（纯规则层）
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone

from engines.shared.models import Issue

from .schemas import (
    IssueDependencyEdge,
    IssueDependencyGraph,
    IssueDependencyGraphInput,
    IssueDependencyNode,
)

logger = logging.getLogger(__name__)


class IssueDependencyGraphGenerator:
    """争点依赖图构建器。

    纯规则层，不持有外部状态，可安全复用同一实例。

    使用方式 / Usage:
        generator = IssueDependencyGraphGenerator()
        graph = generator.build(inp)
    """

    def build(self, inp: IssueDependencyGraphInput) -> IssueDependencyGraph:
        """构建争点依赖图。

        Args:
            inp: 包含案件 ID 和争点列表的输入

        Returns:
            IssueDependencyGraph — 含节点、边、拓扑排序及环路检测结果
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        issues = list(inp.issues)

        if not issues:
            return IssueDependencyGraph(
                graph_id=str(uuid.uuid4()),
                case_id=inp.case_id,
                nodes=[],
                edges=[],
                topological_order=[],
                cycles=[],
                has_cycles=False,
                metadata={"issue_count": 0, "edge_count": 0},
                created_at=now,
            )

        known_ids: set[str] = {i.issue_id for i in issues}

        # 构建节点列表，读取 depends_on（兼容字段尚未添加的情况）
        nodes: list[IssueDependencyNode] = []
        edges: list[IssueDependencyEdge] = []

        for issue in issues:
            raw_deps: list[str] = getattr(issue, "depends_on", None) or []
            valid_deps: list[str] = []
            for dep_id in raw_deps:
                if dep_id in known_ids:
                    valid_deps.append(dep_id)
                    edges.append(
                        IssueDependencyEdge(
                            from_issue_id=issue.issue_id,
                            to_issue_id=dep_id,
                        )
                    )
                else:
                    logger.warning(
                        "depends_on 引用了未知 issue_id: %s → %s（已忽略）",
                        issue.issue_id,
                        dep_id,
                    )
            nodes.append(IssueDependencyNode(issue_id=issue.issue_id, depends_on=valid_deps))

        # Kahn 算法拓扑排序
        topological_order, cycles = self._topological_sort(nodes, known_ids)
        has_cycles = len(cycles) > 0

        if has_cycles:
            cycle_ids = {issue_id for cycle in cycles for issue_id in cycle}
            logger.warning(
                "检测到环路依赖！环路节点: %s。这些节点已从拓扑排序中排除。",
                cycle_ids,
            )

        return IssueDependencyGraph(
            graph_id=str(uuid.uuid4()),
            case_id=inp.case_id,
            nodes=nodes,
            edges=edges,
            topological_order=topological_order,
            cycles=cycles,
            has_cycles=has_cycles,
            metadata={
                "issue_count": len(issues),
                "edge_count": len(edges),
                "cycle_count": len(cycles),
                "created_at": now,
            },
            created_at=now,
        )

    # ------------------------------------------------------------------
    # 拓扑排序 / Topological sort (Kahn's algorithm)
    # ------------------------------------------------------------------

    @staticmethod
    def _topological_sort(
        nodes: list[IssueDependencyNode],
        known_ids: set[str],
    ) -> tuple[list[str], list[list[str]]]:
        """Kahn 算法拓扑排序 + 环路检测。

        排序语义：被依赖方（dependency）在前，依赖方（dependent）在后。
        即：若 A depends_on B，则 B 出现在 A 之前。

        Args:
            nodes:     所有争点节点（含已过滤的 depends_on）
            known_ids: 已知 issue_id 集合

        Returns:
            (topological_order, cycles)
            - topological_order: 无环节点的有序 issue_id 列表
            - cycles: 检测到的环路列表（每条为参与环路的 issue_id 列表）
        """
        # 建立入度表和邻接表（边方向：to_id → from_id，即依赖方指向被依赖方）
        # in_degree[v] = 有多少节点依赖于 v（被依赖方的入度）
        # 等价于：计算每个节点有几个"前驱"（即它依赖的节点数）
        in_degree: dict[str, int] = {n.issue_id: 0 for n in nodes}
        # adjacency: 当节点 u 完成后，哪些节点的入度减少
        # u 被依赖 → 其完成后，依赖 u 的节点入度减 1
        adjacency: dict[str, list[str]] = defaultdict(list)

        for node in nodes:
            in_degree[node.issue_id] = len(node.depends_on)
            for dep_id in node.depends_on:
                adjacency[dep_id].append(node.issue_id)

        # 初始队列：入度为 0 的节点（不依赖任何节点，可优先分析）
        queue: deque[str] = deque(
            sorted(
                [node_id for node_id, deg in in_degree.items() if deg == 0],
                # 稳定排序：保持输入相对顺序，便于测试
            )
        )

        topological_order: list[str] = []

        while queue:
            node_id = queue.popleft()
            topological_order.append(node_id)
            for dependent_id in adjacency[node_id]:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    queue.append(dependent_id)

        # 剩余非零入度节点参与了环路
        cycle_node_ids = {node_id for node_id, deg in in_degree.items() if deg > 0}

        cycles: list[list[str]] = []
        if cycle_node_ids:
            cycles = IssueDependencyGraphGenerator._extract_cycles(cycle_node_ids, nodes)

        return topological_order, cycles

    @staticmethod
    def _extract_cycles(
        cycle_node_ids: set[str],
        nodes: list[IssueDependencyNode],
    ) -> list[list[str]]:
        """从环路节点集合中提取具体环路（DFS）。

        简化实现：对每个未访问的环路节点做 DFS 找最短环，
        用于 warning 日志和审计，不追求枚举所有环路。
        """
        node_map = {n.issue_id: n for n in nodes if n.issue_id in cycle_node_ids}
        visited: set[str] = set()
        cycles: list[list[str]] = []

        for start_id in sorted(cycle_node_ids):
            if start_id in visited:
                continue
            # DFS 找从 start_id 出发的一条环路
            path: list[str] = []
            path_set: set[str] = set()
            found = IssueDependencyGraphGenerator._dfs_find_cycle(
                start_id, node_map, path, path_set, cycle_node_ids
            )
            if found:
                # 截取从环路起点到当前节点的路径
                start_idx = path.index(path[-1]) if path[-1] in path[:-1] else 0
                cycle = path[start_idx:]
                cycles.append(cycle)
                visited.update(cycle)

        return cycles if cycles else [sorted(cycle_node_ids)]

    @staticmethod
    def _dfs_find_cycle(
        node_id: str,
        node_map: dict[str, IssueDependencyNode],
        path: list[str],
        path_set: set[str],
        cycle_node_ids: set[str],
    ) -> bool:
        """DFS 查找一条包含 node_id 的环路。"""
        path.append(node_id)
        path_set.add(node_id)

        node = node_map.get(node_id)
        if node is None:
            path.pop()
            path_set.discard(node_id)
            return False

        for dep_id in node.depends_on:
            if dep_id not in cycle_node_ids:
                continue
            if dep_id in path_set:
                path.append(dep_id)  # 环路闭合点
                return True
            if IssueDependencyGraphGenerator._dfs_find_cycle(
                dep_id, node_map, path, path_set, cycle_node_ids
            ):
                return True

        path.pop()
        path_set.discard(node_id)
        return False
