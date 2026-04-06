from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

import api.app as app_module
import api.service as service_module
from api.schemas import CaseStatus
from api.service import CaseStore, ScenarioService, run_analysis
from engines.shared.models import Evidence, EvidenceIndex, EvidenceStatus, EvidenceType, IssueTree
from engines.shared.models.analysis import Issue, IssueStatus, IssueType


_CASE_INFO = {
    "case_type": "civil_loan",
    "plaintiff": {"party_id": "p-test", "name": "Plaintiff"},
    "defendant": {"party_id": "d-test", "name": "Defendant"},
    "claims": [],
    "defenses": [],
}


def _make_material() -> dict:
    return {
        "source_id": "src-001",
        "role": "plaintiff",
        "doc_type": "contract",
        "text": "Loan agreement",
    }


def _make_issue_tree(case_id: str) -> IssueTree:
    issue = Issue(
        issue_id="issue-001",
        case_id=case_id,
        title="Repayment obligation",
        description="Whether repayment remains due",
        issue_type=IssueType.legal,
        status=IssueStatus.open,
    )
    return IssueTree(case_id=case_id, issues=[issue], burdens=[])


def _make_evidence_index(case_id: str) -> EvidenceIndex:
    evidence = Evidence(
        evidence_id="ev-001",
        case_id=case_id,
        owner_party_id="p-test",
        title="Loan agreement",
        source="src-001",
        summary="Signed agreement",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=["fact-001"],
        status=EvidenceStatus.private,
    )
    return EvidenceIndex(case_id=case_id, evidence=[evidence])


def _make_fake_result(case_id: str, run_id: str = "run-test-001"):
    from engines.adversarial.schemas import AdversarialResult, RoundPhase, RoundState
    from engines.shared.models import AgentOutput

    output = AgentOutput(
        output_id="out-001",
        case_id=case_id,
        run_id=run_id,
        state_id="state-001",
        phase="opening",
        round_index=1,
        agent_role_code="plaintiff_agent",
        owner_party_id="p-test",
        issue_ids=["issue-001"],
        title="Opening",
        body="Opening body",
        evidence_citations=["ev-001"],
        statement_class="fact",
        created_at="2026-04-02T00:00:00Z",
    )
    return AdversarialResult(
        case_id=case_id,
        run_id=run_id,
        rounds=[RoundState(round_number=1, phase=RoundPhase.claim, outputs=[output])],
        summary=None,
    )


def test_extract_endpoint_is_single_flight():
    test_store = CaseStore()

    with (
        patch.object(service_module, "store", test_store),
        patch.object(app_module, "store", test_store),
    ):
        client = TestClient(app_module.app)
        create_resp = client.post("/api/cases/", json=_CASE_INFO)
        case_id = create_resp.json()["case_id"]
        client.post(f"/api/cases/{case_id}/materials", json=_make_material())

        scheduled: list[str] = []

        def fake_create_task(coro):
            scheduled.append("extract")
            coro.close()
            return MagicMock()

        with patch("api.app.asyncio.create_task", side_effect=fake_create_task):
            first = client.post(f"/api/cases/{case_id}/extract")
            second = client.post(f"/api/cases/{case_id}/extract")

        assert first.status_code == 202
        assert second.status_code == 202
        assert len(scheduled) == 1
        assert test_store.get(case_id).status == CaseStatus.extracting


def test_analyze_endpoint_is_single_flight():
    test_store = CaseStore()

    with (
        patch.object(service_module, "store", test_store),
        patch.object(app_module, "store", test_store),
    ):
        client = TestClient(app_module.app)
        create_resp = client.post("/api/cases/", json=_CASE_INFO)
        case_id = create_resp.json()["case_id"]
        record = test_store.get(case_id)
        assert record is not None
        record.ev_index = _make_evidence_index(case_id)
        record.issue_tree = _make_issue_tree(case_id)
        record.extraction_data = {
            "evidence": [e.model_dump(mode="json") for e in record.ev_index.evidence],
            "issues": [i.model_dump(mode="json") for i in record.issue_tree.issues],
        }
        record.status = CaseStatus.confirmed

        scheduled: list[str] = []

        def fake_create_task(coro):
            scheduled.append("analyze")
            coro.close()
            return MagicMock()

        with patch("api.app.asyncio.create_task", side_effect=fake_create_task):
            first = client.post(f"/api/cases/{case_id}/analyze")
            second = client.post(f"/api/cases/{case_id}/analyze")

        assert first.status_code == 202
        assert second.status_code == 202
        assert len(scheduled) == 1
        assert test_store.get(case_id).status == CaseStatus.analyzing


def test_analysis_stream_replays_history_once():
    test_store = CaseStore()

    with (
        patch.object(service_module, "store", test_store),
        patch.object(app_module, "store", test_store),
    ):
        record = test_store.create(_CASE_INFO)
        record.status = CaseStatus.analyzing
        record.progress = ["step1", "step2"]
        record._progress_queue.put_nowait(None)

        client = TestClient(app_module.app)
        with client.stream("GET", f"/api/cases/{record.case_id}/analysis") as response:
            lines = [line for line in response.iter_lines() if line]

    progress_lines = [line for line in lines if '"type": "progress"' in line]
    assert progress_lines == [
        'data: {"type": "progress", "message": "step1"}',
        'data: {"type": "progress", "message": "step2"}',
    ]


