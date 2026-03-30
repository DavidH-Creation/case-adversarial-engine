"""
交互追问引擎 — Interactive Followup Engine.

接收报告产物、争点树和证据索引，支持律师对报告结论进行多轮深度追问，
每轮回答保持完整的证据引用和争点绑定。
Receives ReportArtifact + IssueTree + EvidenceIndex, supports multi-turn
lawyer Q&A on report conclusions with full citation and issue binding.
"""

from .responder import FollowupResponder, LLMClient
from .schemas import (
    EvidenceIndex,
    EvidenceItem,
    InteractionTurn,
    IssueTree,
    LLMCitationItem,
    LLMFollowupOutput,
    ReportArtifact,
    ReportSection,
    SessionState,
    StatementClass,
)
from .session_manager import SessionManager
from .validator import (
    MAX_QUESTION_LENGTH,
    InteractionValidationError,
    TurnValidationError,
    ValidationReport,
    ValidationResult,
    sanitize_question,
    validate_turn,
    validate_turn_strict,
)

__all__ = [
    # Engine
    "FollowupResponder",
    "LLMClient",
    # Session
    "SessionManager",
    "SessionState",
    # Core schemas
    "InteractionTurn",
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
    "MAX_QUESTION_LENGTH",
    "ValidationReport",
    "ValidationResult",
    "TurnValidationError",
    "InteractionValidationError",
    "sanitize_question",
    "validate_turn",
    "validate_turn_strict",
]
