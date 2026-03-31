"""
AdversarialSummarizer 单元测试。
AdversarialSummarizer unit tests.
"""

from __future__ import annotations

import json
import pytest

from engines.shared.models import (
    AccessDomain,
    Evidence,
    EvidenceIndex,
    EvidenceType,
    Issue,
    IssueTree,
    IssueType,
)
from engines.adversarial.schemas import (
    AdversarialResult,
    AdversarialSummary,
    Argument,
    ConflictEntry,
    MissingEvidenceReport,
    RoundConfig,
    RoundPhase,
    RoundState,
    StrongestArgument,
    UnresolvedIssueDetail,
    MissingEvidenceSummary,
)
from engines.adversarial.summarizer import AdversarialSummarizer
from engines.shared.models import AgentOutput, ProcedurePhase, StatementClass
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# 常量 / Constants
# ---------------------------------------------------------------------------

CASE_ID = "case-loan-001"
PLAINTIFF_ID = "party-p-001"
DEFENDANT_ID = "party-d-001"
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

VALID_SUMMARY_JSON = json.dumps(
    {
        "plaintiff_strongest_arguments": [
            {
                "issue_id": "issue-001",
                "position": "原告有转账记录，证明借款已实际交付",
                "evidence_ids": ["ev-001"],
                "reasoning": "直接证明借贷要件，被告无有效反证",
            }
        ],
        "defendant_strongest_defenses": [
            {
                "issue_id": "issue-001",
                "position": "被告否认收款，质疑转账用途为还款",
                "evidence_ids": ["ev-001"],
                "reasoning": "动摇借贷关系成立基础",
            }
        ],
        "unresolved_issues": [
            {
                "issue_id": "issue-001",
                "issue_title": "借贷关系是否成立",
                "why_unresolved": "双方证据存在正面冲突，转账备注不明确，未有定论",
            }
        ],
        "missing_evidence_report": [
            {
                "issue_id": "issue-001",
                "missing_for_party_id": DEFENDANT_ID,
                "gap_description": "被告缺乏收款否认的书面证据或证人证词",
            }
        ],
        "overall_assessment": "原告证据链较完整，被告抗辩薄弱，但核心争点尚未闭合，建议补充被告方反驳证据。",
    },
    ensure_ascii=False,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_agent_output(
    role: str,
    party_id: str,
    round_idx: int,
    phase: ProcedurePhase = ProcedurePhase.opening,
) -> AgentOutput:
    return AgentOutput(
        output_id=f"output-{role}-r{round_idx}",
        case_id=CASE_ID,
        run_id="run-001",
        state_id=f"state-r{round_idx}",
        phase=phase,
        round_index=round_idx,
        agent_role_code=role,
        owner_party_id=party_id,
        issue_ids=["issue-001"],
        title=f"{role} round {round_idx} title",
        body=f"{role} round {round_idx} body 引用证据 ev-001",
        evidence_citations=["ev-001"],
        statement_class=StatementClass.fact,
        created_at=NOW,
    )


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
                evidence_ids=["ev-001"],
            ),
        ],
    )


@pytest.fixture
def minimal_result() -> AdversarialResult:
    """最小化 AdversarialResult，包含所有三轮输出。"""
    p_claim = _make_agent_output("plaintiff_agent", PLAINTIFF_ID, 1)
    d_claim = _make_agent_output("defendant_agent", DEFENDANT_ID, 1)
    ev_output = _make_agent_output("evidence_manager", "system", 2)
    p_rebuttal = _make_agent_output("plaintiff_agent", PLAINTIFF_ID, 3, ProcedurePhase.rebuttal)
    d_rebuttal = _make_agent_output("defendant_agent", DEFENDANT_ID, 3, ProcedurePhase.rebuttal)

    return AdversarialResult(
        case_id=CASE_ID,
        run_id="run-001",
        rounds=[
            RoundState(round_number=1, phase=RoundPhase.claim, outputs=[p_claim, d_claim]),
            RoundState(round_number=2, phase=RoundPhase.evidence, outputs=[ev_output]),
            RoundState(round_number=3, phase=RoundPhase.rebuttal, outputs=[p_rebuttal, d_rebuttal]),
        ],
        unresolved_issues=["issue-001"],
        evidence_conflicts=[
            ConflictEntry(
                issue_id="issue-001",
                plaintiff_evidence_ids=["ev-001"],
                defendant_evidence_ids=[],
                conflict_description="原告有转账记录但被告否认收款",
            )
        ],
        missing_evidence_report=[
            MissingEvidenceReport(
                issue_id="issue-001",
                missing_for_party_id=DEFENDANT_ID,
                description="被告方缺乏直接证据",
            )
        ],
    )


