"""
issue_dependency_graph — 争点依赖图模块（P2）。
Issue Dependency Graph module (P2).

工作流阶段：simulation_run
职责：基于 depends_on 字段构建依赖 DAG，输出拓扑排序分析顺序及环路检测。
"""
from .generator import IssueDependencyGraphGenerator
from .schemas import IssueDependencyEdge, IssueDependencyGraph, IssueDependencyNode

__all__ = [
    "IssueDependencyGraphGenerator",
    "IssueDependencyGraph",
    "IssueDependencyNode",
    "IssueDependencyEdge",
]
