"""
报告生成引擎 — Report Generation Engine.

将争点树（IssueTree）和证据索引（EvidenceIndex）转化为结构化诊断报告。
Transforms IssueTree + EvidenceIndex into a structured diagnostic report.
"""

from .generator import LLMClient, ReportGenerator
from .schemas import (
    EvidenceIndex,
    EvidenceItem,
    IssueTree,
    KeyConclusion,
    ReportArtifact,
    ReportSection,
    StatementClass,
)
from .validator import (
    ReportValidationError,
    ValidationReport,
    ValidationResult,
    validate_report,
    validate_report_strict,
)

__all__ = [
    "ReportGenerator",
    "LLMClient",
    "IssueTree",
    "EvidenceIndex",
    "EvidenceItem",
    "ReportArtifact",
    "ReportSection",
    "KeyConclusion",
    "StatementClass",
    "ValidationReport",
    "ValidationResult",
    "ReportValidationError",
    "validate_report",
    "validate_report_strict",
]
