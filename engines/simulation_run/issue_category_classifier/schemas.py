"""
issue_category_classifier 引擎专用数据模型。
Engine-specific schemas for issue_category_classifier.

共享类型从 engines.shared.models 导入；本模块只保留 LLM 中间模型和引擎 I/O wrapper。
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from engines.shared.models import (  # noqa: F401
    AmountCalculationReport,
    EvidenceIndex,
    IssueCategory,
    IssueTree,
)


# ---------------------------------------------------------------------------
# LLM 中间模型 / LLM intermediate models
# ---------------------------------------------------------------------------


class LLMIssueCategoryItem(BaseModel):
    """LLM 对单个争点的类型分类输出（中间模型，由规则层进一步校验）。"""

    issue_id: str = Field(default="")
    issue_category: str = Field(
        default="",
        description="分类结果；允许值：fact_issue / legal_issue / calculation_issue / procedure_credibility_issue",
    )
    related_claim_entry_ids: list[str] = Field(
        default_factory=list,
        description="当 issue_category=calculation_issue 时，关联的 ClaimCalculationEntry claim_id 列表",
    )
    category_basis: str = Field(
        default="",
        description="分类依据说明（必须非空，否则规则层丢弃 issue_category）",
    )


class LLMIssueCategoryOutput(BaseModel):
    """LLM 批量分类输出（中间模型）。LLM batch classification output (intermediate model)."""

    classifications: list[LLMIssueCategoryItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 引擎 I/O wrapper / Engine I/O wrappers
# ---------------------------------------------------------------------------


class IssueCategoryClassifierInput(BaseModel):
    """IssueCategoryClassifier 输入 wrapper。

    Args:
        case_id:                    案件 ID
        run_id:                     运行快照 ID（写入元信息）
        issue_tree:                 待分类的争点树
        evidence_index:             证据索引（上下文，帮助 LLM 理解争点背景）
        amount_calculation_report:  P0.2 产物（用于校验 calculation_issue 关联）
    """

    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    issue_tree: IssueTree
    evidence_index: EvidenceIndex
    amount_calculation_report: Optional[AmountCalculationReport] = None


class IssueCategoryClassificationResult(BaseModel):
    """争点类型分类结果产物。纳入 CaseWorkspace.artifact_index。

    classified_issue_tree:      issues 已填充 issue_category 字段的争点树
    classification_metadata:    LLM 调用元信息（model/timestamp/分类数量）
    unclassified_issue_ids:     未能分类或校验失败的争点 ID（供审计）
    created_at:                 ISO-8601 时间戳
    """

    classified_issue_tree: IssueTree
    classification_metadata: dict[str, Any] = Field(default_factory=dict)
    unclassified_issue_ids: list[str] = Field(default_factory=list)
    created_at: str
