"""
Unit 9: 分析结果查询端点测试
Tests for:
  GET /api/cases/{case_id}/artifacts
  GET /api/cases/{case_id}/artifacts/{artifact_name}
  GET /api/cases/{case_id}/report/markdown

Units 4, 5, 6: evidence lifecycle, baseline emission, workspace persistence
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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


# ---------------------------------------------------------------------------
# Unit 4: evidence lifecycle via EvidenceStateMachine
# ---------------------------------------------------------------------------


def _make_fake_adversarial_result(case_id: str, run_id: str, cited_ids: list[str]):
    """Build a minimal AdversarialResult with the given cited evidence IDs."""
    from engines.adversarial.schemas import AdversarialResult, RoundState, RoundPhase
    from engines.shared.models import AgentOutput

    outputs = []
    if cited_ids:
        output = AgentOutput(
            output_id=f"out-{run_id[:8]}",
            case_id=case_id,
            run_id=run_id,
            state_id="state-test",
            phase="opening",
            round_index=1,
            agent_role_code="plaintiff_agent",
            owner_party_id="p1",
            issue_ids=["issue-001"],
            title="Test argument",
            body="Test body",
            evidence_citations=cited_ids,
            statement_class="fact",
            created_at="2026-03-31T00:00:00Z",
        )
        outputs.append(output)
    round_state = RoundState(round_number=1, phase=RoundPhase.claim, outputs=outputs)
    return AdversarialResult(
        case_id=case_id,
        run_id=run_id,
        rounds=[round_state],
    )


def _make_ev(evidence_id: str, case_id: str, owner_party_id: str):
    """Build a minimal private Evidence object."""
    from engines.shared.models import Evidence, EvidenceStatus, AccessDomain

    return Evidence(
        evidence_id=evidence_id,
        case_id=case_id,
        owner_party_id=owner_party_id,
        title="Test evidence",
        source="test source",
        summary="test summary",
        evidence_type="documentary",
        target_fact_ids=["fact-001"],
        status=EvidenceStatus.private,
        access_domain=AccessDomain.owner_private,
    )


class TestUnit4EvidenceStateMachine:
    """Unit 4: API analysis must promote evidence via EvidenceStateMachine, not direct mutation."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        store._cases.clear()
        # Disable workspace writes during unit tests
        import api.service as svc

        self._orig_base = svc._WORKSPACE_BASE
        svc._WORKSPACE_BASE = None
        yield
        store._cases.clear()
        svc._WORKSPACE_BASE = self._orig_base

    def test_cited_evidence_promoted_via_state_machine(self, tmp_path):
        """Cited private evidence must reach admitted_for_discussion via state machine."""
        from api.service import run_analysis
        from engines.shared.models import EvidenceIndex, EvidenceStatus, AccessDomain, IssueTree

        record = store.create(_CASE_INFO)
        case_id = record.case_id
        p_id = _CASE_INFO["plaintiff"]["party_id"]
        d_id = _CASE_INFO["defendant"]["party_id"]

        ev_cited = _make_ev("ev-cited", case_id, p_id)
        ev_uncited = _make_ev("ev-uncited", case_id, d_id)
        record.ev_index = EvidenceIndex(case_id=case_id, evidence=[ev_cited, ev_uncited])
        record.issue_tree = IssueTree(case_id=case_id)
        record.status = CaseStatus.confirmed

        fake_result = _make_fake_adversarial_result(case_id, "run-test-unit4", ["ev-cited"])
        fake_result = fake_result.model_copy(update={"summary": None})

        with patch("api.service._run_rounds", new_callable=AsyncMock, return_value=fake_result):
            with patch("api.service._PROJECT_ROOT", tmp_path):
                asyncio.run(run_analysis(record))

        cited = next(e for e in record.ev_index.evidence if e.evidence_id == "ev-cited")
        uncited = next(e for e in record.ev_index.evidence if e.evidence_id == "ev-uncited")

        assert cited.status == EvidenceStatus.admitted_for_discussion
        assert cited.access_domain == AccessDomain.admitted_record
        assert uncited.status == EvidenceStatus.private
        assert uncited.access_domain == AccessDomain.owner_private

    def test_promoted_evidence_access_domain_consistent_with_status(self, tmp_path):
        """access_domain must be admitted_record after promotion — no stale domain."""
        from api.service import run_analysis
        from engines.shared.models import EvidenceIndex, EvidenceStatus, AccessDomain, IssueTree

        record = store.create(_CASE_INFO)
        case_id = record.case_id
        p_id = _CASE_INFO["plaintiff"]["party_id"]

        ev = _make_ev("ev-001", case_id, p_id)
        record.ev_index = EvidenceIndex(case_id=case_id, evidence=[ev])
        record.issue_tree = IssueTree(case_id=case_id)
        record.status = CaseStatus.confirmed

        fake_result = _make_fake_adversarial_result(case_id, "run-domain-check", ["ev-001"])
        fake_result = fake_result.model_copy(update={"summary": None})

        with patch("api.service._run_rounds", new_callable=AsyncMock, return_value=fake_result):
            with patch("api.service._PROJECT_ROOT", tmp_path):
                asyncio.run(run_analysis(record))

        promoted = record.ev_index.evidence[0]
        # status and access_domain must be jointly consistent
        assert promoted.status == EvidenceStatus.admitted_for_discussion
        assert promoted.access_domain == AccessDomain.admitted_record

    def test_uncited_evidence_not_promoted(self, tmp_path):
        """Evidence not cited in any round must remain private."""
        from api.service import run_analysis
        from engines.shared.models import EvidenceIndex, EvidenceStatus, IssueTree

        record = store.create(_CASE_INFO)
        case_id = record.case_id
        d_id = _CASE_INFO["defendant"]["party_id"]

        ev = _make_ev("ev-not-cited", case_id, d_id)
        record.ev_index = EvidenceIndex(case_id=case_id, evidence=[ev])
        record.issue_tree = IssueTree(case_id=case_id)
        record.status = CaseStatus.confirmed

        # Result cites no evidence
        fake_result = _make_fake_adversarial_result(case_id, "run-nocite", [])
        fake_result = fake_result.model_copy(update={"summary": None})

        with patch("api.service._run_rounds", new_callable=AsyncMock, return_value=fake_result):
            with patch("api.service._PROJECT_ROOT", tmp_path):
                asyncio.run(run_analysis(record))

        assert record.ev_index.evidence[0].status == EvidenceStatus.private


