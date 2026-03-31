"""JudgeAgent 单元测试 — TDD."""

import json

import pytest
from unittest.mock import AsyncMock

from engines.pretrial_conference.agents.judge_agent import JudgeAgent
from engines.pretrial_conference.schemas import (
    JudgeQuestionSet,
    JudgeQuestionType,
)
from engines.shared.models import (
    AccessDomain,
    BlockingCondition,
    BlockingConditionType,
    Evidence,
    EvidenceIndex,
    EvidenceStatus,
    EvidenceType,
    Issue,
    IssueCategory,
    IssueStatus,
    IssueTree,
    IssueType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_issue(
    issue_id="issue-001",
    status=IssueStatus.open,
    category=None,
):
    return Issue(
        issue_id=issue_id,
        case_id="case-001",
        title=f"争点 {issue_id}",
        issue_type=IssueType.factual,
        status=status,
        issue_category=category,
    )


def _make_issue_tree(issues=None):
    return IssueTree(case_id="case-001", issues=issues or [_make_issue()])


def _make_admitted_evidence(
    evidence_id="ev-001",
    owner_party_id="party-plaintiff",
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
        access_domain=AccessDomain.admitted_record,
        status=EvidenceStatus.admitted_for_discussion,
        submitted_by_party_id=owner_party_id,
        challenged_by_party_ids=[],
    )


def _make_llm_response(questions=None):
    """构建 LLM 返回的法官追问 JSON。"""
    if questions is None:
        questions = [
            {
                "question_id": "jq-001",
                "issue_id": "issue-001",
                "evidence_ids": ["ev-001"],
                "question_text": "原告能否解释借条金额与转账记录不一致？",
                "target_party_id": "party-plaintiff",
                "question_type": "contradiction",
                "priority": 1,
            },
        ]
    return json.dumps({"questions": questions})


def _make_agent(llm_response=None):
    mock_llm = AsyncMock()
    mock_llm.create_message.return_value = llm_response or _make_llm_response()
    agent = JudgeAgent(
        llm_client=mock_llm,
        model="test-model",
        temperature=0.0,
        max_retries=1,
    )
    return agent, mock_llm


_RUN_KWARGS = dict(
    case_id="case-001",
    run_id="run-001",
    plaintiff_party_id="party-plaintiff",
    defendant_party_id="party-defendant",
)


# ---------------------------------------------------------------------------
# 基本生成
# ---------------------------------------------------------------------------


class TestBasicGeneration:
    @pytest.mark.asyncio
    async def test_generates_question_set(self):
        agent, _ = _make_agent()
        qs = await agent.generate_questions(
            issue_tree=_make_issue_tree(),
            admitted_evidence=[_make_admitted_evidence()],
            **_RUN_KWARGS,
        )
        assert isinstance(qs, JudgeQuestionSet)
        assert len(qs.questions) == 1
        assert qs.questions[0].question_text

    @pytest.mark.asyncio
    async def test_question_bound_to_issue_and_evidence(self):
        agent, _ = _make_agent()
        qs = await agent.generate_questions(
            issue_tree=_make_issue_tree(),
            admitted_evidence=[_make_admitted_evidence()],
            **_RUN_KWARGS,
        )
        q = qs.questions[0]
        assert q.issue_id == "issue-001"
        assert q.evidence_ids == ["ev-001"]
        assert q.question_type == JudgeQuestionType.contradiction

    @pytest.mark.asyncio
    async def test_max_10_questions_enforced(self):
        """LLM 返回 12 个问题，截断到 10。"""
        questions = [
            {
                "question_id": f"jq-{i:03d}",
                "issue_id": "issue-001",
                "evidence_ids": ["ev-001"],
                "question_text": f"问题 {i}",
                "target_party_id": "party-plaintiff",
                "question_type": "clarification",
                "priority": min(i, 10),
            }
            for i in range(1, 13)
        ]
        agent, _ = _make_agent(_make_llm_response(questions))
        qs = await agent.generate_questions(
            issue_tree=_make_issue_tree(),
            admitted_evidence=[_make_admitted_evidence()],
            **_RUN_KWARGS,
        )
        assert len(qs.questions) <= 10

    @pytest.mark.asyncio
    async def test_case_id_and_run_id_set(self):
        agent, _ = _make_agent()
        qs = await agent.generate_questions(
            issue_tree=_make_issue_tree(),
            admitted_evidence=[_make_admitted_evidence()],
            **_RUN_KWARGS,
        )
        assert qs.case_id == "case-001"
        assert qs.run_id == "run-001"


# ---------------------------------------------------------------------------
# 访问控制
# ---------------------------------------------------------------------------


class TestAccessControl:
    @pytest.mark.asyncio
    async def test_non_admitted_evidence_rejected(self):
        """传入非 admitted 证据应抛 ValueError。"""
        submitted_ev = Evidence(
            evidence_id="ev-bad",
            case_id="case-001",
            owner_party_id="party-plaintiff",
            title="坏证据",
            source="来源",
            summary="摘要",
            evidence_type=EvidenceType.documentary,
            target_fact_ids=["fact-001"],
            target_issue_ids=["issue-001"],
            access_domain=AccessDomain.shared_common,
            status=EvidenceStatus.submitted,
            challenged_by_party_ids=[],
        )
        agent, _ = _make_agent()
        with pytest.raises(ValueError, match="admitted_for_discussion"):
            await agent.generate_questions(
                issue_tree=_make_issue_tree(),
                admitted_evidence=[submitted_ev],
                **_RUN_KWARGS,
            )


# ---------------------------------------------------------------------------
# 反幻觉规则层
# ---------------------------------------------------------------------------


class TestRuleLayer:
    @pytest.mark.asyncio
    async def test_hallucinated_evidence_id_filtered(self):
        questions = [
            {
                "question_id": "jq-001",
                "issue_id": "issue-001",
                "evidence_ids": ["ev-001", "ev-FAKE"],
                "question_text": "问题",
                "target_party_id": "party-plaintiff",
                "question_type": "clarification",
                "priority": 1,
            },
        ]
        agent, _ = _make_agent(_make_llm_response(questions))
        qs = await agent.generate_questions(
            issue_tree=_make_issue_tree(),
            admitted_evidence=[_make_admitted_evidence()],
            **_RUN_KWARGS,
        )
        assert len(qs.questions) == 1
        assert qs.questions[0].evidence_ids == ["ev-001"]

    @pytest.mark.asyncio
    async def test_hallucinated_issue_id_question_dropped(self):
        """引用不存在的 issue_id 的问题被丢弃。"""
        questions = [
            {
                "question_id": "jq-001",
                "issue_id": "issue-FAKE",
                "evidence_ids": ["ev-001"],
                "question_text": "问题",
                "target_party_id": "party-plaintiff",
                "question_type": "clarification",
                "priority": 1,
            },
        ]
        agent, _ = _make_agent(_make_llm_response(questions))
        qs = await agent.generate_questions(
            issue_tree=_make_issue_tree(),
            admitted_evidence=[_make_admitted_evidence()],
            **_RUN_KWARGS,
        )
        assert len(qs.questions) == 0

    @pytest.mark.asyncio
    async def test_invalid_question_type_dropped(self):
        questions = [
            {
                "question_id": "jq-001",
                "issue_id": "issue-001",
                "evidence_ids": ["ev-001"],
                "question_text": "问题",
                "target_party_id": "party-plaintiff",
                "question_type": "invalid_type",
                "priority": 1,
            },
        ]
        agent, _ = _make_agent(_make_llm_response(questions))
        qs = await agent.generate_questions(
            issue_tree=_make_issue_tree(),
            admitted_evidence=[_make_admitted_evidence()],
            **_RUN_KWARGS,
        )
        assert len(qs.questions) == 0

    @pytest.mark.asyncio
    async def test_priority_clamped_to_1_10(self):
        """priority 超范围时被截断到 [1, 10]。"""
        questions = [
            {
                "question_id": "jq-001",
                "issue_id": "issue-001",
                "evidence_ids": ["ev-001"],
                "question_text": "问题",
                "target_party_id": "party-plaintiff",
                "question_type": "clarification",
                "priority": 15,
            },
        ]
        agent, _ = _make_agent(_make_llm_response(questions))
        qs = await agent.generate_questions(
            issue_tree=_make_issue_tree(),
            admitted_evidence=[_make_admitted_evidence()],
            **_RUN_KWARGS,
        )
        assert len(qs.questions) == 1
        assert 1 <= qs.questions[0].priority <= 10


# ---------------------------------------------------------------------------
# 争点过滤
# ---------------------------------------------------------------------------


class TestIssueFiltering:
    @pytest.mark.asyncio
    async def test_resolved_issues_excluded_from_prompt(self):
        """已解决的争点不传入 LLM（仅 open 争点被发送）。"""
        resolved = _make_issue("issue-resolved", status=IssueStatus.resolved)
        open_issue = _make_issue("issue-open", status=IssueStatus.open)
        agent, mock_llm = _make_agent()

        await agent.generate_questions(
            issue_tree=_make_issue_tree([resolved, open_issue]),
            admitted_evidence=[_make_admitted_evidence()],
            **_RUN_KWARGS,
        )
        # 检查 LLM 调用的 user prompt 只包含 open 争点
        call_kwargs = mock_llm.create_message.call_args
        user_prompt = call_kwargs.kwargs.get("user", "")
        assert "issue-open" in user_prompt
        assert "issue-resolved" not in user_prompt


# ---------------------------------------------------------------------------
# LLM 失败
# ---------------------------------------------------------------------------


class TestLLMFailure:
    @pytest.mark.asyncio
    async def test_llm_error_returns_empty_set(self):
        mock_llm = AsyncMock()
        mock_llm.create_message.side_effect = RuntimeError("LLM down")
        agent = JudgeAgent(
            llm_client=mock_llm,
            model="m",
            temperature=0.0,
            max_retries=1,
        )
        qs = await agent.generate_questions(
            issue_tree=_make_issue_tree(),
            admitted_evidence=[_make_admitted_evidence()],
            **_RUN_KWARGS,
        )
        assert qs.questions == []

    @pytest.mark.asyncio
    async def test_malformed_json_returns_empty(self):
        agent, _ = _make_agent("not json")
        qs = await agent.generate_questions(
            issue_tree=_make_issue_tree(),
            admitted_evidence=[_make_admitted_evidence()],
            **_RUN_KWARGS,
        )
        assert qs.questions == []


# ---------------------------------------------------------------------------
# 增强输入
# ---------------------------------------------------------------------------


class TestEnrichment:
    @pytest.mark.asyncio
    async def test_evidence_gaps_in_prompt(self):
        """提供 evidence_gaps 时，prompt 中包含缺口信息。"""
        from engines.shared.models import (
            EvidenceGapItem,
            OutcomeImpactSize,
            PracticallyObtainable,
            SupplementCost,
        )

        gap = EvidenceGapItem(
            gap_id="gap-001",
            case_id="case-001",
            run_id="run-001",
            related_issue_id="issue-001",
            gap_description="缺少转账凭证",
            supplement_cost=SupplementCost.low,
            outcome_impact_size=OutcomeImpactSize.significant,
            practically_obtainable=PracticallyObtainable.yes,
            roi_rank=1,
        )
        agent, mock_llm = _make_agent()
        await agent.generate_questions(
            issue_tree=_make_issue_tree(),
            admitted_evidence=[_make_admitted_evidence()],
            evidence_gaps=[gap],
            **_RUN_KWARGS,
        )
        user_prompt = mock_llm.create_message.call_args.kwargs.get("user", "")
        assert "缺少转账凭证" in user_prompt

    @pytest.mark.asyncio
    async def test_blocking_conditions_in_prompt(self):
        """提供 blocking_conditions 时，prompt 中包含阻断条件。"""
        bc = BlockingCondition(
            condition_id="bc-001",
            condition_type=BlockingConditionType.amount_conflict,
            description="借款金额与利息计算矛盾",
            linked_issue_ids=["issue-001"],
            linked_evidence_ids=["ev-001"],
        )
        agent, mock_llm = _make_agent()
        await agent.generate_questions(
            issue_tree=_make_issue_tree(),
            admitted_evidence=[_make_admitted_evidence()],
            blocking_conditions=[bc],
            **_RUN_KWARGS,
        )
        user_prompt = mock_llm.create_message.call_args.kwargs.get("user", "")
        assert "借款金额与利息计算矛盾" in user_prompt
