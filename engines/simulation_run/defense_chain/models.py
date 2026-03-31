"""
defense_chain 领域模型。
Domain models for defense_chain.

PlaintiffDefenseChain 及关联模型定义于此，供 optimizer.py 和外部消费者使用。
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class DefensePoint(BaseModel):
    """单条防御论点。

    Args:
        point_id:           论点唯一标识
        issue_id:           对应的争点 ID
        defense_strategy:   防御策略摘要（简短，1-2 句话）
        supporting_argument: 详细支撑论证
        evidence_ids:       支持该论点的证据 ID 列表
        priority:           在链中的优先顺序（1 = 最优先）
    """

    point_id: str = Field(..., min_length=1)
    issue_id: str = Field(..., min_length=1)
    defense_strategy: str = Field(..., min_length=1)
    supporting_argument: str = Field(..., min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    priority: int = Field(ge=1, description="在链中的优先顺序（1 = 最优先）")


class PlaintiffDefenseChain(BaseModel):
    """原告方防御策略链。

    汇集针对多个争点的有序防御论点，形成完整的庭审防御策略。

    合约保证：
    - defense_points 按 priority 升序排列（1 在前）
    - confidence_score ∈ [0.0, 1.0]
    - target_issues 与 defense_points 中的 issue_id 一一对应

    Args:
        chain_id:           产物唯一标识
        case_id:            案件 ID
        target_issues:      防御目标争点 issue_id 列表
        defense_points:     有序防御论点列表（按 priority 升序）
        evidence_support:   防御链整体引用的证据 ID 汇总
        confidence_score:   LLM 对整体防御策略的置信度（0.0-1.0）
        strategic_summary:  整体策略摘要文本
        created_at:         ISO-8601 时间戳
    """

    chain_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    target_issues: list[str] = Field(default_factory=list)
    defense_points: list[DefensePoint] = Field(default_factory=list)
    evidence_support: list[str] = Field(
        default_factory=list,
        description="防御链整体引用证据 ID 汇总（去重）",
    )
    confidence_score: float = Field(ge=0.0, le=1.0, description="LLM 对整体防御策略的置信度")
    strategic_summary: str = Field(default="", description="整体防御策略摘要")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
