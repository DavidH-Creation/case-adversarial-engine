"""
Export service — structured JSON export + bulk ZIP packaging.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any, Optional

from .review_service import ReviewStore, review_store
from .schemas import CaseSnapshot, ExportFormat


class CaseExporter:
    """Assemble export payloads from CaseStore + ReviewStore."""

    def __init__(self, rs: ReviewStore | None = None) -> None:
        self._review_store = rs or review_store

    def build_snapshot(self, record: Any) -> CaseSnapshot:
        """Build a CaseSnapshot from a live CaseRecord."""
        info = record.info
        events_raw: list[dict] = []
        if record.workspace_manager is not None:
            try:
                raw_events = record.workspace_manager.load_events()
                events_raw = [
                    e.model_dump(mode="json") for e in raw_events
                ]
            except Exception:
                pass

        reviews_raw: list[dict] = []
        if record.workspace_manager is not None:
            try:
                revs = self._review_store.load_all(
                    record.workspace_manager, record.case_id
                )
                reviews_raw = [r.model_dump(mode="json") for r in revs]
            except Exception:
                pass

        evidence: list[dict] = []
        issues: list[dict] = []
        if record.extraction_data is not None:
            evidence = record.extraction_data.get("evidence", [])
            issues = record.extraction_data.get("issues", [])

        return CaseSnapshot(
            exported_at=datetime.now(timezone.utc),
            case_id=record.case_id,
            case_type=info.get("case_type", ""),
            status=record.status,
            review_status=record.review_status.value,
            parties={
                "plaintiff": info.get("plaintiff", {}),
                "defendant": info.get("defendant", {}),
            },
            claims=info.get("claims", []),
            defenses=info.get("defenses", []),
            evidence=evidence,
            issues=issues,
            analysis_data=record.analysis_data,
            materials_summary={
                "plaintiff": len(record.materials.get("plaintiff", [])),
                "defendant": len(record.materials.get("defendant", [])),
            },
            events=events_raw,
            reviews=reviews_raw,
        )

    def export_json(self, record: Any) -> dict:
        """Return the CaseSnapshot as a plain dict."""
        return self.build_snapshot(record).model_dump(mode="json")

    def export_bulk_zip(
        self,
        records: list[Any],
        fmt: ExportFormat = ExportFormat.json,
    ) -> bytes:
        """Package multiple cases into an in-memory ZIP.

        Nonexistent / None records should be filtered out before calling.
        """
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for record in records:
                cid = record.case_id
                prefix = f"export_{ts}/{cid}/"
                if fmt == ExportFormat.json:
                    snapshot = self.export_json(record)
                    data = json.dumps(snapshot, ensure_ascii=False, indent=2)
                    zf.writestr(f"{prefix}{cid}.json", data)
                elif fmt == ExportFormat.markdown:
                    md = record.report_markdown or ""
                    if md:
                        zf.writestr(f"{prefix}{cid}.md", md)
                elif fmt == ExportFormat.docx:
                    if record.report_path is not None and record.report_path.exists():
                        zf.write(
                            str(record.report_path),
                            f"{prefix}{cid}.docx",
                        )
        return buf.getvalue()


# Global singleton
case_exporter = CaseExporter()
