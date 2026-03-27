"""
evidence_weight_scorer 引擎专用数据模型。
Engine-specific schemas for evidence_weight_scorer.

共享类型从 engines.shared.models 导入；本模块只保留 LLM 中间模型和引擎 I/O wrapper。
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from engines.shared.models import EvidenceIndex  # noqa: F401


# ---------------------------------------------------------------------------
# LLM 中间模型 / LLM intermediate models
# ---------------------------------------------------------------------------


class LLMEvidenceWeightItem(BaseModel):
    """LLM 输出的单条证据权重评分（中间模型，由规则层进一步校验）。"""
    evidence_id: str = Field(default="")
    authenticity_risk: str = Field(default="")       # LLM 原始字符串，规则层映射枚举
    relevance_score: str = Field(default="")
    probative_value: str = Field(default="")
    vulnerability: str = Field(default="")
    admissibility_notes: Optional[str] = None        # high 风险时 LLM 必须提供


class LLMEvidenceWeightOutput(BaseModel):
    """LLM 批量输出（中间模型）。"""
    evidence_weights: list[LLMEvidenceWeightItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 引擎 I/O wrapper / Engine I/O wrapper
# ---------------------------------------------------------------------------


class EvidenceWeightScorerInput(BaseModel):
    """EvidenceWeightScorer 输入 wrapper。

    Args:
        case_id:        案件 ID
        run_id:         运行快照 ID（写入产物元信息）
        evidence_index: 待评分的完整证据索引
    """
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    evidence_index: EvidenceIndex
