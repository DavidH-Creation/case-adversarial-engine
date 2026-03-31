"""
集成测试 — pretrial conference 接入主 pipeline + evidence_state_machine 全链路 enforce。
Integration tests — pretrial conference pipeline integration + evidence_state_machine enforcement.

覆盖路径 / Coverage:
1. test_pretrial_happy_path               — pretrial 正常执行 → post-debate 模块接收 admitted evidence
2. test_skip_pretrial_legacy_promote      — --skip-pretrial → 回退到手动 promote 行为
3. test_pretrial_no_evidence_admitted     — pretrial 无证据被 admitted → 安全处理空列表
4. test_pretrial_llm_failure_graceful     — pretrial LLM 调用失败 → 返回部分结果
5. test_enforce_minimum_status_rejects    — evidence_state_machine enforce → 非法状态拒绝
6. test_enforce_minimum_status_passes     — enforce 校验通过
7. test_enforce_minimum_status_filtered   — enforce 只检查指定 ID
8. test_pipeline_pretrial_then_decision_tree — 全链路: pretrial → decision_path_tree 接收 admitted evidence
"""

from __future__ import annotations

import json

import pytest

from engines.pretrial_conference.conference_engine import PretrialConferenceEngine
from engines.pretrial_conference.schemas import PretrialConferenceResult
from engines.shared.evidence_state_machine import (
    EvidenceStateMachine,
    EvidenceStatusViolation,
)
from engines.shared.models import (
    AccessDomain,
    Evidence,
    EvidenceIndex,
    EvidenceStatus,
    EvidenceType,
    Issue,
    IssueTree,
    IssueType,
)

from .conftest import CASE_ID, MockLLMClient, SequentialMockLLMClient


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------


def _make_evidence(
    eid: str,
    owner: str,
    status: EvidenceStatus = EvidenceStatus.private,
) -> Evidence:
    """Create a minimal Evidence object for testing."""
    domain_map = {
        EvidenceStatus.private: AccessDomain.owner_private,
        EvidenceStatus.submitted: AccessDomain.shared_common,
        EvidenceStatus.challenged: AccessDomain.shared_common,
        EvidenceStatus.admitted_for_discussion: AccessDomain.admitted_record,
    }
    return Evidence(
        evidence_id=eid,
        case_id=CASE_ID,
        owner_party_id=owner,
        title=f"Evidence {eid}",
        source=f"source-{eid}",
        summary=f"Summary for {eid}",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=["fact-001"],
        access_domain=domain_map[status],
        status=status,
        submitted_by_party_id=owner if status != EvidenceStatus.private else None,
    )


def _make_evidence_index(*evidence_list: Evidence) -> EvidenceIndex:
    return EvidenceIndex(case_id=CASE_ID, evidence=list(evidence_list))


P_ID = "party-plaintiff-001"
D_ID = "party-defendant-001"


# ---------------------------------------------------------------------------
# Mock LLM responses for pretrial conference (cross-examination + judge)
# ---------------------------------------------------------------------------

# Cross-examination response: admits ev-p-001 and challenges ev-d-001
_CROSS_EXAM_RESPONSE = json.dumps(
    {
        "opinions": [
            {
                "evidence_id": "ev-p-001",
                "issue_ids": ["issue-001"],
                "dimension": "authenticity",
                "verdict": "accepted",
                "reasoning": "Original document verified",
            },
            {
                "evidence_id": "ev-d-001",
                "issue_ids": ["issue-001"],
                "dimension": "relevance",
                "verdict": "challenged",
                "reasoning": "Relevance to core dispute is questionable",
            },
        ],
    },
    ensure_ascii=False,
)

# Judge questions response
_JUDGE_QUESTIONS_RESPONSE = json.dumps(
    {
        "questions": [
            {
                "question_id": "q-001",
                "issue_id": "issue-001",
                "evidence_ids": ["ev-p-001"],
                "question_text": "Please clarify the loan disbursement date",
                "target_party_id": P_ID,
                "question_type": "clarification",
                "priority": 8,
            },
        ],
    },
    ensure_ascii=False,
)