@pytest.fixture
def config() -> RoundConfig:
    return RoundConfig(max_tokens_per_output=3000, max_retries=2)


class MockLLM:
    """单次成功的 mock LLM。"""

    def __init__(self, response: str = VALID_SUMMARY_JSON):
        self.calls: list[str] = []
        self._response = response

    async def create_message(self, *, system: str, user: str, **kwargs) -> str:
        self.calls.append(user[:80])
        return self._response


class FailingMockLLM:
    """始终抛出异常的 mock LLM。"""

    async def create_message(self, **kwargs) -> str:
        raise RuntimeError("LLM 不可用")


# ---------------------------------------------------------------------------
# 测试 / Tests
# ---------------------------------------------------------------------------


class TestAdversarialSummarizer:
    @pytest.mark.asyncio
    async def test_summarize_returns_adversarial_summary(self, minimal_result, issue_tree, config):
        """返回类型为 AdversarialSummary。"""
        summarizer = AdversarialSummarizer(MockLLM(), config)
        result = await summarizer.summarize(minimal_result, issue_tree)
        assert isinstance(result, AdversarialSummary)

    @pytest.mark.asyncio
    async def test_plaintiff_strongest_arguments_populated(
        self, minimal_result, issue_tree, config
    ):
        """plaintiff_strongest_arguments 非空。"""
        summarizer = AdversarialSummarizer(MockLLM(), config)
        summary = await summarizer.summarize(minimal_result, issue_tree)
        assert len(summary.plaintiff_strongest_arguments) >= 1
        for arg in summary.plaintiff_strongest_arguments:
            assert isinstance(arg, StrongestArgument)

    @pytest.mark.asyncio
    async def test_defendant_strongest_defenses_populated(self, minimal_result, issue_tree, config):
        """defendant_strongest_defenses 非空。"""
        summarizer = AdversarialSummarizer(MockLLM(), config)
        summary = await summarizer.summarize(minimal_result, issue_tree)
        assert len(summary.defendant_strongest_defenses) >= 1
        for defense in summary.defendant_strongest_defenses:
            assert isinstance(defense, StrongestArgument)

    @pytest.mark.asyncio
    async def test_unresolved_issues_have_why_unresolved(self, minimal_result, issue_tree, config):
        """每条 UnresolvedIssueDetail 含非空 why_unresolved。"""
        summarizer = AdversarialSummarizer(MockLLM(), config)
        summary = await summarizer.summarize(minimal_result, issue_tree)
        assert len(summary.unresolved_issues) >= 1
        for item in summary.unresolved_issues:
            assert isinstance(item, UnresolvedIssueDetail)
            assert len(item.why_unresolved) >= 1

    @pytest.mark.asyncio
    async def test_missing_evidence_populated(self, minimal_result, issue_tree, config):
        """missing_evidence_report 非空。"""
        summarizer = AdversarialSummarizer(MockLLM(), config)
        summary = await summarizer.summarize(minimal_result, issue_tree)
        assert len(summary.missing_evidence_report) >= 1
        for item in summary.missing_evidence_report:
            assert isinstance(item, MissingEvidenceSummary)

    @pytest.mark.asyncio
    async def test_overall_assessment_non_empty(self, minimal_result, issue_tree, config):
        """AdversarialSummarizer 路径始终提供非空 overall_assessment（fallback 保证）。
        AdversarialSummarizer always produces a non-None overall_assessment via its fallback.
        """
        summarizer = AdversarialSummarizer(MockLLM(), config)
        summary = await summarizer.summarize(minimal_result, issue_tree)
        assert summary.overall_assessment is not None
        assert len(summary.overall_assessment) >= 1

    @pytest.mark.asyncio
    async def test_evidence_ids_non_empty_in_arguments(self, minimal_result, issue_tree, config):
        """所有 StrongestArgument.evidence_ids 非空。"""
        summarizer = AdversarialSummarizer(MockLLM(), config)
        summary = await summarizer.summarize(minimal_result, issue_tree)
        for arg in summary.plaintiff_strongest_arguments:
            assert len(arg.evidence_ids) >= 1
        for defense in summary.defendant_strongest_defenses:
            assert len(defense.evidence_ids) >= 1

    @pytest.mark.asyncio
    async def test_llm_called_once(self, minimal_result, issue_tree, config):
        """Summarizer 只调用一次 LLM。"""
        mock = MockLLM()
        summarizer = AdversarialSummarizer(mock, config)
        await summarizer.summarize(minimal_result, issue_tree)
        assert len(mock.calls) == 1

    @pytest.mark.asyncio
    async def test_runtime_error_on_repeated_llm_failure(self, minimal_result, issue_tree):
        """超重试次数后抛出 RuntimeError。"""
        config = RoundConfig(max_retries=2)
        summarizer = AdversarialSummarizer(FailingMockLLM(), config)
        with pytest.raises(RuntimeError, match="LLM 调用失败"):
            await summarizer.summarize(minimal_result, issue_tree)


