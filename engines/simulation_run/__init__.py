"""
场景推演引擎 — Simulation Run Engine.

将争点树（IssueTree）和证据索引（EvidenceIndex）结合场景变更集（ChangeSet），
模拟反事实变量注入对各争点的影响，输出结构化差异摘要（DiffSummary）。
Applies a structured change_set to a baseline run snapshot and produces
a per-issue DiffSummary explaining the counterfactual impact.
"""

from .simulator import LLMClient, ScenarioSimulator, load_baseline, parse_change_set, run_whatif
from .schemas import (
    ChangeItem,
    ChangeItemObjectType,
    DiffDirection,
    DiffEntry,
    EvidenceIndex,
    EvidenceItem,
    IssueTree,
    Run,
    Scenario,
    ScenarioInput,
    ScenarioResult,
    ScenarioStatus,
)
from .validator import (
    ScenarioValidationError,
    ValidationReport,
    ValidationResult,
    validate_scenario,
    validate_scenario_result,
    validate_scenario_result_strict,
    validate_scenario_strict,
)

__all__ = [
    "ScenarioSimulator",
    "LLMClient",
    "load_baseline",
    "parse_change_set",
    "run_whatif",
    "ChangeItem",
    "ChangeItemObjectType",
    "DiffDirection",
    "DiffEntry",
    "EvidenceIndex",
    "EvidenceItem",
    "IssueTree",
    "Run",
    "Scenario",
    "ScenarioInput",
    "ScenarioResult",
    "ScenarioStatus",
    "ValidationReport",
    "ValidationResult",
    "ScenarioValidationError",
    "validate_scenario",
    "validate_scenario_result",
    "validate_scenario_strict",
    "validate_scenario_result_strict",
]
