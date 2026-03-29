"""
decision_path_tree 引擎专用数据模型。
Engine-specific schemas for decision_path_tree.

共享类型从 engines.shared.models 导入；本模块只保留 LLM 中间模型和引擎 I/O wrapper。
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from engines.shared.models import (  # noqa: F401
    AmountCalculationReport,
    DecisionPathTree,
    EvidenceIndex,
    IssueTree,
)


# ---------------------------------------------------------------------------
# LLM 中间模型 / LLM intermediate models
# ---------------------------------------------------------------------------


class LLMConfidenceInterval(BaseModel):
    """LLM 输出的置信度区间（中间模型，规则层可能清空）。"""
    lower: float = Field(default=0.0)
    upper: float = Field(default=0.0)


class LLMDecisionPathItem(BaseModel):
    """LLM 输出的单条裁判路径（中间模型，由规则层进一步校验）。"""
    path_id: str = Field(default="")
    trigger_condition: str = Field(default="")
    trigger_issue_ids: list[str] = Field(default_factory=list)
    key_evidence_ids: list[str] = Field(default_factory=list)
    possible_outcome: str = Field(default="")
    confidence_interval: Optional[LLMConfidenceInterval] = None
    path_notes: str = Field(default="")
    # v1.5: 路径可执行化扩展字段
    admissibility_gate: list[str] = Field(default_factory=list)
    result_scope: list[str] = Field(default_factory=list)
    fallback_path_id: str = Field(default="")


class LLMBlockingConditionItem(BaseModel):
    """LLM 输出的阻断条件（中间模型）。"""
    condition_id: str = Field(default="")
    condition_type: str = Field(default="")
    description: str = Field(default="")
    linked_issue_ids: list[str] = Field(default_factory=list)
    linked_evidence_ids: list[str] = Field(default_factory=list)


class LLMDecisionPathTreeOutput(BaseModel):
    """LLM 批量输出（中间模型）。"""
    paths: list[LLMDecisionPathItem] = Field(default_factory=list)
    blocking_conditions: list[LLMBlockingConditionItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 引擎 I/O wrapper / Engine I/O wrappers
# ---------------------------------------------------------------------------


class DecisionPathTreeInput(BaseModel):
    """DecisionPathTreeGenerator 输入 wrapper。

    Args:
        case_id:                    案件 ID
        run_id:                     运行快照 ID（写入产物元信息）
        ranked_issue_tree:          P0.1 产物（issues 已按 outcome_impact 排序并富化）
        evidence_index:             完整证据索引（生成器内部会按 v1.2 过渡规则过滤）
        amount_calculation_report:  P0.2 产物（含 verdict_block_active 和 unresolved_conflicts）
    """
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    ranked_issue_tree: IssueTree
    evidence_index: EvidenceIndex
    amount_calculation_report: AmountCalculationReport
