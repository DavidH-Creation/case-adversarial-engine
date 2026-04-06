"""
Unit 15+17: Web API Enhancement endpoint tests.

Tests for:
  GET  /api/cases/{case_id}/result       — full analysis result
  POST /api/cases/{case_id}/followup     — 202 async followup Q&A
  GET  /api/cases/{case_id}/followup/{job_id} — followup result
  GET  /api/cases/{case_id}/artifacts/{name}  — artifact download (existing)
  CORS middleware presence

Test matrix per endpoint:
- Happy path: correct status code + schema
- Invalid input: 422
- Missing resource: 404
- Wrong state: 400
- Followup: 202 async flow
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.schemas import CaseStatus, FollowupStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _minimal_case_payload():
    return {
        "case_type": "civil_loan",
        "plaintiff": {"name": "张三"},
        "defendant": {"name": "李四"},
        "claims": [],
        "defenses": [],
    }


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient with isolated workspace dir, no auth required."""
    monkeypatch.delenv("API_SECRET_KEY", raising=False)
    monkeypatch.delenv("USERS_FILE", raising=False)
    with patch("api.service._WORKSPACE_BASE", tmp_path):
        from api.app import app

        with TestClient(app) as c:
            yield c


def _setup_analyzed_case(client) -> str:
    """Create a case and force it to 'analyzed' state."""
    resp = client.post("/api/cases/", json=_minimal_case_payload())
    assert resp.status_code == 201
    case_id = resp.json()["case_id"]

    from api.service import store

    record = store.get(case_id)
    record.status = CaseStatus.analyzed
    record.analysis_data = {
        "run_id": "run-test001",
        "overall_assessment": "测试评估结论",
        "rounds": [],
    }
    record.run_id = "run-test001"
    record.artifacts["analysis_summary.json"] = record.analysis_data
    record.artifacts["report.md"] = "# 测试报告"
    record.report_markdown = "# 测试报告"
    return case_id


# ---------------------------------------------------------------------------
# GET /api/cases/{case_id}/result
# ---------------------------------------------------------------------------


class TestGetCaseResult:
    """GET /api/cases/{case_id}/result — full analysis result."""

    def test_returns_result_for_analyzed_case(self, client) -> None:
        case_id = _setup_analyzed_case(client)
        resp = client.get(f"/api/cases/{case_id}/result")
        assert resp.status_code == 200
        body = resp.json()
        assert body["case_id"] == case_id
        assert body["run_id"] == "run-test001"
        assert body["status"] == "analyzed"
        assert body["analysis_data"] is not None
        assert isinstance(body["artifacts"], list)

    def test_returns_result_for_created_case(self, client) -> None:
        """Even non-analyzed cases return result (with null analysis_data)."""
        resp = client.post("/api/cases/", json=_minimal_case_payload())
        case_id = resp.json()["case_id"]
        resp = client.get(f"/api/cases/{case_id}/result")
        assert resp.status_code == 200
        body = resp.json()
        assert body["analysis_data"] is None
        assert body["artifacts"] == []

    def test_404_for_unknown_case(self, client) -> None:
        resp = client.get("/api/cases/case-nonexistent/result")
        assert resp.status_code == 404

    def test_result_includes_artifact_names(self, client) -> None:
        case_id = _setup_analyzed_case(client)
        resp = client.get(f"/api/cases/{case_id}/result")
        body = resp.json()
        assert "analysis_summary.json" in body["artifacts"]
        assert "report.md" in body["artifacts"]


# ---------------------------------------------------------------------------
# GET /api/cases/{case_id}/artifacts/{name}
# ---------------------------------------------------------------------------


class TestGetCaseArtifact:
    """GET /api/cases/{case_id}/artifacts/{name} — download specific artifact."""

    def test_returns_json_artifact(self, client) -> None:
        case_id = _setup_analyzed_case(client)
        resp = client.get(f"/api/cases/{case_id}/artifacts/analysis_summary.json")
        assert resp.status_code == 200
        body = resp.json()
        assert body["overall_assessment"] == "测试评估结论"

    def test_returns_markdown_artifact(self, client) -> None:
        case_id = _setup_analyzed_case(client)
        resp = client.get(f"/api/cases/{case_id}/artifacts/report.md")
        assert resp.status_code == 200

    def test_404_for_missing_artifact(self, client) -> None:
        case_id = _setup_analyzed_case(client)
        resp = client.get(f"/api/cases/{case_id}/artifacts/nonexistent.json")
        assert resp.status_code == 404

    def test_404_for_unknown_case(self, client) -> None:
        resp = client.get("/api/cases/case-nonexistent/artifacts/test.json")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/cases/{case_id}/followup
# ---------------------------------------------------------------------------


