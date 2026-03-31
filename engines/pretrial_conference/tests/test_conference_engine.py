"""PretrialConferenceEngine 集成测试。"""

import json

import pytest
from unittest.mock import AsyncMock

from engines.pretrial_conference.conference_engine import (
    PretrialConferenceEngine,
)
from engines.pretrial_conference.schemas import PretrialConferenceResult
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_issue(issue_id="issue-001"):
    return Issue(
        issue_id=issue_id,
        case_id="case-001",
        title=f"争点 {issue_id}",
        issue_type=IssueType.factual,
    )


def _make_issue_tree():
    return IssueTree(case_id="case-001", issues=[_make_issue()])


def _make_private_evidence(evidence_id, owner_party_id):
    return Evidence(
        evidence_id=evidence_id,
        case_id="case-001",
        owner_party_id=owner_party_id,
        title=f"证据 {evidence_id}",
        source="当事人",
        summary=f"证据 {evidence_id} 摘要",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=["fact-001"],
        target_issue_ids=["issue-001"],
        access_domain=AccessDomain.owner_private,
        status=EvidenceStatus.private,
        challenged_by_party_ids=[],
    )


def _cross_exam_response(*evidence_ids):
    """构建全部 accepted 的质证 LLM 响应。"""
    opinions = []
    for eid in evidence_ids:
        for d in ("authenticity", "relevance", "legality", "probative_value"):
            opinions.append(
                {
                    "evidence_id": eid,
                    "issue_ids": ["issue-001"],
                    "dimension": d,
                    "verdict": "accepted",
                    "reasoning": f"{d} ok",
                }
            )
    return json.dumps({"opinions": opinions})


def _judge_response():
    """构建法官追问 LLM 响应。"""
    return json.dumps(
        {
            "questions": [
                {
                    "question_id": "jq-001",
                    "issue_id": "issue-001",
                    "evidence_ids": ["ev-p1"],
                    "question_text": "请原告说明借款用途",
                    "target_party_id": "party-plaintiff",
                    "question_type": "clarification",
                    "priority": 1,
                },
            ]
        }
    )


def _make_engine_with_mock():
    """创建 engine + mock LLM。

    LLM side_effect:
    - 1st call: cross-exam for plaintiff evidence
    - 2nd call: cross-exam for defendant evidence
    - 3rd call: judge questions
    """
    mock_llm = AsyncMock()
    mock_llm.create_message.side_effect = [
        _cross_exam_response("ev-p1"),  # cross-exam: plaintiff evidence
        _cross_exam_response("ev-d1"),  # cross-exam: defendant evidence
        _judge_response(),  # judge questions
    ]
    engine = PretrialConferenceEngine(
        llm_client=mock_llm,
        model="test-model",
        temperature=0.0,
        max_retries=1,
    )
    return engine, mock_llm


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFullPipeline:
    @pytest.mark.asyncio
    async def test_end_to_end_produces_result(self):
        """全链路：private → submitted → admitted → judge questions。"""
        engine, _ = _make_engine_with_mock()
        ev_p = _make_private_evidence("ev-p1", "party-plaintiff")
        ev_d = _make_private_evidence("ev-d1", "party-defendant")

        result = await engine.run(
            issue_tree=_make_issue_tree(),
            evidence_index=EvidenceIndex(case_id="case-001", evidence=[ev_p, ev_d]),
            plaintiff_party_id="party-plaintiff",
            defendant_party_id="party-defendant",
            plaintiff_evidence_ids=["ev-p1"],
            defendant_evidence_ids=["ev-d1"],
        )

        assert isinstance(result, PretrialConferenceResult)
        assert result.case_id == "case-001"

    @pytest.mark.asyncio
    async def test_evidence_lifecycle(self):
        """证据经历 private → submitted → admitted_for_discussion。"""
        engine, _ = _make_engine_with_mock()
        ev_p = _make_private_evidence("ev-p1", "party-plaintiff")
        ev_d = _make_private_evidence("ev-d1", "party-defendant")

        result = await engine.run(
            issue_tree=_make_issue_tree(),
            evidence_index=EvidenceIndex(case_id="case-001", evidence=[ev_p, ev_d]),
            plaintiff_party_id="party-plaintiff",
            defendant_party_id="party-defendant",
            plaintiff_evidence_ids=["ev-p1"],
            defendant_evidence_ids=["ev-d1"],
        )

        # final_evidence_index 中的证据应为 admitted
        final_idx = result.final_evidence_index
        for ev in final_idx.evidence:
            assert ev.status == EvidenceStatus.admitted_for_discussion

    @pytest.mark.asyncio
    async def test_cross_examination_result_populated(self):
        engine, _ = _make_engine_with_mock()
        ev_p = _make_private_evidence("ev-p1", "party-plaintiff")
        ev_d = _make_private_evidence("ev-d1", "party-defendant")

        result = await engine.run(
            issue_tree=_make_issue_tree(),
            evidence_index=EvidenceIndex(case_id="case-001", evidence=[ev_p, ev_d]),
            plaintiff_party_id="party-plaintiff",
            defendant_party_id="party-defendant",
            plaintiff_evidence_ids=["ev-p1"],
            defendant_evidence_ids=["ev-d1"],
        )

        assert len(result.cross_examination_result.records) == 2

    @pytest.mark.asyncio
    async def test_judge_questions_populated(self):
        engine, _ = _make_engine_with_mock()
        ev_p = _make_private_evidence("ev-p1", "party-plaintiff")
        ev_d = _make_private_evidence("ev-d1", "party-defendant")

        result = await engine.run(
            issue_tree=_make_issue_tree(),
            evidence_index=EvidenceIndex(case_id="case-001", evidence=[ev_p, ev_d]),
            plaintiff_party_id="party-plaintiff",
            defendant_party_id="party-defendant",
            plaintiff_evidence_ids=["ev-p1"],
            defendant_evidence_ids=["ev-d1"],
        )

        assert len(result.judge_questions.questions) >= 1


