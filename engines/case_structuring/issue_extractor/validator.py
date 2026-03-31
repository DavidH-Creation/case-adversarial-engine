"""
JSON Schema 校验器 — 对 IssueTree 进行 schema 合规性与合约约束验证。
JSON Schema validator — validates IssueTree against schema and contract constraints.

加载 schemas/case/issue.schema.json 并对每条 Issue 进行 schema 校验，
同时执行合约级约束检查（完整映射、举证责任分配、引用完整性）。
提供两种 API：
- 原有 validate_issue_tree：返回错误字典列表
- 新增 validate_issue_tree_report：返回统一 ValidationReport dataclass

Loads schemas/case/issue.schema.json and validates each Issue,
plus enforces contract-level constraints (complete mapping, burden assignment,
reference integrity).
Two APIs available:
- validate_issue_tree: returns list of error dicts (original)
- validate_issue_tree_report: returns unified ValidationReport dataclass (new)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


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
    """争点树校验结果汇总 / Aggregated IssueTree validation result."""

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
# Schema 加载 / Schema loading
# ---------------------------------------------------------------------------

# 默认 schema 路径：从仓库根目录解析 / Default schema path resolved from repo root
_DEFAULT_SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "schemas" / "case"
_ISSUE_SCHEMA_FILENAME = "issue.schema.json"


def load_issue_schema(schema_dir: Path | str | None = None) -> dict[str, Any]:
    """
    加载 issue.schema.json。
    Load issue.schema.json.

    Args:
        schema_dir: schema 文件所在目录。默认使用仓库相对路径。
                    Schema directory. Defaults to repo-relative path.

    Returns:
        解析后的 JSON Schema 字典 / Parsed JSON Schema dict.

    Raises:
        FileNotFoundError: 找不到 schema 文件 / Schema file not found.
    """
    if schema_dir is None:
        schema_dir = _DEFAULT_SCHEMA_DIR
    schema_path = Path(schema_dir) / _ISSUE_SCHEMA_FILENAME
    if not schema_path.exists():
        raise FileNotFoundError(f"Issue schema not found: {schema_path}")
    with open(schema_path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 校验逻辑 / Validation logic
# ---------------------------------------------------------------------------


class IssueTreeValidationError(Exception):
    """争点树校验失败异常，包含详细错误列表。
    IssueTree validation failure exception with detailed error list.
    """

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        self.errors = errors
        messages = [f"[{e.get('issue_id', '?')}] {e['message']}" for e in errors]
        super().__init__(
            f"IssueTree validation failed with {len(errors)} error(s):\n" + "\n".join(messages)
        )


def validate_issue_tree(
    issue_tree_data: dict[str, Any],
    schema_dir: Path | str | None = None,
) -> list[dict[str, Any]]:
    """
    校验 IssueTree 对象是否符合 schema 和合约约束。
    Validate an IssueTree dict against schema and contract constraints.

    校验项 / Checks performed:
    1. 每条 Issue 符合 issue.schema.json / Each Issue validates against issue.schema.json
    2. issue_id 全局唯一 / issue_ids are globally unique
    3. parent_issue_id 无悬空引用 / No dangling parent_issue_id references
    4. 核心 Issue（无 parent）至少分配一个 Burden / Root issues have ≥1 Burden
    5. claim_issue_mapping 中每条映射的 issue_ids 非空 / claim mappings have non-empty issue_ids
    6. defense_issue_mapping 中每条映射的 issue_ids 非空 / defense mappings have non-empty issue_ids

    Args:
        issue_tree_data: IssueTree 的字典表示 / IssueTree as a dict.
        schema_dir: schema 文件目录 / Schema directory.

    Returns:
        错误详情列表（空列表表示全部通过）。
        List of error dicts; empty list means all checks passed.

    Raises:
        IssueTreeValidationError: 任一约束违反时抛出 / Raised on any constraint violation.
    """
    schema = load_issue_schema(schema_dir)
    validator = Draft202012Validator(schema)

    all_errors: list[dict[str, Any]] = []

    issues = issue_tree_data.get("issues", [])
    burdens = issue_tree_data.get("burdens", [])
    claim_mappings = issue_tree_data.get("claim_issue_mapping", [])
    defense_mappings = issue_tree_data.get("defense_issue_mapping", [])

    # ── 1. JSON Schema 逐条校验 ───────────────────────────────────────────────
    # Validate each Issue against issue.schema.json
    for i, issue_data in enumerate(issues):
        issue_id = issue_data.get("issue_id", f"<index-{i}>")
        schema_errors = sorted(
            validator.iter_errors(issue_data),
            key=lambda e: list(e.absolute_path),
        )
        for error in schema_errors:
            path = ".".join(str(p) for p in error.absolute_path) or "(root)"
            all_errors.append(
                {
                    "issue_id": issue_id,
                    "index": i,
                    "type": "schema",
                    "message": f"{path}: {error.message}",
                }
            )

    # ── 2. issue_id 全局唯一性 ────────────────────────────────────────────────
    # Enforce globally unique issue_ids
    seen_ids: set[str] = set()
    for issue_data in issues:
        iid = issue_data.get("issue_id", "")
        if iid in seen_ids:
            all_errors.append(
                {
                    "issue_id": iid,
                    "type": "contract",
                    "message": f"重复的 issue_id / Duplicate issue_id: '{iid}'",
                }
            )
        seen_ids.add(iid)

    # ── 3. parent_issue_id 引用完整性 ─────────────────────────────────────────
    # No dangling parent_issue_id references
    for issue_data in issues:
        parent = issue_data.get("parent_issue_id")
        if parent and parent not in seen_ids:
            all_errors.append(
                {
                    "issue_id": issue_data.get("issue_id", "?"),
                    "type": "contract",
                    "message": (
                        f"parent_issue_id '{parent}' 不存在于 issues 中 / does not exist in issues"
                    ),
                }
            )

    # ── 4. 核心争点必须分配 Burden ─────────────────────────────────────────────
    # Root issues (no parent) must have at least one Burden assigned
    burden_issue_ids = {b.get("issue_id", "") for b in burdens}
    for issue_data in issues:
        if issue_data.get("parent_issue_id") is None:
            iid = issue_data.get("issue_id", "")
            if iid and iid not in burden_issue_ids:
                all_errors.append(
                    {
                        "issue_id": iid,
                        "type": "contract",
                        "message": (
                            f"核心争点 / Root issue '{iid}' 缺少举证责任 / has no assigned Burden"
                        ),
                    }
                )

    # ── 5. claim_issue_mapping 的 issue_ids 非空 ─────────────────────────────
    for mapping in claim_mappings:
        if not mapping.get("issue_ids"):
            all_errors.append(
                {
                    "issue_id": None,
                    "type": "contract",
                    "message": (
                        f"claim_id '{mapping.get('claim_id')}' 的 issue_ids 为空 / "
                        f"empty issue_ids in claim_issue_mapping"
                    ),
                }
            )

    # ── 6. defense_issue_mapping 的 issue_ids 非空 ───────────────────────────
    for mapping in defense_mappings:
        if not mapping.get("issue_ids"):
            all_errors.append(
                {
                    "issue_id": None,
                    "type": "contract",
                    "message": (
                        f"defense_id '{mapping.get('defense_id')}' 的 issue_ids 为空 / "
                        f"empty issue_ids in defense_issue_mapping"
                    ),
                }
            )

    if all_errors:
        raise IssueTreeValidationError(all_errors)

    return all_errors


# ---------------------------------------------------------------------------
# ValidationReport API（统一格式）/ Unified ValidationReport API
# ---------------------------------------------------------------------------


def validate_issue_tree_report(
    issue_tree_data: dict[str, Any],
    schema_dir: Path | str | None = None,
) -> ValidationReport:
    """校验 IssueTree，返回统一 ValidationReport。
    Validate IssueTree, returning a unified ValidationReport.

    与 validate_issue_tree 不同，此函数不抛出异常，返回结构化报告。
    Unlike validate_issue_tree, this function never raises; returns a structured report.

    Args:
        issue_tree_data: IssueTree 的字典表示 / IssueTree as a dict.
        schema_dir: schema 文件目录 / Schema directory.

    Returns:
        ValidationReport 包含所有 errors 和 warnings。
    """
    report = ValidationReport()
    try:
        validate_issue_tree(issue_tree_data, schema_dir)
    except IssueTreeValidationError as exc:
        for err in exc.errors:
            issue_id = err.get("issue_id") or ""
            report.errors.append(
                ValidationResult(
                    code=f"ISSUE_TREE_{err.get('type', 'error').upper()}",
                    message=err.get("message", ""),
                    location=str(issue_id),
                )
            )
    except Exception as exc:
        # schema 文件缺失、编码错误等 / Schema not found, encoding errors, etc.
        report.errors.append(
            ValidationResult(
                code="SCHEMA_LOAD_ERROR",
                message=str(exc),
            )
        )
    return report
