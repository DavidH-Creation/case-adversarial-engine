"""
Pipeline + WorkspaceManager 集成测试。
Integration tests for Pipeline artifact persistence via WorkspaceManager.

覆盖路径 / Coverage:
1. test_evidence_indexer_output_persists_and_reloads
   — EvidenceIndexer mock run → save_evidence_index → 新实例 load → 对象等价
2. test_full_pipeline_workspace_roundtrip
   — 完整四步序列（init → 各类产物 save → save_run）→ 新实例 reload → 所有 index 一致
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engines.case_structuring.evidence_indexer.indexer import EvidenceIndexer
from engines.shared.models import (
    AccessDomain,
    ArtifactRef,
    Burden,
    BurdenStatus,
    Claim,
    Defense,
    DiffDirection,
    Evidence,
    EvidenceIndex,
    EvidenceStatus,
    EvidenceType,
    InputSnapshot,
    Issue,
    IssueStatus,
    IssueTree,
    IssueType,
    KeyConclusion,
    MaterialRef,
    PromptProfile,
    ReportArtifact,
    ReportSection,
    Run,
    StatementClass,
    WorkflowStage,
)
from engines.shared.workspace_manager import WorkspaceManager

from .conftest import CASE_ID, WORKSPACE_ID, MockLLMClient

# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------

_EVIDENCE_INDEXER_RESPONSE = json.dumps(
    [
        {
            "title": "借条原件",
            "summary": "被告于2024年1月15日出具借条，载明借款本金50万元",
            "evidence_type": "documentary",
            "source_id": "mat-integ-001",
            "target_facts": ["fact-persist-001-loan-agreement"],
            "target_issues": [],
        },
        {
            "title": "银行转账回单",
            "summary": "工商银行回单显示原告于2024年1月15日转账500,000元",
            "evidence_type": "electronic_data",
            "source_id": "mat-integ-002",
            "target_facts": ["fact-persist-001-loan-disbursement"],
            "target_issues": [],
        },
    ],
    ensure_ascii=False,
)


def _make_issue_tree(case_id: str) -> IssueTree:
    issue = Issue(
        issue_id="issue-persist-001",
        case_id=case_id,
        title="借贷关系成立",
        issue_type=IssueType.factual,
        status=IssueStatus.open,
    )
    burden = Burden(
        burden_id="burden-persist-001",
        case_id=case_id,
        issue_id="issue-persist-001",
        burden_party_id="party-plaintiff-001",
        proof_standard="优势证据",
        status=BurdenStatus.not_met,
    )
    return IssueTree(case_id=case_id, issues=[issue], burdens=[burden])


def _make_report(case_id: str, run_id: str) -> ReportArtifact:
    kc = KeyConclusion(
        conclusion_id="kc-persist-001",
        text="借贷关系成立",
        statement_class=StatementClass.fact,
        supporting_evidence_ids=["evidence-persist-001-001"],
    )
    section = ReportSection(
        section_id="sec-persist-001",
        section_index=1,
        title="借贷关系",
        body="根据借条原件及转账回单，借贷关系成立。",
        linked_evidence_ids=["evidence-persist-001-001"],
        key_conclusions=[kc],
    )
    return ReportArtifact(
        report_id="report-persist-001",
        case_id=case_id,
        run_id=run_id,
        title="民间借贷案件分析报告",
        summary="借贷关系成立，原告诉请具有事实依据。",
        sections=[section],
    )


def _make_run(case_id: str, run_id: str) -> Run:
    return Run(
        run_id=run_id,
        case_id=case_id,
        workspace_id=WORKSPACE_ID,
        trigger_type="manual",
        input_snapshot=InputSnapshot(),
        output_refs=[
            ArtifactRef(
                object_type="EvidenceIndex",
                object_id="evidence-index-persist-001",
                storage_ref="artifacts/evidence_index.json",
            )
        ],
        started_at="2026-03-26T00:00:00Z",
        finished_at="2026-03-26T00:00:10Z",
        status="completed",
    )


# ---------------------------------------------------------------------------
# Test 1: EvidenceIndexer → WorkspaceManager persist → reload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evidence_indexer_output_persists_and_reloads(
    tmp_path: Path, sample_materials
) -> None:
    """EvidenceIndexer 输出通过 WorkspaceManager 持久化后能正确 reload。
    EvidenceIndexer output saved via WorkspaceManager is correctly reloaded.
    """
    persist_case_id = "case-persist-001"

    # Run the engine (returns list[Evidence])
    evidences = await EvidenceIndexer(
        llm_client=MockLLMClient(_EVIDENCE_INDEXER_RESPONSE),
        case_type="civil_loan",
    ).index(
        materials=sample_materials,
        case_id=persist_case_id,
        owner_party_id="party-plaintiff-001",
        case_slug="persist-001",
    )
    assert len(evidences) == 2

    # Wrap into EvidenceIndex envelope for persistence
    evidence_index = EvidenceIndex(case_id=persist_case_id, evidence=evidences)

    # Init and save
    wm = WorkspaceManager(base_dir=tmp_path, case_id=persist_case_id)
    wm.init_workspace("civil")
    wm.save_evidence_index(evidence_index)

    # Reload with a fresh WorkspaceManager instance
    wm2 = WorkspaceManager(base_dir=tmp_path, case_id=persist_case_id)
    reloaded = wm2.load_evidence_index()

    assert reloaded is not None
    assert reloaded.case_id == evidence_index.case_id
    assert len(reloaded.evidence) == len(evidence_index.evidence)
    reloaded_ids = {e.evidence_id for e in reloaded.evidence}
    original_ids = {e.evidence_id for e in evidence_index.evidence}
    assert reloaded_ids == original_ids

    # Verify material_index was updated
    ws = wm2.load_workspace()
    assert ws is not None
    assert len(ws["material_index"]["Evidence"]) == 2


# ---------------------------------------------------------------------------
# Test 2: Full four-step pipeline → workspace roundtrip
# ---------------------------------------------------------------------------


def test_full_pipeline_workspace_roundtrip(tmp_path: Path) -> None:
    """完整四步序列（init → 各类产物 save → save_run）后 reload 所有 index 一致。
    Full four-step sequence followed by reload keeps all index entries consistent.
    """
    case_id = "case-persist-002"
    run_id = "run-persist-001"
    wm = WorkspaceManager(base_dir=tmp_path, case_id=case_id)

    # Step 0: init workspace
    ws = wm.init_workspace("civil")
    assert ws["case_id"] == case_id
    assert ws["run_ids"] == []

    # Step 1: save evidence_index
    evidence = Evidence(
        evidence_id="evidence-persist-002-001",
        case_id=case_id,
        owner_party_id="party-plaintiff-001",
        title="借条原件",
        source="mat-persist-001",
        summary="借款本金50万元",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=["fact-persist-002-001"],
        access_domain=AccessDomain.owner_private,
        status=EvidenceStatus.private,
    )
    evidence_index = EvidenceIndex(case_id=case_id, evidence=[evidence])
    wm.save_evidence_index(evidence_index)

    # Step 2: save issue_tree
    issue_tree = _make_issue_tree(case_id)
    wm.save_issue_tree(issue_tree)

    # Step 3: save claims/defenses
    claim = Claim(
        claim_id="claim-persist-002-001",
        case_id=case_id,
        owner_party_id="party-plaintiff-001",
        title="归还借款本金",
    )
    defense = Defense(
        defense_id="defense-persist-002-001",
        case_id=case_id,
        owner_party_id="party-defendant-001",
        against_claim_id="claim-persist-002-001",
    )
    wm.save_claims_defenses([claim], [defense])

    # Step 4: save report
    report = _make_report(case_id, run_id)
    wm.save_report(report)

    # Step 5: advance workflow stage
    wm.advance_stage(WorkflowStage.report_generation)

    # Step 6: save run
    run = _make_run(case_id, run_id)
    wm.save_run(run)

    # ── Reload with a fresh WorkspaceManager ──────────────────────────────
    wm2 = WorkspaceManager(base_dir=tmp_path, case_id=case_id)

    # Workspace index consistency
    ws2 = wm2.load_workspace()
    assert ws2 is not None
    assert ws2["case_id"] == case_id
    assert run_id in ws2["run_ids"]
    assert ws2["current_workflow_stage"] == WorkflowStage.report_generation.value

    # material_index: Evidence, Claim, Defense, Issue, Burden populated
    assert len(ws2["material_index"]["Evidence"]) == 1
    assert ws2["material_index"]["Evidence"][0]["object_id"] == "evidence-persist-002-001"
    assert len(ws2["material_index"]["Claim"]) == 1
    assert len(ws2["material_index"]["Defense"]) == 1
    assert len(ws2["material_index"]["Issue"]) == 1
    assert len(ws2["material_index"]["Burden"]) == 1

    # artifact_index: ReportArtifact populated
    assert len(ws2["artifact_index"]["ReportArtifact"]) == 1
    assert ws2["artifact_index"]["ReportArtifact"][0]["object_id"] == "report-persist-001"

    # Artifact round-trip equality
    reloaded_index = wm2.load_evidence_index()
    assert reloaded_index is not None
    assert reloaded_index.evidence[0].evidence_id == "evidence-persist-002-001"

    reloaded_tree = wm2.load_issue_tree()
    assert reloaded_tree is not None
    assert reloaded_tree.issues[0].issue_id == "issue-persist-001"
    assert reloaded_tree.burdens[0].burden_id == "burden-persist-001"

    reloaded_report = wm2.load_report()
    assert reloaded_report is not None
    assert reloaded_report.report_id == "report-persist-001"
    assert reloaded_report.sections[0].key_conclusions[0].conclusion_id == "kc-persist-001"

    reloaded_run = wm2.load_run(run_id)
    assert reloaded_run is not None
    assert reloaded_run.run_id == run_id
    assert reloaded_run.status == "completed"

    # claims/defenses round-trip
    result = wm2.load_claims_defenses()
    assert result is not None
    claims, defenses = result
    assert len(claims) == 1
    assert len(defenses) == 1
    assert claims[0].claim_id == "claim-persist-002-001"
    assert defenses[0].defense_id == "defense-persist-002-001"
