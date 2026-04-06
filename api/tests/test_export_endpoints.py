"""Phase 5: Export endpoint tests — single JSON, markdown, bulk ZIP."""

import io
import zipfile

import pytest


def test_export_json_analyzed_case(client, analyzed_case_id):
    """GET /api/cases/{id}/export?format=json returns full case snapshot."""
    resp = client.get(f"/api/cases/{analyzed_case_id}/export?format=json")
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_id"] == analyzed_case_id
    assert body["export_version"] == "1.0"
    assert "exported_at" in body
    assert "evidence" in body
    assert "issues" in body
    assert "analysis_data" in body
    assert "parties" in body
    assert "materials_summary" in body
    assert "events" in body
    assert "reviews" in body


def test_export_json_not_found(client):
    """GET /api/cases/nonexistent/export?format=json returns 404."""
    resp = client.get("/api/cases/case-nonexistent/export?format=json")
    assert resp.status_code == 404


def test_export_markdown_no_report(client, analyzed_case_id):
    """GET /api/cases/{id}/export?format=markdown returns 404 if no report."""
    resp = client.get(f"/api/cases/{analyzed_case_id}/export?format=markdown")
    assert resp.status_code == 404


def test_export_markdown_with_report(client, analyzed_case_id):
    """GET /api/cases/{id}/export?format=markdown returns report.md content."""
    from api.service import store

    record = store.get(analyzed_case_id)
    record.report_markdown = "# 测试报告\n\n这是测试内容。"

    resp = client.get(f"/api/cases/{analyzed_case_id}/export?format=markdown")
    assert resp.status_code == 200
    assert "测试报告" in resp.text


def test_export_event_logged(client, analyzed_case_id):
    """Exporting a case emits an 'exported' event."""
    client.get(f"/api/cases/{analyzed_case_id}/export?format=json")
    resp = client.get(f"/api/cases/{analyzed_case_id}/events")
    assert resp.status_code == 200
    events = resp.json()["events"]
    exported = [e for e in events if e["event_type"] == "exported"]
    assert len(exported) >= 1
    assert exported[-1]["payload"]["format"] == "json"


def test_bulk_export_zip(client, analyzed_case_id):
    """POST /api/export/bulk returns valid ZIP with case data."""
    resp = client.post(
        "/api/export/bulk",
        json={"case_ids": [analyzed_case_id], "format": "json"},
    )
    assert resp.status_code == 200
    assert "application/zip" in resp.headers.get("content-type", "")
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    assert any(analyzed_case_id in n for n in names)


def test_bulk_export_skips_missing(client, analyzed_case_id):
    """Bulk export skips non-existent case_ids without error."""
    resp = client.post(
        "/api/export/bulk",
        json={"case_ids": [analyzed_case_id, "case-nonexistent"], "format": "json"},
    )
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    assert any(analyzed_case_id in n for n in names)
    assert not any("nonexistent" in n for n in names)


def test_bulk_export_over_50_rejected(client):
    """Bulk export with >50 case_ids returns 422."""
    ids = [f"case-{i:012d}" for i in range(51)]
    resp = client.post(
        "/api/export/bulk",
        json={"case_ids": ids, "format": "json"},
    )
    assert resp.status_code == 422


def test_bulk_export_empty_list(client):
    """Bulk export with empty list returns valid empty ZIP."""
    resp = client.post(
        "/api/export/bulk",
        json={"case_ids": [], "format": "json"},
    )
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    assert len(zf.namelist()) == 0