# ---------------------------------------------------------------------------
# Unit 5: canonical baseline artifacts + stable run_id
# ---------------------------------------------------------------------------


class TestUnit5BaselineEmission:
    """Unit 5: analysis must write baseline artifacts and expose stable run_id."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        store._cases.clear()
        import api.service as svc

        self._orig_base = svc._WORKSPACE_BASE
        svc._WORKSPACE_BASE = None
        yield
        store._cases.clear()
        svc._WORKSPACE_BASE = self._orig_base

    def test_analysis_data_contains_run_id(self, tmp_path):
        """analysis_data must contain run_id after analysis completes."""
        from api.service import run_analysis
        from engines.shared.models import EvidenceIndex, IssueTree

        record = store.create(_CASE_INFO)
        case_id = record.case_id
        record.ev_index = EvidenceIndex(case_id=case_id, evidence=[])
        record.issue_tree = IssueTree(case_id=case_id)
        record.status = CaseStatus.confirmed

        fake_result = _make_fake_adversarial_result(case_id, "run-stable-id", [])
        fake_result = fake_result.model_copy(update={"summary": None})

        with patch("api.service._run_rounds", new_callable=AsyncMock, return_value=fake_result):
            with patch("api.service._PROJECT_ROOT", tmp_path):
                asyncio.run(run_analysis(record))

        assert record.run_id == "run-stable-id"
        assert record.analysis_data is not None
        assert record.analysis_data["run_id"] == "run-stable-id"

    def test_baseline_artifacts_written_to_outputs_run_id(self, tmp_path):
        """Baseline issue_tree.json + evidence_index.json must be written under outputs/{run_id}/."""
        from api.service import run_analysis
        from engines.shared.models import EvidenceIndex, IssueTree

        record = store.create(_CASE_INFO)
        case_id = record.case_id
        record.ev_index = EvidenceIndex(case_id=case_id, evidence=[])
        record.issue_tree = IssueTree(case_id=case_id)
        record.status = CaseStatus.confirmed

        fake_result = _make_fake_adversarial_result(case_id, "run-baseline-write", [])
        fake_result = fake_result.model_copy(update={"summary": None})

        with patch("api.service._run_rounds", new_callable=AsyncMock, return_value=fake_result):
            with patch("api.service._PROJECT_ROOT", tmp_path):
                asyncio.run(run_analysis(record))

        baseline_dir = tmp_path / "outputs" / "run-baseline-write"
        assert baseline_dir.is_dir()
        assert (baseline_dir / "issue_tree.json").exists()
        assert (baseline_dir / "evidence_index.json").exists()
        assert (baseline_dir / "result.json").exists()

    def test_scenario_service_can_find_baseline_by_run_id(self, tmp_path):
        """ScenarioService must be able to locate baseline via run_id from analysis."""
        from api.service import run_analysis, ScenarioService
        from engines.shared.models import EvidenceIndex, IssueTree

        record = store.create(_CASE_INFO)
        case_id = record.case_id
        record.ev_index = EvidenceIndex(case_id=case_id, evidence=[])
        record.issue_tree = IssueTree(case_id=case_id)
        record.status = CaseStatus.confirmed

        fake_result = _make_fake_adversarial_result(case_id, "run-scenario-link", [])
        fake_result = fake_result.model_copy(update={"summary": None})

        with patch("api.service._run_rounds", new_callable=AsyncMock, return_value=fake_result):
            with patch("api.service._PROJECT_ROOT", tmp_path):
                asyncio.run(run_analysis(record))

        # ScenarioService should find the baseline at outputs/{run_id}/
        svc = ScenarioService(tmp_path / "outputs")
        baseline_dir = tmp_path / "outputs" / record.run_id
        assert baseline_dir.is_dir(), "baseline dir must exist for scenario service"


# ---------------------------------------------------------------------------
# Unit 6: workspace-backed persistence
# ---------------------------------------------------------------------------


class TestUnit6WorkspacePersistence:
    """Unit 6: CaseStore must persist durable state and support restart recovery."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        store._cases.clear()
        import api.service as svc

        self._orig_base = svc._WORKSPACE_BASE
        svc._WORKSPACE_BASE = tmp_path / "workspaces" / "api"
        self._tmp = tmp_path
        yield
        store._cases.clear()
        svc._WORKSPACE_BASE = self._orig_base

    def test_create_initializes_workspace(self):
        """CaseStore.create() must initialize a workspace directory."""
        import api.service as svc

        record = store.create(_CASE_INFO)
        ws_dir = svc._WORKSPACE_BASE / record.case_id
        assert ws_dir.is_dir(), "workspace dir must exist after create"
        assert (ws_dir / "workspace.json").exists(), "workspace.json must exist"
        assert (ws_dir / "case_meta.json").exists(), "case_meta.json must exist"

    def test_analysis_completion_persists_run_id(self, tmp_path):
        """After analysis, case_meta.json must contain run_id."""
        import api.service as svc
        from api.service import run_analysis
        from engines.shared.models import EvidenceIndex, IssueTree

        record = store.create(_CASE_INFO)
        case_id = record.case_id
        record.ev_index = EvidenceIndex(case_id=case_id, evidence=[])
        record.issue_tree = IssueTree(case_id=case_id)
        record.status = CaseStatus.confirmed

        fake_result = _make_fake_adversarial_result(case_id, "run-persisted-001", [])
        fake_result = fake_result.model_copy(update={"summary": None})

        with patch("api.service._run_rounds", new_callable=AsyncMock, return_value=fake_result):
            with patch("api.service._PROJECT_ROOT", tmp_path):
                asyncio.run(run_analysis(record))

        meta_path = svc._WORKSPACE_BASE / case_id / "case_meta.json"
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        assert meta["run_id"] == "run-persisted-001"
        assert meta["status"] == "analyzed"

    def test_load_from_workspace_recovers_completed_case(self, tmp_path):
        """After clearing memory, load_from_workspace must reconstruct analyzed CaseRecord."""
        import api.service as svc
        from api.service import run_analysis
        from engines.shared.models import EvidenceIndex, IssueTree

        record = store.create(_CASE_INFO)
        case_id = record.case_id
        record.ev_index = EvidenceIndex(case_id=case_id, evidence=[])
        record.issue_tree = IssueTree(case_id=case_id)
        record.status = CaseStatus.confirmed

        fake_result = _make_fake_adversarial_result(case_id, "run-recovery-001", [])
        fake_result = fake_result.model_copy(update={"summary": None})

        with patch("api.service._run_rounds", new_callable=AsyncMock, return_value=fake_result):
            with patch("api.service._PROJECT_ROOT", tmp_path):
                asyncio.run(run_analysis(record))

        # Simulate restart: clear in-memory store
        store._cases.clear()
        assert store.get(case_id) is None, "must be gone from memory"

        # Recovery via workspace
        recovered = store.load_from_workspace(case_id)
        assert recovered is not None, "must be recoverable from workspace"
        assert recovered.case_id == case_id
        assert recovered.status == CaseStatus.analyzed
        assert recovered.run_id == "run-recovery-001"
        assert recovered.analysis_data is not None
        assert recovered.analysis_data["run_id"] == "run-recovery-001"

    def test_load_from_workspace_returns_none_for_unknown_case(self):
        """load_from_workspace must return None for a case_id that was never created."""
        result = store.load_from_workspace("case-does-not-exist")
        assert result is None


# ---------------------------------------------------------------------------
# iter_progress — SSE 重连历史回放
# ---------------------------------------------------------------------------


class TestIterProgressReplay:
    @pytest.mark.asyncio
    async def test_iter_progress_replays_history_after_completion(self):
        """已完成的 case，SSE 重连应先回放 progress 历史，再发送完成事件，不能直接返回空。"""
        record = store.create(_CASE_INFO)
        record.status = CaseStatus.analyzed
        record.progress = ["step1", "step2", "done"]

        events = [e async for e in record.iter_progress()]
        assert len(events) >= 3, f"期望 ≥3 个事件，实际得到 {events}"
        assert "step1" in events[0]
        assert "done" in events[-1]

    @pytest.mark.asyncio
    async def test_iter_progress_replays_history_after_failed(self):
        """失败的 case，重连也应回放已有历史。"""
        record = store.create(_CASE_INFO)
        record.status = CaseStatus.failed
        record.progress = ["init", "error: timeout"]

        events = [e async for e in record.iter_progress()]
        assert len(events) >= 2
        assert "init" in events[0]
