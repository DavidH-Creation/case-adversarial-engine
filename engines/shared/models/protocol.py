"""
协议与场景层模型 / Protocol and scenario layer models.

包含变量注入、差异条目和场景对象。
"""

from __future__ import annotations

from typing import Any, Union

from pydantic import BaseModel, Field

from engines.shared.models.core import (
    ChangeItemObjectType,
    DiffDirection,
    ScenarioStatus,
)


# ---------------------------------------------------------------------------
# 场景层 / Scenario layer
# ---------------------------------------------------------------------------


class ChangeItem(BaseModel):
    """单条变量注入。"""
    target_object_type: ChangeItemObjectType
    target_object_id: str = Field(..., min_length=1)
    field_path: str = Field(..., min_length=1)
    old_value: Any = None
    new_value: Any = None


class DiffEntry(BaseModel):
    """单争点差异条目。NO affected_party_ids per spec."""
    issue_id: str = Field(..., min_length=1)
    impact_description: str = Field(..., min_length=1)
    direction: DiffDirection


class Scenario(BaseModel):
    """场景对象。NO separate DiffSummary wrapper per spec."""
    scenario_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    baseline_run_id: str = Field(..., min_length=1)
    change_set: list[ChangeItem]
    diff_summary: Union[str, list[DiffEntry]] = Field(...)
    affected_issue_ids: list[str] = Field(default_factory=list)
    affected_evidence_ids: list[str] = Field(default_factory=list)
    status: ScenarioStatus
