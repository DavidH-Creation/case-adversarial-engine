"""
API 请求/响应模型 — 基于现有 Pydantic 模型，独立于引擎内部结构。
API request/response models — independent from internal engine schemas.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class CaseStatus(str, Enum):
    created = "created"
    extracting = "extracting"
    extracted = "extracted"
    confirmed = "confirmed"
    analyzing = "analyzing"
    analyzed = "analyzed"
    failed = "failed"


# ---------------------------------------------------------------------------
# POST /api/cases/
# ---------------------------------------------------------------------------


class PartyInfo(BaseModel):
    party_id: str = Field(default_factory=lambda: f"party-{uuid.uuid4().hex[:8]}")
    name: str


class ClaimInput(BaseModel):
    claim_id: str = Field(default_factory=lambda: f"claim-{uuid.uuid4().hex[:8]}")
    title: str
    description: str
    claim_type: str = "other"
    claimed_amount: Optional[float] = None


class DefenseInput(BaseModel):
    defense_id: str = Field(default_factory=lambda: f"defense-{uuid.uuid4().hex[:8]}")
    title: str
    description: str


class CreateCaseRequest(BaseModel):
    case_type: str = "civil_loan"
    plaintiff: PartyInfo
    defendant: PartyInfo
    claims: list[ClaimInput] = Field(default_factory=list)
    defenses: list[DefenseInput] = Field(default_factory=list)


class CreateCaseResponse(BaseModel):
    case_id: str
    status: CaseStatus


# ---------------------------------------------------------------------------
# GET /api/cases/{case_id}
# ---------------------------------------------------------------------------


class CaseInfoResponse(BaseModel):
    case_id: str
    status: CaseStatus
    info: dict[str, Any]
    progress: list[str]
    error: Optional[str] = None
    has_extraction: bool = False
    has_analysis: bool = False
    run_id: Optional[str] = None  # Unit 5: analysis run_id for Scenario API
    review_status: Optional[str] = None  # v2.5 Phase 3


# ---------------------------------------------------------------------------
# POST /api/cases/{case_id}/materials
# ---------------------------------------------------------------------------


class AddMaterialRequest(BaseModel):
    source_id: str = Field(default_factory=lambda: f"src-{uuid.uuid4().hex[:8]}")
    role: str  # "plaintiff" | "defendant"
    doc_type: str = "general"
    text: str


class AddMaterialResponse(BaseModel):
    source_id: str
    role: str
    doc_type: str
    char_count: int


# ---------------------------------------------------------------------------
# GET /api/cases/{case_id}/extraction
# ---------------------------------------------------------------------------


class ExtractionResponse(BaseModel):
    status: CaseStatus
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    issues: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# POST /api/cases/{case_id}/confirm
# ---------------------------------------------------------------------------


class ConfirmRequest(BaseModel):
    issues: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# GET /api/cases/{case_id}/analysis  (SSE)
# ---------------------------------------------------------------------------


class AnalysisResponse(BaseModel):
    status: CaseStatus
    run_id: Optional[str] = None  # Unit 5: stable id for Scenario API
    overall_assessment: Optional[str] = None
    plaintiff_args: list[dict[str, Any]] = Field(default_factory=list)
    defendant_defenses: list[dict[str, Any]] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)
    evidence_conflicts: list[dict[str, Any]] = Field(default_factory=list)
    rounds: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# POST /api/scenarios/run
# GET  /api/scenarios/{scenario_id}
# ---------------------------------------------------------------------------


class ChangeItemRequest(BaseModel):
    target_object_type: str
    target_object_id: str
    field_path: str
    old_value: Any = None
    new_value: Any = None


class ScenarioRunRequest(BaseModel):
    run_id: str
    change_set: list[ChangeItemRequest]


class DiffEntryResponse(BaseModel):
    issue_id: str
    impact_description: str
    direction: str


class ScenarioDiffResponse(BaseModel):
    scenario_id: str
    case_id: str
    baseline_run_id: str
    diff_entries: list[DiffEntryResponse]
    affected_issue_ids: list[str]
    affected_evidence_ids: list[str]
    status: str


# ---------------------------------------------------------------------------
# GET /api/cases  (list + filter + paginate)
# ---------------------------------------------------------------------------


class CaseListEntry(BaseModel):
    case_id: str
    status: CaseStatus
    case_type: str
    plaintiff_name: str
    defendant_name: str
    created_at: datetime
    updated_at: datetime
    has_report: bool
    review_status: str = "none"  # v2.5 Phase 3


class CaseListResponse(BaseModel):
    items: list[CaseListEntry]
    total: int
    page: int
    page_size: int


class CaseListQuery(BaseModel):
    status: Optional[CaseStatus] = None
    case_type: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort: str = "-created_at"


# ---------------------------------------------------------------------------
# GET /api/cases/{case_id}/events  (v2.5 Phase 2: audit trail)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Review models (v2.5 Phase 3: human review workflow)
# ---------------------------------------------------------------------------


class ReviewStatus(str, Enum):
    none = "none"
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"
    revision_requested = "revision_requested"


class SectionFlag(BaseModel):
    section_key: str  # e.g. "overall_assessment", "issue.issue-001"
    flag: str  # "approved" | "flagged" | "needs_revision"
    comment: Optional[str] = None


class ReviewRequest(BaseModel):
    action: ReviewStatus  # pending_review / approved / rejected / revision_requested
    comment: Optional[str] = None
    section_flags: list[SectionFlag] = Field(default_factory=list)


class ReviewResponse(BaseModel):
    review_id: str
    case_id: str
    action: ReviewStatus
    reviewer_id: str  # Phase 4 前固定为 "anonymous"
    comment: Optional[str]
    section_flags: list[SectionFlag]
    created_at: datetime


class ReviewListResponse(BaseModel):
    case_id: str
    current_review_status: ReviewStatus
    reviews: list[ReviewResponse]


# ---------------------------------------------------------------------------
# GET /api/cases/{case_id}/events  (v2.5 Phase 2: audit trail)
# ---------------------------------------------------------------------------


class CaseEventResponse(BaseModel):
    event_id: str
    event_type: str
    actor_id: str
    payload: dict
    created_at: datetime


class CaseEventsResponse(BaseModel):
    case_id: str
    events: list[CaseEventResponse]
    count: int
