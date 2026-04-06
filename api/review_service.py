"""
Review service — stores and retrieves human review records.
v2.5 Phase 3: per-case review workflow with disk persistence.

Disk layout: {workspace_dir}/{case_id}/reviews/{review_id}.json
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from .schemas import ReviewStatus, SectionFlag

logger = logging.getLogger(__name__)


class ReviewRecord(BaseModel):
    review_id: str = Field(default_factory=lambda: f"rev-{uuid.uuid4().hex[:12]}")
    case_id: str
    action: ReviewStatus
    reviewer_id: str = "anonymous"
    comment: Optional[str] = None
    section_flags: list[SectionFlag] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReviewStore:
    """Per-case review records, persisted to {workspace_dir}/{case_id}/reviews/{review_id}.json.

    ReviewStore only handles read/write; the current review_status lives on CaseRecord.
    """

    def save(self, workspace_manager, record: ReviewRecord) -> None:
        """Persist a single review record to disk."""
        reviews_dir = workspace_manager.workspace_dir / "reviews"
        reviews_dir.mkdir(parents=True, exist_ok=True)
        path = reviews_dir / f"{record.review_id}.json"
        data = record.model_dump(mode="json")
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_all(self, workspace_manager, case_id: str) -> list[ReviewRecord]:
        """Load all review records for a case, sorted by created_at ascending."""
        reviews_dir = workspace_manager.workspace_dir / "reviews"
        if not reviews_dir.exists():
            return []
        records: list[ReviewRecord] = []
        for path in sorted(reviews_dir.glob("rev-*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                records.append(ReviewRecord.model_validate(data))
            except Exception:
                logger.warning("Skipping invalid review file: %s", path, exc_info=True)
        records.sort(key=lambda r: r.created_at)
        return records

    def load_one(self, workspace_manager, review_id: str) -> Optional[ReviewRecord]:
        """Load a single review record by ID."""
        reviews_dir = workspace_manager.workspace_dir / "reviews"
        path = reviews_dir / f"{review_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ReviewRecord.model_validate(data)
        except Exception:
            logger.warning("Failed to load review %s", review_id, exc_info=True)
            return None


# Global singleton
review_store = ReviewStore()
