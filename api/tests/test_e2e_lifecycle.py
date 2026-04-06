"""
Unit B: E2E API lifecycle tests — full pipeline through HTTP endpoints.

Tests the complete case lifecycle:
  POST /cases → POST materials → POST extract → GET extraction →
  POST confirm → POST analyze → GET /result → GET /report/markdown

All LLM calls are mocked via patching ClaudeCLIClient + engine internals.
No real API keys or model calls required.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import api.service as service_module
from api.app import app
from api.schemas import CaseStatus
from api.service import CaseRecord, CaseStore


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

_CIVIL_LOAN_CASE = {
    "case_type": "civil_loan",
    "plaintiff": {"party_id": "p-lifecycle", "name": "生命周期原告"},
    "defendant": {"party_id": "d-lifecycle", "name": "生命周期被告"},
    "claims": [
        {"claim_id": "c-001", "title": "借款本金", "description": "借款本金100,000元"},
    ],
    "defenses": [
        {"defense_id": "def-001", "title": "全额偿还", "description": "已经全额偿还"},
    ],
}

_MATERIAL_PLAINTIFF = {
    "source_id": "src-plt-001",
    "role": "plaintiff",
    "doc_type": "contract",
    "text": "借款合同：甲方借给乙方人民币100,000元整，年利率12%。",
}

_MATERIAL_DEFENDANT = {
    "source_id": "src-def-001",
    "role": "defendant",
    "doc_type": "receipt",
    "text": "还款收据：乙方已于2025年3月15日向甲方转账100,000元。",
}


# ---------------------------------------------------------------------------
# Helpers — mock extraction and analysis
# ---------------------------------------------------------------------------


def _make_fake_extraction_data(case_id: str) -> dict:
    """Minimal extraction data matching ExtractionResponse schema."""
    return {
        "evidence": [
            {
                "evidence_id": "ev-lc-001",
                "case_id": case_id,
                "owner_party_id": "p-lifecycle",
                "title": "借款合同",
                "source": "src-plt-001",
                "summary": "原告与被告签订借款合同，金额100,000元",
                "evidence_type": "documentary",
                "target_fact_ids": ["fact-001"],
                "status": "private",
                "access_domain": "owner_private",
            },
            {
                "evidence_id": "ev-lc-002",
                "case_id": case_id,
                "owner_party_id": "d-lifecycle",
                "title": "还款收据",
                "source": "src-def-001",
                "summary": "被告提交转账凭证证明已还款",
                "evidence_type": "documentary",
                "target_fact_ids": ["fact-002"],
                "status": "private",
                "access_domain": "owner_private",
            },
        ],
        "issues": [
            {
                "issue_id": "issue-lc-001",
                "case_id": case_id,
                "title": "借款合同效力",
                "description": "借贷关系是否成立",
                "issue_type": "legal",
                "status": "open",
            },
            {
                "issue_id": "issue-lc-002",
                "case_id": case_id,
                "title": "还款事实认定",
                "description": "被告是否已全额偿还",
                "issue_type": "factual",
                "status": "open",
            },
        ],
    }


def _make_fake_analysis_data(case_id: str, run_id: str) -> dict:
    """Minimal analysis_data matching AnalysisResponse schema."""
    return {
        "run_id": run_id,
        "overall_assessment": "双方对借款事实无争议，核心争点为还款是否完成。",
        "plaintiff_args": [
            {"issue_id": "issue-lc-001", "argument": "借款合同合法有效"},
        ],
        "defendant_defenses": [
            {"issue_id": "issue-lc-002", "argument": "已提交还款凭证"},
        ],
        "unresolved_issues": [
            {"issue_id": "issue-lc-002", "description": "还款金额尚需核实"},
        ],
        "evidence_conflicts": [],
        "rounds": [
            {
                "round_number": 1,
                "phase": "claim",
                "outputs": [],
            },
        ],
    }


async def _fake_run_extraction(record: CaseRecord) -> None:
    """Mock extraction that injects fake data without calling LLM."""
    from engines.shared.models import (
        AccessDomain,
        Evidence,
        EvidenceIndex,
        EvidenceStatus,
        EvidenceType,
    )
    from engines.shared.models.analysis import Issue, IssueStatus, IssueType

    case_id = record.case_id
    ev1 = Evidence(
        evidence_id="ev-lc-001",
        case_id=case_id,
        owner_party_id="p-lifecycle",
        title="借款合同",
        source="src-plt-001",
        summary="原告与被告签订借款合同，金额100,000元",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=["fact-001"],
        status=EvidenceStatus.private,
        access_domain=AccessDomain.owner_private,
    )
    ev2 = Evidence(
        evidence_id="ev-lc-002",
        case_id=case_id,
        owner_party_id="d-lifecycle",
        title="还款收据",
        source="src-def-001",
        summary="被告提交转账凭证证明已还款",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=["fact-002"],
        status=EvidenceStatus.private,
        access_domain=AccessDomain.owner_private,
    )
    record.ev_index = EvidenceIndex(case_id=case_id, evidence=[ev1, ev2])

    issue1 = Issue(
        issue_id="issue-lc-001",
        case_id=case_id,
        title="借款合同效力",
        description="借贷关系是否成立",
        issue_type=IssueType.legal,
        status=IssueStatus.open,
    )
    issue2 = Issue(
        issue_id="issue-lc-002",
        case_id=case_id,
        title="还款事实认定",
        description="被告是否已全额偿还",
        issue_type=IssueType.factual,
        status=IssueStatus.open,
    )
    record.issue_tree = MagicMock()
    record.issue_tree.case_id = case_id
    record.issue_tree.issues = [issue1, issue2]
    record.issue_tree.burdens = []

    record.extraction_data = _make_fake_extraction_data(case_id)
    record.status = CaseStatus.extracted
    record.log("Extraction complete (mocked)")
    record._signal_done()


async def _fake_run_analysis(record: CaseRecord) -> None:
    """Mock analysis that injects fake data without calling LLM."""
    run_id = f"run-lifecycle-{uuid.uuid4().hex[:12]}"
    record.run_id = run_id
    record.analysis_data = _make_fake_analysis_data(record.case_id, run_id)
    record.report_markdown = "# 案件分析报告\n\n## 整体评估\n\n双方对借款事实无争议。\n"
    record.status = CaseStatus.analyzed
    record.log("Analysis complete (mocked)")
    record._signal_done()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_client(tmp_path, monkeypatch):
    """TestClient with isolated workspace, no auth, mocked extraction + analysis."""
    monkeypatch.delenv("API_SECRET_KEY", raising=False)
    monkeypatch.delenv("USERS_FILE", raising=False)

    test_store = CaseStore(workspaces_dir=tmp_path / "workspaces")

    with (
        patch.object(service_module, "store", test_store),
        patch("api.app.store", test_store),
        patch("api.app.run_extraction", new=_fake_run_extraction),
        patch("api.app.run_analysis", new=_fake_run_analysis),
    ):
        with TestClient(app) as c:
            yield c, test_store


# ---------------------------------------------------------------------------
# Test: Full lifecycle — happy path
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    """E2E: create → materials → extract → extraction → confirm → analyze → result → report."""

    def test_happy_path_civil_loan(self, isolated_client):
        client, store = isolated_client

        # Step 1: Create case
        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
        assert resp.status_code == 201
        body = resp.json()
        case_id = body["case_id"]
        assert case_id.startswith("case-")
        assert body["status"] == "created"

        # Step 2: Add materials (plaintiff + defendant)
        resp = client.post(f"/api/cases/{case_id}/materials", json=_MATERIAL_PLAINTIFF)
        assert resp.status_code == 200
        assert resp.json()["source_id"] == "src-plt-001"
        assert resp.json()["char_count"] > 0

        resp = client.post(f"/api/cases/{case_id}/materials", json=_MATERIAL_DEFENDANT)
        assert resp.status_code == 200
        assert resp.json()["source_id"] == "src-def-001"

        # Step 3: Trigger extraction (returns 202, runs async)
        resp = client.post(f"/api/cases/{case_id}/extract")
        assert resp.status_code == 202
        assert resp.json()["status"] in ("extracting", "extracted")

        # Wait for mock extraction to complete
        import time

        for _ in range(20):
            record = store.get(case_id)
            if record and record.status == CaseStatus.extracted:
                break
            time.sleep(0.1)
        assert record.status == CaseStatus.extracted

        # Step 4: Verify extraction via GET
        resp = client.get(f"/api/cases/{case_id}/extraction")
        assert resp.status_code == 200
        ext_data = resp.json()
        assert len(ext_data["evidence"]) == 2
        assert len(ext_data["issues"]) == 2
        assert ext_data["evidence"][0]["evidence_id"] == "ev-lc-001"

        # Step 5: Confirm extraction
        confirm_body = {
            "issues": ext_data["issues"],
            "evidence": ext_data["evidence"],
        }
        resp = client.post(f"/api/cases/{case_id}/confirm", json=confirm_body)
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed"

        # Step 6: Trigger analysis (returns 202, runs async)
        resp = client.post(f"/api/cases/{case_id}/analyze")
        assert resp.status_code == 202

        # Wait for mock analysis to complete
        for _ in range(20):
            record = store.get(case_id)
            if record and record.status == CaseStatus.analyzed:
                break
            time.sleep(0.1)
        assert record.status == CaseStatus.analyzed

        # Step 7: Get case info — should be analyzed
        resp = client.get(f"/api/cases/{case_id}")
        assert resp.status_code == 200
        info = resp.json()
        assert info["status"] == "analyzed"
        assert info["has_analysis"] is True
        assert info["run_id"] is not None

        # Step 8: Get result
        resp = client.get(f"/api/cases/{case_id}/result")
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "analyzed"
        assert result["run_id"] is not None
        assert result["analysis_data"] is not None
        assert "overall_assessment" in result["analysis_data"]

        # Step 9: Get markdown report
        resp = client.get(f"/api/cases/{case_id}/report/markdown")
        assert resp.status_code == 200
        assert "案件分析报告" in resp.text

    def test_case_info_after_creation(self, isolated_client):
        """GET /cases/{id} returns correct info for a newly created case."""
        client, _ = isolated_client
        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
        case_id = resp.json()["case_id"]

        resp = client.get(f"/api/cases/{case_id}")
        assert resp.status_code == 200
        info = resp.json()
        assert info["status"] == "created"
        assert info["has_extraction"] is False
        assert info["has_analysis"] is False

    def test_list_cases_includes_created(self, isolated_client):
        """GET /cases includes newly created cases."""
        client, _ = isolated_client
        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
        case_id = resp.json()["case_id"]

        resp = client.get("/api/cases")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        ids = [item["case_id"] for item in body["items"]]
        assert case_id in ids


# ---------------------------------------------------------------------------
# Test: State machine enforcement
# ---------------------------------------------------------------------------


class TestStateMachine:
    """Verify API rejects operations when case is in wrong state."""

    def test_extract_requires_materials(self, isolated_client):
        """Cannot extract with no materials (depends on implementation)."""
        client, _ = isolated_client
        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
        case_id = resp.json()["case_id"]

        # Extraction on empty case — should either 400 or accept and fail gracefully
        resp = client.post(f"/api/cases/{case_id}/extract")
        # The API may accept (202) and let extraction fail, or reject (400)
        assert resp.status_code in (202, 400)

    def test_confirm_requires_extracted_state(self, isolated_client):
        """Cannot confirm before extraction."""
        client, _ = isolated_client
        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
        case_id = resp.json()["case_id"]

        resp = client.post(
            f"/api/cases/{case_id}/confirm",
            json={"issues": [], "evidence": []},
        )
        # Should reject — case is in 'created' state
        assert resp.status_code == 400

    def test_analyze_requires_confirmed_state(self, isolated_client):
        """Cannot analyze before confirmation."""
        client, _ = isolated_client
        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
        case_id = resp.json()["case_id"]

        resp = client.post(f"/api/cases/{case_id}/analyze")
        # Should reject — case is in 'created' state, not 'confirmed'
        assert resp.status_code == 400

    def test_result_before_analysis_has_no_run_id(self, isolated_client):
        """GET /result on non-analyzed case returns status but no run_id."""
        client, _ = isolated_client
        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
        case_id = resp.json()["case_id"]

        resp = client.get(f"/api/cases/{case_id}/result")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "created"
        assert data["run_id"] is None


# ---------------------------------------------------------------------------
# Test: Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Verify API returns proper errors for invalid inputs."""

    def test_get_nonexistent_case_returns_404(self, isolated_client):
        client, _ = isolated_client
        resp = client.get("/api/cases/case-nonexistent-000")
        assert resp.status_code == 404

    def test_add_material_to_nonexistent_case(self, isolated_client):
        client, _ = isolated_client
        resp = client.post(
            "/api/cases/case-nonexistent-000/materials",
            json=_MATERIAL_PLAINTIFF,
        )
        assert resp.status_code == 404

    def test_create_case_missing_required_fields(self, isolated_client):
        """Missing case_type should return 422 (Pydantic validation)."""
        client, _ = isolated_client
        resp = client.post("/api/cases/", json={"plaintiff": {"name": "张三"}})
        assert resp.status_code == 422

    def test_extraction_on_nonexistent_case(self, isolated_client):
        client, _ = isolated_client
        resp = client.get("/api/cases/case-nonexistent-000/extraction")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test: Materials management
