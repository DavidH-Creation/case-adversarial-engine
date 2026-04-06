"""
CaseIndex 单元测试。
Unit tests for CaseIndex: scan_from_disk, upsert, remove, query (filter/sort/pagination).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from api.case_index import CaseIndex, CaseIndexEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_case_meta(tmp_path, case_id: str, *, status: str = "analyzed",
                     case_type: str = "civil_loan",
                     plaintiff_name: str = "张三",
                     defendant_name: str = "李四",
                     created_at: str = "2026-04-01T00:00:00Z",
                     updated_at: str = "2026-04-01T01:00:00Z",
                     artifact_names: list | None = None):
    d = tmp_path / case_id
    d.mkdir(exist_ok=True)
    meta = {
        "case_id": case_id,
        "status": status,
        "info": {
            "case_type": case_type,
            "plaintiff": {"name": plaintiff_name},
            "defendant": {"name": defendant_name},
        },
        "created_at": created_at,
        "updated_at": updated_at,
        "artifact_names": artifact_names or [],
    }
    (d / "case_meta.json").write_text(json.dumps(meta), encoding="utf-8")


# ---------------------------------------------------------------------------
# scan_from_disk
# ---------------------------------------------------------------------------


def test_scan_from_disk_rebuilds_entries(tmp_path):
    """Scan two case_meta.json files and rebuild the in-memory index."""
    for cid in ["case-aaa", "case-bbb"]:
        _write_case_meta(tmp_path, cid, artifact_names=["report.docx"])

    idx = CaseIndex()
    n = idx.scan_from_disk(tmp_path)
    assert n == 2
    entries, total = idx.query(None, None, None, None, 1, 20, "-created_at")
    assert total == 2
    assert {e["case_id"] for e in entries} == {"case-aaa", "case-bbb"}


def test_scan_from_disk_skips_invalid(tmp_path):
    """Invalid case_meta.json should be skipped, not crash the scan."""
    _write_case_meta(tmp_path, "case-good")
    bad_dir = tmp_path / "case-bad"
    bad_dir.mkdir()
    (bad_dir / "case_meta.json").write_text("{invalid json", encoding="utf-8")

    idx = CaseIndex()
    n = idx.scan_from_disk(tmp_path)
    assert n == 1


def test_scan_from_disk_empty_dir(tmp_path):
    idx = CaseIndex()
    assert idx.scan_from_disk(tmp_path) == 0


def test_scan_has_report_detection(tmp_path):
    """has_report is True when artifact_names contains report.docx."""
    _write_case_meta(tmp_path, "case-with-report", artifact_names=["report.docx"])
    _write_case_meta(tmp_path, "case-no-report", artifact_names=[])

    idx = CaseIndex()
    idx.scan_from_disk(tmp_path)
    entries, _ = idx.query(None, None, None, None, 1, 20, "-created_at")
    by_id = {e["case_id"]: e for e in entries}
    assert by_id["case-with-report"]["has_report"] is True
    assert by_id["case-no-report"]["has_report"] is False


# ---------------------------------------------------------------------------
# upsert / remove
# ---------------------------------------------------------------------------


def test_upsert_and_remove():
    idx = CaseIndex()
    entry: CaseIndexEntry = {
        "case_id": "case-001",
        "status": "created",
        "case_type": "civil_loan",
        "plaintiff_name": "A",
        "defendant_name": "B",
        "created_at": "2026-04-01T00:00:00Z",
        "updated_at": "2026-04-01T00:00:00Z",
        "has_report": False,
    }
    idx.upsert(entry)
    _, total = idx.query(None, None, None, None, 1, 20, "-created_at")
    assert total == 1

    idx.remove("case-001")
    _, total = idx.query(None, None, None, None, 1, 20, "-created_at")
    assert total == 0


def test_upsert_overwrites():
    idx = CaseIndex()
    entry: CaseIndexEntry = {
        "case_id": "case-001",
        "status": "created",
        "case_type": "civil_loan",
        "plaintiff_name": "A",
        "defendant_name": "B",
        "created_at": "2026-04-01T00:00:00Z",
        "updated_at": "2026-04-01T00:00:00Z",
        "has_report": False,
    }
    idx.upsert(entry)
    updated = {**entry, "status": "analyzed", "has_report": True}
    idx.upsert(updated)

    entries, total = idx.query(None, None, None, None, 1, 20, "-created_at")
    assert total == 1
    assert entries[0]["status"] == "analyzed"
    assert entries[0]["has_report"] is True


# ---------------------------------------------------------------------------
# query — filtering
# ---------------------------------------------------------------------------


def _seed_index() -> CaseIndex:
    """Create an index with 5 cases for filter/sort/pagination tests."""
    idx = CaseIndex()
    cases = [
        ("case-1", "created",   "civil_loan",    "2026-04-01T00:00:00Z"),
        ("case-2", "analyzed",  "civil_loan",    "2026-04-02T00:00:00Z"),
        ("case-3", "analyzed",  "criminal",      "2026-04-03T00:00:00Z"),
        ("case-4", "extracting","civil_loan",    "2026-04-04T00:00:00Z"),
        ("case-5", "created",   "contract",      "2026-04-05T00:00:00Z"),
    ]
    for cid, status, ctype, ts in cases:
        idx.upsert({
            "case_id": cid,
            "status": status,
            "case_type": ctype,
            "plaintiff_name": "P",
            "defendant_name": "D",
            "created_at": ts,
            "updated_at": ts,
            "has_report": status == "analyzed",
        })
    return idx


def test_query_filter_by_status():
    idx = _seed_index()
    entries, total = idx.query("analyzed", None, None, None, 1, 20, "-created_at")
    assert total == 2
    assert all(e["status"] == "analyzed" for e in entries)


def test_query_filter_by_case_type():
    idx = _seed_index()
    entries, total = idx.query(None, "civil_loan", None, None, 1, 20, "-created_at")
    assert total == 3
    assert all(e["case_type"] == "civil_loan" for e in entries)


def test_query_filter_by_date_range():
    idx = _seed_index()
    from_dt = datetime(2026, 4, 2, tzinfo=timezone.utc)
    to_dt = datetime(2026, 4, 4, tzinfo=timezone.utc)
    entries, total = idx.query(None, None, from_dt, to_dt, 1, 20, "-created_at")
    assert total == 3  # case-2, case-3, case-4
    ids = {e["case_id"] for e in entries}
    assert ids == {"case-2", "case-3", "case-4"}


def test_query_combined_filters():
    idx = _seed_index()
    entries, total = idx.query("analyzed", "civil_loan", None, None, 1, 20, "-created_at")
    assert total == 1
    assert entries[0]["case_id"] == "case-2"


# ---------------------------------------------------------------------------
# query — sorting
# ---------------------------------------------------------------------------


def test_query_sort_created_at_desc():
    idx = _seed_index()
    entries, _ = idx.query(None, None, None, None, 1, 20, "-created_at")
    dates = [e["created_at"] for e in entries]
    assert dates == sorted(dates, reverse=True)


def test_query_sort_created_at_asc():
    idx = _seed_index()
    entries, _ = idx.query(None, None, None, None, 1, 20, "created_at")
    dates = [e["created_at"] for e in entries]
    assert dates == sorted(dates)


def test_query_sort_status():
    idx = _seed_index()
    entries, _ = idx.query(None, None, None, None, 1, 20, "status")
    statuses = [e["status"] for e in entries]
    assert statuses == sorted(statuses)


# ---------------------------------------------------------------------------
# query — pagination
# ---------------------------------------------------------------------------


def test_query_pagination():
    idx = _seed_index()  # 5 entries

    # Page 1: 2 items
    entries_p1, total = idx.query(None, None, None, None, 1, 2, "-created_at")
    assert total == 5
    assert len(entries_p1) == 2

    # Page 2: 2 items
    entries_p2, total = idx.query(None, None, None, None, 2, 2, "-created_at")
    assert total == 5
    assert len(entries_p2) == 2

    # Page 3: 1 item
    entries_p3, total = idx.query(None, None, None, None, 3, 2, "-created_at")
    assert total == 5
    assert len(entries_p3) == 1

    # No overlap
    all_ids = [e["case_id"] for e in entries_p1 + entries_p2 + entries_p3]
    assert len(set(all_ids)) == 5


def test_query_page_beyond_total():
    idx = _seed_index()
    entries, total = idx.query(None, None, None, None, 100, 20, "-created_at")
    assert total == 5
    assert len(entries) == 0