class TestCreateFollowup:
    """POST /api/cases/{case_id}/followup — async 202 followup."""

    def test_returns_202_with_job_id(self, client) -> None:
        case_id = _setup_analyzed_case(client)

        # Mock the actual async task to avoid LLM calls
        with patch("api.service.FollowupJobManager._run_followup", new_callable=AsyncMock):
            resp = client.post(
                f"/api/cases/{case_id}/followup",
                json={"question": "这个案件的关键争点是什么？"},
            )

        assert resp.status_code == 202
        body = resp.json()
        assert "job_id" in body
        assert body["case_id"] == case_id
        assert body["status"] == "pending"

    def test_400_for_non_analyzed_case(self, client) -> None:
        resp = client.post("/api/cases/", json=_minimal_case_payload())
        case_id = resp.json()["case_id"]

        resp = client.post(
            f"/api/cases/{case_id}/followup",
            json={"question": "问题"},
        )
        assert resp.status_code == 400

    def test_404_for_unknown_case(self, client) -> None:
        resp = client.post(
            "/api/cases/case-nonexistent/followup",
            json={"question": "问题"},
        )
        assert resp.status_code == 404

    def test_422_for_empty_question(self, client) -> None:
        case_id = _setup_analyzed_case(client)
        resp = client.post(
            f"/api/cases/{case_id}/followup",
            json={"question": ""},
        )
        assert resp.status_code == 422

    def test_422_for_missing_question(self, client) -> None:
        case_id = _setup_analyzed_case(client)
        resp = client.post(
            f"/api/cases/{case_id}/followup",
            json={},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/cases/{case_id}/followup/{job_id}
# ---------------------------------------------------------------------------


class TestGetFollowupResult:
    """GET /api/cases/{case_id}/followup/{job_id} — poll followup result."""

    def test_returns_pending_job(self, client) -> None:
        case_id = _setup_analyzed_case(client)

        # Submit job but mock the async runner so it stays pending
        with patch("api.service.FollowupJobManager._run_followup", new_callable=AsyncMock):
            resp = client.post(
                f"/api/cases/{case_id}/followup",
                json={"question": "测试问题"},
            )
        job_id = resp.json()["job_id"]

        resp = client.get(f"/api/cases/{case_id}/followup/{job_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["job_id"] == job_id
        assert body["case_id"] == case_id
        assert body["status"] in ("pending", "running", "completed", "failed")

    def test_returns_completed_job(self, client) -> None:
        """Simulate a completed followup job and verify the result schema."""
        case_id = _setup_analyzed_case(client)

        # Directly populate job manager with a completed job
        from api.service import followup_job_manager

        job_id = "followup-test-done001"
        followup_job_manager._jobs[job_id] = {
            "job_id": job_id,
            "case_id": case_id,
            "status": FollowupStatus.completed.value,
            "session_id": "session-test001",
            "answer": "关键争点是借款合同效力。",
            "issue_ids": ["issue-001"],
            "evidence_ids": ["ev-001"],
            "statement_class": "inference",
            "error": None,
        }

        resp = client.get(f"/api/cases/{case_id}/followup/{job_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["answer"] == "关键争点是借款合同效力。"
        assert body["issue_ids"] == ["issue-001"]
        assert body["evidence_ids"] == ["ev-001"]
        assert body["statement_class"] == "inference"
        assert body["session_id"] == "session-test001"

    def test_returns_failed_job(self, client) -> None:
        """Failed jobs should include error message."""
        case_id = _setup_analyzed_case(client)

        from api.service import followup_job_manager

        job_id = "followup-test-fail001"
        followup_job_manager._jobs[job_id] = {
            "job_id": job_id,
            "case_id": case_id,
            "status": FollowupStatus.failed.value,
            "session_id": None,
            "answer": None,
            "issue_ids": [],
            "evidence_ids": [],
            "statement_class": None,
            "error": "LLM call timed out",
        }

        resp = client.get(f"/api/cases/{case_id}/followup/{job_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"
        assert body["error"] == "LLM call timed out"

    def test_404_for_unknown_job_id(self, client) -> None:
        case_id = _setup_analyzed_case(client)
        resp = client.get(f"/api/cases/{case_id}/followup/followup-nonexistent")
        assert resp.status_code == 404

    def test_404_for_job_on_wrong_case(self, client) -> None:
        """A job belonging to case A should not be accessible via case B."""
        case_id_a = _setup_analyzed_case(client)

        from api.service import followup_job_manager

        job_id = "followup-test-cross001"
        followup_job_manager._jobs[job_id] = {
            "job_id": job_id,
            "case_id": case_id_a,
            "status": FollowupStatus.completed.value,
            "session_id": None,
            "answer": "答案",
            "issue_ids": [],
            "evidence_ids": [],
            "statement_class": "inference",
            "error": None,
        }

        # Create a different case
        resp = client.post("/api/cases/", json=_minimal_case_payload())
        case_id_b = resp.json()["case_id"]

        resp = client.get(f"/api/cases/{case_id_b}/followup/{job_id}")
        assert resp.status_code == 404

    def test_404_for_unknown_case(self, client) -> None:
        resp = client.get("/api/cases/case-nonexistent/followup/followup-test001")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------


class TestCORSMiddleware:
    """CORS headers should be present on responses."""

    def test_cors_headers_on_preflight(self, client) -> None:
        resp = client.options(
            "/api/cases/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        # CORSMiddleware echoes the requesting origin when allow_origins=["*"]
        assert "access-control-allow-origin" in resp.headers

    def test_cors_headers_on_get(self, client) -> None:
        resp = client.get(
            "/api/cases",
            headers={"Origin": "http://localhost:3000"},
        )
        assert resp.headers.get("access-control-allow-origin") == "*"
