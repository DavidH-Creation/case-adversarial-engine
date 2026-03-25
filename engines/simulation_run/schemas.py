"""
场景推演引擎数据模型 — 与 JSON Schema 定义对齐。
Scenario engine data models — aligned with JSON Schema definitions.

所有模型均使用 Pydantic v2，字段定义严格匹配：
All models use Pydantic v2, strictly aligned with:
- schemas/case/scenario.schema.json
- schemas/procedure/run.schema.json
- schemas/indexing.schema.json
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional, Union

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 枚举类型 / Enum types
# ---------------------------------------------------------------------------


class ChangeItemObjectType(str, Enum):
    """change_item 目标对象类型枚举。
    Enum for target_object_type in a ChangeItem.
    """
    Party = "Party"
    Claim = "Claim"
    Defense = "Defense"
    Issue = "Issue"
    Evidence = "Evidence"
    Burden = "Burden"
    ProcedureState = "ProcedureState"
    AgentOutput = "AgentOutput"
    ReportArtifact = "ReportArtifact"


class DiffDirection(str, Enum):
    """差异方向枚举 / Direction of the diff impact on the issue's legal position."""
    strengthen = "strengthen"   # 增强己方立场 / Improves the party's position
    weaken = "weaken"           # 削弱己方立场 / Damages the party's position
    neutral = "neutral"         # 无净方向影响 / Material change with no net directional effect


class ScenarioStatus(str, Enum):
    """场景生命周期状态 / Scenario lifecycle status."""
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


# ---------------------------------------------------------------------------
# 索引引用模型 / Index reference models
# ---------------------------------------------------------------------------


class MaterialRef(BaseModel):
    """材料索引引用 / Material index reference (maps to indexing.schema.json#material_ref)."""
    index_name: str = Field(default="material_index")
    object_type: str
    object_id: str = Field(..., min_length=1)
    storage_ref: str = Field(..., min_length=1)


class ArtifactRef(BaseModel):
    """产物索引引用 / Artifact index reference (maps to indexing.schema.json#artifact_ref)."""
    index_name: str = Field(default="artifact_index")
    object_type: str
    object_id: str = Field(..., min_length=1)
    storage_ref: str = Field(..., min_length=1)


class InputSnapshot(BaseModel):
    """运行输入快照 / Run input snapshot (maps to indexing.schema.json#input_snapshot)."""
    material_refs: list[MaterialRef] = Field(default_factory=list)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 场景输入模型 / Scenario input models
# ---------------------------------------------------------------------------


class ChangeItem(BaseModel):
    """单条变量注入 / Single field mutation applied to the baseline before re-execution.

    合约约束 / Contract constraint:
    - target_object_type 必须来自注册的 CaseWorkspace 索引类型
    - field_path 使用点分路径（dot-notation）
    - old_value / new_value 允许为 null
    """
    target_object_type: ChangeItemObjectType
    target_object_id: str = Field(..., min_length=1)
    field_path: str = Field(..., min_length=1)
    old_value: Any = None
    new_value: Any = None


class ScenarioInput(BaseModel):
    """场景引擎输入合约 / Scenario engine input contract (per scenario_engine_contract.md)."""
    scenario_id: str = Field(..., min_length=1)
    baseline_run_id: str = Field(..., min_length=1)
    change_set: list[ChangeItem]
    workspace_id: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# 共享输入模型：IssueTree / EvidenceIndex
# Shared input models mirroring report_generation schemas
# ---------------------------------------------------------------------------


class FactProposition(BaseModel):
    """事实命题 / Fact proposition within an Issue."""
    proposition_id: str
    text: str
    status: Optional[str] = None
    linked_evidence_ids: list[str] = Field(default_factory=list)


class Issue(BaseModel):
    """争点对象 / Issue object, matching issue.schema.json."""
    issue_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    issue_type: str
    parent_issue_id: Optional[str] = None
    related_claim_ids: list[str] = Field(default_factory=list)
    related_defense_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    burden_ids: list[str] = Field(default_factory=list)
    fact_propositions: list[FactProposition] = Field(default_factory=list)
    status: Optional[str] = None
    created_at: Optional[str] = None


class Burden(BaseModel):
    """举证责任对象 / Burden of proof object."""
    burden_id: str
    case_id: str
    issue_id: str
    bearer_party_id: str
    description: str
    proof_standard: Optional[str] = None
    legal_basis: Optional[str] = None
    status: Optional[str] = None


