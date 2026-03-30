"""
defense_chain 引擎专用数据模型。
Engine-specific schemas for defense_chain.

共享类型从 engines.shared.models 导入；本模块只保留输入/输出 wrapper 和 LLM 中间模型。
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from engines.shared.models import EvidenceIndex, Issue  # noqa: F401

from .models import DefensePoint, PlaintiffDefenseChain  # noqa: F401


# ---------------------------------------------------------------------------
# LLM 中间模型 / LLM intermediate models
# ---------------------------------------------------------------------------


class LLMDefensePointOutput(BaseModel):
    """LLM 对单个争点生成的防御论点（中间模型）。"""
    issue_id: str = Field(..., min_length=1)
    defense_strategy: str = Field(default="")
    supporting_argument: str = Field(default="")
    evidence_ids: list[str] = Field(default_factory=list)
    priority: int = Field(default=1, ge=1)


class LLMDefenseChainOutput(BaseModel):
    """LLM 生成的完整防御链输出（中间模型）。"""
    defense_points: list[LLMDefensePointOutput] = Field(default_factory=list)
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    strategic_summary: str = Field(default="")


# ---------------------------------------------------------------------------
# 引擎 I/O wrapper / Engine I/O wrappers
# ---------------------------------------------------------------------------


class DefenseChainInput(BaseModel):
    """DefenseChainOptimizer 输入 wrapper。

    Args:
        case_id:            案件 ID
        run_id:             运行快照 ID
        issues:             待防御的争点列表（应含 P0.1 富化字段）
        evidence_index:     证据索引（用于证据 ID 校验和引用）
        plaintiff_party_id: 原告方 party_id（防御对象）
    """
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    issues: list[Issue] = Field(default_factory=list)
    evidence_index: EvidenceIndex
    plaintiff_party_id: str = Field(..., min_length=1)


class DefenseChainResult(BaseModel):
    """防御链优化结果产物。

    Args:
        chain:                  生成的原告方防御策略链
        unevaluated_issue_ids:  未能生成防御论点的争点 ID（LLM 遗漏或失败）
        metadata:               LLM 调用元信息
    """
    chain: PlaintiffDefenseChain
    unevaluated_issue_ids: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
