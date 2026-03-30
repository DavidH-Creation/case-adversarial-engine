"""
交互追问校验器 — 对 InteractionTurn 进行合约合规性验证 + 输入净化。
Interaction turn validator — validates InteractionTurn against contract constraints + input sanitization.

校验维度 / Validation dimensions:
1. 证据边界（evidence_ids ⊆ 报告已引用证据）/ Evidence boundary
2. 争点绑定（issue_ids 非空）/ Issue binding (non-empty)
3. 陈述分类（statement_class 有效）/ Statement classification
4. 必填字段完整性 / Required field completeness
5. 悬空争点引用（issue_ids 中的 ID 在已知争点集合中存在）/ Dangling issue reference

输入净化 / Input sanitization:
- 最大长度 2000 字符 / Max length 2000 characters
- HTML/script 标签过滤 / HTML/script tag filtering
- 空输入拒绝 / Empty input rejection
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .schemas import InteractionTurn, StatementClass

# ---------------------------------------------------------------------------
# 输入净化常量 / Input sanitization constants
# ---------------------------------------------------------------------------

MAX_QUESTION_LENGTH = 2000

# 匹配 <script>...</script> 和 <style>...</style> 整块内容（含标签和内容）
_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL
)
# 匹配剩余的 HTML 标签 / Matches remaining HTML tags
_HTML_TAG_RE = re.compile(r"<[^>]+>", re.IGNORECASE)


# ---------------------------------------------------------------------------
# 校验结果数据类 / Validation result dataclass
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """单条校验错误 / A single validation error entry."""

    code: str
    message: str
    location: str = ""  # 错误位置（如 turn_id）


@dataclass
class ValidationReport:
    """追问轮次校验结果汇总 / Aggregated turn validation result."""

    errors: list[ValidationResult] = field(default_factory=list)
    warnings: list[ValidationResult] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """无 error 则校验通过 / Validation passes if no errors."""
        return len(self.errors) == 0

    @property
    def citation_completeness(self) -> float:
        """计算引用完整性得分（0.0–1.0）。
        Compute citation completeness score (0.0–1.0).
        """
        citation_errors = [
            e for e in self.errors if e.code == "EVIDENCE_BOUNDARY_VIOLATION"
        ]
        if citation_errors:
            return 0.0
        return 1.0

    def summary(self) -> str:
        """返回人类可读的校验摘要 / Return human-readable validation summary."""
        if self.is_valid:
            return f"校验通过 / Validation PASSED (warnings: {len(self.warnings)})"
        lines = [
            f"校验失败 / Validation FAILED "
            f"({len(self.errors)} errors, {len(self.warnings)} warnings):"
        ]
        for err in self.errors:
            location = f" [{err.location}]" if err.location else ""
            lines.append(f"  ERROR [{err.code}]{location}: {err.message}")
        for warn in self.warnings:
            location = f" [{warn.location}]" if warn.location else ""
            lines.append(f"  WARN  [{warn.code}]{location}: {warn.message}")
        return "\n".join(lines)


class TurnValidationError(Exception):
    """追问校验失败异常，包含详细错误列表。
    Turn validation failed exception with detailed error list.
    """

    def __init__(self, validation_report: ValidationReport) -> None:
        self.validation_report = validation_report
        super().__init__(validation_report.summary())


# Alias for backwards compatibility / 向后兼容别名
InteractionValidationError = TurnValidationError


# ---------------------------------------------------------------------------
# 核心校验函数 / Core validation functions
# ---------------------------------------------------------------------------


def validate_turn(
    turn: InteractionTurn,
    known_issue_ids: set[str] | None = None,
    report_evidence_ids: set[str] | None = None,
) -> ValidationReport:
    """校验 InteractionTurn 是否符合合约约束。
    Validate InteractionTurn against contract constraints.

    Args:
        turn: 待校验的追问轮次 / Turn to validate
        known_issue_ids: 已知争点 ID 集合，用于悬空引用校验 / Known issue IDs for dangling ref check
        report_evidence_ids: 报告已引用证据 ID 集合，用于证据边界校验 / Report evidence IDs

    Returns:
        ValidationReport 包含所有 errors 和 warnings
    """
    result = ValidationReport()
    loc = turn.turn_id if turn.turn_id else "unknown_turn"

    # ── 1. 必填字段校验 / Required field checks ──────────────────────────────
    if not turn.turn_id:
        result.errors.append(ValidationResult(
            code="MISSING_FIELD",
            message="turn_id 不能为空 / turn_id cannot be empty",
            location=loc,
        ))
    if not turn.question:
        result.errors.append(ValidationResult(
            code="MISSING_FIELD",
            message="question 不能为空 / question cannot be empty",
            location=loc,
        ))
    if not turn.answer:
        result.errors.append(ValidationResult(
            code="MISSING_FIELD",
            message="answer 不能为空 / answer cannot be empty",
            location=loc,
        ))
    if not turn.report_id:
        result.errors.append(ValidationResult(
            code="MISSING_FIELD",
            message="report_id 不能为空 / report_id cannot be empty",
            location=loc,
        ))

    # ── 2. 争点绑定校验 / Issue binding check ────────────────────────────────
    if not turn.issue_ids:
        result.errors.append(ValidationResult(
            code="EMPTY_ISSUE_IDS",
            message=(
                "issue_ids 不能为空，追问必须绑定至少一个争点 / "
                "issue_ids must not be empty, turn must bind at least one issue"
            ),
            location=loc,
        ))

    # ── 3. 陈述分类校验 / Statement classification check ─────────────────────
    valid_classes = {sc.value for sc in StatementClass}
    sc_value = (
        turn.statement_class.value
        if hasattr(turn.statement_class, "value")
        else turn.statement_class
    )
    if sc_value not in valid_classes:
        result.errors.append(ValidationResult(
            code="INVALID_STATEMENT_CLASS",
            message=(
                f"statement_class 无效: {turn.statement_class!r}，"
                f"合法值 / Valid values: {sorted(valid_classes)}"
            ),
            location=loc,
        ))

    # ── 4. 证据边界校验 / Evidence boundary check ─────────────────────────────
    if report_evidence_ids is not None:
        for eid in turn.evidence_ids:
            if eid not in report_evidence_ids:
                result.errors.append(ValidationResult(
                    code="EVIDENCE_BOUNDARY_VIOLATION",
                    message=(
                        f"evidence_id {eid!r} 不在报告已引用证据中 / "
                        f"evidence_id {eid!r} is not in report-cited evidence"
                    ),
                    location=loc,
                ))

        # 证据引用为空时发出警告 / Warn if no evidence cited
        if not turn.evidence_ids:
            result.warnings.append(ValidationResult(
                code="NO_EVIDENCE_CITED",
                message=(
                    "本轮追问未引用任何证据，事实性断言应有 evidence_id 支撑 / "
                    "No evidence cited in this turn; factual claims should have evidence"
                ),
                location=loc,
            ))

    # ── 5. 悬空争点引用校验 / Dangling issue reference check ──────────────────
    if known_issue_ids is not None:
        for iid in turn.issue_ids:
            if iid not in known_issue_ids:
                result.errors.append(ValidationResult(
                    code="DANGLING_ISSUE_REF",
                    message=(
                        f"issue_id {iid!r} 不在已知争点集合中 / "
                        f"issue_id {iid!r} is not in known issue IDs"
                    ),
                    location=loc,
                ))

    return result


def validate_turn_strict(
    turn: InteractionTurn,
    known_issue_ids: set[str] | None = None,
    report_evidence_ids: set[str] | None = None,
) -> ValidationReport:
    """严格模式校验：有 error 时抛出 TurnValidationError。
    Strict validation: raises TurnValidationError if any errors found.

    Raises:
        TurnValidationError: 存在任一校验错误时 / When any validation error exists
    """
    result = validate_turn(turn, known_issue_ids, report_evidence_ids)
    if not result.is_valid:
        raise TurnValidationError(result)
    return result


# ---------------------------------------------------------------------------
# 输入净化函数 / Input sanitization functions
# ---------------------------------------------------------------------------


def sanitize_question(question: str) -> str:
    """净化用户追问输入。
    Sanitize user followup question input.

    处理逻辑 / Processing:
    1. 去除首尾空白 / Strip leading/trailing whitespace
    2. 移除 HTML/script 标签 / Remove HTML/script tags
    3. 截断至 MAX_QUESTION_LENGTH 字符 / Truncate to MAX_QUESTION_LENGTH characters

    Args:
        question: 原始用户输入 / Raw user input

    Returns:
        净化后的问题字符串 / Sanitized question string

    Raises:
        ValueError: 净化后为空字符串 / Empty string after sanitization
    """
    # Strip whitespace
    cleaned = question.strip()

    # Reject empty input
    if not cleaned:
        raise ValueError(
            "问题不能为空 / Question cannot be empty"
        )

    # Remove <script>/<style> blocks (including content), then remaining tags
    cleaned = _SCRIPT_STYLE_RE.sub("", cleaned)
    cleaned = _HTML_TAG_RE.sub("", cleaned)

    # Re-check after tag removal
    if not cleaned.strip():
        raise ValueError(
            "问题在移除 HTML 标签后为空 / Question is empty after HTML tag removal"
        )
    cleaned = cleaned.strip()

    # Truncate to max length
    if len(cleaned) > MAX_QUESTION_LENGTH:
        cleaned = cleaned[:MAX_QUESTION_LENGTH]

    return cleaned
