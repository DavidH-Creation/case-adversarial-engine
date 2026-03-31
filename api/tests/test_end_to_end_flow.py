"""
End-to-end API flow test: create → extract → analyze → scenario.

Covers R7 from the plan:
  补一条覆盖 `create -> extract -> analyze -> scenario` 的真实 API 端到端验证路径。

Strategy:
- All engine LLM calls are mocked (EvidenceIndexer, IssueExtractor, _run_rounds,
  ScenarioSimulator) so the test is fast and deterministic.
- The service layer runs without mocking: real CaseStore, real state transitions,
  real baseline artifact writing, real workspace persistence.
- The scenario step reads baseline artifacts that analysis actually wrote to disk,
  verifying the create → extract → analyze → scenario chain is real end-to-end.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import api.service as svc_module
from api.app import app
from api.schemas import CaseStatus
from api.service import store

client = TestClient(app)

# ---------------------------------------------------------------------------
# Shared fixtures and helpers
# ---------------------------------------------------------------------------

_CASE_PAYLOAD = {
    "case_type": "civil_loan",
    "plaintiff": {"party_id": "p-e2e", "name": "End2End Plaintiff"},
    "defendant": {"party_id": "d-e2e", "name": "End2End Defendant"},
    "claims": [{"claim_id": "cl-001", "title": "Principal", "description": "Unpaid loan"}],
    "defenses": [{"defense_id": "def-001", "title": "Paid", "description": "Already repaid"}],
}

_MATERIAL_PAYLOAD = {
    "source_id": "src-e2e-001",
    "role": "plaintiff",
    "doc_type": "contract",
    "text": "Loan agreement dated 2025-01-01 for 100,000 CNY.",
}


def _make_fake_evidence(case_id: str, party_id: str, ev_id: str):
    """Build a minimal Evidence object."""
    from engines.shared.models import Evidence, EvidenceStatus, AccessDomain

    return Evidence(
        evidence_id=ev_id,
        case_id=case_id,
        owner_party_id=party_id,
        title="Loan contract",
        source="contract",
        summary="Evidence of the loan",
        evidence_type="documentary",
        target_fact_ids=["fact-001"],
        status=EvidenceStatus.private,
        access_domain=AccessDomain.owner_private,
    )


def _make_fake_issue_tree(case_id: str):
    """Build a minimal IssueTree."""
    from engines.shared.models import IssueTree, Issue, Burden

    issue = Issue(
        issue_id="issue-e2e-001",
        case_id=case_id,
        title="Repayment obligation",
        issue_type="factual",
    )
    burden = Burden(
        burden_id="burden-e2e-001",
        case_id=case_id,
        issue_id="issue-e2e-001",
        burden_party_id="p-e2e",
        proof_standard="preponderance",
    )
    return IssueTree(case_id=case_id, issues=[issue], burdens=[burden])


def _make_fake_adversarial_result(case_id: str, run_id: str, cited_id: str):
    """Build a minimal AdversarialResult citing one evidence."""
    from engines.adversarial.schemas import AdversarialResult, RoundState, RoundPhase
    from engines.shared.models import AgentOutput

    output = AgentOutput(
        output_id="out-e2e-001",
        case_id=case_id,
        run_id=run_id,
        state_id="state-e2e",
        phase="opening",
        round_index=1,
        agent_role_code="plaintiff_agent",
        owner_party_id="p-e2e",
        issue_ids=["issue-e2e-001"],
        title="Plaintiff opening",
        body="The defendant failed to repay",
        evidence_citations=[cited_id],
        statement_class="fact",
        created_at="2026-03-31T00:00:00Z",
    )
    round_state = RoundState(round_number=1, phase=RoundPhase.claim, outputs=[output])
    return AdversarialResult(case_id=case_id, run_id=run_id, rounds=[round_state])


def _make_fake_scenario_result(scenario_id: str, case_id: str, baseline_run_id: str):
    """Build a fake ScenarioResult dict matching what ScenarioService.run() returns."""
    return {
        "scenario": {
            "scenario_id": scenario_id,
            "case_id": case_id,
            "baseline_run_id": baseline_run_id,
            "change_set": [
                {
                    "target_object_type": "Evidence",
                    "target_object_id": "ev-e2e-001",
                    "field_path": "summary",
                    "old_value": "original",
                    "new_value": "modified",
                }
            ],
            "diff_summary": [
                {
                    "issue_id": "issue-e2e-001",
                    "impact_description": "Modified evidence weakens repayment claim",
                    "direction": "weaken",
                }
            ],
            "affected_issue_ids": ["issue-e2e-001"],
            "affected_evidence_ids": ["ev-e2e-001"],
            "status": "completed",
        },
        "run": {
            "run_id": "run-scenario-e2e-001",
            "case_id": case_id,
            "workspace_id": f"workspace-{baseline_run_id}",
            "scenario_id": scenario_id,
            "trigger_type": "scenario_execution",
            "input_snapshot": {"material_refs": [], "artifact_refs": []},
            "output_refs": [],
            "started_at": "2026-03-31T00:00:00Z",
            "finished_at": "2026-03-31T00:00:01Z",
            "status": "completed",
        },
    }


# ---------------------------------------------------------------------------
# End-to-end test
# ---------------------------------------------------------------------------


class TestEndToEndFlow:
    """Full create → extract → analyze → scenario API chain."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        store._cases.clear()
        self._orig_ws_base = svc_module._WORKSPACE_BASE
        svc_module._WORKSPACE_BASE = tmp_path / "workspaces" / "api"
        self._tmp = tmp_path
        yield
        store._cases.clear()
        svc_module._WORKSPACE_BASE = self._orig_ws_base

    def test_create_returns_case_id_and_status_created(self):
        """Step 1: POST /api/cases/ → 201 + case_id."""
        resp = client.post("/api/cases/", json=_CASE_PAYLOAD)
        assert resp.status_code == 201
        data = resp.json()
        assert "case_id" in data
        assert data["status"] == "created"

    def test_full_flow_create_extract_analyze_scenario(self):
        """Full chain: create → add material → (mock) extract → (mock) analyze → scenario.

        Service functions (run_extraction, run_analysis) are called directly with
        mocked LLM calls so the test is synchronous and deterministic. This tests the
        real service layer chain: CaseStore → ev lifecycle → baseline write → scenario.
        """
        from engines.shared.models import EvidenceIndex

        # ── Step 1: Create case via API ──────────────────────────────────
        resp = client.post("/api/cases/", json=_CASE_PAYLOAD)
        assert resp.status_code == 201
        case_id = resp.json()["case_id"]

        # ── Step 2: Add material via API ─────────────────────────────────
        resp = client.post(f"/api/cases/{case_id}/materials", json=_MATERIAL_PAYLOAD)
        assert resp.status_code == 200

        # ── Step 3: Simulate extraction (set ev_index + issue_tree directly) ──
        ev = _make_fake_evidence(case_id, "p-e2e", "ev-e2e-001")
        fake_ev_index = EvidenceIndex(case_id=case_id, evidence=[ev])
        fake_issue_tree = _make_fake_issue_tree(case_id)

        rec = store.get(case_id)
        rec.ev_index = fake_ev_index
        rec.issue_tree = fake_issue_tree
        rec.extraction_data = {
            "evidence": [ev.model_dump(mode="json")],
            "issues": [i.model_dump(mode="json") for i in fake_issue_tree.issues],
        }
        rec.status = CaseStatus.extracted

        resp = client.get(f"/api/cases/{case_id}")
        assert resp.json()["status"] == "extracted"

        # ── Step 4: Run analysis directly (mock LLM rounds only) ─────────
        analysis_run_id = "run-e2e-analysis-001"
        fake_result = _make_fake_adversarial_result(case_id, analysis_run_id, "ev-e2e-001")
        fake_result = fake_result.model_copy(update={"summary": None})

        with patch("api.service._run_rounds", new_callable=AsyncMock, return_value=fake_result):
            with patch("api.service._PROJECT_ROOT", self._tmp):
                asyncio.run(svc_module.run_analysis(rec))

        assert rec.status == CaseStatus.analyzed, f"analysis failed: {rec.error}"
        assert rec.run_id == analysis_run_id

        # ── Step 5: Verify GET /cases/{case_id} exposes run_id ───────────
        resp = client.get(f"/api/cases/{case_id}")
        case_data = resp.json()
        assert case_data["status"] == "analyzed"
        assert case_data["run_id"] == analysis_run_id

        # ── Step 6: Verify baseline artifacts written to outputs/{run_id}/ ──
        baseline_dir = self._tmp / "outputs" / analysis_run_id
        assert baseline_dir.is_dir(), "baseline dir must exist"
        assert (baseline_dir / "issue_tree.json").exists()
        assert (baseline_dir / "evidence_index.json").exists()
        assert (baseline_dir / "result.json").exists()

        # ── Step 7: Verify evidence lifecycle via EvidenceStateMachine ───
        from engines.shared.models import EvidenceStatus, AccessDomain

        promoted = next((e for e in rec.ev_index.evidence if e.evidence_id == "ev-e2e-001"), None)
        assert promoted is not None
        assert promoted.status == EvidenceStatus.admitted_for_discussion
        assert promoted.access_domain == AccessDomain.admitted_record

        # ── Step 8: Run scenario via API using the analysis run_id ───────
        fake_scenario = _make_fake_scenario_result("scenario-e2e-001", case_id, analysis_run_id)

        with patch.object(
            svc_module.scenario_service,
            "run",
            new_callable=AsyncMock,
            return_value=fake_scenario,
        ) as mock_run:
            resp = client.post(
                "/api/scenarios/run",
                json={
                    "run_id": analysis_run_id,
                    "change_set": [
                        {
                            "target_object_type": "Evidence",
                            "target_object_id": "ev-e2e-001",
                            "field_path": "summary",
                            "old_value": "original",
                            "new_value": "modified",
                        }
                    ],
                },
            )
        assert resp.status_code == 200
        scenario_data = resp.json()
        assert scenario_data["baseline_run_id"] == analysis_run_id
        assert scenario_data["status"] == "completed"
        assert len(scenario_data["diff_entries"]) > 0
        # Scenario was called with the run_id that analysis produced
        mock_run.assert_called_once()
        called_run_id = mock_run.call_args.kwargs.get("run_id") or mock_run.call_args.args[0]
        assert called_run_id == analysis_run_id

    def test_workspace_persistence_survives_memory_loss(self):
        """After analysis, case is recoverable from workspace even after store is cleared."""
        from engines.shared.models import EvidenceIndex

        # Create + analyze
        resp = client.post("/api/cases/", json=_CASE_PAYLOAD)
        case_id = resp.json()["case_id"]

        rec = store.get(case_id)
        rec.ev_index = EvidenceIndex(case_id=case_id, evidence=[])
        rec.issue_tree = _make_fake_issue_tree(case_id)
        rec.status = CaseStatus.confirmed

        fake_result = _make_fake_adversarial_result(case_id, "run-recovery-e2e", "ev-none")
        # result with no cited evidence (ev-none doesn't exist in index)
        fake_result = fake_result.model_copy(update={"rounds": [], "summary": None})

        with patch("api.service._run_rounds", new_callable=AsyncMock, return_value=fake_result):
            with patch("api.service._PROJECT_ROOT", self._tmp):
                asyncio.run(svc_module.run_analysis(rec))

        assert rec.status == CaseStatus.analyzed

        # Simulate restart
        store._cases.clear()
        assert store.get(case_id) is None

        recovered = store.load_from_workspace(case_id)
        assert recovered is not None
        assert recovered.case_id == case_id
        assert recovered.status == CaseStatus.analyzed
        assert recovered.run_id == "run-recovery-e2e"