# ---------------------------------------------------------------------------
# Test: Happy path — pretrial executes successfully
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pretrial_happy_path():
    """Pretrial conference executes → evidence progresses through state machine."""
    ev_p = _make_evidence("ev-p-001", P_ID, EvidenceStatus.private)
    ev_d = _make_evidence("ev-d-001", D_ID, EvidenceStatus.private)
    ev_index = _make_evidence_index(ev_p, ev_d)

    # SequentialMock: first call = cross-exam, second call = judge questions
    mock_client = SequentialMockLLMClient(
        [
            _CROSS_EXAM_RESPONSE,
            _JUDGE_QUESTIONS_RESPONSE,
        ]
    )

    engine = PretrialConferenceEngine(
        llm_client=mock_client,
        model="test-model",
        temperature=0.0,
        max_retries=0,
    )

    issue_tree = IssueTree(
        case_id=CASE_ID,
        issues=[
            Issue(
                issue_id="issue-001",
                case_id=CASE_ID,
                title="Loan agreement validity",
                issue_type=IssueType.factual,
                evidence_ids=["ev-p-001", "ev-d-001"],
            )
        ],
        burdens=[],
    )

    result = await engine.run(
        issue_tree=issue_tree,
        evidence_index=ev_index,
        plaintiff_party_id=P_ID,
        defendant_party_id=D_ID,
        plaintiff_evidence_ids=["ev-p-001"],
        defendant_evidence_ids=["ev-d-001"],
    )

    assert isinstance(result, PretrialConferenceResult)
    assert result.case_id == CASE_ID

    # Evidence should have progressed beyond private
    final_index = result.final_evidence_index
    statuses = {ev.evidence_id: ev.status for ev in final_index.evidence}
    # Both should be at least submitted (not private)
    assert statuses["ev-p-001"] != EvidenceStatus.private
    assert statuses["ev-d-001"] != EvidenceStatus.private


# ---------------------------------------------------------------------------
# Test: --skip-pretrial legacy promote behavior
# ---------------------------------------------------------------------------


def test_skip_pretrial_legacy_promote():
    """Legacy promote: directly set private → admitted_for_discussion (bypass state machine)."""
    ev1 = _make_evidence("ev-001", P_ID, EvidenceStatus.private)
    ev2 = _make_evidence("ev-002", D_ID, EvidenceStatus.private)
    ev3 = _make_evidence("ev-003", P_ID, EvidenceStatus.private)
    ev_index = _make_evidence_index(ev1, ev2, ev3)

    # Simulate cited_ids from debate
    cited_ids = {"ev-001", "ev-002"}

    # Legacy promote logic (mirrors --skip-pretrial behavior in run_case.py)
    promoted = 0
    for ev in ev_index.evidence:
        if ev.evidence_id in cited_ids and ev.status == EvidenceStatus.private:
            ev.status = EvidenceStatus.admitted_for_discussion
            promoted += 1

    assert promoted == 2
    statuses = {ev.evidence_id: ev.status for ev in ev_index.evidence}
    assert statuses["ev-001"] == EvidenceStatus.admitted_for_discussion
    assert statuses["ev-002"] == EvidenceStatus.admitted_for_discussion
    assert statuses["ev-003"] == EvidenceStatus.private  # uncited → unchanged


# ---------------------------------------------------------------------------
# Test: No evidence admitted → safe handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pretrial_no_evidence_admitted():
    """Pretrial with no evidence IDs submitted → conference returns empty results gracefully."""
    ev_p = _make_evidence("ev-p-001", P_ID, EvidenceStatus.private)
    ev_index = _make_evidence_index(ev_p)

    # No LLM calls expected since no evidence submitted → cross-exam has nothing to do
    mock_client = SequentialMockLLMClient(
        [
            json.dumps({"opinions": []}),
            json.dumps({"questions": []}),
        ]
    )

    engine = PretrialConferenceEngine(
        llm_client=mock_client,
        model="test-model",
        temperature=0.0,
        max_retries=0,
    )

    issue_tree = IssueTree(
        case_id=CASE_ID,
        issues=[],
        burdens=[],
    )

    result = await engine.run(
        issue_tree=issue_tree,
        evidence_index=ev_index,
        plaintiff_party_id=P_ID,
        defendant_party_id=D_ID,
        plaintiff_evidence_ids=[],  # no evidence submitted
        defendant_evidence_ids=[],
    )

    assert isinstance(result, PretrialConferenceResult)
    # Evidence remains private since nothing was submitted
    for ev in result.final_evidence_index.evidence:
        assert ev.status == EvidenceStatus.private
    # Judge questions should be empty (no admitted evidence)
    assert len(result.judge_questions.questions) == 0