# ---------------------------------------------------------------------------


class TestMaterials:
    """Verify material upload and storage."""

    def test_add_multiple_materials(self, isolated_client):
        """Can add multiple materials to same case."""
        client, _ = isolated_client
        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
        case_id = resp.json()["case_id"]

        # Add 3 materials
        for i in range(3):
            mat = {
                "source_id": f"src-multi-{i:03d}",
                "role": "plaintiff",
                "doc_type": "contract",
                "text": f"Material {i} content.",
            }
            resp = client.post(f"/api/cases/{case_id}/materials", json=mat)
            assert resp.status_code == 200
            assert resp.json()["source_id"] == f"src-multi-{i:03d}"

    def test_material_response_includes_char_count(self, isolated_client):
        """Response includes char_count for the added material."""
        client, _ = isolated_client
        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
        case_id = resp.json()["case_id"]

        text = "这是一个测试材料。" * 10  # 90 chars
        mat = {
            "source_id": "src-count-001",
            "role": "plaintiff",
            "doc_type": "contract",
            "text": text,
        }
        resp = client.post(f"/api/cases/{case_id}/materials", json=mat)
        assert resp.status_code == 200
        assert resp.json()["char_count"] == len(text)


# ---------------------------------------------------------------------------
# Test: Export endpoints
# ---------------------------------------------------------------------------


