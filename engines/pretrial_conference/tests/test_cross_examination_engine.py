"""CrossExaminationEngine 单元测试 — TDD RED phase."""

import json

import pytest
from unittest.mock import AsyncMock

from engines.pretrial_conference.cross_examination_engine import (
    CrossExaminationEngine,
)
from engines.pretrial_conference.schemas import (
    CrossExaminationDimension,
    CrossExaminationResult,
    CrossExaminationVerdict,
)
from engines.shared.models import (
    AccessDomain,
    Evidence,
    EvidenceIndex,
    EvidenceStatus,
    EvidenceType,
    IssueTree,
    Issue,
    IssueType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_issue(issue_id="issue-001"):
    return Issue(
        issue_id=issue_id,
        case_id="case-001",
        title="借款事实争点",
        issue_type=IssueType.factual,
    )


def _make_issue_tree(issues=None):
    return IssueTree(case_id="case-001", issues=issues or [_make_issue()])


_DOMAIN_MAP = {
    EvidenceStatus.private: AccessDomain.owner_private,
    EvidenceStatus.submitted: AccessDomain.shared_common,
    EvidenceStatus.challenged: AccessDomain.shared_common,
    EvidenceStatus.admitted_for_discussion: AccessDomain.admitted_record,
}


def _make_evidence(
    evidence_id="ev-001",
    owner_party_id="party-plaintiff",
    status=EvidenceStatus.submitted,
):
    return Evidence(
        evidence_id=evidence_id,
        case_id="case-001",
        owner_party_id=owner_party_id,
        title=f"证据 {evidence_id}",
        source="当事人提交",
        summary=f"证据 {evidence_id} 内容摘要",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=["fact-001"],
        target_issue_ids=["issue-001"],
        access_domain=_DOMAIN_MAP[status],
        status=status,
        submitted_by_party_id=(
            owner_party_id if status != EvidenceStatus.private else None
        ),
        challenged_by_party_ids=[],
    )


def _make_evidence_index(evidences=None):
    return EvidenceIndex(
        case_id="case-001",
        evidence=evidences or [_make_evidence()],
    )


def _all_accepted_json(evidence_id="ev-001"):
    """LLM 返回全部 4 维度 accepted。"""
    return json.dumps({
        "opinions": [
            {
                "evidence_id": evidence_id,
                "issue_ids": ["issue-001"],
                "dimension": d,
                "verdict": "accepted",
                "reasoning": f"{d} 无异议",
            }
            for d in ("authenticity", "relevance", "legality", "probative_value")
        ]
    })


def _one_challenged_json(evidence_id="ev-001"):
    """LLM 返回 authenticity challenged，其余 accepted。"""
    opinions = [
        {
            "evidence_id": evidence_id,
            "issue_ids": ["issue-001"],
            "dimension": "authenticity",
            "verdict": "challenged",
            "reasoning": "签名疑似伪造",
        },
    ]
    for d in ("relevance", "legality", "probative_value"):
        opinions.append({
            "evidence_id": evidence_id,
            "issue_ids": ["issue-001"],
            "dimension": d,
            "verdict": "accepted",
            "reasoning": f"{d} 无异议",
        })
    return json.dumps({"opinions": opinions})


def _make_engine(llm_response=None):
    mock_llm = AsyncMock()
    if isinstance(llm_response, list):
        mock_llm.create_message.side_effect = llm_response
    else:
        mock_llm.create_message.return_value = (
            llm_response or _all_accepted_json()
        )
    engine = CrossExaminationEngine(
        llm_client=mock_llm,
        model="test-model",
        temperature=0.0,
        max_retries=1,
    )
    return engine, mock_llm


_RUN_KWARGS = dict(
    plaintiff_party_id="party-plaintiff",
    defendant_party_id="party-defendant",
)


# ---------------------------------------------------------------------------
# 基本流程
# ---------------------------------------------------------------------------


class TestBasicFlow:
    @pytest.mark.asyncio
    async def test_all_accepted_becomes_admitted(self):
        """全部维度 accepted → admitted_for_discussion。"""
        engine, _ = _make_engine(_all_accepted_json())
        result, updated = await engine.run(
            evidence_index=_make_evidence_index(),
            issue_tree=_make_issue_tree(),
            **_RUN_KWARGS,
        )
        assert isinstance(result, CrossExaminationResult)
        assert len(result.records) == 1
        assert result.records[0].result_status == "admitted_for_discussion"
        ev = updated.evidence[0]
        assert ev.status == EvidenceStatus.admitted_for_discussion

    @pytest.mark.asyncio
    async def test_any_challenged_stays_challenged(self):
        """任一维度 challenged → challenged。"""
        engine, _ = _make_engine(_one_challenged_json())
        result, updated = await engine.run(
            evidence_index=_make_evidence_index(),
            issue_tree=_make_issue_tree(),
            **_RUN_KWARGS,
        )
        assert len(result.records) == 1
        assert result.records[0].result_status == "challenged"
        ev = updated.evidence[0]
        assert ev.status == EvidenceStatus.challenged

    @pytest.mark.asyncio
    async def test_result_has_case_and_run_id(self):
        engine, _ = _make_engine()
        result, _ = await engine.run(
            evidence_index=_make_evidence_index(),
            issue_tree=_make_issue_tree(),
            **_RUN_KWARGS,
        )
        assert result.case_id == "case-001"
        assert result.run_id  # non-empty


# ---------------------------------------------------------------------------
# 证据过滤
# ---------------------------------------------------------------------------


class TestEvidenceFiltering:
    @pytest.mark.asyncio
    async def test_private_evidence_excluded(self):
        """private 证据不参与质证。"""
        priv = _make_evidence("ev-priv", "party-plaintiff", EvidenceStatus.private)
        sub = _make_evidence("ev-sub", "party-plaintiff", EvidenceStatus.submitted)
        engine, _ = _make_engine(_all_accepted_json("ev-sub"))

        result, updated = await engine.run(
            evidence_index=_make_evidence_index([priv, sub]),
            issue_tree=_make_issue_tree(),
            **_RUN_KWARGS,
        )
        assert len(result.records) == 1
        assert result.records[0].evidence_id == "ev-sub"
        priv_ev = next(e for e in updated.evidence if e.evidence_id == "ev-priv")
        assert priv_ev.status == EvidenceStatus.private

    @pytest.mark.asyncio
    async def test_already_admitted_excluded(self):
        """已 admitted 的证据不再质证。"""
        adm = _make_evidence(
            "ev-adm", "party-plaintiff", EvidenceStatus.admitted_for_discussion
        )
        sub = _make_evidence("ev-sub", "party-plaintiff", EvidenceStatus.submitted)
        engine, _ = _make_engine(_all_accepted_json("ev-sub"))

        result, _ = await engine.run(
            evidence_index=_make_evidence_index([adm, sub]),
            issue_tree=_make_issue_tree(),
            **_RUN_KWARGS,
        )
        assert len(result.records) == 1
        assert result.records[0].evidence_id == "ev-sub"

    @pytest.mark.asyncio
    async def test_no_submitted_returns_empty(self):
        """无 submitted 证据时返回空结果，不调用 LLM。"""
        priv = _make_evidence("ev-priv", "party-plaintiff", EvidenceStatus.private)
        engine, mock_llm = _make_engine()

        result, _ = await engine.run(
            evidence_index=_make_evidence_index([priv]),
            issue_tree=_make_issue_tree(),
            **_RUN_KWARGS,
        )
        assert result.records == []
        mock_llm.create_message.assert_not_called()


# ---------------------------------------------------------------------------
# 对方质证
# ---------------------------------------------------------------------------


class TestOpposingPartyExamines:
    @pytest.mark.asyncio
    async def test_plaintiff_evidence_examined_by_defendant(self):
        engine, _ = _make_engine()
        result, _ = await engine.run(
            evidence_index=_make_evidence_index([
                _make_evidence("ev-001", "party-plaintiff"),
            ]),
            issue_tree=_make_issue_tree(),
            **_RUN_KWARGS,
        )
        for op in result.records[0].opinions:
            assert op.examiner_party_id == "party-defendant"

    @pytest.mark.asyncio
    async def test_defendant_evidence_examined_by_plaintiff(self):
        engine, _ = _make_engine(_all_accepted_json("ev-def"))
        result, _ = await engine.run(
            evidence_index=_make_evidence_index([
                _make_evidence("ev-def", "party-defendant"),
            ]),
            issue_tree=_make_issue_tree(),
            **_RUN_KWARGS,
        )
        for op in result.records[0].opinions:
            assert op.examiner_party_id == "party-plaintiff"


# ---------------------------------------------------------------------------
# 焦点清单
# ---------------------------------------------------------------------------


class TestFocusList:
    @pytest.mark.asyncio
    async def test_challenged_generates_focus_item(self):
        engine, _ = _make_engine(_one_challenged_json())
        result, _ = await engine.run(
            evidence_index=_make_evidence_index(),
            issue_tree=_make_issue_tree(),
            **_RUN_KWARGS,
        )
        assert len(result.focus_list) >= 1
        focus = result.focus_list[0]
        assert focus.evidence_id == "ev-001"
        assert focus.dimension == CrossExaminationDimension.authenticity

    @pytest.mark.asyncio
    async def test_all_accepted_no_focus(self):
        engine, _ = _make_engine(_all_accepted_json())
        result, _ = await engine.run(
            evidence_index=_make_evidence_index(),
            issue_tree=_make_issue_tree(),
            **_RUN_KWARGS,
        )
        assert result.focus_list == []


# ---------------------------------------------------------------------------
# 规则层 — 反幻觉
# ---------------------------------------------------------------------------


class TestRuleLayer:
    @pytest.mark.asyncio
    async def test_hallucinated_evidence_id_filtered(self):
        response = json.dumps({
            "opinions": [
                {
                    "evidence_id": "ev-FAKE",
                    "issue_ids": ["issue-001"],
                    "dimension": "authenticity",
                    "verdict": "challenged",
                    "reasoning": "伪造引用",
                },
                {
                    "evidence_id": "ev-001",
                    "issue_ids": ["issue-001"],
                    "dimension": "authenticity",
                    "verdict": "accepted",
                    "reasoning": "正常引用",
                },
            ]
        })
        engine, _ = _make_engine(response)
        result, _ = await engine.run(
            evidence_index=_make_evidence_index(),
            issue_tree=_make_issue_tree(),
            **_RUN_KWARGS,
        )
        assert len(result.records) == 1
        for op in result.records[0].opinions:
            assert op.evidence_id == "ev-001"

    @pytest.mark.asyncio
    async def test_invalid_dimension_filtered(self):
        response = json.dumps({
            "opinions": [
                {
                    "evidence_id": "ev-001",
                    "issue_ids": ["issue-001"],
                    "dimension": "invalid_dim",
                    "verdict": "accepted",
                    "reasoning": "无效维度",
                },
                {
                    "evidence_id": "ev-001",
                    "issue_ids": ["issue-001"],
                    "dimension": "authenticity",
                    "verdict": "accepted",
                    "reasoning": "有效维度",
                },
            ]
        })
        engine, _ = _make_engine(response)
        result, _ = await engine.run(
            evidence_index=_make_evidence_index(),
            issue_tree=_make_issue_tree(),
            **_RUN_KWARGS,
        )
        assert len(result.records) == 1
        assert all(
            op.dimension == CrossExaminationDimension.authenticity
            for op in result.records[0].opinions
        )

    @pytest.mark.asyncio
    async def test_hallucinated_issue_ids_filtered(self):
        response = json.dumps({
            "opinions": [
                {
                    "evidence_id": "ev-001",
                    "issue_ids": ["issue-001", "issue-FAKE"],
                    "dimension": "authenticity",
                    "verdict": "accepted",
                    "reasoning": "理由",
                },
            ]
        })
        engine, _ = _make_engine(response)
        result, _ = await engine.run(
            evidence_index=_make_evidence_index(),
            issue_tree=_make_issue_tree(),
            **_RUN_KWARGS,
        )
        op = result.records[0].opinions[0]
        assert op.issue_ids == ["issue-001"]


# ---------------------------------------------------------------------------
# LLM 失败
# ---------------------------------------------------------------------------


class TestLLMFailure:
    @pytest.mark.asyncio
    async def test_llm_error_returns_empty(self):
        mock_llm = AsyncMock()
        mock_llm.create_message.side_effect = RuntimeError("LLM down")
        engine = CrossExaminationEngine(
            llm_client=mock_llm, model="m", temperature=0.0, max_retries=1,
        )
        result, updated = await engine.run(
            evidence_index=_make_evidence_index(),
            issue_tree=_make_issue_tree(),
            **_RUN_KWARGS,
        )
        assert result.records == []
        assert updated.evidence[0].status == EvidenceStatus.submitted

    @pytest.mark.asyncio
    async def test_malformed_json_returns_empty(self):
        engine, _ = _make_engine("this is not json at all")
        result, _ = await engine.run(
            evidence_index=_make_evidence_index(),
            issue_tree=_make_issue_tree(),
            **_RUN_KWARGS,
        )
        assert result.records == []


# ---------------------------------------------------------------------------
# 多证据场景
# ---------------------------------------------------------------------------


class TestMultipleEvidence:
    @pytest.mark.asyncio
    async def test_two_evidence_mixed_outcome(self):
        """ev-001 全 accepted → admitted; ev-002 有 challenged → challenged。"""
        ev1 = _make_evidence("ev-001", "party-plaintiff")
        ev2 = _make_evidence("ev-002", "party-plaintiff")
        response = json.dumps({
            "opinions": [
                # ev-001: 4 个 accepted
                *[
                    {
                        "evidence_id": "ev-001",
                        "issue_ids": ["issue-001"],
                        "dimension": d,
                        "verdict": "accepted",
                        "reasoning": "ok",
                    }
                    for d in (
                        "authenticity",
                        "relevance",
                        "legality",
                        "probative_value",
                    )
                ],
                # ev-002: authenticity challenged
                {
                    "evidence_id": "ev-002",
                    "issue_ids": ["issue-001"],
                    "dimension": "authenticity",
                    "verdict": "challenged",
                    "reasoning": "存疑",
                },
                *[
                    {
                        "evidence_id": "ev-002",
                        "issue_ids": ["issue-001"],
                        "dimension": d,
                        "verdict": "accepted",
                        "reasoning": "ok",
                    }
                    for d in ("relevance", "legality", "probative_value")
                ],
            ]
        })
        engine, _ = _make_engine(response)
        result, updated = await engine.run(
            evidence_index=_make_evidence_index([ev1, ev2]),
            issue_tree=_make_issue_tree(),
            **_RUN_KWARGS,
        )
        assert len(result.records) == 2
        rec1 = next(r for r in result.records if r.evidence_id == "ev-001")
        rec2 = next(r for r in result.records if r.evidence_id == "ev-002")
        assert rec1.result_status == "admitted_for_discussion"
        assert rec2.result_status == "challenged"

    @pytest.mark.asyncio
    async def test_both_parties_evidence_examined(self):
        """双方各有 submitted 证据，均应被对方质证。"""
        p_ev = _make_evidence("ev-p", "party-plaintiff")
        d_ev = _make_evidence("ev-d", "party-defendant")
        response = json.dumps({
            "opinions": [
                {
                    "evidence_id": eid,
                    "issue_ids": ["issue-001"],
                    "dimension": d,
                    "verdict": "accepted",
                    "reasoning": "ok",
                }
                for eid in ("ev-p", "ev-d")
                for d in (
                    "authenticity",
                    "relevance",
                    "legality",
                    "probative_value",
                )
            ]
        })
        engine, _ = _make_engine(response)
        result, _ = await engine.run(
            evidence_index=_make_evidence_index([p_ev, d_ev]),
            issue_tree=_make_issue_tree(),
            **_RUN_KWARGS,
        )
        assert len(result.records) == 2
        ids = {r.evidence_id for r in result.records}
        assert ids == {"ev-p", "ev-d"}