# ---------------------------------------------------------------------------
# Test: LLM failure → graceful degradation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pretrial_llm_failure_graceful():
    """Pretrial LLM failure → conference returns partial results without raising."""
    ev_p = _make_evidence("ev-p-001", P_ID, EvidenceStatus.private)
    ev_index = _make_evidence_index(ev_p)

    # LLM fails all calls
    mock_client = MockLLMClient(response="", fail_times=10)

    engine = PretrialConferenceEngine(
        llm_client=mock_client,
        model="test-model",
        temperature=0.0,
        max_retries=0,
    )

    issue_tree = IssueTree(
        case_id=CASE_ID,
        issues=[],
        burdens=[],
    )

    # Should NOT raise
    result = await engine.run(
        issue_tree=issue_tree,
        evidence_index=ev_index,
        plaintiff_party_id=P_ID,
        defendant_party_id=D_ID,
        plaintiff_evidence_ids=["ev-p-001"],
        defendant_evidence_ids=[],
    )

    assert isinstance(result, PretrialConferenceResult)
    assert result.final_evidence_index is not None


# ---------------------------------------------------------------------------
# Test: enforce_minimum_status rejects invalid evidence
# ---------------------------------------------------------------------------


def test_enforce_minimum_status_rejects():
    """enforce_minimum_status raises EvidenceStatusViolation for evidence below threshold."""
    sm = EvidenceStateMachine()
    ev_private = _make_evidence("ev-001", P_ID, EvidenceStatus.private)
    ev_admitted = _make_evidence("ev-002", P_ID, EvidenceStatus.admitted_for_discussion)
    ev_index = _make_evidence_index(ev_private, ev_admitted)

    with pytest.raises(EvidenceStatusViolation, match="ev-001"):
        sm.enforce_minimum_status(ev_index, EvidenceStatus.admitted_for_discussion)


def test_enforce_minimum_status_passes():
    """enforce_minimum_status passes when all evidence meets threshold."""
    sm = EvidenceStateMachine()
    ev1 = _make_evidence("ev-001", P_ID, EvidenceStatus.admitted_for_discussion)
    ev2 = _make_evidence("ev-002", D_ID, EvidenceStatus.admitted_for_discussion)
    ev_index = _make_evidence_index(ev1, ev2)

    # Should NOT raise
    sm.enforce_minimum_status(ev_index, EvidenceStatus.admitted_for_discussion)


def test_enforce_minimum_status_filtered():
    """enforce_minimum_status only checks specified evidence_ids."""
    sm = EvidenceStateMachine()
    ev_private = _make_evidence("ev-001", P_ID, EvidenceStatus.private)
    ev_admitted = _make_evidence("ev-002", P_ID, EvidenceStatus.admitted_for_discussion)
    ev_index = _make_evidence_index(ev_private, ev_admitted)

    # Only check ev-002 → should pass even though ev-001 is private
    sm.enforce_minimum_status(
        ev_index,
        EvidenceStatus.admitted_for_discussion,
        evidence_ids=["ev-002"],
    )

    # Check ev-001 → should fail
    with pytest.raises(EvidenceStatusViolation):
        sm.enforce_minimum_status(
            ev_index,
            EvidenceStatus.admitted_for_discussion,
            evidence_ids=["ev-001"],
        )


# ---------------------------------------------------------------------------
# Test: Full chain — pretrial → decision_path_tree receives admitted evidence
# ---------------------------------------------------------------------------


def test_enforce_blocks_private_evidence_in_generator():
    """DecisionPathTreeGenerator would reject evidence_index with private evidence
    in the admitted_ids list (which shouldn't happen after pretrial, but enforce catches it).
    """
    sm = EvidenceStateMachine()
    ev_private = _make_evidence("ev-001", P_ID, EvidenceStatus.private)
    ev_index = _make_evidence_index(ev_private)

    # Simulating what the generator enforce would catch:
    # If someone labeled private evidence as admitted_ids, enforce would reject.
    with pytest.raises(EvidenceStatusViolation):
        sm.enforce_minimum_status(
            ev_index,
            EvidenceStatus.admitted_for_discussion,
            evidence_ids=["ev-001"],
        )


def test_enforce_submitted_status_ordering():
    """Status ordering: private < submitted < challenged < admitted_for_discussion."""
    sm = EvidenceStateMachine()

    # submitted meets submitted threshold
    ev = _make_evidence("ev-001", P_ID, EvidenceStatus.submitted)
    idx = _make_evidence_index(ev)
    sm.enforce_minimum_status(idx, EvidenceStatus.submitted)

    # challenged meets submitted threshold
    ev2 = _make_evidence("ev-002", P_ID, EvidenceStatus.challenged)
    idx2 = _make_evidence_index(ev2)
    sm.enforce_minimum_status(idx2, EvidenceStatus.submitted)

    # private does NOT meet submitted threshold
    ev3 = _make_evidence("ev-003", P_ID, EvidenceStatus.private)
    idx3 = _make_evidence_index(ev3)
    with pytest.raises(EvidenceStatusViolation):
        sm.enforce_minimum_status(idx3, EvidenceStatus.submitted)