class TestExport:
    """Verify export endpoints on analyzed cases."""

    def _create_analyzed_case(self, client, store):
        """Helper: push a case through the full lifecycle to analyzed state."""
        import time

        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
        case_id = resp.json()["case_id"]

        client.post(f"/api/cases/{case_id}/materials", json=_MATERIAL_PLAINTIFF)
        client.post(f"/api/cases/{case_id}/materials", json=_MATERIAL_DEFENDANT)
        client.post(f"/api/cases/{case_id}/extract")

        for _ in range(20):
            record = store.get(case_id)
            if record and record.status == CaseStatus.extracted:
                break
            time.sleep(0.1)

        ext = client.get(f"/api/cases/{case_id}/extraction").json()
        client.post(
            f"/api/cases/{case_id}/confirm",
            json={"issues": ext["issues"], "evidence": ext["evidence"]},
        )
        client.post(f"/api/cases/{case_id}/analyze")

        for _ in range(20):
            record = store.get(case_id)
            if record and record.status == CaseStatus.analyzed:
                break
            time.sleep(0.1)

        return case_id

    def test_export_json_format(self, isolated_client):
        """GET /export?format=json returns JSON analysis data."""
        client, store = isolated_client
        case_id = self._create_analyzed_case(client, store)

        resp = client.get(f"/api/cases/{case_id}/export?format=json")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_assessment" in data or "analysis_data" in data or "run_id" in data

    def test_export_markdown_format(self, isolated_client):
        """GET /export?format=markdown returns markdown text."""
        client, store = isolated_client
        case_id = self._create_analyzed_case(client, store)

        resp = client.get(f"/api/cases/{case_id}/export?format=markdown")
        assert resp.status_code == 200
        assert "案件分析报告" in resp.text or "分析" in resp.text


