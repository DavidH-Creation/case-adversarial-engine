"""
案件内存索引 — 启动时扫描磁盘重建，运行时同步更新。
In-memory case index — rebuilt from disk on startup, kept in sync at runtime.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import TypedDict

logger = logging.getLogger(__name__)


class CaseIndexEntry(TypedDict):
    case_id: str
    status: str
    case_type: str
    plaintiff_name: str
    defendant_name: str
    created_at: str  # ISO8601
    updated_at: str  # ISO8601
    has_report: bool
    review_status: str  # ReviewStatus.value — "none" by default


class CaseIndex:
    """In-memory case index.

    Rebuilt on startup via scan_from_disk(); kept current by upsert() calls
    from CaseStore.create() / save_to_disk().  Thread-safe.
    """

    def __init__(self) -> None:
        self._entries: dict[str, CaseIndexEntry] = {}
        self._lock = Lock()

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def upsert(self, entry: CaseIndexEntry) -> None:
        with self._lock:
            self._entries[entry["case_id"]] = entry

    def remove(self, case_id: str) -> None:
        with self._lock:
            self._entries.pop(case_id, None)

    # ------------------------------------------------------------------
    # Disk scan (startup rebuild)
    # ------------------------------------------------------------------

    def scan_from_disk(self, workspaces_dir: Path) -> int:
        """Walk workspaces_dir/*/case_meta.json and rebuild the index.

        Returns the number of cases successfully indexed.
        Individual failures are logged as warnings and skipped.
        """
        count = 0
        if not workspaces_dir.exists():
            return 0
        for child in sorted(workspaces_dir.iterdir()):
            meta_path = child / "case_meta.json"
            if not meta_path.is_file():
                continue
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                entry = _meta_to_index_entry(meta)
                self.upsert(entry)
                count += 1
            except Exception:
                logger.warning("Skipping invalid case_meta at %s", meta_path, exc_info=True)
        return count

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        status: str | None,
        case_type: str | None,
        from_date: datetime | None,
        to_date: datetime | None,
        page: int,
        page_size: int,
        sort: str,
    ) -> tuple[list[CaseIndexEntry], int]:
        """Filter, sort, and paginate the index.

        Returns (page_entries, total_matching).
        sort: field name optionally prefixed with '-' for descending.
        Supported fields: created_at, updated_at, status.
        """
        with self._lock:
            items = list(self._entries.values())

        # -- Filter --
        if status is not None:
            items = [e for e in items if e["status"] == status]
        if case_type is not None:
            items = [e for e in items if e["case_type"] == case_type]
        if from_date is not None:
            items = [e for e in items if _parse_iso(e["created_at"]) >= from_date]
        if to_date is not None:
            items = [e for e in items if _parse_iso(e["created_at"]) <= to_date]

        total = len(items)

        # -- Sort --
        descending = sort.startswith("-")
        field = sort.lstrip("-")
        if field not in ("created_at", "updated_at", "status"):
            field = "created_at"
        items.sort(key=lambda e: str(e.get(field, "")), reverse=descending)

        # -- Paginate --
        start = (page - 1) * page_size
        end = start + page_size
        return items[start:end], total


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_iso(s: str) -> datetime:
    """Parse an ISO8601 string, normalizing 'Z' to '+00:00'."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _meta_to_index_entry(meta: dict) -> CaseIndexEntry:
    """Convert a case_meta.json dict to a CaseIndexEntry."""
    info = meta.get("info", {})
    artifact_names = meta.get("artifact_names", [])
    return CaseIndexEntry(
        case_id=meta["case_id"],
        status=meta.get("status", "created"),
        case_type=info.get("case_type", ""),
        plaintiff_name=info.get("plaintiff", {}).get("name", ""),
        defendant_name=info.get("defendant", {}).get("name", ""),
        created_at=meta.get("created_at", ""),
        updated_at=meta.get("updated_at", ""),
        has_report="report.docx" in artifact_names,
        review_status=meta.get("review_status", "none"),
    )
