"""
程序设置引擎 — Procedure Setup Engine.

根据案件类型、当事人信息和争点树，生成完整的诉讼程序状态序列（ProcedureState[]）、
程序配置（ProcedureConfig）和时间线事件（TimelineEvent[]）。
Generates a complete procedure state sequence (ProcedureState[]),
procedure config (ProcedureConfig), and timeline events (TimelineEvent[])
from case type, parties, and IssueTree.
"""

from .planner import LLMClient, ProcedurePlanner
from .schemas import (
    AccessDomain,
    ArtifactRef,
    Burden,
    ClaimIssueMapping,
    DefenseIssueMapping,
    EvidenceStatusValue,
    FactProposition,
    InputSnapshot,
    Issue,
    IssueTree,
    MaterialRef,
    PHASE_ORDER,
    PartyInfo,
    ProcedureConfig,
    ProcedurePhase,
    ProcedureSetupInput,
    ProcedureSetupResult,
    ProcedureState,
    Run,
    TimelineEvent,
)
from .validator import (
    ProcedureValidationError,
    ValidationReport,
    ValidationResult,
    validate_procedure_setup_result,
    validate_procedure_setup_result_strict,
    validate_procedure_state,
)

__all__ = [
    "ProcedurePlanner",
    "LLMClient",
    # Enums / Constants
    "ProcedurePhase",
    "AccessDomain",
    "EvidenceStatusValue",
    "PHASE_ORDER",
    # Input models
    "ProcedureSetupInput",
    "PartyInfo",
    "IssueTree",
    "Issue",
    "Burden",
    "FactProposition",
    "ClaimIssueMapping",
    "DefenseIssueMapping",
    # Output models
    "ProcedureSetupResult",
    "ProcedureState",
    "ProcedureConfig",
    "TimelineEvent",
    "Run",
    # Index models
    "MaterialRef",
    "ArtifactRef",
    "InputSnapshot",
    # Validator
    "ValidationReport",
    "ValidationResult",
    "ProcedureValidationError",
    "validate_procedure_state",
    "validate_procedure_setup_result",
    "validate_procedure_setup_result_strict",
]
