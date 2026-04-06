"""
Case Extractor schemas — Pydantic models for structured case extraction.
案件提取器数据模型 — 从原始法律文本提取结构化案件信息。

Two model layers:
  1. LLM output models (LLMExtracted*) — what the LLM returns
  2. Pipeline-compatible models (Extracted*) — what gets written to YAML
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# LLM output models — intermediate representation from LLM
# ---------------------------------------------------------------------------


class LLMExtractedParty(BaseModel):
    """LLM 提取的当事人信息。"""

    role: str = Field(..., description="plaintiff 或 defendant")
    name: str = Field(..., description="当事人姓名/名称")
    party_id: str = Field(default="", description="自动生成的 party ID")


class LLMExtractedMaterial(BaseModel):
    """LLM 提取的单条证据材料。"""

    source_id: str = Field(..., description="材料唯一 ID")
    text: str = Field(..., description="材料文本内容")
    submitter: str = Field(..., description="提交方: plaintiff 或 defendant")
    document_type: str = Field(default="other", description="文书类型")


class LLMExtractedClaim(BaseModel):
    """LLM 提取的诉请。"""

    claim_id: str = Field(..., description="诉请 ID, e.g. c-001")
    claim_category: str = Field(..., description="诉请类别")
    title: str = Field(..., description="诉请标题")
    claim_text: str = Field(..., description="诉请详细描述")


class LLMExtractedDefense(BaseModel):
    """LLM 提取的抗辩。"""

    defense_id: str = Field(..., description="抗辩 ID, e.g. d-001")
    defense_category: str = Field(..., description="抗辩类别")
    against_claim_id: str = Field(..., description="针对的诉请 ID")
    title: str = Field(..., description="抗辩标题")
    defense_text: str = Field(..., description="抗辩详细描述")


class LLMExtractedLoan(BaseModel):
    """LLM 提取的借款交易。"""

    tx_id: str
    date: str
    amount: str
    evidence_id: str
    principal_base_contribution: bool = True


class LLMExtractedRepayment(BaseModel):
    """LLM 提取的还款交易。"""

    tx_id: str
    date: str
    amount: str
    evidence_id: str
    attributed_to: str | None = None
    attribution_basis: str = ""


class LLMExtractedDisputed(BaseModel):
    """LLM 提取的争议金额。"""

    item_id: str
    amount: str
    dispute_description: str
    plaintiff_attribution: str = ""
    defendant_attribution: str = ""


class LLMExtractedClaimEntry(BaseModel):
    """LLM 提取的诉请金额条目。"""

    claim_id: str
    claim_type: str
    claimed_amount: str
    evidence_ids: list[str] = Field(default_factory=list)


class LLMExtractedFinancials(BaseModel):
    """LLM 提取的财务数据（仅借贷类案件）。"""

    loans: list[LLMExtractedLoan] = Field(default_factory=list)
    repayments: list[LLMExtractedRepayment] = Field(default_factory=list)
    disputed: list[LLMExtractedDisputed] = Field(default_factory=list)
    claim_entries: list[LLMExtractedClaimEntry] = Field(default_factory=list)


class LLMExtractedSummaryRow(BaseModel):
    """LLM 提取的摘要行。"""

    label: str
    description: str


class LLMExtractionOutput(BaseModel):
    """LLM 完整提取结果 — call_structured_llm 返回后 model_validate 此模型。"""

    case_type: str = Field(..., description="案由类型: civil_loan, labor_dispute, real_estate, etc.")
    plaintiff: LLMExtractedParty = Field(..., description="原告信息")
    defendant: LLMExtractedParty = Field(..., description="被告信息")
    summary: list[LLMExtractedSummaryRow] = Field(default_factory=list)
    materials: list[LLMExtractedMaterial] = Field(default_factory=list)
    claims: list[LLMExtractedClaim] = Field(default_factory=list)
    defenses: list[LLMExtractedDefense] = Field(default_factory=list)
    financials: LLMExtractedFinancials | None = Field(
        default=None,
        description="财务数据，仅借贷类案件填写",
    )


# ---------------------------------------------------------------------------
# Pipeline-compatible output — what gets serialized to YAML
# ---------------------------------------------------------------------------


class ExtractedCase(BaseModel):
    """Pipeline-compatible case structure — matches _load_case() requirements.

    Required keys: case_id, case_slug, case_type, parties, materials, claims, defenses.
    """

    case_id: str
    case_slug: str
    case_type: str
    parties: dict[str, dict[str, str]]
    summary: list[list[str]] = Field(default_factory=list)
    materials: dict[str, list[dict[str, Any]]]
    claims: list[dict[str, str]]
    defenses: list[dict[str, str]]
    financials: dict[str, Any] | None = None
    _missing_fields: list[str] = []

    @property
    def missing_fields(self) -> list[str]:
        """Fields the LLM could not extract — user should fill manually."""
        return self._missing_fields
