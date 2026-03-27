"""
对抗引擎专用 schema — RoundConfig、RoundState、Argument、AdversarialResult。
Adversarial engine schemas — RoundConfig, RoundState, Argument, AdversarialResult.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from engines.shared.models import AgentOutput  # noqa: F401 — re-exported for downstream use


# ---------------------------------------------------------------------------
# 枚举 / Enumerations
# ---------------------------------------------------------------------------


class RoundPhase(str, Enum):
    """三轮对抗阶段。Three adversarial round phases."""
    claim = "claim"           # 首轮主张
    evidence = "evidence"    # 证据提交
    rebuttal = "rebuttal"    # 针对性反驳


# ---------------------------------------------------------------------------
# 配置 / Configuration
# ---------------------------------------------------------------------------


class RoundConfig(BaseModel):
    """对抗轮次配置。Adversarial round configuration."""
    num_rounds: int = Field(default=3, ge=1, le=10)
    max_tokens_per_output: int = Field(default=2000, ge=100, le=8000)
    model: str = Field(default="claude-sonnet-4-20250514")
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    max_retries: int = Field(default=3, ge=1)


# ---------------------------------------------------------------------------
# 核心论点 / Core argument
# ---------------------------------------------------------------------------


class Argument(BaseModel):
    """单条法律论点，必须绑定争点和证据。
    Single legal argument, must bind to an issue and cite evidence.
    """
    issue_id: str = Field(..., min_length=1, description="所针对的争点 ID")
    position: str = Field(..., min_length=1, description="论点陈述文本")
    supporting_evidence_ids: list[str] = Field(
        ..., min_length=1, description="支持该论点的证据 ID 列表（必须非空）"
    )
    legal_basis: Optional[str] = Field(default=None, description="适用法律条款（可选）")
    rebuttal_target_output_id: Optional[str] = Field(
        default=None, description="反驳轮中所针对的对方 output_id"
    )


# ---------------------------------------------------------------------------
# 轮次状态 / Round state
# ---------------------------------------------------------------------------


class RoundState(BaseModel):
    """单轮对抗状态快照。Single round adversarial state snapshot."""
    round_number: int = Field(..., ge=1, description="轮次编号（1-based）")
    phase: RoundPhase = Field(..., description="本轮阶段")
    outputs: list[AgentOutput] = Field(default_factory=list, description="本轮所有代理输出")


# ---------------------------------------------------------------------------
# 最终结果 / Final result
# ---------------------------------------------------------------------------


class ConflictEntry(BaseModel):
    """双方证据冲突条目。Evidence conflict between parties."""
    issue_id: str = Field(..., min_length=1)
    plaintiff_evidence_ids: list[str] = Field(default_factory=list)
    defendant_evidence_ids: list[str] = Field(default_factory=list)
    conflict_description: str = Field(..., min_length=1)


class MissingEvidenceReport(BaseModel):
    """缺失证据分析报告。Missing evidence analysis."""
    issue_id: str = Field(..., min_length=1)
    missing_for_party_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# 对抗总结层 / Adversarial summary layer (LLM-powered semantic analysis)
# ---------------------------------------------------------------------------


class StrongestArgument(BaseModel):
    """LLM 分析识别的最强论点，与 Argument 平行但包含推理说明。
    LLM-identified strongest argument, parallel to Argument but with reasoning.
    """
    issue_id: str = Field(..., min_length=1, description="对应争点 ID")
    position: str = Field(..., min_length=1, description="论证文本（必须引用证据）")
    evidence_ids: list[str] = Field(
        ..., min_length=1, description="支持证据 ID，非空"
    )
    reasoning: str = Field(..., min_length=1, description="为什么是最强论点")


class UnresolvedIssueDetail(BaseModel):
    """带原因说明的未闭合争点（LLM 增强版，基础版仅有 issue_id 字符串）。
    Unresolved issue with explanation (LLM-enriched vs rule-based list[str]).
    """
    issue_id: str = Field(..., min_length=1)
    issue_title: str = Field(..., min_length=1)
    why_unresolved: str = Field(..., min_length=1, description="未闭合原因说明")


class MissingEvidenceSummary(BaseModel):
    """LLM 增强的缺证分析，与规则层 MissingEvidenceReport 平行共存（不替代）。
    LLM-enriched missing evidence analysis, coexists with rule-based MissingEvidenceReport.

    字段对齐说明 / Field alignment:
    - missing_for_party_id: 与 MissingEvidenceReport.missing_for_party_id 一致
    - gap_description: 有意偏离 MissingEvidenceReport.description，语义更精确
    """
    issue_id: str = Field(..., min_length=1)
    missing_for_party_id: str = Field(..., min_length=1, description="缺证方 party_id")
    gap_description: str = Field(..., min_length=1, description="缺少什么证据")


class AdversarialSummary(BaseModel):
    """三轮对抗 LLM 语义分析总结产物。
    LLM semantic summary of three-round adversarial debate.
    """
    plaintiff_strongest_arguments: list[StrongestArgument] = Field(
        default_factory=list, description="原告最强论证列表"
    )
    defendant_strongest_defenses: list[StrongestArgument] = Field(
        default_factory=list, description="被告最强抗辩列表"
    )
    unresolved_issues: list[UnresolvedIssueDetail] = Field(
        default_factory=list, description="未闭合争点列表（含原因说明）"
    )
    missing_evidence_report: list[MissingEvidenceSummary] = Field(
        default_factory=list, description="缺证分析列表（LLM 增强）"
    )
    overall_assessment: Optional[str] = Field(
        default=None,
        description=(
            "整体态势评估（不超过 300 字）。v1.2 改为 Optional："
            " DecisionPathTree 存在时由调用方从各路径 possible_outcome 摘要填充；"
            " 直接调用 AdversarialSummarizer 时仍可直接填写。"
        ),
    )


class AdversarialResult(BaseModel):
    """完整对抗模拟结果。Complete adversarial simulation result."""
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    job_id: str = Field(default="", description="关联的 JobManager job_id（可选）")
    rounds: list[RoundState] = Field(default_factory=list, description="所有轮次状态列表")
    plaintiff_best_arguments: list[Argument] = Field(
        default_factory=list, description="原告最有力论点（规则提取）"
    )
    defendant_best_defenses: list[Argument] = Field(
        default_factory=list, description="被告最有力抗辩（规则提取）"
    )
    unresolved_issues: list[str] = Field(
        default_factory=list, description="仍未解决的争点 ID 列表（规则提取）"
    )
    evidence_conflicts: list[ConflictEntry] = Field(
        default_factory=list, description="双方证据冲突列表"
    )
    missing_evidence_report: list[MissingEvidenceReport] = Field(
        default_factory=list, description="缺失证据分析（规则提取）"
    )
    summary: Optional[AdversarialSummary] = Field(
        default=None, description="LLM 语义分析总结（三轮对抗后生成）"
    )
