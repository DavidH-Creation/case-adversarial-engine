"""
案件提取结果 Pydantic schema
Case extraction result Pydantic schemas

两层 schema：
- LLMCaseExtractionOutput：LLM tool_use 返回的原始结构（tool_schema 来源）
- CaseExtractionResult：组装后的结构化提取结果，可序列化为 YAML

Two-layer schemas:
- LLMCaseExtractionOutput: Raw LLM tool_use output (source of tool_schema)
- CaseExtractionResult: Assembled structured result, serializable to YAML
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# LLM 工具调用 schema — tool_use 模式下强制结构化输出
# LLM tool schema — enforces structured output in tool_use mode
# ---------------------------------------------------------------------------


class LLMExtractedClaim(BaseModel):
    """LLM 提取的单项诉讼请求。
    A single extracted litigation claim."""

    claim_category: str = Field(
        description="诉讼请求类型，如：返还借款、利息、赔偿损失、诉讼费用等"
    )
    title: str = Field(description="诉讼请求简短标题（10字以内）")
    claim_text: str = Field(description="诉讼请求完整内容")


class LLMExtractedEvidence(BaseModel):
    """LLM 提取的单项证据描述。
    A single extracted evidence item."""

    description: str = Field(description="证据内容描述")
    document_type: str = Field(
        description=(
            "证据类型：documentary（书证）、electronic_data（电子数据）、"
            "audio_visual（视听资料）、witness_statement（证人证言）、"
            "physical（物证）、expert_opinion（鉴定意见）、other（其他）"
        )
    )
    submitter: str = Field(description="提交方：plaintiff（原告）、defendant（被告）或 unknown")


class LLMCaseExtractionOutput(BaseModel):
    """LLM 结构化提取的全量输出，作为 call_structured_llm 的 tool_schema 来源。
    Full LLM structured extraction output, used as tool_schema for call_structured_llm.
    """

    case_type: str = Field(
        description=(
            "案件类型：civil_loan（民间借贷）、labor_dispute（劳动纠纷）、"
            "real_estate（房产纠纷）；无法判断则填 unknown"
        )
    )
    plaintiff_name: str = Field(description="原告姓名；若文中无法确定则填 unknown")
    defendant_names: list[str] = Field(
        description="被告姓名列表（可多人）；若无法确定则填 ['unknown']"
    )
    claims: list[LLMExtractedClaim] = Field(description="诉讼请求列表；若文中无诉请则填空列表")
    evidence_list: list[LLMExtractedEvidence] = Field(
        description="文中提及的证据列表；若无证据则填空列表"
    )
    disputed_amounts: list[str] = Field(
        description=(
            "文中出现的争议金额（人民币元，纯数字字符串，如 '200000'）。"
            "若有多个不一致的金额则全部列出；若无则填空列表"
        )
    )
    case_summary: str = Field(description="一两句话描述本案核心纠纷；若信息不足则填 unknown")


# ---------------------------------------------------------------------------
# 提取结果对象 — 组装后供 YAML 序列化
# Extraction result objects — assembled for YAML serialization
# ---------------------------------------------------------------------------


class ExtractionParty(BaseModel):
    """当事人提取结果。Extracted party."""

    party_id: str
    name: str  # "unknown" if not determinable


class ExtractionClaim(BaseModel):
    """诉讼请求提取结果。Extracted claim."""

    claim_id: str
    claim_category: str
    title: str
    claim_text: str


class ExtractionEvidence(BaseModel):
    """证据提取结果。Extracted evidence."""

    source_id: str
    description: str
    document_type: str
    submitter: str  # "plaintiff", "defendant", or "unknown"


class DisputedAmount(BaseModel):
    """争议金额（支持单值和多候选值）。
    Disputed amount (supports single value and ambiguous multi-value)."""

    amounts: list[str]  # single value list = deterministic; multiple = ambiguous
    is_ambiguous: bool = False


class CaseExtractionResult(BaseModel):
    """完整案件提取结果，可序列化为 YAML。
    Complete case extraction result, serializable to YAML."""

    case_type: str
    plaintiff: ExtractionParty
    defendants: list[ExtractionParty]
    claims: list[ExtractionClaim]
    evidence_list: list[ExtractionEvidence]
    disputed_amount: DisputedAmount
    case_summary: str
    unknown_fields: list[str] = Field(
        default_factory=list,
        description="标记为 unknown 的字段路径列表",
    )
