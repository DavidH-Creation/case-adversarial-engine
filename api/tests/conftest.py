"""Shared test fixtures for Phase 3+ API tests."""

import json

import bcrypt
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


# ---------------------------------------------------------------------------
# Legacy fixture — no auth (API_SECRET_KEY unset)
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient with isolated workspace dir, no auth required."""
    monkeypatch.delenv("API_SECRET_KEY", raising=False)
    monkeypatch.delenv("USERS_FILE", raising=False)
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
    """Return a case_id in 'analyzed' state (no real LLM calls)."""
    from api.service import store
    from api.schemas import CaseStatus

    record = store.get(created_case_id)
    record.status = CaseStatus.analyzed
    record.analysis_data = {"run_id": "run-test001", "overall_assessment": "测试"}
    record.run_id = "run-test001"
    return created_case_id


# ---------------------------------------------------------------------------
# Phase 4 JWT fixtures
# ---------------------------------------------------------------------------

_TEST_SECRET = "test-secret-key"
_TEST_USERS = [
    {
        "user_id": "usr-admin001",
        "name": "管理员",
        "email": "admin@lawfirm.com",
        "role": "admin",
        "hashed_pwd": bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode(),
        "is_active": True,
    },
    {
        "user_id": "usr-junior001",
        "name": "初级律师",
        "email": "junior@lawfirm.com",
        "role": "junior_lawyer",
        "hashed_pwd": bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode(),
        "is_active": True,
    },
    {
        "user_id": "usr-reviewer001",
        "name": "复核员",
        "email": "reviewer@lawfirm.com",
        "role": "reviewer",
        "hashed_pwd": bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode(),
        "is_active": True,
    },
    {
        "user_id": "usr-readonly001",
        "name": "只读用户",
        "email": "readonly@lawfirm.com",
        "role": "readonly",
        "hashed_pwd": bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode(),
        "is_active": True,
    },
    {
        "user_id": "usr-disabled001",
        "name": "已禁用",
        "email": "disabled@lawfirm.com",
        "role": "admin",
        "hashed_pwd": bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode(),
        "is_active": False,
    },
]


@pytest.fixture
def client_with_users(tmp_path, monkeypatch):
    """TestClient with test users.json + JWT signing key configured."""
    users_file = tmp_path / "users.json"
    users_file.write_text(json.dumps(_TEST_USERS), encoding="utf-8")
    monkeypatch.setenv("API_SECRET_KEY", _TEST_SECRET)
    monkeypatch.setenv("USERS_FILE", str(users_file))
    with patch("api.service._WORKSPACE_BASE", tmp_path / "workspaces"):
        from api.app import app

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


def _get_jwt(client_with_users, email: str) -> str:
    resp = client_with_users.post(
        "/api/auth/token",
        json={"email": email, "password": "secret"},
    )
    assert resp.status_code == 200, f"Token request failed for {email}: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture
def jwt_for_admin(client_with_users):
    return _get_jwt(client_with_users, "admin@lawfirm.com")


@pytest.fixture
def jwt_for_junior(client_with_users):
    return _get_jwt(client_with_users, "junior@lawfirm.com")


@pytest.fixture
def jwt_for_reviewer(client_with_users):
    return _get_jwt(client_with_users, "reviewer@lawfirm.com")


@pytest.fixture
def jwt_for_readonly(client_with_users):
    return _get_jwt(client_with_users, "readonly@lawfirm.com")


@pytest.fixture
def created_case_id_with_users(client_with_users, jwt_for_admin):
    """Create a case using admin JWT and return case_id."""
    headers = {"Authorization": f"Bearer {jwt_for_admin}"}
    resp = client_with_users.post(
        "/api/cases/",
        json=_minimal_case_payload(),
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["case_id"]
