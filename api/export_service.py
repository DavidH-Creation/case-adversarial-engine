"""
导出服务 — 单案件 JSON / Markdown 导出 + 多案件 ZIP 打包（Phase 5）。
CaseExporter: export_json, export_markdown, export_bulk_zip.
"""

from __future__ import annotations

import io
import json
import logging
import zipfile
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from .review_service import ReviewStore
from .schemas import CaseStatus

logger = logging.getLogger(__name__)


class ExportFormat(str, Enum):
    json = "json"
    docx = "docx"
    markdown = "markdown"


class CaseExporter:
    """Assembles structured export data from CaseStore + ReviewStore."""

    def __init__(self, store: Any, review_store: ReviewStore) -> None:
        self._store = store
        self._review_store = review_store

    def export_json(self, case_id: str) -> Optional[dict]:
        """Assemble full case JSON snapshot. Returns None if case not found."""
        record = self._store.get(case_id)
        if record is None:
            return None

        info = record.info
        # Build materials summary (counts only, no raw text)
        materials_summary = {
            role: len(mats)
            for role, mats in record.materials.items()
        }

        # Load events
        events: list[dict] = []
        if record.workspace_manager is not None:
            try:
                raw_events = record.workspace_manager.load_events()
                events = [e.model_dump(mode="json") for e in raw_events]
            except Exception:
                logger.warning("Failed to load events for case %s", case_id)

        # Load reviews
        reviews: list[dict] = []
        if record.workspace_manager is not None:
            try:
                raw_reviews = self._review_store.load_all(
                    record.workspace_manager, case_id
                )
                reviews = [r.model_dump(mode="json") for r in raw_reviews]
            except Exception:
                logger.warning("Failed to load reviews for case %s", case_id)

        # Extraction data
        evidence = (record.extraction_data or {}).get("evidence", [])
        issues = (record.extraction_data or {}).get("issues", [])

        # Claims and defenses from info
        claims = info.get("claims", [])
        defenses = info.get("defenses", [])

        # Parties
        parties = {}
        if "plaintiff" in info:
            parties["plaintiff"] = info["plaintiff"]
        if "defendant" in info:
            parties["defendant"] = info["defendant"]

        return {
            "export_version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "case_id": case_id,
            "case_type": info.get("case_type", ""),
            "status": record.status.value,
            "review_status": record.review_status.value,
            "parties": parties,
            "claims": claims,
            "defenses": defenses,
            "evidence": evidence,
            "issues": issues,
            "analysis_data": record.analysis_data,
            "materials_summary": materials_summary,
            "events": events,
            "reviews": reviews,
        }

    def export_markdown(self, case_id: str) -> Optional[str]:
        """Return report.md content, or None if not available."""
        record = self._store.get(case_id)
        if record is None:
            return None
        return record.report_markdown

    def export_bulk_zip(
        self,
        case_ids: list[str],
        fmt: ExportFormat,
    ) -> bytes:
        """Pack multiple cases into a ZIP in memory. Skips missing cases."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for cid in case_ids:
                if fmt == ExportFormat.json:
                    data = self.export_json(cid)
                    if data is None:
                        continue
                    content = json.dumps(data, ensure_ascii=False, indent=2)
                    zf.writestr(f"export_{ts}/{cid}/{cid}.json", content)
                elif fmt == ExportFormat.markdown:
                    md = self.export_markdown(cid)
                    if md is None:
                        continue
                    zf.writestr(f"export_{ts}/{cid}/{cid}.md", md)
                elif fmt == ExportFormat.docx:
                    record = self._store.get(cid)
                    if record is None or record.report_path is None:
                        continue
                    if not record.report_path.exists():
                        continue
                    zf.write(
                        str(record.report_path),
                        f"export_{ts}/{cid}/{cid}.docx",
                    )
        return buf.getvalue()
