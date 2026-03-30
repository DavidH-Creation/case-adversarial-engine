"""
API 请求/响应模型 — 基于现有 Pydantic 模型，独立于引擎内部结构。
API request/response models — independent from internal engine schemas.
"""
from __future__ import annotations

import uuid
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
    overall_assessment: Optional[str] = None
    plaintiff_args: list[dict[str, Any]] = Field(default_factory=list)
    defendant_defenses: list[dict[str, Any]] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)
    evidence_conflicts: list[dict[str, Any]] = Field(default_factory=list)
    rounds: list[dict[str, Any]] = Field(default_factory=list)
