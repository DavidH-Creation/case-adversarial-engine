"""
证据索引引擎数据模型。
Evidence indexer engine data models.

共享类型从 engines.shared.models 导入；本模块只保留：
- EvidenceIndexResult（引擎专用 wrapper）
- LLMEvidenceItem（LLM 中间解析模型）
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

# 从共享模块导入所有共享类型 / Import all shared types
from engines.shared.models import (  # noqa: F401
    AccessDomain,
    Evidence,
    EvidenceStatus,
    EvidenceType,
    RawMaterial,
)


# ---------------------------------------------------------------------------
# 引擎专用 wrapper / Engine-specific wrapper
# ---------------------------------------------------------------------------


class EvidenceIndexResult(BaseModel):
    """
    证据索引结果（引擎输出 wrapper）。
    Evidence indexer output wrapper.

    工作格式：case_id + evidence 列表 + 元信息。
    Working format: case_id + evidence list + metadata.
    NOTE: 磁盘 artifact 格式（含 artifact_id, evidences 等）由 WorkspaceManager 负责序列化。
    """
    case_id: str = Field(..., min_length=1)
    evidence: list[Evidence]
    extraction_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="提取过程的元信息（模型、耗时、token 数等）",
    )


# ---------------------------------------------------------------------------
# LLM 中间结构 / LLM intermediate structures
# ---------------------------------------------------------------------------


class LLMEvidenceItem(BaseModel):
    """LLM 返回的单条证据提取结果（尚未补全 ID 等字段）。"""
    title: str
    summary: str
    evidence_type: str  # 中文或英文均可，indexer 负责映射
    source_id: str
    target_facts: list[str] = Field(default_factory=list)
    target_issues: list[str] = Field(default_factory=list)
