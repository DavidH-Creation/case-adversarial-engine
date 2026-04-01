"""
类案搜索引擎 — Similar Case Search Engine.

基于本地案例索引的类案检索：关键词提取 → 本地搜索 → 语义排序。
"""
from .keyword_extractor import KeywordExtractor
from .local_search import LocalCaseSearcher
from .relevance_ranker import RelevanceRanker
from .schemas import (
    CaseIndexEntry,
    CaseKeywords,
    RankedCase,
    RelevanceScore,
)

__all__ = [
    "KeywordExtractor",
    "LocalCaseSearcher",
    "RelevanceRanker",
    "CaseIndexEntry",
    "CaseKeywords",
    "RankedCase",
    "RelevanceScore",
]
