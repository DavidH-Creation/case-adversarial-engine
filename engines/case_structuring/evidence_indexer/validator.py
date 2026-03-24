"""
JSON Schema 校验器 — 对 Evidence 对象进行 schema 合规性验证。

加载 schemas/case/evidence.schema.json 并逐条校验。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator, ValidationError


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
        EvidenceValidationError: 任一 Evidence 校验失촥时抛出。
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
