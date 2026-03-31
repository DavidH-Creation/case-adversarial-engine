"""
Unit tests for Bearer Token authentication middleware.
Covers: 401 when key configured, 200 with valid token, open access when key not set.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.app import app

client = TestClient(app, raise_server_exceptions=False)

_CASE_PAYLOAD = {
    "case_type": "civil_loan",
    "plaintiff": {"party_id": "p1", "name": "原告甲"},
    "defendant": {"party_id": "d1", "name": "被告乙"},
    "claims": [],
    "defenses": [],
}


def test_protected_endpoint_returns_401_without_token(monkeypatch):
    """当 API_SECRET_KEY 已配置时，无 token 请求应返回 401。"""
    monkeypatch.setenv("API_SECRET_KEY", "test-secret")
    resp = client.post("/api/cases/", json=_CASE_PAYLOAD)
    assert resp.status_code == 401


def test_protected_endpoint_accepts_valid_token(monkeypatch):
    """当 API_SECRET_KEY 已配置时，携带正确 Bearer token 应通过认证。"""
    monkeypatch.setenv("API_SECRET_KEY", "test-secret")
    resp = client.post(
        "/api/cases/",
        json=_CASE_PAYLOAD,
        headers={"Authorization": "Bearer test-secret"},
    )
    assert resp.status_code in (200, 201)


def test_protected_endpoint_rejects_wrong_token(monkeypatch):
    """错误的 token 应返回 401。"""
    monkeypatch.setenv("API_SECRET_KEY", "test-secret")
    resp = client.post(
        "/api/cases/",
        json=_CASE_PAYLOAD,
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


def test_no_auth_when_key_not_configured(monkeypatch):
    """未配置 API_SECRET_KEY 时，所有请求应开放访问（不强制认证）。"""
    monkeypatch.delenv("API_SECRET_KEY", raising=False)
    resp = client.post("/api/cases/", json=_CASE_PAYLOAD)
    assert resp.status_code != 401
