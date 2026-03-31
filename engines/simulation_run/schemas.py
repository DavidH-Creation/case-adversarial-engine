"""
场景推演引擎数据模型。
Scenario engine data models.

共享类型从 engines.shared.models 导入；本模块只保留引擎专用 wrapper 和 LLM 中间结构。
Shared types imported from engines.shared.models; only engine-specific wrappers and LLM intermediate structures kept here.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

# 从共享模块导入所有共享类型（re-exported for backward compat）
from engines.shared.models import (  # noqa: F401
    ArtifactRef,
    Burden,
    ChangeItem,
    ChangeItemObjectType,
    ClaimIssueMapping,
    DefenseIssueMapping,
    DiffDirection,
    DiffEntry,
    Evidence as EvidenceItem,  # backward compat alias
    Evidence,
    EvidenceIndex,
    FactProposition,
    InputSnapshot,
    Issue,
    IssueTree,
    MaterialRef,
    Run,
    Scenario,
    ScenarioStatus,
)


# ---------------------------------------------------------------------------
# 引擎专用输入合约 / Engine-specific input contract
# ---------------------------------------------------------------------------


class ScenarioInput(BaseModel):
    """场景引擎输入合约。"""

    scenario_id: str = Field(..., min_length=1)
    baseline_run_id: str = Field(..., min_length=1)
    change_set: list[ChangeItem]
    workspace_id: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# 引擎专用结果 wrapper / Engine-specific result wrapper
# ---------------------------------------------------------------------------


class ScenarioResult(BaseModel):
    """场景推演结果。"""

    scenario: Scenario
    run: Run


# ---------------------------------------------------------------------------
# LLM 中间结构 / LLM intermediate structures
# ---------------------------------------------------------------------------


class LLMDiffEntry(BaseModel):
    """LLM 返回的单条差异条目（尚未规范化）。"""

    issue_id: str
    impact_description: str
    direction: str  # "strengthen" / "weaken" / "neutral"


class LLMDiffOutput(BaseModel):
    """LLM 返回的完整差异分析（尚未规范化）。"""

    diff_entries: list[LLMDiffEntry]
    summary: str = ""
