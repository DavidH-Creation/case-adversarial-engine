"""
类案搜索数据模型。
Similar case search data models.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class CaseKeywords(BaseModel):
    """LLM 提取的案件搜索关键词。"""

    cause_of_action: str = Field(..., min_length=1, description="案由")
    legal_relations: list[str] = Field(default_factory=list, description="法律关系")
    dispute_focuses: list[str] = Field(default_factory=list, description="争议焦点")
    relevant_statutes: list[str] = Field(default_factory=list, description="相关法条")
    search_terms: list[str] = Field(default_factory=list, description="搜索关键词")


class CaseIndexEntry(BaseModel):
    """本地案例索引中的单条记录。"""

    case_number: str = Field(..., min_length=1, description="案号")
    court: str = Field(..., min_length=1, description="审理法院")
    cause_of_action: str = Field(..., min_length=1, description="案由")
    keywords: list[str] = Field(default_factory=list, description="关键词")
    summary: str = Field(default="", description="一句话摘要")
    url: str = Field(default="", description="案例库链接")


class RelevanceScore(BaseModel):
    """LLM 语义相关性评分（0.0 ~ 1.0）。"""

    fact_similarity: float = Field(..., ge=0.0, le=1.0, description="事实相似度")
    legal_relation_similarity: float = Field(..., ge=0.0, le=1.0, description="法律关系相似度")
    dispute_focus_similarity: float = Field(..., ge=0.0, le=1.0, description="争议焦点相似度")
    judgment_reference_value: float = Field(..., ge=0.0, le=1.0, description="裁判参考价值")
    overall: float = Field(..., ge=0.0, le=1.0, description="综合评分")


class RankedCase(BaseModel):
    """经 LLM 排序后的类案结果。"""

    case: CaseIndexEntry
    relevance: RelevanceScore
    analysis: str = Field(default="", description="与本案相关性分析")


# ---------------------------------------------------------------------------
# LLM 中间结构 / LLM intermediate structures
# ---------------------------------------------------------------------------


class LLMKeywordsOutput(BaseModel):
    """LLM 返回的关键词提取结果（中间结构）。"""

    cause_of_action: str
    legal_relations: list[str] = Field(default_factory=list)
    dispute_focuses: list[str] = Field(default_factory=list)
    relevant_statutes: list[str] = Field(default_factory=list)
    search_terms: list[str] = Field(default_factory=list)


class LLMRankedItem(BaseModel):
    """LLM 返回的单条排序结果（中间结构）。"""

    case_number: str
    fact_similarity: float
    legal_relation_similarity: float
    dispute_focus_similarity: float
    judgment_reference_value: float
    overall: float
    analysis: str = ""
