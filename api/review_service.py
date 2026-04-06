"""
Review service — ReviewRecord persistence and retrieval.

Storage: {workspace_dir}/{case_id}/reviews/{review_id}.json (atomic write).
ReviewStore only handles read/write; current review_status lives on CaseRecord.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from engines.shared.workspace_manager import WorkspaceManager

from .schemas import ReviewStatus, SectionFlag


class ReviewRecord(BaseModel):
    review_id: str = Field(default_factory=lambda: f"rev-{uuid.uuid4().hex[:12]}")
    case_id: str
    action: ReviewStatus
    reviewer_id: str = "anonymous"
    comment: Optional[str] = None
    section_flags: list[SectionFlag] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReviewStore:
    """Per-case review records stored under {workspace_dir}/{case_id}/reviews/."""

    def save(self, wm: WorkspaceManager, record: ReviewRecord) -> None:
        reviews_dir = wm.workspace_dir / "reviews"
        reviews_dir.mkdir(parents=True, exist_ok=True)
        target = reviews_dir / f"{record.review_id}.json"
        tmp = target.with_suffix(".tmp")
        data = json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2)
        tmp.write_text(data, encoding="utf-8")
        tmp.replace(target)

    def load_all(self, wm: WorkspaceManager, case_id: str) -> list[ReviewRecord]:
        reviews_dir = wm.workspace_dir / "reviews"
        if not reviews_dir.exists():
            return []
        records: list[ReviewRecord] = []
        for p in sorted(reviews_dir.glob("rev-*.json")):
            try:
                obj = json.loads(p.read_text(encoding="utf-8"))
                records.append(ReviewRecord.model_validate(obj))
            except Exception:
                continue
        records.sort(key=lambda r: r.created_at)
        return records


# Global singleton
review_store = ReviewStore()
