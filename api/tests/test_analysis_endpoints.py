"""
Unit 9: 分析结果查询端点测试
Tests for:
  GET /api/cases/{case_id}/artifacts
  GET /api/cases/{case_id}/artifacts/{artifact_name}
  GET /api/cases/{case_id}/report/markdown
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.schemas import CaseStatus
from api.service import CaseRecord, store

client = TestClient(app)


# ---------------------------------------------------------------------------
# 测试辅助
# ---------------------------------------------------------------------------

_CASE_INFO = {
    "case_type": "civil_loan",
    "plaintiff": {"party_id": "p1", "name": "原告甲"},
    "defendant": {"party_id": "d1", "name": "被告乙"},
    "claims": [],
    "defenses": [],
}

_ANALYSIS_DATA = {
    "overall_assessment": "综合态势：被告证据较充分",
    "plaintiff_args": [],
    "defendant_defenses": [],
    "unresolved_issues": ["issue-001", "issue-002"],
    "evidence_conflicts": [],
    "rounds": [],
}


def _make_record(
    *,
    artifacts: dict | None = None,
    report_markdown: str | None = None,
    status: CaseStatus = CaseStatus.analyzed,
) -> CaseRecord:
    """在全局 store 中创建一条预设好的 CaseRecord。"""
    record = store.create(_CASE_INFO)
    record.status = status
    record.analysis_data = _ANALYSIS_DATA.copy()
    if artifacts is not None:
        record.artifacts = artifacts
    if report_markdown is not None:
        record.report_markdown = report_markdown
    return record


@pytest.fixture(autouse=True)
def clear_store():
    """每个测试前后清空全局 store，确保测试隔离。"""
    store._cases.clear()
    yield
    store._cases.clear()


# ---------------------------------------------------------------------------
# GET /api/cases/{case_id}/artifacts
# ---------------------------------------------------------------------------

class TestListArtifacts:
    def test_happy_path_returns_artifact_names(self):
        """run_id 存在 + artifacts 已填充 → 200 + 文件名列表"""
        record = _make_record(
            artifacts={
                "result.json": {"run_id": "run-abc"},
                "analysis_summary.json": {"overall": "ok"},
            }
        )
        resp = client.get(f"/api/cases/{record.case_id}/artifacts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == record.case_id
        assert set(data["artifacts"]) == {"result.json", "analysis_summary.json"}

    def test_empty_artifacts_returns_empty_list(self):
        """分析完成但 artifacts 为空 → 200 + 空列表"""
        record = _make_record(artifacts={})
        resp = client.get(f"/api/cases/{record.case_id}/artifacts")
        assert resp.status_code == 200
        assert resp.json()["artifacts"] == []

    def test_unknown_run_id_returns_404(self):
        """run_id 不存在 → 统一 404 错误格式"""
        resp = client.get("/api/cases/nonexistent-run-id/artifacts")
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == 404
        assert "error" in body


# ---------------------------------------------------------------------------
# GET /api/cases/{case_id}/artifacts/{artifact_name}
# ---------------------------------------------------------------------------

class TestGetArtifact:
    def test_happy_path_returns_artifact_json(self):
        """run_id 存在 + artifact 存在 → 200 + 有效 JSON"""
        payload = {"run_id": "run-xyz", "rounds": [], "case_id": "case-001"}
        record = _make_record(artifacts={"result.json": payload})
        resp = client.get(f"/api/cases/{record.case_id}/artifacts/result.json")
        assert resp.status_code == 200
        assert resp.json() == payload

    def test_second_artifact_is_accessible(self):
        """多个 artifacts 时，每个都可独立访问"""
        record = _make_record(
            artifacts={
                "result.json": {"key": "val1"},
                "analysis_summary.json": {"key": "val2"},
            }
        )
        resp = client.get(f"/api/cases/{record.case_id}/artifacts/analysis_summary.json")
        assert resp.status_code == 200
        assert resp.json() == {"key": "val2"}

    def test_artifact_not_available_returns_404(self):
        """run_id 存在但 artifact 不存在（pipeline 中断）→ 404 + 说明 artifact not yet available"""
        record = _make_record(artifacts={})
        resp = client.get(f"/api/cases/{record.case_id}/artifacts/result.json")
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == 404
        assert "error" in body
        # 错误信息应说明产物尚不可用
        assert "result.json" in body["error"]

    def test_unknown_run_id_returns_404(self):
        """run_id 不存在 → 统一 404 错误格式"""
        resp = client.get("/api/cases/ghost-run-id/artifacts/result.json")
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == 404
        assert "error" in body


# ---------------------------------------------------------------------------
# GET /api/cases/{case_id}/report/markdown
# ---------------------------------------------------------------------------

class TestGetMarkdownReport:
    def test_happy_path_returns_markdown_content(self):
        """run_id 存在 + 报告已生成 → 200 + Markdown 文本"""
        md = "# 分析报告\n\n## 摘要\n\n测试内容"
        record = _make_record(report_markdown=md)
        resp = client.get(f"/api/cases/{record.case_id}/report/markdown")
        assert resp.status_code == 200
        assert resp.text == md

    def test_report_content_type_is_markdown(self):
        """响应 Content-Type 应为 text/markdown"""
        record = _make_record(report_markdown="# test")
        resp = client.get(f"/api/cases/{record.case_id}/report/markdown")
        assert resp.status_code == 200
        assert "text/markdown" in resp.headers["content-type"]

    def test_report_not_available_returns_404(self):
        """run_id 存在但 report_markdown 为 None → 404 + 统一错误格式"""
        record = _make_record(report_markdown=None)
        resp = client.get(f"/api/cases/{record.case_id}/report/markdown")
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == 404
        assert "error" in body

    def test_unknown_run_id_returns_404(self):
        """run_id 不存在 → 统一 404 错误格式"""
        resp = client.get("/api/cases/ghost-run-id/report/markdown")
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == 404
        assert "error" in body
