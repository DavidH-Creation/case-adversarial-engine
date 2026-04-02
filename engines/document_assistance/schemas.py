"""
文书辅助引擎数据模型。
Document assistance engine data models.

结构化填空策略：schema 定义骨架字段，LLM 只填充 List[str] 内容条目。
Structured fill strategy: schema defines skeleton fields, LLM fills only List[str] content items.

所有文书草稿必须引用至少 1 个 evidence_id（evidence_ids_cited 强制非空）。
All document drafts must cite at least 1 evidence_id (evidence_ids_cited must be non-empty).
"""

from __future__ import annotations

from typing import Any, Optional, Union

from pydantic import BaseModel, Field, field_validator

from engines.shared.models import EvidenceIndex, IssueTree


# ---------------------------------------------------------------------------
# 编号条目模型 / Numbered item model
# ---------------------------------------------------------------------------


class NumberedItem(BaseModel):
    """带序号的文书条目。
    A numbered document item with seq and text.
    """

    seq: int = Field(description="序号 / Sequence number")
    text: str = Field(description="内容 / Content text")


def _normalize_numbered_items(v: list) -> list[dict]:
    """Accept both list[str] and list[dict{seq, text}], normalize to list[dict].

    - str items are auto-wrapped: ``{"seq": i, "text": item}``
    - dict items are passed through as-is
    - NumberedItem instances are converted to dict via model_dump
    """
    result = []
    for i, item in enumerate(v, 1):
        if isinstance(item, str):
            result.append({"seq": i, "text": item})
        elif isinstance(item, NumberedItem):
            result.append({"seq": item.seq, "text": item.text})
        elif isinstance(item, dict):
            result.append(item)
        else:
            result.append({"seq": i, "text": str(item)})
    return result


# ---------------------------------------------------------------------------
# 文书骨架模型 / Document skeleton models
# ---------------------------------------------------------------------------


class PleadingDraft(BaseModel):
    """起诉状骨架 — 原告方使用。
    Pleading draft skeleton — used by plaintiff.
    """

    header: str = Field(description="文书标题及案件基本信息行 / Document title and case info line")
    fact_narrative_items: list[NumberedItem] = Field(
        description="事实陈述条目列表（每条含 seq 序号和 text 内容）/ Fact narrative items"
    )
    legal_claim_items: list[NumberedItem] = Field(
        description="法律依据及请求权基础条目 / Legal basis and cause-of-action items"
    )
    prayer_for_relief_items: list[NumberedItem] = Field(
        description="具体诉讼请求条目 / Specific prayer-for-relief items"
    )
    evidence_ids_cited: list[str] = Field(
        description="文书中引用的证据 ID 列表（强制非空）/ Evidence IDs cited (mandatory non-empty)"
    )
    attack_chain_basis: str = Field(
        default="unavailable",
        description="攻击链策略依据；OptimalAttackChain 不可用时标记 'unavailable' / Attack chain basis",
    )

    @field_validator(
        "fact_narrative_items", "legal_claim_items", "prayer_for_relief_items", mode="before"
    )
    @classmethod
    def _normalize_items(cls, v: list) -> list[dict]:
        return _normalize_numbered_items(v)


class DefenseStatement(BaseModel):
    """答辩状骨架 — 被告方使用。
    Defense statement skeleton — used by defendant.
    """

    header: str = Field(description="文书标题及案件基本信息行 / Document title and case info line")
    denial_items: list[NumberedItem] = Field(
        description="逐项否认原告主张的条目 / Items denying plaintiff's claims"
    )
    defense_claim_items: list[NumberedItem] = Field(
        description="实质性抗辩主张条目（至少 1 条回应原告核心主张）/ Substantive defense claim items"
    )
    counter_prayer_items: list[NumberedItem] = Field(
        description="被告反请求或要求驳回原告诉请的条目 / Counter-prayer or dismissal request items"
    )
    evidence_ids_cited: list[str] = Field(
        description="文书中引用的证据 ID 列表（强制非空）/ Evidence IDs cited (mandatory non-empty)"
    )

    @field_validator("denial_items", "defense_claim_items", "counter_prayer_items", mode="before")
    @classmethod
    def _normalize_items(cls, v: list) -> list[dict]:
        return _normalize_numbered_items(v)


class CrossExaminationOpinionItem(BaseModel):
    """针对单个证据的质证意见条目。
    Cross-examination opinion item for a single evidence.
    """

    evidence_id: str = Field(description="被质证的证据 ID / Evidence ID being examined")
    opinion_text: str = Field(
        description="针对该证据的质证意见（一条，简明具体）/ Opinion on this evidence"
    )


class CrossExaminationOpinion(BaseModel):
    """质证意见框架 — 基于 EvidenceIndex 逐证据生成意见条目。
    Cross-examination opinion framework — generates per-evidence opinion items from EvidenceIndex.

    注意：与 pretrial_conference 中的 CrossExaminationOpinion 不同，此处为文书层质证意见，
    非整体文书。EvidenceIndex 为空时 items=[] 且不抛错。
    Note: distinct from pretrial_conference CrossExaminationOpinion — this is a document-level
    opinion framework. When EvidenceIndex is empty, items=[] without error.
    """

    items: list[CrossExaminationOpinionItem] = Field(
        default_factory=list,
        description="逐证据质证意见条目列表（每证据恰好 1 条）/ Per-evidence opinion items",
    )
    evidence_ids_cited: list[str] = Field(
        default_factory=list,
        description="引用的证据 ID 列表（EvidenceIndex 非空时强制非空）/ Cited evidence IDs",
    )


# ---------------------------------------------------------------------------
# 输入模型 / Input model
# ---------------------------------------------------------------------------


class DocumentAssistanceInput(BaseModel):
    """DocumentAssistanceEngine.generate() 的输入。
    Input to DocumentAssistanceEngine.generate().
    """

    case_id: str
    run_id: str
    doc_type: str = Field(description="文书类型：'pleading' | 'defense' | 'cross_exam'")
    case_type: str = Field(description="案件类型：'civil_loan' | 'labor_dispute' | 'real_estate'")
    issue_tree: IssueTree
    evidence_index: EvidenceIndex
    case_data: dict[str, Any] = Field(default_factory=dict)
    attack_chain: Optional[Any] = Field(
        default=None,
        description="OptimalAttackChain 产物（可选）/ OptimalAttackChain artifact (optional)",
    )


# ---------------------------------------------------------------------------
# 输出模型 / Output model
# ---------------------------------------------------------------------------


class DocumentDraft(BaseModel):
    """DocumentAssistanceEngine 输出 — 结构化文书草稿。
    DocumentAssistanceEngine output — structured document draft.
    """

    doc_type: str = Field(description="'pleading' | 'defense' | 'cross_exam'")
    case_type: str = Field(description="'civil_loan' | 'labor_dispute' | 'real_estate'")
    case_id: str
    run_id: str
    content: Union[PleadingDraft, DefenseStatement, CrossExaminationOpinion] = Field(
        description="文书骨架内容 / Document skeleton content",
        discriminator=None,
    )
    evidence_ids_cited: list[str] = Field(
        description="文书中引用的所有证据 ID / All evidence IDs cited in the document"
    )
    generated_at: str = Field(description="生成时间 ISO8601 / Generation time ISO8601")


# ---------------------------------------------------------------------------
# 异常 / Exceptions
# ---------------------------------------------------------------------------


class DocumentGenerationError(Exception):
    """文书生成失败时抛出。
    Raised when document generation fails.

    错误消息必须包含 doc_type 和 case_type 以便诊断。
    Error message must include doc_type and case_type for diagnostics.
    """
