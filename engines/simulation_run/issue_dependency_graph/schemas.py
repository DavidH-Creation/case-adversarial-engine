"""
issue_dependency_graph 引擎专用数据模型。
Engine-specific schemas for issue_dependency_graph.

共享类型从 engines.shared.models 导入；本模块只保留引擎 I/O wrapper。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from engines.shared.models import Issue  # noqa: F401


# ---------------------------------------------------------------------------
# 图结构模型 / Graph structure models
# ---------------------------------------------------------------------------


class IssueDependencyNode(BaseModel):
    """依赖图中的单个争点节点。"""

    issue_id: str = Field(..., min_length=1)
    depends_on: list[str] = Field(
        default_factory=list,
        description="该争点直接依赖的 issue_id 列表（来自 Issue.depends_on 字段）",
    )


class IssueDependencyEdge(BaseModel):
    """依赖关系有向边：from_issue_id → to_issue_id 表示 from 依赖 to。"""

    from_issue_id: str = Field(..., min_length=1, description="依赖方争点 ID")
    to_issue_id: str = Field(..., min_length=1, description="被依赖方争点 ID")


# ---------------------------------------------------------------------------
# 引擎 I/O wrapper / Engine I/O wrappers
# ---------------------------------------------------------------------------


class IssueDependencyGraphInput(BaseModel):
    """IssueDependencyGraphGenerator 输入 wrapper。

    Args:
        case_id:    案件 ID
        issues:     争点列表（需含 depends_on 字段，由另一任务添加）
    """

    case_id: str = Field(..., min_length=1)
    issues: list[Issue] = Field(default_factory=list)


class IssueDependencyGraph(BaseModel):
    """争点依赖图产物。

    合约保证：
    - topological_order 仅包含无环图部分（排除所有参与 cycle 的争点）
    - has_cycles == True 时 cycles 非空
    - edges 中的所有 issue_id 均在 nodes 中存在
    - created_at 为 ISO-8601 时间戳

    Args:
        graph_id:           产物唯一标识
        case_id:            案件 ID
        nodes:              图中所有争点节点
        edges:              所有依赖关系有向边
        topological_order:  无环部分的拓扑排序（依赖方在后，被依赖方在前）
        cycles:             检测到的环路列表（每条 cycle 为 issue_id 列表）
        has_cycles:         是否存在环路
        metadata:           构建元信息（issue 数量、边数等）
        created_at:         ISO-8601 时间戳
    """

    graph_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    nodes: list[IssueDependencyNode]
    edges: list[IssueDependencyEdge]
    topological_order: list[str] = Field(
        description="无环部分的分析顺序（被依赖争点在前，依赖方在后）"
    )
    cycles: list[list[str]] = Field(
        default_factory=list,
        description="检测到的环路（每条 cycle 为参与环路的 issue_id 列表）",
    )
    has_cycles: bool = Field(default=False)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