class ClaimIssueMapping(BaseModel):
    """诉请-争点映射 / Claim-to-issue mapping."""
    claim_id: str
    issue_ids: list[str]


class DefenseIssueMapping(BaseModel):
    """抗辩-争点映射 / Defense-to-issue mapping."""
    defense_id: str
    issue_ids: list[str]


class IssueTree(BaseModel):
    """争点树输入 / IssueTree input, matching issue_tree.schema.json."""
    case_id: str = Field(..., min_length=1)
    run_id: Optional[str] = None
    job_id: Optional[str] = None
    issues: list[Issue]
    burdens: list[Burden]
    claim_issue_mapping: list[ClaimIssueMapping]
    defense_issue_mapping: list[DefenseIssueMapping]
    extraction_metadata: Optional[dict[str, Any]] = None


class EvidenceItem(BaseModel):
    """单条证据对象 / Single evidence item, matching evidence.schema.json."""
    evidence_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    owner_party_id: Optional[str] = None
    title: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    evidence_type: str
    target_fact_ids: list[str] = Field(default_factory=list)
    target_issue_ids: list[str] = Field(default_factory=list)
    access_domain: Optional[str] = None
    status: Optional[str] = None
    submitted_by_party_id: Optional[str] = None
    challenged_by_party_ids: list[str] = Field(default_factory=list)
    admissibility_notes: Optional[str] = None


class EvidenceIndex(BaseModel):
    """证据索引输入 / Evidence index input."""
    case_id: str
    evidence: list[EvidenceItem]
    extraction_metadata: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# 输出模型 / Output models
# ---------------------------------------------------------------------------


class DiffEntry(BaseModel):
    """单争点差异条目 / Per-issue diff entry produced after scenario execution.

    合约约束 / Contract constraint:
    - impact_description 必须非空，且可追溯到 change_set 中至少一条 ChangeItem
    - direction 必须是 strengthen / weaken / neutral
    """
    issue_id: str = Field(..., min_length=1)
    impact_description: str = Field(
        ...,
        min_length=1,
        description="可追溯到 change_set 的影响描述 / Human-readable impact traceable to change_set",
    )
    direction: DiffDirection


class Scenario(BaseModel):
    """场景对象 / Scenario object, matching scenario.schema.json.

    由 ScenarioSimulator 生成，必须满足以下合约：
    Generated by ScenarioSimulator, must satisfy:
    - diff_summary 为字面量 "baseline"（baseline anchor）或 DiffEntry[]（执行后）
    - 每条 diff_entry 可追溯到 change_set 中的至少一条 ChangeItem
    - affected_issue_ids 覆盖所有 diff_entry.issue_id
    """
    scenario_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    baseline_run_id: str = Field(..., min_length=1)
    change_set: list[ChangeItem]
    diff_summary: Union[str, list[DiffEntry]] = Field(
        ...,
        description="'baseline' 字面量（baseline anchor）或 DiffEntry[] / Literal 'baseline' or DiffEntry[]",
    )
    affected_issue_ids: list[str] = Field(default_factory=list)
    affected_evidence_ids: list[str] = Field(default_factory=list)
    status: ScenarioStatus


class Run(BaseModel):
    """执行快照 / Run execution snapshot, matching run.schema.json."""
    run_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    workspace_id: str = Field(..., min_length=1)
    scenario_id: Optional[str] = None
    trigger_type: str = Field(..., min_length=1)
    input_snapshot: InputSnapshot
    output_refs: list[ArtifactRef] = Field(default_factory=list)
    started_at: str
    finished_at: Optional[str] = None
    status: str


class ScenarioResult(BaseModel):
    """场景推演结果 / Result returned by ScenarioSimulator.

    包含更新后的 Scenario 和新创建的 Run。
    Contains the updated Scenario and the newly created Run.
    """
    scenario: Scenario
    run: Run


# ---------------------------------------------------------------------------
# LLM 中间结构 / LLM intermediate structures
# ---------------------------------------------------------------------------


class LLMDiffEntry(BaseModel):
    """LLM 返回的单条差异条目（尚未规范化）。
    Single diff entry as returned by LLM (before normalization).
    """
    issue_id: str
    impact_description: str
    direction: str  # "strengthen" / "weaken" / "neutral"


class LLMDiffOutput(BaseModel):
    """LLM 返回的完整差异分析（尚未规范化）。
    Full diff analysis as returned by LLM (before normalization).
    """
    diff_entries: list[LLMDiffEntry]
    summary: str = ""  # 可选的整体摘要 / Optional overall change summary
