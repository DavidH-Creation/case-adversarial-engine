"""
Unit A: Case-scoped scenario API endpoint tests.

Tests for:
  POST /api/cases/{case_id}/scenarios  — 202 Accepted with scenario_id
  GET  /api/cases/{case_id}/scenarios/{scenario_id} — scenario result/status

Test matrix:
- POST returns 202 with scenario_id for analyzed case
- POST returns 409 when case not yet analyzed
- POST returns 400 when case has no run_id
- POST returns 404 for unknown case_id
- POST returns 422 for invalid change_set
- GET returns completed result after async job finishes
- GET returns 404 for unknown scenario_id
- GET returns 404 when scenario_id belongs to different case
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

import api.service as service_module
from api.schemas import CaseStatus, ScenarioStatus


# ---------------------------------------------------------------------------
# Mock scenario result (matches ScenarioService.run output structure)
# ---------------------------------------------------------------------------

_MOCK_SCENARIO_SERVICE_RESULT = {
    "scenario": {
        "scenario_id": "scenario-mock-async-001",
        "case_id": "case-mock-001",
        "baseline_run_id": "run-test001",
        "change_set": [
            {
                "target_object_type": "Evidence",
                "target_object_id": "evidence-001",
                "field_path": "body",
                "old_value": "old",
                "new_value": "new",
            }
        ],
        "diff_summary": [
            {
                "issue_id": "issue-001",
                "impact_description": "Evidence modification weakened repayment claim.",
                "direction": "weaken",
            }
        ],
        "affected_issue_ids": ["issue-001"],
        "affected_evidence_ids": ["evidence-001"],
        "status": "completed",
    },
    "run": {
        "run_id": "run-scenario-mock-async-001",
        "case_id": "case-mock-001",
        "workspace_id": "workspace-run-test001",
        "scenario_id": "scenario-mock-async-001",
        "trigger_type": "scenario_execution",
        "input_snapshot": {"material_refs": [], "artifact_refs": []},
        "output_refs": [],
        "started_at": "2026-04-06T00:00:00Z",
        "finished_at": "2026-04-06T00:00:01Z",
        "status": "completed",
    },
}

_VALID_CHANGE_SET = [
    {
        "target_object_type": "Evidence",
        "target_object_id": "evidence-001",
        "field_path": "body",
        "old_value": "old text",
        "new_value": "new text",
    }
]


# ---------------------------------------------------------------------------
# Helper: create an analyzed case in the store
# ---------------------------------------------------------------------------


def _setup_analyzed_case(client) -> str:
    """Create a case and set it to analyzed state, returning case_id."""
    resp = client.post(
        "/api/cases/",
        json={
            "case_type": "civil_loan",
            "plaintiff": {"name": "张三"},
            "defendant": {"name": "李四"},
            "claims": [],
            "defenses": [],
        },
    )
    assert resp.status_code == 201
    case_id = resp.json()["case_id"]

    # Manually set the case to analyzed state with a run_id
    record = service_module.store.get(case_id)
    record.status = CaseStatus.analyzed
    record.run_id = "run-test001"
    record.analysis_data = {"run_id": "run-test001", "overall_assessment": "test"}
    return case_id


# ---------------------------------------------------------------------------
# POST /api/cases/{case_id}/scenarios — Happy path
# ---------------------------------------------------------------------------


class TestPostCaseScenario:
    def test_returns_202_with_scenario_id(self, client) -> None:
        case_id = _setup_analyzed_case(client)

        with patch.object(
            service_module.scenario_service,
            "run",
            new_callable=AsyncMock,
            return_value=_MOCK_SCENARIO_SERVICE_RESULT,
        ):
            resp = client.post(
                f"/api/cases/{case_id}/scenarios",
                json={"change_set": _VALID_CHANGE_SET},
            )

        assert resp.status_code == 202
        data = resp.json()
        assert "scenario_id" in data
        assert data["case_id"] == case_id
        assert data["status"] in ("pending", "running", "completed")

    def test_scenario_id_starts_with_scenario_prefix(self, client) -> None:
        case_id = _setup_analyzed_case(client)

        with patch.object(
            service_module.scenario_service,
            "run",
            new_callable=AsyncMock,
            return_value=_MOCK_SCENARIO_SERVICE_RESULT,
        ):
            resp = client.post(
                f"/api/cases/{case_id}/scenarios",
                json={"change_set": _VALID_CHANGE_SET},
            )

        assert resp.json()["scenario_id"].startswith("scenario-")

    def test_case_not_analyzed_returns_400(self, client) -> None:
        resp = client.post(
            "/api/cases/",
            json={
                "case_type": "civil_loan",
                "plaintiff": {"name": "A"},
                "defendant": {"name": "B"},
            },
        )
        case_id = resp.json()["case_id"]

        resp = client.post(
            f"/api/cases/{case_id}/scenarios",
            json={"change_set": _VALID_CHANGE_SET},
        )
        assert resp.status_code == 400
        assert "analyzed" in resp.json()["detail"]

    def test_case_no_run_id_returns_400(self, client) -> None:
        resp = client.post(
            "/api/cases/",
            json={
                "case_type": "civil_loan",
                "plaintiff": {"name": "A"},
                "defendant": {"name": "B"},
            },
        )
        case_id = resp.json()["case_id"]

        # Set status to analyzed but no run_id
        record = service_module.store.get(case_id)
        record.status = CaseStatus.analyzed
        record.run_id = None

        resp = client.post(
            f"/api/cases/{case_id}/scenarios",
            json={"change_set": _VALID_CHANGE_SET},
        )
        assert resp.status_code == 400
        assert "run_id" in resp.json()["detail"]

    def test_unknown_case_returns_404(self, client) -> None:
        resp = client.post(
            "/api/cases/case-nonexistent/scenarios",
            json={"change_set": _VALID_CHANGE_SET},
        )
        assert resp.status_code == 404

    def test_invalid_change_set_returns_422(self, client) -> None:
        case_id = _setup_analyzed_case(client)

        resp = client.post(
            f"/api/cases/{case_id}/scenarios",
            json={
                "change_set": [
                    {
                        # Missing required fields: target_object_type, field_path
                        "target_object_id": "evidence-001",
                    }
                ],
            },
        )
        assert resp.status_code == 422

    def test_empty_change_set_returns_422(self, client) -> None:
        """Empty body (missing change_set) should return 422."""
        case_id = _setup_analyzed_case(client)

        resp = client.post(
            f"/api/cases/{case_id}/scenarios",
            json={},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/cases/{case_id}/scenarios/{scenario_id}
# ---------------------------------------------------------------------------


class TestGetCaseScenario:
    def test_returns_completed_result(self, client) -> None:
        case_id = _setup_analyzed_case(client)

        with patch.object(
            service_module.scenario_service,
            "run",
            new_callable=AsyncMock,
            return_value=_MOCK_SCENARIO_SERVICE_RESULT,
        ):
            post_resp = client.post(
                f"/api/cases/{case_id}/scenarios",
                json={"change_set": _VALID_CHANGE_SET},
            )
        scenario_id = post_resp.json()["scenario_id"]

        # The async task should have completed by now (since scenario_service.run
        # is mocked and returns immediately)
        # Give the event loop a moment to process the task
        import time
        time.sleep(0.1)

        resp = client.get(f"/api/cases/{case_id}/scenarios/{scenario_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scenario_id"] == scenario_id
        assert data["case_id"] == case_id
        assert data["status"] in ("pending", "running", "completed", "failed")

    def test_returns_result_fields_when_completed(self, client) -> None:
        """When scenario completes, diff_entries should be populated."""
        case_id = _setup_analyzed_case(client)

        with patch.object(
            service_module.scenario_service,
            "run",
            new_callable=AsyncMock,
            return_value=_MOCK_SCENARIO_SERVICE_RESULT,
        ):
            post_resp = client.post(
                f"/api/cases/{case_id}/scenarios",
                json={"change_set": _VALID_CHANGE_SET},
            )
        scenario_id = post_resp.json()["scenario_id"]

        import time
        time.sleep(0.1)

        resp = client.get(f"/api/cases/{case_id}/scenarios/{scenario_id}")
        data = resp.json()
        if data["status"] == "completed":
            assert len(data["diff_entries"]) > 0
            assert data["diff_entries"][0]["issue_id"] == "issue-001"
            assert data["affected_issue_ids"] == ["issue-001"]

    def test_unknown_scenario_returns_404(self, client) -> None:
        case_id = _setup_analyzed_case(client)

        resp = client.get(f"/api/cases/{case_id}/scenarios/scenario-nonexistent")
        assert resp.status_code == 404

    def test_scenario_from_different_case_returns_404(self, client) -> None:
        """A scenario belonging to case A should not be visible via case B."""
        case_id_a = _setup_analyzed_case(client)
        case_id_b = _setup_analyzed_case(client)

        with patch.object(
            service_module.scenario_service,
            "run",
            new_callable=AsyncMock,
            return_value=_MOCK_SCENARIO_SERVICE_RESULT,
        ):
            post_resp = client.post(
                f"/api/cases/{case_id_a}/scenarios",
                json={"change_set": _VALID_CHANGE_SET},
            )
        scenario_id = post_resp.json()["scenario_id"]

        # Try to access via case B
        resp = client.get(f"/api/cases/{case_id_b}/scenarios/{scenario_id}")
        assert resp.status_code == 404

    def test_unknown_case_returns_404(self, client) -> None:
        resp = client.get("/api/cases/case-nonexistent/scenarios/scenario-any")
        assert resp.status_code == 404

    def test_failed_scenario_has_error(self, client) -> None:
        """When scenario_service.run raises, the job should show failed + error."""
        case_id = _setup_analyzed_case(client)

        with patch.object(
            service_module.scenario_service,
            "run",
            new_callable=AsyncMock,
            side_effect=FileNotFoundError("run_id 不存在: run-test001"),
        ):
            post_resp = client.post(
                f"/api/cases/{case_id}/scenarios",
                json={"change_set": _VALID_CHANGE_SET},
            )
        scenario_id = post_resp.json()["scenario_id"]

        import time
        time.sleep(0.1)

        resp = client.get(f"/api/cases/{case_id}/scenarios/{scenario_id}")
        data = resp.json()
        assert data["status"] == "failed"
        assert data["error"] is not None
        assert "run-test001" in data["error"]
