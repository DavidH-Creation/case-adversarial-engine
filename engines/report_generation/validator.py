"""
报告校验器 — 对 ReportArtifact 进行合约合规性验证。
Report validator — validates ReportArtifact against contract constraints.

校验维度 / Validation dimensions:
1. citation_completeness = 100%（每条关键结论有 ≥1 证据引用）
2. 推演回连（每个章节有 linked_output_ids）
3. 陈述分类（每条结论有 statement_class）
4. 争点覆盖（报告覆盖 IssueTree 所有顶层 Issue）
5. 摘要长度 ≤ 500 字
6. 零悬空引用（所有引用 ID 可解析）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .schemas import IssueTree, ReportArtifact


# ---------------------------------------------------------------------------
# 校验结果数据类 / Validation result dataclass
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """单条校验错误 / A single validation error entry."""

    code: str
    message: str
    location: str = ""  # 错误位置（如 section_id、conclusion_id）


@dataclass
class ValidationReport:
    """报告校验结果汇总 / Aggregated report validation result."""

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
        citation_errors = [e for e in self.errors if e.code == "CITATION_MISSING"]
        if citation_errors:
            return 0.0
        return 1.0

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


class ReportValidationError(Exception):
    """报告校验失败异常，包含详细错误列表。
    Report validation failed exception with detailed error list.
    """

    def __init__(self, validation_report: ValidationReport) -> None:
        self.validation_report = validation_report
        super().__init__(validation_report.summary())


# ---------------------------------------------------------------------------
# 核心校验函数 / Core validation functions
# ---------------------------------------------------------------------------


def validate_report(
    report: ReportArtifact,
    issue_tree: IssueTree | None = None,
    known_evidence_ids: set[str] | None = None,
) -> ValidationReport:
    """校验 ReportArtifact 是否符合合约约束。
    Validate ReportArtifact against contract constraints.

    Args:
        report: 待校验的报告产物 / Report artifact to validate
        issue_tree: 原始争点树，用于争点覆盖校验 / Original IssueTree for coverage check
        known_evidence_ids: 已知证据 ID 集合，用于悬空引用校验 / Known evidence IDs

    Returns:
        ValidationReport 包含所有 errors 和 warnings
    """
    result = ValidationReport()

    # ── 1. 顶层结构校验 / Top-level structure ───────────────────────────────
    if not report.report_id:
        result.errors.append(
            ValidationResult(
                code="MISSING_FIELD",
                message="report_id 不能为空 / report_id cannot be empty",
            )
        )
    if not report.summary:
        result.errors.append(
            ValidationResult(
                code="MISSING_FIELD",
                message="summary 不能为空 / summary cannot be empty",
            )
        )
    if not report.sections:
        result.errors.append(
            ValidationResult(
                code="NO_SECTIONS",
                message="报告必须包含至少一个章节 / Report must have at least one section",
            )
        )

    # ── 2. summary 长度校验 / Summary length ────────────────────────────────
    if report.summary and len(report.summary) > 500:
        result.errors.append(
            ValidationResult(
                code="SUMMARY_TOO_LONG",
                message=(
                    f"summary 超过 500 字 ({len(report.summary)} 字) / "
                    f"Summary exceeds 500 chars ({len(report.summary)})"
                ),
            )
        )

    # ── 3. 逐章节校验 / Per-section validation ──────────────────────────────
    section_indices: list[int] = []
    for sec in report.sections:
        loc = sec.section_id

        # section_index 重复检查 / Duplicate section_index check
        section_indices.append(sec.section_index)

        # linked_output_ids 不能为空（推演回连）
        if not sec.linked_output_ids:
            result.errors.append(
                ValidationResult(
                    code="MISSING_OUTPUT_LINK",
                    message=(
                        f"章节 {sec.section_id} 的 linked_output_ids 为空 / "
                        f"Section {sec.section_id} has empty linked_output_ids"
                    ),
                    location=loc,
                )
            )

        # linked_evidence_ids 不能为空
        if not sec.linked_evidence_ids:
            result.warnings.append(
                ValidationResult(
                    code="NO_SECTION_EVIDENCE",
                    message=f"章节 {sec.section_id} 无证据引用 / Section {sec.section_id} has no evidence references",
                    location=loc,
                )
            )

        # 逐结论校验 / Per-conclusion validation
        for concl in sec.key_conclusions:
            cloc = concl.conclusion_id

            # citation_completeness 校验
            if not concl.supporting_evidence_ids:
                result.errors.append(
                    ValidationResult(
                        code="CITATION_MISSING",
                        message=(
                            f"结论 {concl.conclusion_id} 的 supporting_evidence_ids 为空 / "
                            f"Conclusion {concl.conclusion_id} has no supporting_evidence_ids"
                        ),
                        location=cloc,
                    )
                )

            # statement_class 校验（Pydantic 已约束枚举值，此处为额外安全检查）
            if not concl.statement_class:
                result.errors.append(
                    ValidationResult(
                        code="MISSING_STATEMENT_CLASS",
                        message=f"结论 {concl.conclusion_id} 缺少 statement_class",
                        location=cloc,
                    )
                )

    # section_index 重复
    if len(section_indices) != len(set(section_indices)):
        result.errors.append(
            ValidationResult(
                code="DUPLICATE_SECTION_INDEX",
                message=f"section_index 存在重复: {section_indices}",
            )
        )

    # ── 4. 争点覆盖校验 / Issue coverage ────────────────────────────────────
    if issue_tree is not None:
        root_issue_ids = {
            issue.issue_id for issue in issue_tree.issues if issue.parent_issue_id is None
        }
        covered_issue_ids: set[str] = set()
        for sec in report.sections:
            covered_issue_ids.update(sec.linked_issue_ids)

        uncovered = root_issue_ids - covered_issue_ids
        if uncovered:
            result.errors.append(
                ValidationResult(
                    code="ISSUE_COVERAGE_INCOMPLETE",
                    message=(f"以下顶层争点未被报告覆盖 / Root issues not covered: {uncovered}"),
                )
            )

    # ── 5. 悬空引用校验 / Dangling reference check ──────────────────────────
    if known_evidence_ids is not None:
        for sec in report.sections:
            for eid in sec.linked_evidence_ids:
                if eid not in known_evidence_ids:
                    result.errors.append(
                        ValidationResult(
                            code="DANGLING_EVIDENCE_REF",
                            message=(
                                f"章节 {sec.section_id} 引用了不存在的 evidence_id: {eid!r} / "
                                f"Dangling evidence reference: {eid!r}"
                            ),
                            location=sec.section_id,
                        )
                    )
            for concl in sec.key_conclusions:
                for eid in concl.supporting_evidence_ids:
                    if eid not in known_evidence_ids:
                        result.errors.append(
                            ValidationResult(
                                code="DANGLING_EVIDENCE_REF",
                                message=(
                                    f"结论 {concl.conclusion_id} 引用了不存在的 evidence_id: {eid!r}"
                                ),
                                location=concl.conclusion_id,
                            )
                        )

    return result


def validate_report_strict(
    report: ReportArtifact,
    issue_tree: IssueTree | None = None,
    known_evidence_ids: set[str] | None = None,
) -> ValidationReport:
    """严格模式校验：有 error 时抛出 ReportValidationError。
    Strict validation: raises ReportValidationError if any errors found.

    Raises:
        ReportValidationError: 存在任一校验错误时 / When any validation error exists
    """
    result = validate_report(report, issue_tree, known_evidence_ids)
    if not result.is_valid:
        raise ReportValidationError(result)
    return result


# ---------------------------------------------------------------------------
# JSON Schema 校验（可选）/ JSON Schema validation (optional)
# ---------------------------------------------------------------------------


def load_report_schema(schema_dir: Path | str | None = None) -> dict[str, Any]:
    """加载 report_artifact.schema.json。
    Load report_artifact.schema.json.

    Args:
        schema_dir: schema 文件所在目录 / Directory containing schema files.

    Returns:
        JSON Schema 字典 / Parsed JSON Schema dict.
    """
    import json

    if schema_dir is None:
        schema_dir = Path(__file__).resolve().parent.parent.parent / "schemas" / "reporting"
    schema_path = Path(schema_dir) / "report_artifact.schema.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"Report schema not found: {schema_path}")
    with open(schema_path, encoding="utf-8") as f:
        return json.load(f)