class TestEvidenceSubmission:
    @pytest.mark.asyncio
    async def test_bulk_submit_transitions_private_to_submitted(self):
        """Stage 1: 指定的 private 证据 → submitted。"""
        mock_llm = AsyncMock()
        mock_llm.create_message.side_effect = [
            _cross_exam_response("ev-p1"),
            _judge_response(),
        ]
        engine = PretrialConferenceEngine(
            llm_client=mock_llm,
            model="test-model",
            temperature=0.0,
            max_retries=1,
        )
        ev_p = _make_private_evidence("ev-p1", "party-plaintiff")
        ev_stay = _make_private_evidence("ev-p2", "party-plaintiff")

        result = await engine.run(
            issue_tree=_make_issue_tree(),
            evidence_index=EvidenceIndex(
                case_id="case-001",
                evidence=[ev_p, ev_stay],
            ),
            plaintiff_party_id="party-plaintiff",
            defendant_party_id="party-defendant",
            plaintiff_evidence_ids=["ev-p1"],  # only submit ev-p1
            defendant_evidence_ids=[],
        )

        # ev-p2 should still be private in final index
        ev2 = next(e for e in result.final_evidence_index.evidence if e.evidence_id == "ev-p2")
        assert ev2.status == EvidenceStatus.private


class TestNoEvidenceToSubmit:
    @pytest.mark.asyncio
    async def test_no_evidence_ids_produces_empty_result(self):
        """不提交证据时，质证和追问均为空。"""
        mock_llm = AsyncMock()
        engine = PretrialConferenceEngine(
            llm_client=mock_llm,
            model="test-model",
            temperature=0.0,
            max_retries=1,
        )
        ev = _make_private_evidence("ev-001", "party-plaintiff")

        result = await engine.run(
            issue_tree=_make_issue_tree(),
            evidence_index=EvidenceIndex(case_id="case-001", evidence=[ev]),
            plaintiff_party_id="party-plaintiff",
            defendant_party_id="party-defendant",
            plaintiff_evidence_ids=[],
            defendant_evidence_ids=[],
        )

        assert result.cross_examination_result.records == []
        assert result.judge_questions.questions == []
        mock_llm.create_message.assert_not_called()


class TestLLMFailureGraceful:
    @pytest.mark.asyncio
    async def test_all_llm_failures_still_returns_result(self):
        """LLM 全部失败仍返回 PretrialConferenceResult（空内容）。"""
        mock_llm = AsyncMock()
        mock_llm.create_message.side_effect = RuntimeError("LLM down")
        engine = PretrialConferenceEngine(
            llm_client=mock_llm,
            model="test-model",
            temperature=0.0,
            max_retries=1,
        )
        ev = _make_private_evidence("ev-001", "party-plaintiff")

        result = await engine.run(
            issue_tree=_make_issue_tree(),
            evidence_index=EvidenceIndex(case_id="case-001", evidence=[ev]),
            plaintiff_party_id="party-plaintiff",
            defendant_party_id="party-defendant",
            plaintiff_evidence_ids=["ev-001"],
            defendant_evidence_ids=[],
        )

        assert isinstance(result, PretrialConferenceResult)
        # Evidence should still be submitted (cross-exam failed, no transition)
        ev_final = result.final_evidence_index.evidence[0]
        assert ev_final.status == EvidenceStatus.submitted
