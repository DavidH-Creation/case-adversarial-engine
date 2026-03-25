"""
JSON Schema 校验器 — 对 Evidence 对象进行 schema 合规性验证。

加载 schemas/case/evidence.schema.json 并逐条校验。
提供两种 API：
- 原有 validate_evidence / validate_evidence_batch：返回错误字典列表
- 新增 validate_evidence_report：返回统一 ValidationReport dataclass
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator, ValidationError


# ---------------------------------------------------------------------------
# 统一校验结果数据类 / Unified validation result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """单条校验错误 / A single validation error entry."""
    code: str
    message: str
    location: str = ""


@dataclass
class ValidationReport:
    """证据校验结果汇总 / Aggregated evidence validation result."""
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


# ---------------------------------------------------------------------------
# Schema 加载
# ---------------------------------------------------------------------------

# 默认 schema 路径：从仓库根目录解析
_DEFAULT_SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "schemas" / "case"
_EVIDENCE_SCHEMA_FILENAME = "evidence.schema.json"


def load_evidence_schema(schema_dir: Path | str | None = None) -> dict[str, Any]:
    """
    加载 evidence.schema.json。

    Args:
        schema_dir: schema 文件所在目录。默认使用仓库相对路径。

    Returns:
        解析后的 JSON Schema 字典。

    Raises:
        FileNotFoundError: 找不到 schema 文件。
    """
    if schema_dir is None:
        schema_dir = _DEFAULT_SCHEMA_DIR
    schema_path = Path(schema_dir) / _EVIDENCE_SCHEMA_FILENAME
    if not schema_path.exists():
        raise FileNotFoundError(f"Evidence schema not found: {schema_path}")
    with open(schema_path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 校验逻辑
# ---------------------------------------------------------------------------

class EvidenceValidationError(Exception):
    """证据校验失败异常，包含详细错误列表。"""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        self.errors = errors
        messages = [f"[{e['evidence_id']}] {e['message']}" for e in errors]
        super().__init__(f"Evidence validation failed with {len(errors)} error(s):\n" + "\n".join(messages))


def validate_evidence(
    evidence_data: dict[str, Any],
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """
    校验单条 Evidence 对象是否符合 JSON Schema。

    Args:
        evidence_data: Evidence 的字典表示。
        schema: 预加载的 schema 字典。若为 None 则自动加载。

    Returns:
        错误消息列表。空列表表示校验通过。
    """
    if schema is None:
        schema = load_evidence_schema()

    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for error in sorted(validator.iter_errors(evidence_data), key=lambda e: list(e.absolute_path)):
        path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"{path}: {error.message}")
    return errors


def validate_evidence_batch(
    evidences: list[dict[str, Any]],
    schema: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    批量校验 Evidence 列表。

    Args:
        evidences: Evidence 字典列表。
        schema: 预加载的 schema 字典。

    Returns:
        包含错误详情的列表。空列表表示全部通过。

    Raises:
        EvidenceValidationError: 任一 Evidence 校验失败时抛出。
    """
    if schema is None:
        schema = load_evidence_schema()

    all_errors: list[dict[str, Any]] = []
    for i, evidence_data in enumerate(evidences):
        eid = evidence_data.get("evidence_id", f"<index-{i}>")
        errors = validate_evidence(evidence_data, schema)
        for msg in errors:
            all_errors.append({"evidence_id": eid, "index": i, "message": msg})

    if all_errors:
        raise EvidenceValidationError(all_errors)

    return all_errors


# ---------------------------------------------------------------------------
# ValidationReport API（统一格式）/ Unified ValidationReport API
# ---------------------------------------------------------------------------


def validate_evidence_report(
    evidences: list[dict[str, Any]],
    schema: dict[str, Any] | None = None,
) -> ValidationReport:
    """批量校验 Evidence 列表，返回统一 ValidationReport。
    Batch-validate Evidence list, returning a unified ValidationReport.

    与 validate_evidence_batch 不同，此函数不抛出异常，返回结构化报告。
    Unlike validate_evidence_batch, this function never raises; returns a structured report.

    Args:
        evidences: Evidence 字典列表 / List of Evidence dicts.
        schema: 预加载的 schema 字典，None 时自动加载 / Preloaded schema, auto-loaded if None.

    Returns:
        ValidationReport 包含所有 errors 和 warnings。
    """
    if schema is None:
        try:
            schema = load_evidence_schema()
        except FileNotFoundError as exc:
            report = ValidationReport()
            report.errors.append(ValidationResult(
                code="SCHEMA_NOT_FOUND",
                message=str(exc),
            ))
            return report

    report = ValidationReport()
    for i, evidence_data in enumerate(evidences):
        eid = evidence_data.get("evidence_id", f"<index-{i}>")
        errors = validate_evidence(evidence_data, schema)
        for msg in errors:
            report.errors.append(ValidationResult(
                code="SCHEMA_VIOLATION",
                message=msg,
                location=eid,
            ))

    return report
