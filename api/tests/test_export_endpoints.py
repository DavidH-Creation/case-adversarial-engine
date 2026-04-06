"""Tests for Phase 5: export endpoints (JSON, markdown, bulk ZIP)."""

import io
import zipfile

import pytest


class TestSingleCaseJsonExport:
    """GET /api/cases/{case_id}/export?format=json"""

    def test_export_json_analyzed_case(self, client, analyzed_case_id):
        resp = client.get(f"/api/cases/{analyzed_case_id}/export?format=json")
        assert resp.status_code == 200
        body = resp.json()
        assert body["case_id"] == analyzed_case_id
        assert body["export_version"] == "1.0"
        assert "evidence" in body
        assert "issues" in body
        assert "analysis_data" in body
        assert "events" in body
        assert "reviews" in body
        assert "materials_summary" in body
        assert "parties" in body

    def test_export_json_unanalyzed_case(self, client, created_case_id):
        """Created (unanalyzed) case should still export — analysis_data will be null."""
        resp = client.get(f"/api/cases/{created_case_id}/export?format=json")
        assert resp.status_code == 200
        body = resp.json()
        assert body["analysis_data"] is None

    def test_export_json_nonexistent_case(self, client):
        resp = client.get("/api/cases/case-nonexistent/export?format=json")
        assert resp.status_code == 404

    def test_export_json_has_content_disposition(self, client, analyzed_case_id):
        resp = client.get(f"/api/cases/{analyzed_case_id}/export?format=json")
        assert resp.status_code == 200
        cd = resp.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert analyzed_case_id in cd


class TestSingleCaseMarkdownExport:
    """GET /api/cases/{case_id}/export?format=markdown"""

    def test_export_markdown_with_report(self, client, analyzed_case_id):
        # Set up a markdown report on the record
        from api.service import store

        record = store.get(analyzed_case_id)
        record.report_markdown = "# 测试报告\n内容"
        resp = client.get(f"/api/cases/{analyzed_case_id}/export?format=markdown")
        assert resp.status_code == 200
        assert "测试报告" in resp.text

    def test_export_markdown_no_report(self, client, created_case_id):
        resp = client.get(f"/api/cases/{created_case_id}/export?format=markdown")
        assert resp.status_code == 404


class TestBulkExport:
    """POST /api/cases/export/bulk"""

    def test_bulk_export_zip_json(self, client, analyzed_case_id):
        resp = client.post(
            "/api/cases/export/bulk",
            json={"case_ids": [analyzed_case_id], "format": "json"},
        )
        assert resp.status_code == 200
        assert "application/zip" in resp.headers["content-type"]
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        names = zf.namelist()
        assert any(analyzed_case_id in n for n in names)

    def test_bulk_export_skip_nonexistent(self, client, analyzed_case_id):
        """Nonexistent case_ids are silently skipped."""
        resp = client.post(
            "/api/cases/export/bulk",
            json={
                "case_ids": [analyzed_case_id, "case-nonexistent"],
                "format": "json",
            },
        )
        assert resp.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        names = zf.namelist()
        assert any(analyzed_case_id in n for n in names)
        assert not any("case-nonexistent" in n for n in names)

    def test_bulk_export_empty_list(self, client):
        """Empty case_ids → still returns a valid (empty) ZIP."""
        resp = client.post(
            "/api/cases/export/bulk",
            json={"case_ids": [], "format": "json"},
        )
        assert resp.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        assert len(zf.namelist()) == 0

    def test_bulk_export_over_50_returns_422(self, client):
        """conlist(str, max_length=50) should reject >50 case_ids."""
        case_ids = [f"case-{i:04d}" for i in range(51)]
        resp = client.post(
            "/api/cases/export/bulk",
            json={"case_ids": case_ids, "format": "json"},
        )
        assert resp.status_code == 422


class TestExportEvents:
    """Export operations should emit 'exported' events."""

    def test_json_export_emits_event(self, client, analyzed_case_id):
        client.get(f"/api/cases/{analyzed_case_id}/export?format=json")
        resp = client.get(f"/api/cases/{analyzed_case_id}/events")
        assert resp.status_code == 200
        events = resp.json()["events"]
        exported = [e for e in events if e["event_type"] == "exported"]
        assert len(exported) >= 1
        assert exported[-1]["payload"]["format"] == "json"
