"""
WorkspaceManager 单元测试。
Unit tests for WorkspaceManager.

覆盖路径 / Coverage:
1. Lifecycle: init_workspace, load_workspace
2. Run persistence: save_run, load_run (roundtrip, idempotent, missing, case_id mismatch)
3. Artifact persistence: save_* / load_* roundtrips for all artifact types
4. material_index / artifact_index updates
5. advance_stage
6. Four-step sequence end-to-end
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from engines.shared.models import (
    AccessDomain,
    AgentOutput,
    ArtifactRef,
    BurdenStatus,
    Claim,
    Defense,
    DiffDirection,
    DiffEntry,
    Evidence,
    EvidenceIndex,
    EvidenceStatus,
    EvidenceType,
    FactProposition,
    InputSnapshot,
    InteractionTurn,
    Issue,
    IssueStatus,
    IssueTree,
    IssueType,
    KeyConclusion,
    MaterialRef,
    ProcedurePhase,
    PropositionStatus,
    ReportArtifact,
    ReportSection,
    Run,
    Scenario,
    ScenarioStatus,
    ChangeItem,
    ChangeItemObjectType,
    StatementClass,
    WorkflowStage,
    Burden,
)
from engines.shared.workspace_manager import WorkspaceManager


# ---------------------------------------------------------------------------
# 工具函数 / Utilities
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mgr(tmp_path: Path, case_id: str = "case-test-001") -> WorkspaceManager:
    return WorkspaceManager(base_dir=tmp_path, case_id=case_id)


# ---------------------------------------------------------------------------
# 最小测试夹具 / Minimal test fixtures
# ---------------------------------------------------------------------------

CASE_ID = "case-test-001"


def _make_evidence(eid: str = "evidence-001") -> Evidence:
    return Evidence(
        evidence_id=eid,
        case_id=CASE_ID,
        owner_party_id="party-plaintiff-001",
        title="借条原件",
        source="mat-001",
        summary="借条一份",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=["fact-001"],
        access_domain=AccessDomain.owner_private,
        status=EvidenceStatus.private,
    )


def _make_evidence_index(case_id: str = CASE_ID) -> EvidenceIndex:
    return EvidenceIndex(
        case_id=case_id,
        evidence=[_make_evidence("evidence-001"), _make_evidence("evidence-002")],
    )


def _make_claim(cid: str = "claim-001") -> Claim:
    return Claim(
        claim_id=cid,
        case_id=CASE_ID,
        owner_party_id="party-plaintiff-001",
        title="归还本金",
        claim_text="请求被告归还借款本金",
    )


def _make_defense(did: str = "defense-001") -> Defense:
    return Defense(
        defense_id=did,
        case_id=CASE_ID,
        owner_party_id="party-defendant-001",
        against_claim_id="claim-001",
        defense_text="已部分归还",
    )


def _make_issue(iid: str = "issue-001") -> Issue:
    return Issue(
        issue_id=iid,
        case_id=CASE_ID,
        title="借贷关系成立",
        issue_type=IssueType.factual,
        status=IssueStatus.open,
    )


def _make_burden(bid: str = "burden-001") -> Burden:
    from engines.shared.models import Burden
    return Burden(
        burden_id=bid,
        case_id=CASE_ID,
        issue_id="issue-001",
        burden_party_id="party-plaintiff-001",
        status=BurdenStatus.not_met,
    )


def _make_issue_tree(case_id: str = CASE_ID) -> IssueTree:
    return IssueTree(
        case_id=case_id,
        issues=[_make_issue("issue-001"), _make_issue("issue-002")],
        burdens=[_make_burden("burden-001")],
    )


def _make_report(case_id: str = CASE_ID) -> ReportArtifact:
    section = ReportSection(
        section_id="sec-001",
        section_index=1,
        title="借贷关系认定",
        body="根据借条和转账回单，借贷关系成立。",
        linked_issue_ids=["issue-001"],
        linked_evidence_ids=["evidence-001"],
        key_conclusions=[
            KeyConclusion(
                conclusion_id="conc-001",
                text="借贷关系成立",
                statement_class=StatementClass.inference,
                supporting_evidence_ids=["evidence-001"],
            )
        ],
    )
    return ReportArtifact(
        report_id="report-001",
        case_id=case_id,
        run_id="run-001",
        title="民间借贷案件分析报告",
        summary="综合分析认为借贷关系成立",
        sections=[section],
    )


def _make_turn(tid: str = "turn-001", case_id: str = CASE_ID) -> InteractionTurn:
    return InteractionTurn(
        turn_id=tid,
        case_id=case_id,
        report_id="report-001",
        run_id="run-001",
        question="借贷关系是否成立？",
        answer="成立，有借条和转账回单为证。",
        issue_ids=["issue-001"],
        evidence_ids=["evidence-001"],
        statement_class=StatementClass.inference,
    )


def _make_scenario(sid: str = "scenario-001", case_id: str = CASE_ID) -> Scenario:
    return Scenario(
        scenario_id=sid,
        case_id=case_id,
        baseline_run_id="run-001",
        change_set=[
            ChangeItem(
                target_object_type=ChangeItemObjectType.Evidence,
                target_object_id="evidence-001",
                field_path="status",
                old_value="private",
                new_value="submitted",
            )
        ],
        diff_summary=[
            DiffEntry(
                issue_id="issue-001",
                impact_description="证据状态变更影响举证责任",
                direction=DiffDirection.strengthen,
            )
        ],
        affected_issue_ids=["issue-001"],
        affected_evidence_ids=["evidence-001"],
        status=ScenarioStatus.completed,
    )


def _make_run(run_id: str = "run-001", workspace_id: str = "ws-case-test-001") -> Run:
    return Run(
        run_id=run_id,
        case_id=CASE_ID,
        workspace_id=workspace_id,
        scenario_id=None,
        trigger_type="case_structuring",
        input_snapshot=InputSnapshot(material_refs=[], artifact_refs=[]),
        output_refs=[],
        started_at=_now(),
        finished_at=None,
        status="running",
    )


# ---------------------------------------------------------------------------
# 生命周期测试 / Lifecycle tests
# ---------------------------------------------------------------------------


def test_init_workspace_creates_workspace_json(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    assert (tmp_path / CASE_ID / "workspace.json").exists()


def test_init_workspace_structure_matches_spec(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    ws = mgr.init_workspace("civil")

    assert ws["workspace_id"] == f"ws-{CASE_ID}"
    assert ws["case_id"] == CASE_ID
    assert ws["case_type"] == "civil"
    assert ws["current_workflow_stage"] == "case_structuring"
    assert ws["run_ids"] == []
    assert ws["active_scenario_id"] is None
    assert ws["status"] == "active"

    for key in ("Party", "Claim", "Defense", "Issue", "Evidence", "Burden", "ProcedureState"):
        assert key in ws["material_index"]
        assert ws["material_index"][key] == []

    for key in ("AgentOutput", "ReportArtifact", "InteractionTurn", "Scenario"):
        assert key in ws["artifact_index"]
        assert ws["artifact_index"][key] == []


def test_load_workspace_returns_none_when_missing(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    assert mgr.load_workspace() is None


def test_load_workspace_after_init(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    ws = mgr.load_workspace()
    assert ws is not None
    assert ws["case_id"] == CASE_ID


# ---------------------------------------------------------------------------
# Run 持久化测试 / Run persistence tests
# ---------------------------------------------------------------------------


def test_save_and_load_run_roundtrip(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    run = _make_run()
    mgr.save_run(run)

    loaded = mgr.load_run(run.run_id)
    assert loaded is not None
    assert loaded.run_id == run.run_id
    assert loaded.case_id == run.case_id
    assert loaded.trigger_type == run.trigger_type
    assert loaded.status == run.status


def test_save_run_appends_to_run_ids(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    run = _make_run()
    mgr.save_run(run)

    ws = mgr.load_workspace()
    assert ws is not None
    assert run.run_id in ws["run_ids"]


def test_save_run_idempotent_no_duplicate_run_ids(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    run = _make_run()
    mgr.save_run(run)
    mgr.save_run(run)  # 重复保存

    ws = mgr.load_workspace()
    assert ws is not None
    assert ws["run_ids"].count(run.run_id) == 1


def test_save_multiple_runs_all_registered(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    run1 = _make_run("run-001")
    run2 = _make_run("run-002")
    mgr.save_run(run1)
    mgr.save_run(run2)

    ws = mgr.load_workspace()
    assert ws is not None
    assert "run-001" in ws["run_ids"]
    assert "run-002" in ws["run_ids"]


def test_load_run_returns_none_when_missing(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    assert mgr.load_run("nonexistent-run") is None


def test_load_run_raises_on_case_id_mismatch(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")

    # 手动写入一个 case_id 不匹配的 run 文件
    run_path = mgr._run_path("run-bad")
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text(
        json.dumps({"run_id": "run-bad", "case_id": "WRONG-CASE"}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="case_id mismatch"):
        mgr.load_run("run-bad")


def test_run_file_is_written_atomically(tmp_path: Path) -> None:
    """验证写完后没有残留 .tmp 文件。
    Verify no stale .tmp file remains after write.
    """
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    mgr.save_run(_make_run())
    tmp_files = list((tmp_path / CASE_ID / "runs").glob("*.tmp"))
    assert tmp_files == []


# ---------------------------------------------------------------------------
# 证据索引测试 / EvidenceIndex tests
# ---------------------------------------------------------------------------


def test_save_evidence_index_writes_file(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    mgr.save_evidence_index(_make_evidence_index())
    assert (tmp_path / CASE_ID / "artifacts" / "evidence_index.json").exists()


def test_save_evidence_index_updates_material_index(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    ei = _make_evidence_index()
    mgr.save_evidence_index(ei)

    ws = mgr.load_workspace()
    assert ws is not None
    refs = ws["material_index"]["Evidence"]
    assert len(refs) == 2
    ids = {r["object_id"] for r in refs}
    assert ids == {"evidence-001", "evidence-002"}
    for r in refs:
        assert r["storage_ref"] == "artifacts/evidence_index.json"
        assert r["object_type"] == "Evidence"


def test_load_evidence_index_returns_none_when_missing(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    assert mgr.load_evidence_index() is None


def test_load_evidence_index_roundtrip(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    ei = _make_evidence_index()
    mgr.save_evidence_index(ei)

    loaded = mgr.load_evidence_index()
    assert loaded is not None
    assert loaded.case_id == CASE_ID
    assert len(loaded.evidence) == 2
    ids = {e.evidence_id for e in loaded.evidence}
    assert ids == {"evidence-001", "evidence-002"}


def test_load_evidence_index_raises_on_case_id_mismatch(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    bad_ei = _make_evidence_index(case_id="WRONG-CASE")
    # 直接写文件绕过 WorkspaceManager 的 case_id 检查
    path = mgr._artifacts_dir() / "evidence_index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bad_ei.model_dump()), encoding="utf-8")

    with pytest.raises(ValueError, match="case_id mismatch"):
        mgr.load_evidence_index()


# ---------------------------------------------------------------------------
# 诉请与抗辩测试 / Claims and Defenses tests
# ---------------------------------------------------------------------------


def test_save_claims_defenses_writes_file(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    mgr.save_claims_defenses([_make_claim()], [_make_defense()])
    assert (tmp_path / CASE_ID / "artifacts" / "claim_defense.json").exists()


def test_load_claims_defenses_returns_none_when_missing(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    assert mgr.load_claims_defenses() is None


def test_load_claims_defenses_roundtrip(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    claims = [_make_claim("claim-001"), _make_claim("claim-002")]
    defenses = [_make_defense("defense-001")]
    mgr.save_claims_defenses(claims, defenses)

    result = mgr.load_claims_defenses()
    assert result is not None
    loaded_claims, loaded_defenses = result
    assert len(loaded_claims) == 2
    assert len(loaded_defenses) == 1
    assert loaded_claims[0].claim_id == "claim-001"
    assert loaded_defenses[0].defense_id == "defense-001"


def test_save_claims_defenses_updates_material_index(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    claims = [_make_claim("claim-001")]
    defenses = [_make_defense("defense-001")]
    mgr.save_claims_defenses(claims, defenses)

    ws = mgr.load_workspace()
    assert ws is not None
    claim_refs = ws["material_index"]["Claim"]
    defense_refs = ws["material_index"]["Defense"]
    assert len(claim_refs) == 1
    assert claim_refs[0]["object_id"] == "claim-001"
    assert len(defense_refs) == 1
    assert defense_refs[0]["object_id"] == "defense-001"


# ---------------------------------------------------------------------------
# 争点树测试 / IssueTree tests
# ---------------------------------------------------------------------------


def test_save_issue_tree_updates_material_index(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    it = _make_issue_tree()
    mgr.save_issue_tree(it)

    ws = mgr.load_workspace()
    assert ws is not None
    issue_refs = ws["material_index"]["Issue"]
    burden_refs = ws["material_index"]["Burden"]
    assert len(issue_refs) == 2
    assert len(burden_refs) == 1
    assert burden_refs[0]["object_id"] == "burden-001"


def test_load_issue_tree_returns_none_when_missing(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    assert mgr.load_issue_tree() is None


def test_load_issue_tree_roundtrip(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    it = _make_issue_tree()
    mgr.save_issue_tree(it)

    loaded = mgr.load_issue_tree()
    assert loaded is not None
    assert loaded.case_id == CASE_ID
    assert len(loaded.issues) == 2
    assert len(loaded.burdens) == 1


# ---------------------------------------------------------------------------
# 报告测试 / ReportArtifact tests
# ---------------------------------------------------------------------------


def test_save_report_updates_artifact_index(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    report = _make_report()
    mgr.save_report(report)

    ws = mgr.load_workspace()
    assert ws is not None
    refs = ws["artifact_index"]["ReportArtifact"]
    assert len(refs) == 1
    assert refs[0]["object_id"] == "report-001"
    assert refs[0]["storage_ref"] == "artifacts/report.json"


def test_load_report_returns_none_when_missing(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    assert mgr.load_report() is None


def test_load_report_roundtrip(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    report = _make_report()
    mgr.save_report(report)

    loaded = mgr.load_report()
    assert loaded is not None
    assert loaded.report_id == "report-001"
    assert loaded.case_id == CASE_ID
    assert len(loaded.sections) == 1


# ---------------------------------------------------------------------------
# 追问轮次测试 / InteractionTurn tests
# ---------------------------------------------------------------------------


def test_save_interaction_turn_sequential_numbering(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")

    mgr.save_interaction_turn(_make_turn("turn-001"))
    mgr.save_interaction_turn(_make_turn("turn-002"))

    assert (tmp_path / CASE_ID / "artifacts" / "turns" / "turn_001.json").exists()
    assert (tmp_path / CASE_ID / "artifacts" / "turns" / "turn_002.json").exists()


def test_save_interaction_turn_updates_artifact_index(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    mgr.save_interaction_turn(_make_turn("turn-001"))

    ws = mgr.load_workspace()
    assert ws is not None
    turns = ws["artifact_index"]["InteractionTurn"]
    assert len(turns) == 1
    assert turns[0]["object_id"] == "turn-001"
    assert turns[0]["storage_ref"] == "artifacts/turns/turn_001.json"


# ---------------------------------------------------------------------------
# 场景测试 / Scenario tests
# ---------------------------------------------------------------------------


def test_save_scenario_result_updates_artifact_index(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    scenario = _make_scenario("scenario-001")
    mgr.save_scenario_result(scenario)

    ws = mgr.load_workspace()
    assert ws is not None
    refs = ws["artifact_index"]["Scenario"]
    assert len(refs) == 1
    assert refs[0]["object_id"] == "scenario-001"
    assert refs[0]["storage_ref"] == "artifacts/scenarios/scenario_scenario-001.json"


def test_save_scenario_result_file_path(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    mgr.save_scenario_result(_make_scenario("scenario-001"))
    assert (
        tmp_path / CASE_ID / "artifacts" / "scenarios" / "scenario_scenario-001.json"
    ).exists()


# ---------------------------------------------------------------------------
# 阶段推进测试 / Stage advancement tests
# ---------------------------------------------------------------------------


def test_advance_stage_updates_workspace(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")

    mgr.advance_stage(WorkflowStage.case_structuring)
    ws = mgr.load_workspace()
    assert ws is not None
    assert ws["current_workflow_stage"] == "case_structuring"

    mgr.advance_stage(WorkflowStage.report_generation)
    ws = mgr.load_workspace()
    assert ws is not None
    assert ws["current_workflow_stage"] == "report_generation"


# ---------------------------------------------------------------------------
# 四步序列端到端测试 / Four-step sequence end-to-end test
# ---------------------------------------------------------------------------


def test_four_step_run_sequence(tmp_path: Path) -> None:
    """演示 spec 定义的四步序列：
    1. Pipeline 创建 Run（status=running）
    2. 引擎执行（模拟：直接构造结果）
    3. Pipeline 填 output_refs，更新 status/finished_at
    4. WorkspaceManager.save_evidence_index() + save_run()

    Demonstrates spec four-step sequence:
    1. Pipeline creates Run (status=running)
    2. Engines execute (simulated: directly construct results)
    3. Pipeline fills output_refs, updates status/finished_at
    4. WorkspaceManager.save_evidence_index() + save_run()
    """
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")

    # Step 1: Pipeline creates Run before engine execution
    run = Run(
        run_id="run-001",
        case_id=CASE_ID,
        workspace_id="ws-case-test-001",
        scenario_id=None,
        trigger_type="case_structuring",
        input_snapshot=InputSnapshot(material_refs=[], artifact_refs=[]),
        output_refs=[],
        started_at=_now(),
        finished_at=None,
        status="running",
    )

    # Step 2: Engine executes (simulated)
    ei = _make_evidence_index()

    # Step 3: Pipeline fills output_refs + marks completed
    run.output_refs = [
        MaterialRef(
            index_name="material_index",
            object_type="Evidence",
            object_id="evidence-001",
            storage_ref="artifacts/evidence_index.json",
        )
    ]
    run.finished_at = _now()
    run.status = "completed"

    # Step 4: WorkspaceManager writes artifacts then Run
    mgr.save_evidence_index(ei)
    mgr.save_run(run)
    mgr.advance_stage(WorkflowStage.case_structuring)

    # Assertions
    ws = mgr.load_workspace()
    assert ws is not None
    assert "run-001" in ws["run_ids"]
    assert ws["current_workflow_stage"] == "case_structuring"
    assert len(ws["material_index"]["Evidence"]) == 2

    loaded_run = mgr.load_run("run-001")
    assert loaded_run is not None
    assert loaded_run.status == "completed"
    assert loaded_run.finished_at is not None
    assert len(loaded_run.output_refs) == 1

    loaded_ei = mgr.load_evidence_index()
    assert loaded_ei is not None
    assert len(loaded_ei.evidence) == 2

    # Artifacts file and run file both exist
    assert (tmp_path / CASE_ID / "artifacts" / "evidence_index.json").exists()
    assert (tmp_path / CASE_ID / "runs" / "run_run-001.json").exists()


def test_save_run_without_init_raises(tmp_path: Path) -> None:
    """未初始化 workspace 时调用 save_run 应抛 ValueError。
    save_run before init_workspace should raise ValueError.
    """
    mgr = _mgr(tmp_path)
    run = _make_run()
    with pytest.raises(ValueError, match="not initialized"):
        mgr.save_run(run)


# ---------------------------------------------------------------------------
# AgentOutput 持久化测试 / AgentOutput persistence tests
# ---------------------------------------------------------------------------


def _make_agent_output(
    output_id: str = "ao-001",
    owner_party_id: str = "party-plaintiff-001",
    run_id: str = "run-001",
) -> AgentOutput:
    return AgentOutput(
        output_id=output_id,
        case_id=CASE_ID,
        run_id=run_id,
        state_id="state-001",
        phase=ProcedurePhase.opening,
        round_index=0,
        agent_role_code="plaintiff_agent",
        owner_party_id=owner_party_id,
        issue_ids=["issue-001"],
        title="原告开庭陈述",
        body="原告主张：被告应归还借款本金及利息。",
        evidence_citations=["evidence-001"],
        statement_class=StatementClass.fact,
        risk_flags=[],
        created_at=_now(),
    )


def test_save_agent_output_owner_private_routing(tmp_path: Path) -> None:
    """owner_private 产物路由到 artifacts/private/{party_id}/agent_outputs/。
    owner_private output routes to artifacts/private/{party_id}/agent_outputs/.
    """
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    output = _make_agent_output(output_id="ao-001", owner_party_id="party-plaintiff-001")

    storage_ref = mgr.save_agent_output(output, AccessDomain.owner_private)

    expected_ref = "artifacts/private/party-plaintiff-001/agent_outputs/ao-001.json"
    assert storage_ref == expected_ref
    expected_path = tmp_path / CASE_ID / expected_ref
    assert expected_path.exists()


def test_save_agent_output_shared_routing(tmp_path: Path) -> None:
    """shared_common 产物路由到 artifacts/shared/agent_outputs/。
    shared_common output routes to artifacts/shared/agent_outputs/.
    """
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    output = _make_agent_output(output_id="ao-002")

    storage_ref = mgr.save_agent_output(output, AccessDomain.shared_common)

    expected_ref = "artifacts/shared/agent_outputs/ao-002.json"
    assert storage_ref == expected_ref
    assert (tmp_path / CASE_ID / expected_ref).exists()


def test_save_agent_output_admitted_routing(tmp_path: Path) -> None:
    """admitted_record 产物路由到 artifacts/admitted/agent_outputs/。
    admitted_record output routes to artifacts/admitted/agent_outputs/.
    """
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    output = _make_agent_output(output_id="ao-003")

    storage_ref = mgr.save_agent_output(output, AccessDomain.admitted_record)

    expected_ref = "artifacts/admitted/agent_outputs/ao-003.json"
    assert storage_ref == expected_ref
    assert (tmp_path / CASE_ID / expected_ref).exists()


def test_save_agent_output_updates_artifact_index(tmp_path: Path) -> None:
    """save_agent_output 必须更新 artifact_index.AgentOutput。
    save_agent_output must register entry in artifact_index.AgentOutput.
    """
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    output = _make_agent_output(output_id="ao-idx")

    mgr.save_agent_output(output, AccessDomain.owner_private)

    ws = mgr.load_workspace()
    assert ws is not None
    ao_refs = ws["artifact_index"]["AgentOutput"]
    assert len(ao_refs) == 1
    assert ao_refs[0]["object_id"] == "ao-idx"
    assert ao_refs[0]["object_type"] == "AgentOutput"
    assert "ao-idx" in ao_refs[0]["storage_ref"]


def test_save_agent_output_multiple_appends(tmp_path: Path) -> None:
    """多次调用 save_agent_output 应逐条追加到 artifact_index，不覆盖。
    Multiple save_agent_output calls must append, not overwrite.
    """
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")

    for i in range(3):
        output = _make_agent_output(output_id=f"ao-{i:03d}")
        mgr.save_agent_output(output, AccessDomain.owner_private)

    ws = mgr.load_workspace()
    assert ws is not None
    assert len(ws["artifact_index"]["AgentOutput"]) == 3


def test_load_agent_output_roundtrip(tmp_path: Path) -> None:
    """save → load 往返测试，字段完整。
    save then load roundtrip preserves all fields.
    """
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")
    original = _make_agent_output(output_id="ao-rt")

    storage_ref = mgr.save_agent_output(original, AccessDomain.owner_private)
    loaded = mgr.load_agent_output(original.output_id, storage_ref)

    assert loaded is not None
    assert loaded.output_id == original.output_id
    assert loaded.case_id == original.case_id
    assert loaded.issue_ids == original.issue_ids
    assert loaded.evidence_citations == original.evidence_citations


def test_load_agent_output_returns_none_when_missing(tmp_path: Path) -> None:
    """storage_ref 指向不存在的文件时返回 None。
    Returns None when storage_ref points to a non-existent file.
    """
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")

    result = mgr.load_agent_output(
        "ao-missing",
        "artifacts/private/party-x/agent_outputs/ao-missing.json",
    )
    assert result is None


def test_save_agent_output_different_parties_isolated(tmp_path: Path) -> None:
    """不同当事方的 owner_private 产物写入不同目录，互不干扰。
    Different parties' owner_private outputs land in separate directories.
    """
    mgr = _mgr(tmp_path)
    mgr.init_workspace("civil")

    out_p = _make_agent_output(output_id="ao-p", owner_party_id="party-plaintiff-001")
    out_d = _make_agent_output(output_id="ao-d", owner_party_id="party-defendant-001")

    ref_p = mgr.save_agent_output(out_p, AccessDomain.owner_private)
    ref_d = mgr.save_agent_output(out_d, AccessDomain.owner_private)

    assert "party-plaintiff-001" in ref_p
    assert "party-defendant-001" in ref_d
    assert ref_p != ref_d

    # 各自文件存在
    assert (tmp_path / CASE_ID / ref_p).exists()
    assert (tmp_path / CASE_ID / ref_d).exists()
    # 原告文件不在被告目录下
    assert "party-defendant-001" not in ref_p
    assert "party-plaintiff-001" not in ref_d
