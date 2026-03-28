"""
v1.5 庭前会议数据模型。
Pretrial conference data models for v1.5.

模型层级：
- CrossExaminationDimension — 质证四维度枚举
- CrossExaminationOpinion — 单方对单条证据在单维度的意见
- CrossExaminationRecord — 单条证据完整质证记录
- CrossExaminationFocusItem — 质证焦点清单条目
- CrossExaminationResult — 质证阶段完整输出
- JudgeQuestion — 法官追问条目
- JudgeQuestionSet — 法官追问集合
- PretrialConferenceResult — 庭前会议顶层输出
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from engines.shared.models import EvidenceIndex


# ---------------------------------------------------------------------------
# 枚举 / Enums
# ---------------------------------------------------------------------------


class CrossExaminationDimension(str, Enum):
    """质证四维度。"""
    authenticity = "authenticity"          # 真实性
    relevance = "relevance"               # 关联性
    legality = "legality"                 # 合法性
    probative_value = "probative_value"   # 证明力


class CrossExaminationVerdict(str, Enum):
    """单维度质证结论。"""
    accepted = "accepted"       # 认可
    challenged = "challenged"   # 不认可
    reserved = "reserved"       # 保留意见


class JudgeQuestionType(str, Enum):
    """法官追问类型。"""
    clarification = "clarification"       # 澄清
    contradiction = "contradiction"       # 矛盾发现
    gap = "gap"                           # 缺证识别
    legal_basis = "legal_basis"           # 法律依据


# ---------------------------------------------------------------------------
# 质证模型 / Cross-examination models
# ---------------------------------------------------------------------------


class CrossExaminationOpinion(BaseModel):
    """一方对一条证据在一个维度的意见。"""
    evidence_id: str = Field(..., min_length=1)
    issue_ids: list[str] = Field(..., min_length=1)
    dimension: CrossExaminationDimension
    verdict: CrossExaminationVerdict
    reasoning: str = Field(..., min_length=1, description="质证理由")
    examiner_party_id: str = Field(..., min_length=1, description="质证方 party_id")


class CrossExaminationRecord(BaseModel):
    """单条证据的完整质证记录。"""
    evidence_id: str = Field(..., min_length=1)
    evidence_title: str = Field(default="")
    owner_party_id: str = Field(..., min_length=1)
    opinions: list[CrossExaminationOpinion] = Field(default_factory=list)
    result_status: str = Field(
        ...,
        description="质证后证据状态：admitted_for_discussion 或 challenged",
    )
    admissibility_notes: Optional[str] = None


class CrossExaminationFocusItem(BaseModel):
    """《质证焦点清单》单条。"""
    evidence_id: str = Field(..., min_length=1)
    issue_id: str = Field(..., min_length=1)
    dimension: CrossExaminationDimension
    dispute_summary: str = Field(..., min_length=1)
    is_resolved: bool = False


class CrossExaminationResult(BaseModel):
    """质证阶段完整输出。"""
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    records: list[CrossExaminationRecord] = Field(default_factory=list)
    focus_list: list[CrossExaminationFocusItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 法官追问模型 / Judge question models
# ---------------------------------------------------------------------------


class JudgeQuestion(BaseModel):
    """法官追问条目。"""
    question_id: str = Field(..., min_length=1)
    issue_id: str = Field(..., min_length=1)
    evidence_ids: list[str] = Field(..., min_length=1)
    question_text: str = Field(..., min_length=1)
    target_party_id: str = Field(..., min_length=1)
    question_type: JudgeQuestionType
    priority: int = Field(..., ge=1, le=10)


class JudgeQuestionSet(BaseModel):
    """《法官可能追问 Top10》。"""
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    questions: list[JudgeQuestion] = Field(default_factory=list, max_length=10)


# ---------------------------------------------------------------------------
# 顶层输出 / Top-level output
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# LLM 中间模型（解析用）/ LLM intermediate models (for parsing)
# ---------------------------------------------------------------------------


class LLMOpinionItem(BaseModel):
    """LLM 输出的单条质证意见（中间格式）。"""
    evidence_id: str = ""
    issue_ids: list[str] = Field(default_factory=list)
    dimension: str = ""
    verdict: str = ""
    reasoning: str = ""


class LLMCrossExaminationOutput(BaseModel):
    """LLM 质证输出（中间格式）。"""
    opinions: list[LLMOpinionItem] = Field(default_factory=list)


class LLMJudgeQuestionItem(BaseModel):
    """LLM 输出的单条法官追问（中间格式）。"""
    question_id: str = ""
    issue_id: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    question_text: str = ""
    target_party_id: str = ""
    question_type: str = ""
    priority: int = 5


class LLMJudgeQuestionOutput(BaseModel):
    """LLM 法官追问输出（中间格式）。"""
    questions: list[LLMJudgeQuestionItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 顶层输出 / Top-level output
# ---------------------------------------------------------------------------


class PretrialConferenceResult(BaseModel):
    """庭前会议顶层输出信封。"""
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    cross_examination_result: CrossExaminationResult
    judge_questions: JudgeQuestionSet
    final_evidence_index: EvidenceIndex = Field(
        ..., description="质证后的 EvidenceIndex（证据状态已更新）"
    )
