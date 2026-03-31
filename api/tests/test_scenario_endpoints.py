"""
Unit 8: Scenario API 端点测试。
Tests for POST /api/scenarios/run and GET /api/scenarios/{scenario_id}.

Test scenarios (per spec):
- Happy path: 有效 change_set → 200 + ScenarioDiff JSON，diff_entries 非空
- Edge case: run_id 不存在 → 404 + 包含 run_id 的明确错误消息
- Error path: change_set 格式非法（缺必填字段）→ 422 + Pydantic validation error
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import api.service as service_module
from api.app import app

# ---------------------------------------------------------------------------
# 公共测试数据
# ---------------------------------------------------------------------------

_MOCK_RESULT = {
    "scenario": {
        "scenario_id": "scenario-mock-001",
        "case_id": "case-civil-loan-test-001",
        "baseline_run_id": "run-baseline-001",
        "change_set": [
            {
                "target_object_type": "Evidence",
                "target_object_id": "evidence-001",
                "field_path": "body",
                "old_value": "original text",
                "new_value": "modified text",
            }
        ],
        "diff_summary": [
            {
                "issue_id": "issue-001",
                "impact_description": "Evidence was modified, weakening the repayment claim.",
                "direction": "weaken",
            }
        ],
        "affected_issue_ids": ["issue-001"],
        "affected_evidence_ids": ["evidence-001"],
        "status": "completed",
    },
    "run": {
        "run_id": "run-scenario-mock-001",
        "case_id": "case-civil-loan-test-001",
        "workspace_id": "workspace-run-baseline-001",
        "scenario_id": "scenario-mock-001",
        "trigger_type": "scenario_execution",
        "input_snapshot": {"material_refs": [], "artifact_refs": []},
        "output_refs": [],
        "started_at": "2026-03-31T00:00:00Z",
        "finished_at": "2026-03-31T00:00:01Z",
        "status": "completed",
    },
}

_VALID_CHANGE_SET = [
    {
        "target_object_type": "Evidence",
        "target_object_id": "evidence-001",
        "field_path": "body",
        "old_value": "original text",
        "new_value": "modified text",
    }
]

client = TestClient(app)


# ---------------------------------------------------------------------------
# Happy path: POST /api/scenarios/run
# ---------------------------------------------------------------------------

def test_run_scenario_happy_path_returns_200_and_diff():
    """有效 change_set → 200 + ScenarioDiff JSON，diff_entries 非空。"""
    with patch.object(
        service_module.scenario_service,
        "run",
        new_callable=AsyncMock,
        return_value=_MOCK_RESULT,
    ):
        response = client.post(
            "/api/scenarios/run",
            json={"run_id": "run-baseline-001", "change_set": _VALID_CHANGE_SET},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["scenario_id"] == "scenario-mock-001"
    assert data["case_id"] == "case-civil-loan-test-001"
    assert data["baseline_run_id"] == "run-baseline-001"
    assert data["status"] == "completed"
    assert len(data["diff_entries"]) > 0
    assert data["diff_entries"][0]["direction"] == "weaken"
    assert data["diff_entries"][0]["issue_id"] == "issue-001"
    assert data["affected_issue_ids"] == ["issue-001"]
    assert data["affected_evidence_ids"] == ["evidence-001"]


# ---------------------------------------------------------------------------
# GET /api/scenarios/{scenario_id}
# ---------------------------------------------------------------------------

def test_get_scenario_found_returns_200():
    """GET /scenarios/{scenario_id} — scenario 存在 → 200 + ScenarioDiff。"""
    with patch.object(
        service_module.scenario_service,
        "get",
        return_value=_MOCK_RESULT,
    ):
        response = client.get("/api/scenarios/scenario-mock-001")

    assert response.status_code == 200
    data = response.json()
    assert data["scenario_id"] == "scenario-mock-001"
    assert len(data["diff_entries"]) > 0


def test_get_scenario_not_found_returns_404():
    """GET /scenarios/{scenario_id} — scenario 不存在 → 404。"""
    with patch.object(
        service_module.scenario_service,
        "get",
        return_value=None,
    ):
        response = client.get("/api/scenarios/nonexistent-scenario-id")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Edge case: run_id 不存在 → 404 + 包含 run_id 的明确错误消息
# ---------------------------------------------------------------------------

def test_run_scenario_run_id_not_found_returns_404_with_run_id():
    """run_id 不存在 → 404 + 响应 detail 包含 run_id。"""
    with patch.object(
        service_module.scenario_service,
        "run",
        new_callable=AsyncMock,
        side_effect=FileNotFoundError("run_id 不存在: nonexistent-run-001"),
    ):
        response = client.post(
            "/api/scenarios/run",
            json={"run_id": "nonexistent-run-001", "change_set": _VALID_CHANGE_SET},
        )

    assert response.status_code == 404
    assert "nonexistent-run-001" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Error path: change_set 格式非法 → 422 + Pydantic validation error
# ---------------------------------------------------------------------------

def test_run_scenario_invalid_change_set_missing_required_fields_returns_422():
    """change_set 缺必填字段（target_object_type, field_path）→ 422。"""
    response = client.post(
        "/api/scenarios/run",
        json={
            "run_id": "run-baseline-001",
            "change_set": [
                {
                    # Missing required: target_object_type, field_path
                    "target_object_id": "evidence-001",
                }
            ],
        },
    )

    assert response.status_code == 422


def test_run_scenario_missing_run_id_returns_422():
    """请求体缺少 run_id → 422。"""
    response = client.post(
        "/api/scenarios/run",
        json={"change_set": _VALID_CHANGE_SET},
    )

    assert response.status_code == 422
