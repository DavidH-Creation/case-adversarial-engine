"""
Pydantic 数据模型 — 与 JSON Schema 定义对齐。

所有模型均使用 Pydantic v2，字段定义严格匹配
schemas/case/evidence.schema.json 和 schemas/case/evidence_index.schema.json。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# 枚举类型
# ---------------------------------------------------------------------------

class EvidenceType(str, Enum):
    """证据类型枚举，对应《民事诉讼法》证据种类。"""
    documentary = "documentary"          # 书证
    physical = "physical"                # 物证
    witness_statement = "witness_statement"  # 证人证言
    electronic_data = "electronic_data"  # 电子数据
    expert_opinion = "expert_opinion"    # 鉴定意见
    audio_visual = "audio_visual"        # 视听资料
    other = "other"


class AccessDomain(str, Enum):
    """证据可见域。"""
    owner_private = "owner_private"
    shared_common = "shared_common"
    admitted_record = "admitted_record"


class EvidenceStatus(str, Enum):
    """证据生命周期状态。"""
    private = "private"
    submitted = "submitted"
    challenged = "challenged"
    admitted_for_discussion = "admitted_for_discussion"


# ---------------------------------------------------------------------------
# 输入模型
# ---------------------------------------------------------------------------

class RawMaterial(BaseModel):
    """原始案件材料段落，眱调用方提供。"""
    source_id: str = Field(..., min_length=1, description="材料唯一标识符")
    text: str = Field(..., min_length=1, description="纯文本内容")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="开放元数据（document_type, date, submitter 等）",
    )


# ---------------------------------------------------------------------------
# 输出模型
# ---------------------------------------------------------------------------

class Evidence(BaseModel):
    """
    结构化证据对象，对应 schemas/case/evidence.schema.json。

    由 EvidenceIndexer 生成，初始状态恒为 private / owner_private。
    """
    evidence_id: str = Field(..., min_length=1, description="全局唯一 ID: evidence-{slug}-{seq}")
    case_id: str = Field(..., min_length=1)
    owner_party_id: str = Field(..., min_length=1, description="证据所有方 party_id")
    title: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1, description="来源材料标识")
    summary: str = Field(..., min_length=1, description="人类可读摘要")
    evidence_type: EvidenceType
    target_fact_ids: list[str] = Field(..., min_length=1, description="至少绑定一条待证事实")
    target_issue_ids: list[str] = Field(default_factory=list)
    access_domain: AccessDomain = AccessDomain.owner_private
    status: EvidenceStatus = EvidenceStatus.private
    submitted_by_party_id: Optional[str] = None
    challenged_by_party_ids: list[str] = Field(default_factory=list)
    admissibility_notes: Optional[str] = None

    @field_validator("target_fact_ids")
    @classmethod
    def at_least_one_fact(cls, v: list[str]) -> list[str]:
        """合同约束：每条证据必须绑定至少一条事实命题。"""
        if not v:
            raise ValueError("target_fact_ids 不能为空，至少绑定一条事实命题")
        return v


class EvidenceIndexResult(BaseModel):
    """
    证据索引结果，对应 evidence_index.schema.json 的核心输出。

    包含输入快照与输出证据列表，便于重放和审计。
    """
    case_id: str = Field(..., min_length=1)
    evidence: list[Evidence]
    extraction_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="提取过程的元信息（模型、耗时、token 数等）",
    )


# ---------------------------------------------------------------------------
# LLM 返回的中间结构（解析 LLM JSON 输出用）
# ---------------------------------------------------------------------------

class LLMEvidenceItem(BaseModel):
    """LLM 返回的单条证据提取结果（尚未补全 ID 等字段）。"""
    title: str
    summary: str
    evidence_type: str  # 中文或英文均可，indexer 负责映射
    source_id: str
    target_facts: list[str] = Field(default_factory=list)
    target_issues: list[str] = Field(default_factory=list)