def test_reports_and_artifacts_survive_workspace_recovery(tmp_path):
    test_store = CaseStore(workspaces_dir=tmp_path / "workspaces" / "api")
    original_ws_base = service_module._WORKSPACE_BASE
    original_root = service_module._PROJECT_ROOT

    def fake_docx_generator(*, output_dir: Path, **kwargs):
        path = output_dir / "report.docx"
        path.write_bytes(b"fake-docx")
        return path

    try:
        service_module._WORKSPACE_BASE = tmp_path / "workspaces" / "api"
        service_module._PROJECT_ROOT = tmp_path

        with (
            patch.object(service_module, "store", test_store),
            patch.object(app_module, "store", test_store),
        ):
            client = TestClient(app_module.app)
            create_resp = client.post("/api/cases/", json=_CASE_INFO)
            case_id = create_resp.json()["case_id"]
            record = test_store.get(case_id)
            assert record is not None
            record.ev_index = _make_evidence_index(case_id)
            record.issue_tree = _make_issue_tree(case_id)
            record.status = CaseStatus.confirmed

            fake_result = _make_fake_result(case_id, run_id="run-recovery-001")
            with patch("api.service._run_rounds", new=AsyncMock(return_value=fake_result)):
                with patch(
                    "api.service._generate_markdown_report", return_value="# persisted report"
                ):
                    with patch(
                        "engines.report_generation.v3.report_writer.build_four_layer_report",
                        return_value=MagicMock(model_dump_json=lambda: '{"report_id":"r","case_id":"c","run_id":"r","perspective":"neutral","layer1":{"cover_summary":{"neutral_conclusion":"","winning_move":"","blocking_conditions":[]},"timeline":[],"evidence_priorities":[],"evidence_traffic_lights":[],"scenario_tree_summary":""},"layer2":{"fact_base":[],"issue_map":[],"evidence_cards":[],"unified_electronic_strategy":"","evidence_battle_matrix":[],"scenario_tree":null},"layer3":{"outputs":[]},"layer4":{"adversarial_transcripts_md":"","evidence_index_md":"","timeline_md":"","glossary_md":"","amount_calculation_md":""},"created_at":"2024-01-01T00:00:00Z"}'),
                    ):
                        with patch(
                            "engines.report_generation.docx_generator.generate_docx_v3_report",
                            side_effect=fake_docx_generator,
                        ):
                            asyncio.run(run_analysis(record))

            test_store._cases.clear()

            artifacts_resp = client.get(f"/api/cases/{case_id}/artifacts")
            artifact_resp = client.get(f"/api/cases/{case_id}/artifacts/result.json")
            markdown_resp = client.get(f"/api/cases/{case_id}/report/markdown")
            docx_resp = client.get(f"/api/cases/{case_id}/report")

        assert artifacts_resp.status_code == 200
        assert set(artifacts_resp.json()["artifacts"]) >= {
            "result.json",
            "analysis_summary.json",
            "report.md",
        }
        assert artifact_resp.status_code == 200
        assert artifact_resp.json()["run_id"] == "run-recovery-001"
        assert markdown_resp.status_code == 200
        assert markdown_resp.text == "# persisted report"
        assert docx_resp.status_code == 200
        assert docx_resp.content == b"fake-docx"
    finally:
        service_module._WORKSPACE_BASE = original_ws_base
        service_module._PROJECT_ROOT = original_root


def test_scenario_service_reads_case_type_from_baseline_metadata(tmp_path):
    outputs_dir = tmp_path / "outputs"
    baseline_dir = outputs_dir / "run-baseline-001"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    (baseline_dir / "baseline_meta.json").write_text(
        json.dumps(
            {
                "case_id": "case-001",
                "run_id": "run-baseline-001",
                "case_type": "real_estate",
            }
        ),
        encoding="utf-8",
    )

    issue_tree = _make_issue_tree("case-001")
    evidence_index = _make_evidence_index("case-001")
    simulator_instance = MagicMock()
    fake_result = MagicMock()
    fake_result.model_dump.return_value = {
        "scenario": {
            "scenario_id": "scenario-001",
            "case_id": "case-001",
            "baseline_run_id": "run-baseline-001",
            "diff_summary": [],
            "affected_issue_ids": [],
            "affected_evidence_ids": [],
            "status": "completed",
        },
        "run": {
            "run_id": "run-scenario-001",
            "case_id": "case-001",
            "workspace_id": "workspace-run-baseline-001",
            "scenario_id": "scenario-001",
            "trigger_type": "scenario_execution",
            "input_snapshot": {"material_refs": [], "artifact_refs": []},
            "output_refs": [],
            "started_at": "2026-04-02T00:00:00Z",
            "finished_at": "2026-04-02T00:00:01Z",
            "status": "completed",
        },
    }
    simulator_instance.simulate = AsyncMock(return_value=fake_result)

    with (
        patch(
            "engines.simulation_run.simulator.load_baseline",
            return_value=(issue_tree, evidence_index, "run-baseline-001"),
        ),
        patch(
            "engines.simulation_run.simulator.ScenarioSimulator",
            return_value=simulator_instance,
        ) as simulator_cls,
    ):
        service = ScenarioService(outputs_dir)
        asyncio.run(
            service.run(
                run_id="run-baseline-001",
                change_set=[
                    {
                        "target_object_type": "Evidence",
                        "target_object_id": "ev-001",
                        "field_path": "summary",
                        "old_value": "before",
                        "new_value": "after",
                    }
                ],
            )
        )

    assert simulator_cls.call_args.kwargs["case_type"] == "real_estate"