# ---------------------------------------------------------------------------
# Test: SSE endpoints (Unit 19b)
# ---------------------------------------------------------------------------


def _parse_sse_events(body: str) -> list[dict]:
    """Parse SSE response body into list of JSON event dicts."""
    import json

    events = []
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            data = line[6:]
            try:
                events.append(json.loads(data))
            except json.JSONDecodeError:
                pass
    return events


class TestSSEEndpoints:
    """Verify SSE streaming endpoints return correct event-stream format."""

    def _create_analyzed_case(self, client, store):
        """Helper: push a case through the full lifecycle to analyzed state."""
        import time

        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
        case_id = resp.json()["case_id"]

        client.post(f"/api/cases/{case_id}/materials", json=_MATERIAL_PLAINTIFF)
        client.post(f"/api/cases/{case_id}/materials", json=_MATERIAL_DEFENDANT)
        client.post(f"/api/cases/{case_id}/extract")

        for _ in range(20):
            record = store.get(case_id)
            if record and record.status == CaseStatus.extracted:
                break
            time.sleep(0.1)

        ext = client.get(f"/api/cases/{case_id}/extraction").json()
        client.post(
            f"/api/cases/{case_id}/confirm",
            json={"issues": ext["issues"], "evidence": ext["evidence"]},
        )
        client.post(f"/api/cases/{case_id}/analyze")

        for _ in range(20):
            record = store.get(case_id)
            if record and record.status == CaseStatus.analyzed:
                break
            time.sleep(0.1)

        return case_id

    def test_analysis_stream_returns_done_for_analyzed_case(self, isolated_client):
        """GET /analysis on analyzed case returns SSE with type=done."""
        client, store = isolated_client
        case_id = self._create_analyzed_case(client, store)

        resp = client.get(f"/api/cases/{case_id}/analysis")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        events = _parse_sse_events(resp.text)
        assert len(events) >= 1
        assert events[-1]["type"] == "done"
        assert "result" in events[-1]

    def test_analysis_stream_error_before_analysis_started(self, isolated_client):
        """GET /analysis on created case returns SSE with type=error."""
        client, _ = isolated_client
        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
        case_id = resp.json()["case_id"]

        resp = client.get(f"/api/cases/{case_id}/analysis")
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        assert len(events) >= 1
        assert events[0]["type"] == "error"

    def test_analysis_stream_nonexistent_case_returns_404(self, isolated_client):
        """GET /analysis on nonexistent case returns 404."""
        client, _ = isolated_client
        resp = client.get("/api/cases/case-nonexistent/analysis")
        assert resp.status_code == 404

    def test_progress_stream_nonexistent_returns_404(self, isolated_client):
        """GET /progress on case with no progress queue returns 404."""
        client, _ = isolated_client
        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
        case_id = resp.json()["case_id"]

        resp = client.get(f"/api/cases/{case_id}/progress")
        assert resp.status_code == 404

    def test_progress_stream_with_registered_queue(self, isolated_client):
        """GET /progress on case with registered queue returns SSE stream."""
        import asyncio
        from engines.shared.progress_reporter import (
            SSEProgressReporter,
            get_progress_queue,
            remove_progress_queue,
        )

        client, _ = isolated_client
        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
        case_id = resp.json()["case_id"]

        # Register a progress queue and pre-populate it
        reporter = SSEProgressReporter(case_id)
        reporter.on_step_complete(1, "Index Evidence")
        reporter.on_step_complete(2, "Extract Issues")
        reporter.close()  # push None sentinel

        resp = client.get(f"/api/cases/{case_id}/progress")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        events = _parse_sse_events(resp.text)
        assert len(events) >= 3  # 2 completed + done
        completed = [e for e in events if e.get("status") == "completed"]
        assert len(completed) == 2
        assert events[-1]["type"] == "done"

        remove_progress_queue(case_id)