# ---------------------------------------------------------------------------
# AdversarialSummary schema 单元测试
# ---------------------------------------------------------------------------


class TestAdversarialSummarySchema:
    def test_overall_assessment_can_be_none(self):
        """overall_assessment 在 v1.2 改为 Optional，可以为 None（DecisionPathTree 存在时）。"""
        summary = AdversarialSummary(
            plaintiff_strongest_arguments=[],
            defendant_strongest_defenses=[],
            unresolved_issues=[],
            missing_evidence_report=[],
            overall_assessment=None,
        )
        assert summary.overall_assessment is None

    def test_overall_assessment_string_still_accepted(self):
        """overall_assessment 传入字符串仍然有效（向后兼容）。"""
        summary = AdversarialSummary(
            plaintiff_strongest_arguments=[],
            defendant_strongest_defenses=[],
            unresolved_issues=[],
            missing_evidence_report=[],
            overall_assessment="态势评估文本",
        )
        assert summary.overall_assessment == "态势评估文本"

    def test_strongest_argument_requires_evidence_ids(self):
        """evidence_ids 为必填非空列表。"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            StrongestArgument(
                issue_id="issue-001",
                position="test",
                evidence_ids=[],  # 空 — 应报错
                reasoning="test",
            )

    def test_valid_adversarial_summary(self):
        """合法的 AdversarialSummary 可以正常创建。"""
        summary = AdversarialSummary(
            plaintiff_strongest_arguments=[
                StrongestArgument(
                    issue_id="issue-001",
                    position="原告论点",
                    evidence_ids=["ev-001"],
                    reasoning="最强",
                )
            ],
            defendant_strongest_defenses=[],
            unresolved_issues=[
                UnresolvedIssueDetail(
                    issue_id="issue-001",
                    issue_title="借贷关系",
                    why_unresolved="冲突未解决",
                )
            ],
            missing_evidence_report=[],
            overall_assessment="整体评估",
        )
        assert len(summary.plaintiff_strongest_arguments) == 1
        assert len(summary.unresolved_issues) == 1
        assert summary.overall_assessment == "整体评估"
