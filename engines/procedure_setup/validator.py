"""
程序设置校验器 — 对 ProcedureState / ProcedureSetupResult 进行合约合规性验证。
Procedure setup validator — validates ProcedureState / ProcedureSetupResult against contract constraints.

校验维度 / Validation dimensions:
1. 必填字段非空（state_id, case_id, phase）
2. phase 必须来自合法枚举值
3. judge_questions 阶段不得包含 owner_private 读取域
4. output_branching 阶段 admissible_evidence_statuses 必须仅包含 admitted_for_discussion
5. 程序状态序列必须覆盖全部八个阶段
6. next_state_ids 一致性（terminal 状态显式标记）
7. Run 合约（trigger_type = "procedure_setup"）
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .schemas import (
    PHASE_ORDER,
    IssueTree,
    ProcedureSetupResult,
    ProcedureState,
    Run,
)


# ---------------------------------------------------------------------------
# 校验结果数据类 / Validation result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """单条校验错误 / A single validation error entry."""
    code: str
    message: str
    location: str = ""  # 错误位置（如 state_id、phase）/ Error location (e.g. state_id, phase)


@dataclass
class ValidationReport:
    """程序设置校验结果汇总 / Aggregated procedure setup validation result."""
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


class ProcedureValidationError(Exception):
    """程序设置校验失败异常，包含详细错误列表。
    Procedure setup validation failed exception with detailed error list.
    """

    def __init__(self, validation_report: ValidationReport) -> None:
        self.validation_report = validation_report
        super().__init__(validation_report.summary())


# ---------------------------------------------------------------------------
# 合法值常量 / Valid value constants
# ---------------------------------------------------------------------------

_VALID_PHASES: set[str] = set(PHASE_ORDER)
_VALID_ACCESS_DOMAINS: set[str] = {"owner_private", "shared_common", "admitted_record"}
_VALID_EVIDENCE_STATUSES: set[str] = {
    "private", "submitted", "challenged", "admitted_for_discussion"
}


# ---------------------------------------------------------------------------
# 核心校验函数 / Core validation functions
# ---------------------------------------------------------------------------


def validate_procedure_state(
    state: ProcedureState,
    known_issue_ids: set[str] | None = None,
) -> ValidationReport:
    """校验单个 ProcedureState 是否符合合约约束。
    Validate a single ProcedureState against contract constraints.

    Args:
        state: 待校验的程序状态 / ProcedureState to validate
        known_issue_ids: 已知争点 ID 集合（用于悬空引用校验）/ Known issue IDs for dangling ref check

    Returns:
        ValidationReport 包含所有 errors 和 warnings
    """
    result = ValidationReport()
    loc = state.state_id or "<unknown>"

    # ── 1. 必填字段 / Required fields ─────────────────────────────────────
    if not state.state_id:
        result.errors.append(ValidationResult(
            code="MISSING_FIELD",
            message="state_id 不能为空 / state_id cannot be empty",
        ))
    if not state.case_id:
        result.errors.append(ValidationResult(
            code="MISSING_FIELD",
            message="case_id 不能为空 / case_id cannot be empty",
            location=loc,
        ))
    if not state.phase:
        result.errors.append(ValidationResult(
            code="MISSING_FIELD",
            message="phase 不能为空 / phase cannot be empty",
            location=loc,
        ))

    # ── 2. phase 合法值 / Valid phase ──────────────────────────────────────
    if state.phase and state.phase not in _VALID_PHASES:
        result.errors.append(ValidationResult(
            code="INVALID_PHASE",
            message=(
                f"phase 无效值 {state.phase!r}，必须来自 ProcedurePhase 枚举 / "
                f"Invalid phase {state.phase!r}, must be from ProcedurePhase enum"
            ),
            location=loc,
        ))

    # ── 3. 访问域合法值 / Valid access domains ─────────────────────────────
    for domain in state.readable_access_domains:
        if domain not in _VALID_ACCESS_DOMAINS:
            result.errors.append(ValidationResult(
                code="INVALID_ACCESS_DOMAIN",
                message=(
                    f"readable_access_domains 包含无效值 {domain!r} / "
                    f"readable_access_domains contains invalid value {domain!r}"
                ),
                location=loc,
            ))

    # ── 4. judge_questions 访问域约束 / judge_questions access constraint ──
    # judge_questions 不得读取 owner_private（裁判不得接触当事人私有材料）
    if state.phase == "judge_questions":
        if "owner_private" in state.readable_access_domains:
            result.errors.append(ValidationResult(
                code="JUDGE_QUESTIONS_OWNER_PRIVATE_VIOLATION",
                message=(
                    "judge_questions 阶段禁止读取 owner_private 域 / "
                    "judge_questions phase must not include owner_private in readable_access_domains"
                ),
                location=loc,
            ))

    # ── 5. output_branching 证据状态约束 / output_branching evidence constraint ──
    # output_branching 只能基于 admitted_for_discussion 的证据
    if state.phase == "output_branching":
        for status in state.admissible_evidence_statuses:
            if status != "admitted_for_discussion":
                result.errors.append(ValidationResult(
                    code="OUTPUT_BRANCHING_INADMISSIBLE_STATUS",
                    message=(
                        f"output_branching 阶段仅允许 admitted_for_discussion，"
                        f"不允许 {status!r} / "
                        f"output_branching phase only allows admitted_for_discussion, "
                        f"not {status!r}"
                    ),
                    location=loc,
                ))
            break  # 只报告第一个违规

    # ── 6. 证据状态合法值 / Valid evidence statuses ─────────────────────────
    for status in state.admissible_evidence_statuses:
        if status not in _VALID_EVIDENCE_STATUSES:
            result.errors.append(ValidationResult(
                code="INVALID_EVIDENCE_STATUS",
                message=(
                    f"admissible_evidence_statuses 包含无效值 {status!r} / "
                    f"admissible_evidence_statuses contains invalid value {status!r}"
                ),
                location=loc,
            ))

    # ── 7. entry_conditions / exit_conditions 非空校验 / Non-empty conditions ──
    if not state.entry_conditions:
        result.warnings.append(ValidationResult(
            code="EMPTY_ENTRY_CONDITIONS",
            message=(
                f"状态 {loc} 的 entry_conditions 为空 / "
                f"entry_conditions is empty for state {loc}"
            ),
            location=loc,
        ))
    if not state.exit_conditions:
        result.warnings.append(ValidationResult(
            code="EMPTY_EXIT_CONDITIONS",
            message=(
                f"状态 {loc} 的 exit_conditions 为空 / "
                f"exit_conditions is empty for state {loc}"
            ),
            location=loc,
        ))

    # ── 8. 悬空 open_issue_ids 校验 / Dangling open_issue_ids ──────────────
    if known_issue_ids is not None:
        for issue_id in state.open_issue_ids:
            if issue_id not in known_issue_ids:
                result.errors.append(ValidationResult(
                    code="DANGLING_ISSUE_REF",
                    message=(
                        f"open_issue_ids 引用了不存在的 issue_id: {issue_id!r} / "
                        f"open_issue_ids references unknown issue_id: {issue_id!r}"
                    ),
                    location=loc,
                ))

    # ── 9. 终止状态显式标记 / Terminal state explicit marking ──────────────
    # output_branching 是唯一的终止阶段，应无 next_state_ids
    if state.phase == "output_branching" and state.next_state_ids:
        result.warnings.append(ValidationResult(
            code="TERMINAL_STATE_HAS_NEXT",
            message=(
                "output_branching 是终止状态，不应有 next_state_ids / "
                "output_branching is a terminal state and should not have next_state_ids"
            ),
            location=loc,
        ))

    return result


def validate_procedure_setup_result(
    result_obj: ProcedureSetupResult,
    issue_tree: IssueTree | None = None,
    known_issue_ids: set[str] | None = None,
) -> ValidationReport:
    """校验 ProcedureSetupResult 的合约合规性。
    Validate ProcedureSetupResult contract compliance.

    在逐状态校验基础上增加结果级别校验：
    Extends per-state validation with result-level checks:
    - 程序状态序列必须覆盖全部八个阶段
    - Run 合约校验

    Args:
        result_obj: 待校验的程序设置结果 / ProcedureSetupResult to validate
        issue_tree: 原始争点树 / Original IssueTree for dangling ref check
        known_issue_ids: 已知争点 ID 集合 / Known issue IDs set
    """
    report = ValidationReport()

    # 计算有效 known_issue_ids / Compute effective known_issue_ids
    _known_ids = known_issue_ids
    if _known_ids is None and issue_tree is not None:
        _known_ids = {i.issue_id for i in issue_tree.issues}

    # ── 逐状态校验 / Per-state validation ──────────────────────────────────
    for state in result_obj.procedure_states:
        state_report = validate_procedure_state(state, _known_ids)
        report.errors.extend(state_report.errors)
        report.warnings.extend(state_report.warnings)

    # ── 阶段覆盖性校验 / Phase coverage check ─────────────────────────────
    covered_phases = {s.phase for s in result_obj.procedure_states}
    missing_phases = set(PHASE_ORDER) - covered_phases
    if missing_phases:
        report.errors.append(ValidationResult(
            code="MISSING_PHASES",
            message=(
                f"程序状态序列缺少以下阶段 / Procedure state sequence missing phases: "
                f"{missing_phases}"
            ),
        ))

    # ── ProcedureConfig 合约 / ProcedureConfig contract ───────────────────
    cfg = result_obj.procedure_config
    if cfg.total_phases != len(PHASE_ORDER):
        report.warnings.append(ValidationResult(
            code="CONFIG_PHASE_COUNT_MISMATCH",
            message=(
                f"procedure_config.total_phases ({cfg.total_phases}) 与"
                f" 标准阶段数 ({len(PHASE_ORDER)}) 不一致 / "
                f"procedure_config.total_phases ({cfg.total_phases}) does not match "
                f"standard phase count ({len(PHASE_ORDER)})"
            ),
        ))
    if cfg.evidence_submission_deadline_days <= 0:
        report.errors.append(ValidationResult(
            code="INVALID_DEADLINE",
            message=(
                "evidence_submission_deadline_days 必须大于 0 / "
                "evidence_submission_deadline_days must be greater than 0"
            ),
        ))

    # ── Run 合约 / Run contract ────────────────────────────────────────────
    run = result_obj.run
    if not run.run_id:
        report.errors.append(ValidationResult(
            code="RUN_MISSING_FIELD",
            message="run.run_id 不能为空 / run.run_id cannot be empty",
        ))
    if not run.workspace_id:
        report.errors.append(ValidationResult(
            code="RUN_MISSING_FIELD",
            message="run.workspace_id 不能为空 / run.workspace_id cannot be empty",
        ))
    if run.trigger_type != "procedure_setup":
        report.errors.append(ValidationResult(
            code="RUN_WRONG_TRIGGER_TYPE",
            message=(
                f"run.trigger_type 必须为 'procedure_setup'，实际为 {run.trigger_type!r} / "
                f"run.trigger_type must be 'procedure_setup', got {run.trigger_type!r}"
            ),
            location=run.run_id or "<unknown>",
        ))

    # ── output_refs 非空 / Non-empty output_refs ──────────────────────────
    if not run.output_refs:
        report.warnings.append(ValidationResult(
            code="RUN_EMPTY_OUTPUT_REFS",
            message=(
                f"run {run.run_id} 的 output_refs 为空 / "
                f"run {run.run_id} has empty output_refs"
            ),
            location=run.run_id or "<unknown>",
        ))

    return report


def validate_procedure_setup_result_strict(
    result_obj: ProcedureSetupResult,
    issue_tree: IssueTree | None = None,
    known_issue_ids: set[str] | None = None,
) -> ValidationReport:
    """严格模式校验：有 error 时抛出 ProcedureValidationError。
    Strict validation: raises ProcedureValidationError if any errors found.

    Raises:
        ProcedureValidationError: 存在任一校验错误时 / When any validation error exists
    """
    report = validate_procedure_setup_result(result_obj, issue_tree, known_issue_ids)
    if not report.is_valid:
        raise ProcedureValidationError(report)
    return report
