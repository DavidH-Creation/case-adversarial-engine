"""
场景校验器 — 对 Scenario / ScenarioResult 进行合约合规性验证。
Scenario validator — validates Scenario / ScenarioResult against contract constraints.

校验维度 / Validation dimensions:
1. 必填字段非空（scenario_id, case_id, baseline_run_id）
2. diff_summary 为合法值（"baseline" 字面量 或 DiffEntry[]）
3. 每条 diff_entry.impact_description 非空
4. 每条 diff_entry.direction 为合法枚举值（strengthen/weaken/neutral）
5. affected_issue_ids 覆盖所有 diff_entry.issue_id
6. baseline anchor 约束（change_set=[] 时 diff_summary 必须是 "baseline"）
7. Run 合约（trigger_type, scenario_id 非空）
8. 零悬空引用（diff_entry.issue_id 必须在 known_issue_ids 中）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .schemas import (
    DiffEntry,
    IssueTree,
    Run,
    Scenario,
    ScenarioResult,
)


# ---------------------------------------------------------------------------
# 校验结果数据类 / Validation result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """单条校验错误 / A single validation error entry."""
    code: str
    message: str
    location: str = ""  # 错误位置（如 scenario_id、diff_entry issue_id）


@dataclass
class ValidationReport:
    """场景校验结果汇总 / Aggregated scenario validation result."""
    errors: list[ValidationResult] = field(default_factory=list)
    warnings: list[ValidationResult] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """无 error 则校验通过 / Validation passes if no errors."""
        return len(self.errors) == 0

    def summary(self) -> str:
        """返回人类可读的校验摘要 / Return human-readable validation summary."""
        if self.is_valid:
            return f"校验通过 / Validation PASSED (warnings: {len(self.warnings)})"
        lines = [
            f"校验失败 / Validation FAILED ({len(self.errors)} errors, {len(self.warnings)} warnings):"
        ]
        for err in self.errors:
            location = f" [{err.location}]" if err.location else ""
            lines.append(f"  ERROR [{err.code}]{location}: {err.message}")
        for warn in self.warnings:
            location = f" [{warn.location}]" if warn.location else ""
            lines.append(f"  WARN  [{warn.code}]{location}: {warn.message}")
        return "\n".join(lines)


class ScenarioValidationError(Exception):
    """场景校验失败异常，包含详细错误列表。
    Scenario validation failed exception with detailed error list.
    """

    def __init__(self, validation_report: ValidationReport) -> None:
        self.validation_report = validation_report
        super().__init__(validation_report.summary())


# ---------------------------------------------------------------------------
# 核心校验函数 / Core validation functions
# ---------------------------------------------------------------------------


def validate_scenario(
    scenario: Scenario,
    issue_tree: IssueTree | None = None,
    known_issue_ids: set[str] | None = None,
) -> ValidationReport:
    """校验 Scenario 是否符合合约约束。
    Validate Scenario against contract constraints.

    Args:
        scenario: 待校验的场景对象 / Scenario object to validate
        issue_tree: 原始争点树，用于悬空引用校验 / Original IssueTree for dangling ref check
        known_issue_ids: 已知争点 ID 集合 / Known issue IDs set

    Returns:
        ValidationReport 包含所有 errors 和 warnings
    """
    result = ValidationReport()

    # ── 1. 必填字段校验 / Required fields ────────────────────────────────────
    if not scenario.scenario_id:
        result.errors.append(ValidationResult(
            code="MISSING_FIELD",
            message="scenario_id 不能为空 / scenario_id cannot be empty",
        ))
    if not scenario.case_id:
        result.errors.append(ValidationResult(
            code="MISSING_FIELD",
            message="case_id 不能为空 / case_id cannot be empty",
        ))
    if not scenario.baseline_run_id:
        result.errors.append(ValidationResult(
            code="MISSING_FIELD",
            message="baseline_run_id 不能为空 / baseline_run_id cannot be empty",
        ))

    # ── 2. baseline anchor 约束 / Baseline anchor constraint ─────────────────
    # change_set 为空时 diff_summary 必须是字面量 "baseline"
    if not scenario.change_set:
        if scenario.diff_summary != "baseline":
            result.errors.append(ValidationResult(
                code="BASELINE_ANCHOR_VIOLATION",
                message=(
                    "change_set 为空时 diff_summary 必须为字面量 'baseline' / "
                    "diff_summary must be literal 'baseline' when change_set is empty"
                ),
                location=scenario.scenario_id,
            ))
        # baseline anchor 无需进一步校验 diff_entries
        return result

    # ── 3. diff_summary 类型校验 / diff_summary type check ───────────────────
    if scenario.diff_summary == "baseline":
        result.errors.append(ValidationResult(
            code="DIFF_SUMMARY_SENTINEL_ON_NONBASELINE",
            message=(
                "change_set 非空时 diff_summary 不能是字面量 'baseline' / "
                "diff_summary cannot be 'baseline' when change_set is non-empty"
            ),
            location=scenario.scenario_id,
        ))
        return result

    if not isinstance(scenario.diff_summary, list):
        result.errors.append(ValidationResult(
            code="INVALID_DIFF_SUMMARY_TYPE",
            message=(
                f"diff_summary 类型无效，期望 DiffEntry[] / "
                f"Invalid diff_summary type, expected DiffEntry[]: {type(scenario.diff_summary)}"
            ),
            location=scenario.scenario_id,
        ))
        return result

    diff_entries: list[DiffEntry] = scenario.diff_summary

    # ── 4. diff_entries 为空校验 / Empty diff_entries ────────────────────────
    if not diff_entries:
        result.warnings.append(ValidationResult(
            code="EMPTY_DIFF_ENTRIES",
            message=(
                "diff_summary 为空数组，变更集对所有争点均无影响 / "
                "diff_summary is empty; change_set has no impact on any issue"
            ),
            location=scenario.scenario_id,
        ))

    # ── 5. 逐条 diff_entry 校验 / Per-entry validation ───────────────────────
    valid_directions = {"strengthen", "weaken", "neutral"}
    for entry in diff_entries:
        loc = entry.issue_id

        # impact_description 非空
        if not entry.impact_description or not entry.impact_description.strip():
            result.errors.append(ValidationResult(
                code="EMPTY_IMPACT_DESCRIPTION",
                message=(
                    f"diff_entry[{entry.issue_id}].impact_description 不能为空 / "
                    f"impact_description cannot be empty for issue {entry.issue_id}"
                ),
                location=loc,
            ))

        # direction 合法值
        if entry.direction.value not in valid_directions:
            result.errors.append(ValidationResult(
                code="INVALID_DIRECTION",
                message=(
                    f"diff_entry[{entry.issue_id}].direction 无效值 {entry.direction!r} / "
                    f"Invalid direction value {entry.direction!r} for issue {entry.issue_id}"
                ),
                location=loc,
            ))

    # ── 6. affected_issue_ids 覆盖性校验 / affected_issue_ids coverage ────────
    diff_entry_issue_ids = {e.issue_id for e in diff_entries}
    affected_set = set(scenario.affected_issue_ids)
    uncovered = diff_entry_issue_ids - affected_set
    if uncovered:
        result.errors.append(ValidationResult(
            code="AFFECTED_ISSUE_IDS_INCOMPLETE",
            message=(
                f"以下 diff_entry.issue_id 未出现在 affected_issue_ids 中 / "
                f"diff_entry issue_ids not in affected_issue_ids: {uncovered}"
            ),
        ))

    # ── 7. 悬空引用校验 / Dangling reference check ───────────────────────────
    # 计算有效 known_issue_ids（优先使用显式传入的集合）
    _known_ids = known_issue_ids
    if _known_ids is None and issue_tree is not None:
        _known_ids = {i.issue_id for i in issue_tree.issues}

    if _known_ids is not None:
        for entry in diff_entries:
            if entry.issue_id not in _known_ids:
                result.errors.append(ValidationResult(
                    code="DANGLING_ISSUE_REF",
                    message=(
                        f"diff_entry 引用了不存在的 issue_id: {entry.issue_id!r} / "
                        f"Dangling issue reference: {entry.issue_id!r}"
                    ),
                    location=entry.issue_id,
                ))

    return result


def validate_scenario_result(
    scenario_result: ScenarioResult,
    issue_tree: IssueTree | None = None,
    known_issue_ids: set[str] | None = None,
) -> ValidationReport:
    """校验 ScenarioResult（Scenario + Run）的合约合规性。
    Validate ScenarioResult (Scenario + Run) contract compliance.

    在 validate_scenario 基础上增加 Run 级别校验。
    Extends validate_scenario with Run-level checks.
    """
    result = validate_scenario(
        scenario_result.scenario,
        issue_tree=issue_tree,
        known_issue_ids=known_issue_ids,
    )

    run = scenario_result.run

    # ── Run 必填字段 / Run required fields ──────────────────────────────────
    if not run.run_id:
        result.errors.append(ValidationResult(
            code="RUN_MISSING_FIELD",
            message="run.run_id 不能为空 / run.run_id cannot be empty",
        ))
    if not run.workspace_id:
        result.errors.append(ValidationResult(
            code="RUN_MISSING_FIELD",
            message="run.workspace_id 不能为空 / run.workspace_id cannot be empty",
        ))

    # ── trigger_type 必须是 scenario_execution / trigger_type check ──────────
    if run.trigger_type != "scenario_execution":
        result.errors.append(ValidationResult(
            code="RUN_WRONG_TRIGGER_TYPE",
            message=(
                f"run.trigger_type 必须为 'scenario_execution'，实际为 {run.trigger_type!r} / "
                f"run.trigger_type must be 'scenario_execution', got {run.trigger_type!r}"
            ),
            location=run.run_id,
        ))

    # ── scenario_id 一致性 / scenario_id consistency ─────────────────────────
    if run.scenario_id != scenario_result.scenario.scenario_id:
        result.errors.append(ValidationResult(
            code="RUN_SCENARIO_ID_MISMATCH",
            message=(
                f"run.scenario_id ({run.scenario_id!r}) 与 scenario.scenario_id "
                f"({scenario_result.scenario.scenario_id!r}) 不一致 / "
                f"run.scenario_id does not match scenario.scenario_id"
            ),
            location=run.run_id,
        ))

    # ── output_refs 非空 / Non-empty output_refs ─────────────────────────────
    if not run.output_refs:
        result.warnings.append(ValidationResult(
            code="RUN_EMPTY_OUTPUT_REFS",
            message=(
                f"run {run.run_id} 的 output_refs 为空 / "
                f"run {run.run_id} has empty output_refs"
            ),
            location=run.run_id,
        ))

    return result


def validate_scenario_strict(
    scenario: Scenario,
    issue_tree: IssueTree | None = None,
    known_issue_ids: set[str] | None = None,
) -> ValidationReport:
    """严格模式校验：有 error 时抛出 ScenarioValidationError。
    Strict validation: raises ScenarioValidationError if any errors found.

    Raises:
        ScenarioValidationError: 存在任一校验错误时 / When any validation error exists
    """
    result = validate_scenario(scenario, issue_tree, known_issue_ids)
    if not result.is_valid:
        raise ScenarioValidationError(result)
    return result


def validate_scenario_result_strict(
    scenario_result: ScenarioResult,
    issue_tree: IssueTree | None = None,
    known_issue_ids: set[str] | None = None,
) -> ValidationReport:
    """严格模式校验 ScenarioResult：有 error 时抛出 ScenarioValidationError。
    Strict validation for ScenarioResult: raises ScenarioValidationError on any error.

    Raises:
        ScenarioValidationError: 存在任一校验错误时 / When any validation error exists
    """
    result = validate_scenario_result(scenario_result, issue_tree, known_issue_ids)
    if not result.is_valid:
        raise ScenarioValidationError(result)
    return result
