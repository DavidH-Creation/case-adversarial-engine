"""
Issue Extractor — 争点抽取引擎。

从 Claims + Defenses + Evidence 中提取争议焦点，
构建争点树，并为每个核心争点分配举证责任。
"""

from .extractor import IssueExtractor
from .schemas import (
    Burden,
    BurdenStatus,
    ClaimIssueMapping,
    DefenseIssueMapping,
    ExtractionMetadata,
    FactProposition,
    Issue,
    IssueStatus,
    IssueTree,
    IssueType,
    PropositionStatus,
)
from .validator import (
    IssueTreeValidationError,
    validate_issue_tree,
)

__all__ = [
    "IssueExtractor",
    "Issue",
    "IssueTree",
    "IssueType",
    "IssueStatus",
    "Burden",
    "BurdenStatus",
    "FactProposition",
    "PropositionStatus",
    "ClaimIssueMapping",
    "DefenseIssueMapping",
    "ExtractionMetadata",
    "IssueTreeValidationError",
    "validate_issue_tree",
]
