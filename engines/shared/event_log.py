"""
Append-only JSONL event log for case audit trails.

Storage path: {workspace_dir}/{case_id}/events.jsonl
Each line is one JSON object (CaseEvent.model_dump(mode='json')).

Thread-safety: per-instance threading.Lock protects append.
open(path, 'a') is NOT atomic on Windows — explicit Lock required.
Single-process deployment; instance-level lock is sufficient.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class EventType(str, Enum):
    case_created = "case_created"
    material_added = "material_added"
    extraction_started = "extraction_started"
    extraction_done = "extraction_done"
    extraction_failed = "extraction_failed"
    confirmed = "confirmed"
    analysis_started = "analysis_started"
    analysis_done = "analysis_done"
    analysis_failed = "analysis_failed"
    review_submitted = "review_submitted"  # Phase 3
    exported = "exported"  # Phase 5


class CaseEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:12]}")
    case_id: str
    event_type: EventType
    actor_id: str = "system"  # Phase 4: real user_id
    payload: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EventLog:
    """Thread-safe append-only JSONL event log.

    Storage: {workspace_dir}/{case_id}/events.jsonl
    """

    def __init__(self, workspace_dir: Path, case_id: str) -> None:
        self._path = workspace_dir / case_id / "events.jsonl"
        self._lock = threading.Lock()

    def append(self, event: CaseEvent) -> None:
        """Thread-safe append. Never overwrites existing lines."""
        line = json.dumps(event.model_dump(mode="json"), ensure_ascii=False) + "\n"
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line)

    def load_all(self) -> list[CaseEvent]:
        """Return all events ordered by created_at ascending."""
        if not self._path.exists():
            return []
        events: list[CaseEvent] = []
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                events.append(CaseEvent.model_validate(json.loads(line)))
        events.sort(key=lambda e: e.created_at)
        return events

    def load_since(self, after_event_id: str) -> list[CaseEvent]:
        """Return events after the given event_id (for incremental polling).

        If after_event_id is not found, returns all events.
        """
        all_events = self.load_all()
        for i, ev in enumerate(all_events):
            if ev.event_id == after_event_id:
                return all_events[i + 1 :]
        return all_events
