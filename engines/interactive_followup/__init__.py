"""
交互追问引擎 — Interactive Followup Engine.

接收报告产物、争点树和证据索引，支持律师对报告结论进行多轮深度追问，
每轮回答保持完整的证据引用和争点绑定。
Receives ReportArtifact + IssueTree + EvidenceIndex, supports multi-turn
lawyer Q&A on report conclusions with full citation and issue binding.
"""

from .responder import FollowupResponder, LLMClient
from .schemas import (
    Citation,
    EvidenceIndex,
    EvidenceItem,
    FollowupAnswer,
    FollowupQuestion,
    InteractionTurn,
    IssueTree,
    LLMCitationItem,
    LLMFollowupOutput,
    ReportArtifact,
    ReportSection,
    SessionState,
    StatementClass,
)
from .validator import (
    InteractionValidationError,
    TurnValidationError,
    ValidationReport,
    ValidationResult,
    validate_turn,
    validate_turn_strict,
)

__all__ = [
    # Engine
    "FollowupResponder",
    "LLMClient",
    # Core schemas
    "InteractionTurn",
    "SessionState",
    "FollowupQuestion",
    "FollowupAnswer",
    "Citation",
    "IssueTree",
    "EvidenceIndex",
    "EvidenceItem",
    "ReportArtifact",
    "ReportSection",
    "StatementClass",
    # LLM intermediate
    "LLMCitationItem",
    "LLMFollowupOutput",
    # Validator
    "ValidationReport",
    "ValidationResult",
    "TurnValidationError",
    "InteractionValidationError",
    "validate_turn",
    "validate_turn_strict",
]
