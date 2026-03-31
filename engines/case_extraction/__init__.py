"""
案件输入简化引擎 — 文本 → YAML 自动提取
Case Input Simplification Engine — text to YAML automatic extraction
"""

from .extractor import CaseExtractor
from .schemas import CaseExtractionResult

__all__ = ["CaseExtractor", "CaseExtractionResult"]
