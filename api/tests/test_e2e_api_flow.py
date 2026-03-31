"""
端到端 API 流程测试。
End-to-end API flow test: create case → extract (mocked) → analyze (mocked) → scenario.

验证：
- P1-1: 证据提升通过 EvidenceStateMachine（access_domain 同步更新）
- P1-2: run_analysis 持久化 baseline 文件到 outputs/<run_id>/，analysis_data 含 run_id
- P2-3: CaseStore 与 WorkspaceManager 集成，进程重启后可从磁盘恢复案件状态
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import anyio
import pytest
from fastapi.testclient import TestClient

import api.service as service_module
from api.app import app
from api.schemas import CaseStatus
from api.service import CaseRecord, CaseStore, _PROJECT_ROOT, run_analysis
from engines.adversarial.schemas import AdversarialResult, RoundPhase, RoundState
from engines.shared.models import (
    AccessDomain,
    AgentOutput,
    Evidence,
    EvidenceIndex,
    EvidenceStatus,
    EvidenceType,
    IssueTree,
    ProcedurePhase,
    StatementClass,
)
from engines.shared.models.analysis import Issue, IssueStatus, IssueType

# ---------------------------------------------------------------------------
# 测试数据
# ---------------------------------------------------------------------------

_CASE_BODY = {
    "case_type": "civil_loan",
    "plaintiff": {"party_id": "p-e2e", "name": "E2E原告"},
    "defendant": {"party_id": "d-e2e", "name": "E2E被告"},
    "claims": [],
    "defenses": [],
}

_MATERIAL_BODY = {
    "source_id": "src-e2e-001",
    "role": "plaintiff",
    "doc_type": "contract",
    "text": "E2E test material: loan agreement for 100,000 CNY.",
}

_CHANGE_SET = [
    {
        "target_object_type": "Evidence",
        "target_object_id": "ev-e2e-001",
        "field_path": "summary",
        "old_value": "original loan contract",
        "new_value": "contested loan contract",
    }
]


# ---------------------------------------------------------------------------
# 辅助构建函数
# ---------------------------------------------------------------------------


def _make_ev_index(case_id: str) -> EvidenceIndex:
    ev = Evidence(
        evidence_id="ev-e2e-001",
        case_id=case_id,
        owner_party_id="p-e2e",
        title="E2E loan contract",
        source="src-e2e-001",
        summary="Loan contract for 100k CNY",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=["fact-e2e-001"],
        status=EvidenceStatus.private,
        access_domain=AccessDomain.owner_private,
    )
    return EvidenceIndex(case_id=case_id, evidence=[ev])


def _make_issue_tree(case_id: str) -> IssueTree:
    issue = Issue(
        issue_id="issue-e2e-001",
        case_id=case_id,
        title="借款合同效力",
        description="是否存在合法借贷关系",
        issue_type=IssueType.legal,
        status=IssueStatus.open,
    )
    return IssueTree(case_id=case_id, issues=[issue], burdens=[])


def _make_agent_output(case_id: str, run_id: str, cited_ev_id: str) -> AgentOutput:
    """构造引用了 cited_ev_id 的 AgentOutput，用于触发证据状态提升。"""
    return AgentOutput(
        output_id=f"out-e2e-{uuid.uuid4().hex[:8]}",
        case_id=case_id,
        run_id=run_id,
        state_id="state-e2e-r1",
        phase=ProcedurePhase.opening,
        round_index=0,
        agent_role_code="plaintiff_agent",
        owner_party_id="p-e2e",
        issue_ids=["issue-e2e-001"],
        title="原告开庭陈述",
        body="原告主张存在合法借贷关系，并提交合同作为证据。",
        evidence_citations=[cited_ev_id],
        statement_class=StatementClass.fact,
        created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


async def _fake_run_rounds(
    record: CaseRecord,
    issue_tree: IssueTree,
    evidence_index: EvidenceIndex,
    claude,
    config,
    plaintiff_id: str,
    defendant_id: str,
) -> AdversarialResult:
    """替代 _run_rounds 的无 LLM 版本：返回包含证据引用的最小化 AdversarialResult。"""
    run_id = f"run-e2e-{uuid.uuid4().hex[:12]}"
    agent_out = _make_agent_output(issue_tree.case_id, run_id, "ev-e2e-001")
    round_state = RoundState(
        round_number=1,
        phase=RoundPhase.claim,
        outputs=[agent_out],
    )
    return AdversarialResult(
        case_id=issue_tree.case_id,
        run_id=run_id,
        rounds=[round_state],
        summary=None,
    )


# ---------------------------------------------------------------------------
# E2E 测试
# ---------------------------------------------------------------------------


def test_e2e_create_extract_analyze_scenario(tmp_path):
    """
    端到端流程：
    1. POST /api/cases/ → 201, 获得 case_id
    2. POST /api/cases/{case_id}/materials → 200
    3. 直接注入提取状态（模拟 LLM 提取完成）
    4. GET /api/cases/{case_id}/extraction → 200
    5. 运行 run_analysis（mock _run_rounds，无 LLM）
    6. 断言 P1-1: evidence.status=admitted_for_discussion, access_domain=admitted_record
    7. 断言 P1-2: baseline 文件存在, analysis_data["run_id"] 有效
    8. 断言 P2-3: 工作区持久化，磁盘恢复后状态正确
    9. POST /api/scenarios/run 使用 run_id → 200
    """
    # 使用独立的临时工作区目录，避免污染全局 store
    test_store = CaseStore(workspaces_dir=tmp_path / "workspaces")

    with patch.object(service_module, "store", test_store), patch("api.app.store", test_store):
        client = TestClient(app)

        # ── Step 1: 创建案件 ───────────────────────────────────────────
        resp = client.post("/api/cases/", json=_CASE_BODY)
        assert resp.status_code == 201
        case_id = resp.json()["case_id"]
        assert case_id.startswith("case-")

        # ── Step 2: 添加材料 ───────────────────────────────────────────
        resp = client.post(f"/api/cases/{case_id}/materials", json=_MATERIAL_BODY)
        assert resp.status_code == 200
        assert resp.json()["source_id"] == "src-e2e-001"

        # ── Step 3: 注入提取状态（跳过真实 LLM）──────────────────────
        record = test_store.get(case_id)
        assert record is not None
        record.ev_index = _make_ev_index(case_id)
        record.issue_tree = _make_issue_tree(case_id)
        record.extraction_data = {
            "evidence": [e.model_dump(mode="json") for e in record.ev_index.evidence],
            "issues": [i.model_dump(mode="json") for i in record.issue_tree.issues],
        }
        record.status = CaseStatus.extracted

        # ── Step 4: 验证提取 API ───────────────────────────────────────
        resp = client.get(f"/api/cases/{case_id}/extraction")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["evidence"]) == 1
        assert data["evidence"][0]["evidence_id"] == "ev-e2e-001"
        assert len(data["issues"]) == 1

        # ── Step 5: 运行 run_analysis（mock _run_rounds）────────────────
        async def _do_analysis():
            with patch("api.service._run_rounds", new=_fake_run_rounds):
                await run_analysis(record)

        anyio.run(_do_analysis)

        # ── Step 6: P1-1 — 证据通过 EvidenceStateMachine 提升 ─────────
        assert record.status == CaseStatus.analyzed, f"Expected analyzed, got {record.status}"
        ev = record.ev_index.evidence[0]
        assert ev.status == EvidenceStatus.admitted_for_discussion, (
            f"Expected admitted_for_discussion, got {ev.status}"
        )
        assert ev.access_domain == AccessDomain.admitted_record, (
            f"Expected admitted_record, got {ev.access_domain} (access_domain must be updated by ESM)"
        )

        # ── Step 7: P1-2 — baseline 文件存在，run_id 在 analysis_data ─
        assert record.analysis_data is not None
        assert "run_id" in record.analysis_data, (
            "analysis_data must contain run_id for scenario API"
        )
        run_id = record.analysis_data["run_id"]
        assert run_id == record.run_id

        baseline_dir = _PROJECT_ROOT / "outputs" / run_id
        assert (baseline_dir / "issue_tree.json").exists(), "issue_tree.json must be persisted"
        assert (baseline_dir / "evidence_index.json").exists(), (
            "evidence_index.json must be persisted"
        )
        assert (baseline_dir / "result.json").exists(), "result.json must be persisted"

        # result.json 中 run_id 字段正确（供 load_baseline 使用）
        result_data = json.loads((baseline_dir / "result.json").read_text(encoding="utf-8"))
        assert result_data["run_id"] == run_id

        # ── Step 8: P2-3 — 工作区持久化与磁盘恢复 ─────────────────────
        from engines.shared.workspace_manager import WorkspaceManager

        wm = WorkspaceManager(tmp_path / "workspaces", case_id)
        meta = wm.load_case_meta()
        assert meta is not None, "case_meta.json must be saved"
        assert meta["status"] == CaseStatus.analyzed.value

        # 从内存中移除，模拟进程重启
        del test_store._cases[case_id]
        assert case_id not in test_store._cases

        # 从磁盘恢复
        restored = test_store.get(case_id)
        assert restored is not None, "Case must be recoverable from disk"
        assert restored.status == CaseStatus.analyzed
        assert restored.analysis_data is not None
        assert restored.analysis_data.get("run_id") == run_id
        assert restored.run_id == run_id

        # ── Step 9: 场景推演 API（mock scenario_service.run）──────────
        mock_scenario_result = {
            "scenario": {
                "scenario_id": "scenario-e2e-test-001",
                "case_id": case_id,
                "baseline_run_id": run_id,
                "change_set": _CHANGE_SET,
                "diff_summary": [
                    {
                        "issue_id": "issue-e2e-001",
                        "impact_description": "Contested contract weakens repayment claim.",
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
                "workspace_id": f"workspace-{run_id}",
                "scenario_id": "scenario-e2e-test-001",
                "trigger_type": "scenario_execution",
                "input_snapshot": {"material_refs": [], "artifact_refs": []},
                "output_refs": [],
                "started_at": "2026-03-31T00:00:00Z",
                "finished_at": "2026-03-31T00:00:01Z",
                "status": "completed",
            },
        }

        with patch.object(
            service_module.scenario_service,
            "run",
            new_callable=AsyncMock,
            return_value=mock_scenario_result,
        ):
            resp = client.post(
                "/api/scenarios/run",
                json={"run_id": run_id, "change_set": _CHANGE_SET},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["scenario_id"] == "scenario-e2e-test-001"
        assert data["baseline_run_id"] == run_id
        assert data["case_id"] == case_id
        assert len(data["diff_entries"]) == 1
        assert data["diff_entries"][0]["direction"] == "weaken"
        assert data["affected_issue_ids"] == ["issue-e2e-001"]
        assert data["status"] == "completed"
