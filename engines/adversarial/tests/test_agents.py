"""
PartyAgent 单元测试 — 使用 mock LLMClient，不调用真实 API。
PartyAgent unit tests — uses mock LLMClient, no real API calls.
"""
from __future__ import annotations

import json
import pytest

from engines.shared.models import (
    AccessDomain,
    AgentRole,
    Evidence,
    EvidenceIndex,
    EvidenceType,
    Issue,
    IssueTree,
    IssueType,
)
from engines.adversarial.agents.base_agent import BasePartyAgent
from engines.adversarial.agents.plaintiff import PlaintiffAgent
from engines.adversarial.agents.defendant import DefendantAgent
from engines.adversarial.agents.evidence_mgr import EvidenceManagerAgent
from engines.adversarial.schemas import RoundConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CASE_ID = "case-test-001"
PLAINTIFF_ID = "party-plaintiff-001"
DEFENDANT_ID = "party-defendant-001"


def _make_llm_response(
    title: str = "测试主张",
    body: str = "测试正文，引用证据 ev-001。",
    issue_ids: list[str] | None = None,
    evidence_citations: list[str] | None = None,
    arguments: list[dict] | None = None,
) -> str:
    payload = {
        "title": title,
        "body": body,
        "case_id": CASE_ID,
        "issue_ids": issue_ids or ["issue-001"],
        "evidence_citations": evidence_citations or ["ev-001"],
        "risk_flags": [],
        "arguments": arguments or [
            {
                "issue_id": "issue-001",
                "position": "借款关系成立，原告已实际交付借款。",
                "supporting_evidence_ids": ["ev-001"],
                "legal_basis": "《民法典》第667条",
            }
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


class MockLLMClient:
    """固定返回 JSON 的 mock LLM 客户端。"""

    def __init__(self, response: str | None = None):
        self._response = response or _make_llm_response()
        self.call_count = 0

    async def create_message(self, *, system: str, user: str, **kwargs) -> str:
        self.call_count += 1
        return self._response


@pytest.fixture
def config() -> RoundConfig:
    return RoundConfig(num_rounds=3, max_tokens_per_output=2000, max_retries=2)


@pytest.fixture
def issue_tree() -> IssueTree:
    return IssueTree(
        case_id=CASE_ID,
        issues=[
            Issue(
                issue_id="issue-001",
                case_id=CASE_ID,
                title="借贷关系是否成立",
                issue_type=IssueType.factual,
                evidence_ids=["ev-001", "ev-002"],
            ),
            Issue(
                issue_id="issue-002",
                case_id=CASE_ID,
                title="还款事实认定",
                issue_type=IssueType.factual,
                evidence_ids=["ev-003"],
            ),
        ],
    )


@pytest.fixture
def plaintiff_evidence() -> list[Evidence]:
    return [
        Evidence(
            evidence_id="ev-001",
            case_id=CASE_ID,
            owner_party_id=PLAINTIFF_ID,
            title="借条原件",
            source="原告提交",
            summary="载明借款5万元，还款日期2023-06-01",
            evidence_type=EvidenceType.documentary,
            target_fact_ids=["fact-001"],
            access_domain=AccessDomain.owner_private,
        ),
        Evidence(
            evidence_id="ev-002",
            case_id=CASE_ID,
            owner_party_id=PLAINTIFF_ID,
            title="银行转账记录",
            source="原告提交",
            summary="2023-01-01向被告账户转账5万元",
            evidence_type=EvidenceType.electronic_data,
            target_fact_ids=["fact-002"],
            access_domain=AccessDomain.shared_common,
        ),
    ]


@pytest.fixture
def defendant_evidence() -> list[Evidence]:
    return [
        Evidence(
            evidence_id="ev-003",
            case_id=CASE_ID,
            owner_party_id=DEFENDANT_ID,
            title="还款收条",
            source="被告提交",
            summary="2023-05-01已还款3万元收条",
            evidence_type=EvidenceType.documentary,
            target_fact_ids=["fact-003"],
            access_domain=AccessDomain.owner_private,
        ),
    ]


# ---------------------------------------------------------------------------
# PlaintiffAgent 测试
# ---------------------------------------------------------------------------


class TestPlaintiffAgent:
    @pytest.mark.asyncio
    async def test_generate_claim_returns_agent_output(
        self, config, issue_tree, plaintiff_evidence
    ):
        mock_llm = MockLLMClient()
        agent = PlaintiffAgent(mock_llm, PLAINTIFF_ID, config)

        output = await agent.generate_claim(
            issue_tree=issue_tree,
            visible_evidence=plaintiff_evidence,
            context_outputs=[],
            run_id="run-001",
            state_id="state-001",
            round_index=1,
        )

        assert output.agent_role_code == AgentRole.plaintiff_agent.value
        assert output.owner_party_id == PLAINTIFF_ID
        assert output.round_index == 1
        assert len(output.issue_ids) >= 1
        assert len(output.evidence_citations) >= 1
        assert mock_llm.call_count == 1

    @pytest.mark.asyncio
    async def test_generate_rebuttal_calls_llm(
        self, config, issue_tree, plaintiff_evidence
    ):
        from engines.shared.models import AgentOutput, ProcedurePhase, StatementClass
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        mock_opponent_output = AgentOutput(
            output_id="output-def-r1-abc123",
            case_id=CASE_ID,
            run_id="run-001",
            state_id="state-001",
            phase=ProcedurePhase.opening,
            round_index=1,
            agent_role_code=AgentRole.defendant_agent.value,
            owner_party_id=DEFENDANT_ID,
            issue_ids=["issue-001"],
            title="被告抗辩",
            body="被告未收到该款项。",
            evidence_citations=["ev-003"],
            statement_class=StatementClass.fact,
            created_at=now,
        )

        mock_llm = MockLLMClient()
        agent = PlaintiffAgent(mock_llm, PLAINTIFF_ID, config)

        output = await agent.generate_rebuttal(
            issue_tree=issue_tree,
            visible_evidence=plaintiff_evidence,
            context_outputs=[mock_opponent_output],
            opponent_outputs=[mock_opponent_output],
            run_id="run-001",
            state_id="state-003",
            round_index=3,
        )

        assert output.agent_role_code == AgentRole.plaintiff_agent.value
        assert output.round_index == 3
        assert mock_llm.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_llm_failure(self, config, issue_tree, plaintiff_evidence):
        call_count = 0

        class FlakyLLMClient:
            async def create_message(self, **kwargs) -> str:
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    raise RuntimeError("临时网络错误")
                return _make_llm_response()

        agent = PlaintiffAgent(FlakyLLMClient(), PLAINTIFF_ID, config)
        output = await agent.generate_claim(
            issue_tree=issue_tree,
            visible_evidence=plaintiff_evidence,
            context_outputs=[],
            run_id="run-001",
            state_id="state-001",
            round_index=1,
        )
        assert output is not None
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self, config, issue_tree, plaintiff_evidence):
        class AlwaysFailLLM:
            async def create_message(self, **kwargs) -> str:
                raise RuntimeError("持续失败")

        agent = PlaintiffAgent(AlwaysFailLLM(), PLAINTIFF_ID, config)
        with pytest.raises(RuntimeError, match="LLM 调用失败"):
            await agent.generate_claim(
                issue_tree=issue_tree,
                visible_evidence=plaintiff_evidence,
                context_outputs=[],
                run_id="run-001",
                state_id="state-001",
                round_index=1,
            )

    @pytest.mark.asyncio
    async def test_rejects_hallucinated_evidence_id(
        self, config, issue_tree, plaintiff_evidence
    ):
        """引用不在可见证据中的 ID 应触发重试，重试耗尽后抛 RuntimeError。"""
        response = _make_llm_response(evidence_citations=["ev-999"])  # ev-999 不存在
        mock_llm = MockLLMClient(response=response)
        agent = PlaintiffAgent(mock_llm, PLAINTIFF_ID, config)

        with pytest.raises(RuntimeError, match="LLM 调用失败"):
            await agent.generate_claim(
                issue_tree=issue_tree,
                visible_evidence=plaintiff_evidence,
                context_outputs=[],
                run_id="run-001",
                state_id="state-001",
                round_index=1,
            )
        assert mock_llm.call_count == config.max_retries

    @pytest.mark.asyncio
    async def test_retry_on_bad_citations_succeeds(
        self, config, issue_tree, plaintiff_evidence
    ):
        """首次返回幻觉证据 ID，第二次返回合法 ID → 成功，共调用 2 次 LLM。"""
        call_count = 0

        class SequentialMockLLM:
            async def create_message(self, **kwargs) -> str:
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return _make_llm_response(evidence_citations=["ev-999"])
                return _make_llm_response()

        agent = PlaintiffAgent(SequentialMockLLM(), PLAINTIFF_ID, config)
        output = await agent.generate_claim(
            issue_tree=issue_tree,
            visible_evidence=plaintiff_evidence,
            context_outputs=[],
            run_id="run-001",
            state_id="state-001",
            round_index=1,
        )
        assert output is not None
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_rejects_empty_issue_ids_after_aggregation(
        self, config, issue_tree, plaintiff_evidence
    ):
        """顶层 issue_ids 和 arguments 均为空时应 RuntimeError（禁止 unknown-issue fallback）。"""
        response = json.dumps({
            "title": "no issues",
            "body": "body",
            "case_id": CASE_ID,
            "issue_ids": [],
            "evidence_citations": ["ev-001"],
            "risk_flags": [],
            "arguments": [],
        }, ensure_ascii=False)
        mock_llm = MockLLMClient(response=response)
        agent = PlaintiffAgent(mock_llm, PLAINTIFF_ID, config)

        with pytest.raises(RuntimeError, match="LLM 调用失败"):
            await agent.generate_claim(
                issue_tree=issue_tree,
                visible_evidence=plaintiff_evidence,
                context_outputs=[],
                run_id="run-001",
                state_id="state-001",
                round_index=1,
            )


# ---------------------------------------------------------------------------
# DefendantAgent 测试
# ---------------------------------------------------------------------------


class TestDefendantAgent:
    @pytest.mark.asyncio
    async def test_generate_claim_returns_defendant_role(
        self, config, issue_tree, defendant_evidence
    ):
        # 使用被告可见证据 ev-003（而非默认的 ev-001）
        mock_llm = MockLLMClient(response=_make_llm_response(evidence_citations=["ev-003"]))
        agent = DefendantAgent(mock_llm, DEFENDANT_ID, config)

        output = await agent.generate_claim(
            issue_tree=issue_tree,
            visible_evidence=defendant_evidence,
            context_outputs=[],
            run_id="run-001",
            state_id="state-001",
            round_index=1,
        )

        assert output.agent_role_code == AgentRole.defendant_agent.value
        assert output.owner_party_id == DEFENDANT_ID

    @pytest.mark.asyncio
    async def test_evidence_citations_from_arguments(
        self, config, issue_tree, defendant_evidence
    ):
        """当顶层 evidence_citations 为空时，应从 arguments 中聚合。"""
        response = json.dumps({
            "title": "被告抗辩",
            "body": "已偿还全部借款。",
            "case_id": CASE_ID,
            "issue_ids": [],          # 空 — 应从 arguments 聚合
            "evidence_citations": [],  # 空 — 应从 arguments 聚合
            "risk_flags": [],
            "arguments": [
                {
                    "issue_id": "issue-002",
                    "position": "已还款3万元，有收条为证。",
                    "supporting_evidence_ids": ["ev-003"],
                }
            ],
        }, ensure_ascii=False)

        mock_llm = MockLLMClient(response=response)
        agent = DefendantAgent(mock_llm, DEFENDANT_ID, config)

        output = await agent.generate_claim(
            issue_tree=issue_tree,
            visible_evidence=defendant_evidence,
            context_outputs=[],
            run_id="run-001",
            state_id="state-001",
            round_index=1,
        )

        assert "issue-002" in output.issue_ids
        assert "ev-003" in output.evidence_citations


# ---------------------------------------------------------------------------
# EvidenceManagerAgent 测试
# ---------------------------------------------------------------------------


class TestEvidenceManagerAgent:
    def _make_ev_manager_response(self) -> str:
        return json.dumps({
            "title": "证据整理摘要",
            "body": "双方在借款金额上存在冲突。",
            "case_id": CASE_ID,
            "issue_ids": ["issue-001"],
            "evidence_citations": ["ev-001", "ev-003"],
            "risk_flags": [{"flag_id": "rf-001", "description": "证据冲突", "impact_objects": ["win_rate"]}],
            "conflicts": [
                {
                    "issue_id": "issue-001",
                    "plaintiff_evidence_ids": ["ev-001", "ev-002"],
                    "defendant_evidence_ids": ["ev-003"],
                    "conflict_description": "原告借条与被告收条金额不一致",
                }
            ],
        }, ensure_ascii=False)

    @pytest.mark.asyncio
    async def test_analyze_returns_output_and_conflicts(
        self, config, issue_tree, plaintiff_evidence, defendant_evidence
    ):
        evidence_index = EvidenceIndex(
            case_id=CASE_ID,
            evidence=plaintiff_evidence + defendant_evidence,
        )
        mock_llm = MockLLMClient(response=self._make_ev_manager_response())
        agent = EvidenceManagerAgent(mock_llm, config)

        output, conflicts = await agent.analyze(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_outputs=[],
            defendant_outputs=[],
            run_id="run-001",
            state_id="state-002",
            round_index=2,
        )

        assert output.agent_role_code == AgentRole.evidence_manager.value
        assert output.round_index == 2
        assert len(conflicts) == 1
        assert conflicts[0].issue_id == "issue-001"
        assert "ev-001" in conflicts[0].plaintiff_evidence_ids

    @pytest.mark.asyncio
    async def test_empty_conflicts_when_no_conflict_in_response(
        self, config, issue_tree, plaintiff_evidence, defendant_evidence
    ):
        response = json.dumps({
            "title": "无冲突",
            "body": "无冲突",
            "issue_ids": ["issue-001"],
            "evidence_citations": ["ev-001"],
            "risk_flags": [],
            "conflicts": [],
        }, ensure_ascii=False)

        evidence_index = EvidenceIndex(
            case_id=CASE_ID,
            evidence=plaintiff_evidence + defendant_evidence,
        )
        mock_llm = MockLLMClient(response=response)
        agent = EvidenceManagerAgent(mock_llm, config)

        _, conflicts = await agent.analyze(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_outputs=[],
            defendant_outputs=[],
            run_id="run-001",
            state_id="state-002",
            round_index=2,
        )
        assert conflicts == []

    @pytest.mark.asyncio
    async def test_evidence_manager_rejects_empty_citations(
        self, config, issue_tree, plaintiff_evidence, defendant_evidence
    ):
        """EvidenceManager 返回空 evidence_citations 应触发重试后抛 RuntimeError。"""
        response = json.dumps({
            "title": "无引用",
            "body": "body",
            "issue_ids": ["issue-001"],
            "evidence_citations": [],
            "risk_flags": [],
            "conflicts": [],
        }, ensure_ascii=False)
        evidence_index = EvidenceIndex(
            case_id=CASE_ID,
            evidence=plaintiff_evidence + defendant_evidence,
        )
        mock_llm = MockLLMClient(response=response)
        agent = EvidenceManagerAgent(mock_llm, config)

        with pytest.raises(RuntimeError):
            await agent.analyze(
                issue_tree=issue_tree,
                evidence_index=evidence_index,
                plaintiff_outputs=[],
                defendant_outputs=[],
                run_id="run-001",
                state_id="state-002",
                round_index=2,
            )
