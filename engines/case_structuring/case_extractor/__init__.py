"""
Case Extractor — 从原始法律文书自动提取结构化案件 YAML。
Case Extractor — automatically extract structured case YAML from raw legal documents.

Usage::

    from engines.case_structuring.case_extractor import CaseExtractor, ExtractedCase

    extractor = CaseExtractor(llm_client=client, model="claude-sonnet-4-6")
    result = await extractor.extract([("complaint.txt", text)])
    yaml_str = CaseExtractor.to_yaml(result)
"""

from .extractor import CaseExtractor
from .schemas import (
    ExtractedCase,
    LLMExtractionOutput,
    LLMExtractedClaim,
    LLMExtractedDefense,
    LLMExtractedMaterial,
    LLMExtractedParty,
)

__all__ = [
    "CaseExtractor",
    "ExtractedCase",
    "LLMExtractionOutput",
    "LLMExtractedClaim",
    "LLMExtractedDefense",
    "LLMExtractedMaterial",
    "LLMExtractedParty",
]
