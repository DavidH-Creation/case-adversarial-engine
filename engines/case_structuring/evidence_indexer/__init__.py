"""
Evidence Indexer — 证据索引引擎。

将原始案件材料通过 LLM 提取为结构化 Evidence 对象。
"""

from .indexer import EvidenceIndexer
from .schemas import (
    AccessDomain,
    Evidence,
    EvidenceIndexResult,
    EvidenceStatus,
    EvidenceType,
    RawMaterial,
)
from .validator import (
    EvidenceValidationError,
    validate_evidence,
    validate_evidence_batch,
)

__all__ = [
    "EvidenceIndexer",
    "Evidence",
    "EvidenceIndexResult",
    "EvidenceType",
    "EvidenceStatus",
    "AccessDomain",
    "RawMaterial",
    "EvidenceValidationError",
    "validate_evidence",
    "validate_evidence_batch",
]
