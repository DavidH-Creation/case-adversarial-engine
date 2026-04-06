"""
TDD tests for Phase 4: JWT authentication + RBAC permission matrix.
All tests written BEFORE production code (red phase).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest
from jose import jwt as jose_jwt

# ---------------------------------------------------------------------------
# Constants shared with conftest fixtures
# ---------------------------------------------------------------------------
_TEST_SECRET = "test-secret-key"


# ===========================================================================
# 1. Permission matrix (unit — no HTTP involved)
# ===========================================================================

@pytest.mark.parametrize("role,action,expected", [
    ("admin",         "case_create",        True),
    ("admin",         "admin_users",        True),
    ("senior_lawyer", "case_create",        True),
    ("senior_lawyer", "review_submit",      True),
    ("senior_lawyer", "review_decide",      False),
    ("senior_lawyer", "admin_users",        False),
    ("junior_lawyer", "case_create",        True),
    ("junior_lawyer", "analysis_trigger",   False),
    ("junior_lawyer", "review_submit",      False),
    ("reviewer",      "review_decide",      True),
    ("reviewer",      "case_view",          True),
    ("reviewer",      "case_create",        False),
    ("readonly",      "case_view",          True),
    ("readonly",      "case_list",          True),
    ("readonly",      "material_add",       False),
    ("readonly",      "case_create",        False),
])
def test_permission_matrix(role, action, expected):
    from api.permissions import PERMISSIONS, Action
    from api.users import UserRole
    assert (Action(action) in PERMISSIONS[UserRole(role)]) == expected


# ===========================================================================
# 2. Token issuance
# ===========================================================================

def test_token_issued_for_valid_user(client_with_users):
    resp = client_with_users.post(
        "/api/auth/token",
        json={"email": "admin@lawfirm.com", "password": "secret"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0


def test_token_payload_contains_sub_and_role(client_with_users):
    resp = client_with_users.post(
        "/api/auth/token",
        json={"email": "admin@lawfirm.com", "password": "secret"},
    )
    token = resp.json()["access_token"]
    payload = jose_jwt.decode(token, _TEST_SECRET, algorithms=["HS256"])
    assert payload["sub"] == "usr-admin001"
    assert payload["role"] == "admin"
    assert "exp" in payload


def test_invalid_password_returns_401(client_with_users):
    resp = client_with_users.post(
        "/api/auth/token",
        json={"email": "admin@lawfirm.com", "password": "wrong"},
    )
    assert resp.status_code == 401


def test_unknown_email_returns_401(client_with_users):
    resp = client_with_users.post(
        "/api/auth/token",
        json={"email": "nobody@lawfirm.com", "password": "secret"},
    )
    assert resp.status_code == 401


def test_inactive_user_returns_401(client_with_users):
    resp = client_with_users.post(
        "/api/auth/token",
        json={"email": "disabled@lawfirm.com", "password": "secret"},
    )
    assert resp.status_code == 401


# ===========================================================================
# 3. Protected endpoints — JWT required
# ===========================================================================

def test_protected_endpoint_rejects_no_token(client_with_users):
    resp = client_with_users.get("/api/cases")
    assert resp.status_code == 401


def test_protected_endpoint_accepts_valid_jwt(client_with_users, jwt_for_admin):
    headers = {"Authorization": f"Bearer {jwt_for_admin}"}
    resp = client_with_users.get("/api/cases", headers=headers)
    assert resp.status_code == 200


def test_expired_jwt_returns_401(client_with_users):
    payload = {
        "sub": "usr-admin001",
        "role": "admin",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    token = jose_jwt.encode(payload, _TEST_SECRET, algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}
    resp = client_with_users.get("/api/cases", headers=headers)
    assert resp.status_code == 401


def test_invalid_jwt_signature_returns_401(client_with_users):
    payload = {"sub": "usr-admin001", "role": "admin", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    token = jose_jwt.encode(payload, "wrong-secret", algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}
    resp = client_with_users.get("/api/cases", headers=headers)
    assert resp.status_code == 401


# ===========================================================================
# 4. RBAC enforcement on HTTP endpoints
# ===========================================================================

def test_junior_cannot_trigger_analysis(client_with_users, jwt_for_junior, created_case_id_with_users):
    headers = {"Authorization": f"Bearer {jwt_for_junior}"}
    resp = client_with_users.post(
        f"/api/cases/{created_case_id_with_users}/analyze",
        headers=headers,
    )
    assert resp.status_code == 403


def test_readonly_cannot_create_case(client_with_users, jwt_for_readonly):
    headers = {"Authorization": f"Bearer {jwt_for_readonly}"}
    resp = client_with_users.post(
        "/api/cases/",
        json={
            "case_type": "civil_loan",
            "plaintiff": {"name": "张三"},
            "defendant": {"name": "李四"},
            "claims": [],
            "defenses": [],
        },
        headers=headers,
    )
    assert resp.status_code == 403


def test_reviewer_cannot_create_case(client_with_users, jwt_for_reviewer):
    headers = {"Authorization": f"Bearer {jwt_for_reviewer}"}
    resp = client_with_users.post(
        "/api/cases/",
        json={
            "case_type": "civil_loan",
            "plaintiff": {"name": "张三"},
            "defendant": {"name": "李四"},
            "claims": [],
            "defenses": [],
        },
        headers=headers,
    )
    assert resp.status_code == 403


def test_admin_can_create_case(client_with_users, jwt_for_admin):
    headers = {"Authorization": f"Bearer {jwt_for_admin}"}
    resp = client_with_users.post(
        "/api/cases/",
        json={
            "case_type": "civil_loan",
            "plaintiff": {"name": "张三"},
            "defendant": {"name": "李四"},
            "claims": [],
            "defenses": [],
        },
        headers=headers,
    )
    assert resp.status_code == 201


# ===========================================================================
# 5. Backward compatibility — API_SECRET_KEY as static Bearer (no users.json)
# ===========================================================================

def test_static_bearer_accepted_when_no_users_file(tmp_path, monkeypatch):
    """API_SECRET_KEY set but no USERS_FILE → static Bearer still works."""
    from unittest.mock import patch

    monkeypatch.setenv("API_SECRET_KEY", "my-static-key")
    monkeypatch.delenv("USERS_FILE", raising=False)
    with patch("api.service._WORKSPACE_BASE", tmp_path):
        from api.app import app
        from fastapi.testclient import TestClient

        with TestClient(app, raise_server_exceptions=False) as c:
            headers = {"Authorization": "Bearer my-static-key"}
            resp = c.get("/api/cases", headers=headers)
            assert resp.status_code == 200


# ===========================================================================
# 6. Local dev mode — no API_SECRET_KEY → anonymous admin
# ===========================================================================

def test_no_secret_key_allows_anonymous_access(tmp_path, monkeypatch):
    from unittest.mock import patch

    monkeypatch.delenv("API_SECRET_KEY", raising=False)
    monkeypatch.delenv("USERS_FILE", raising=False)
    with patch("api.service._WORKSPACE_BASE", tmp_path):
        from api.app import app
        from fastapi.testclient import TestClient

        with TestClient(app) as c:
            resp = c.get("/api/cases")
            assert resp.status_code == 200


# ===========================================================================
# 7. UserStore unit tests
# ===========================================================================

def test_user_store_loads_from_json(tmp_path):
    users_data = [
        {
            "user_id": "usr-test001",
            "name": "Test User",
            "email": "test@example.com",
            "role": "admin",
            "hashed_pwd": bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode(),
            "is_active": True,
        }
    ]
    users_file = tmp_path / "users.json"
    users_file.write_text(json.dumps(users_data), encoding="utf-8")

    from api.users import UserStore
    store = UserStore(str(users_file))
    user = store.get_by_email("test@example.com")
    assert user is not None
    assert user.user_id == "usr-test001"

    user_by_id = store.get_by_id("usr-test001")
    assert user_by_id is not None
    assert user_by_id.email == "test@example.com"


def test_user_store_returns_none_for_unknown(tmp_path):
    users_file = tmp_path / "users.json"
    users_file.write_text("[]", encoding="utf-8")

    from api.users import UserStore
    store = UserStore(str(users_file))
    assert store.get_by_email("nobody@example.com") is None
    assert store.get_by_id("usr-missing") is None
