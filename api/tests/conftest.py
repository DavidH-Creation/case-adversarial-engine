"""Shared fixtures for Phase 3+ tests (review, export, etc.)."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


def _minimal_case_payload():
    return {
        "case_type": "civil_loan",
        "plaintiff": {"name": "张三"},
        "defendant": {"name": "李四"},
        "claims": [],
        "defenses": [],
    }


@pytest.fixture
def client(tmp_path):
    # Use tmp_path as workspace dir to isolate test state
    with patch("api.service._WORKSPACE_BASE", tmp_path):
        from api.app import app

        with TestClient(app) as c:
            yield c


@pytest.fixture
def created_case_id(client):
    resp = client.post("/api/cases/", json=_minimal_case_payload())
    assert resp.status_code == 201
    return resp.json()["case_id"]


@pytest.fixture
def analyzed_case_id(client, created_case_id):
    """Return a case ID in 'analyzed' status (no real LLM call)."""
    from api.service import store
    from api.schemas import CaseStatus

    record = store.get(created_case_id)
    record.status = CaseStatus.analyzed
    record.analysis_data = {"run_id": "run-test001", "overall_assessment": "测试"}
    record.run_id = "run-test001"
    return created_case_id
