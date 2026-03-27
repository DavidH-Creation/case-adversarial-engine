"""
IssueImpactRanker 单元测试。
Unit tests for IssueImpactRanker.

测试策略：
- 不依赖真实 LLM；使用 MockLLMClient 返回预定义 JSON
- 分层测试：排序规则 → 校验规则 → 完整 rank() 流程
- 覆盖所有合约保证（见 spec P0.1 约束表）
"""
from __future__ import annotations

import json
from decimal import Decimal

import pytest

from engines.shared.models import (
    AccessDomain,
    AmountCalculationReport,
    AmountConsistencyCheck,
    AttackStrength,
    ClaimCalculationEntry,
    ClaimType,
    Evidence,
    EvidenceIndex,
    EvidenceStatus,
    EvidenceStrength,
    EvidenceType,
    ImpactTarget,
    Issue,
    IssueStatus,
    IssueTree,
    IssueType,
    LoanTransaction,
    OutcomeImpact,
    RecommendedAction,
)
from engines.simulation_run.issue_impact_ranker.ranker import IssueImpactRanker
from engines.simulation_run.issue_impact_ranker.schemas import (
    IssueImpactRankerInput,
    IssueImpactRankingResult,
)


# ---------------------------------------------------------------------------
# Mock LLM 客户端
# ---------------------------------------------------------------------------


class MockLLMClient:
    """返回预定义 JSON 响应的 mock LLM 客户端。
    Mock LLM client that returns predefined JSON responses.
    """

    def __init__(self, response: str, fail_times: int = 0) -> None:
        self._response = response
        self._fail_times = fail_times
        self.call_count = 0
        self.last_system: str | None = None
        self.last_user: str | None = None

    async def create_message(self, *, system: str, user: str, **kwargs) -> str:
        self.call_count += 1
        self.last_system = system
        self.last_user = user
        if self._fail_times > 0:
            self._fail_times -= 1
            raise RuntimeError("模拟 LLM 调用失败")
        return self._response


# ---------------------------------------------------------------------------
# 测试辅助工厂
# ---------------------------------------------------------------------------


def _make_issue(
    issue_id: str,
    title: str = "测试争点",
    evidence_ids: list[str] | None = None,
    **kwargs,
) -> Issue:
    return Issue(
        issue_id=issue_id,
        case_id="case-001",
        title=title,
        issue_type=IssueType.factual,
        evidence_ids=evidence_ids or [],
        **kwargs,
    )


def _make_evidence(evidence_id: str) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        case_id="case-001",
        owner_party_id="party-plaintiff",
        title=f"证据 {evidence_id}",
        source="测试来源",
        summary="测试摘要",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=["fact-001"],
        status=EvidenceStatus.submitted,
        access_domain=AccessDomain.shared_common,
    )


def _make_amount_check(verdict_block: bool = False) -> AmountConsistencyCheck:
    return AmountConsistencyCheck(
        principal_base_unique=not verdict_block,
        all_repayments_attributed=True,
        text_table_amount_consistent=True,
        duplicate_interest_penalty_claim=False,
        claim_total_reconstructable=True,
        unresolved_conflicts=[],
        verdict_block_active=verdict_block,
    )


def _make_amount_report(verdict_block: bool = False) -> AmountCalculationReport:
    return AmountCalculationReport(
        report_id="report-001",
        case_id="case-001",
        run_id="run-001",
        loan_transactions=[
            LoanTransaction(
                tx_id="loan-001",
                date="2024-01-01",
                amount=Decimal("100000"),
                evidence_id="ev-loan-001",
                principal_base_contribution=True,
            )
        ],
        repayment_transactions=[],
        disputed_amount_attributions=[],
        claim_calculation_table=[
            ClaimCalculationEntry(
                claim_id="claim-001",
                claim_type=ClaimType.principal,
                claimed_amount=Decimal("100000"),
                calculated_amount=Decimal("100000"),
                delta=Decimal("0"),
                delta_explanation="一致",
            )
        ],
        consistency_check_result=_make_amount_check(verdict_block),
    )


def _make_ranker_input(
    issues: list[Issue],
    evidence: list[Evidence] | None = None,
    verdict_block: bool = False,
) -> IssueImpactRankerInput:
    return IssueImpactRankerInput(
        case_id="case-001",
        run_id="run-test-001",
        issue_tree=IssueTree(case_id="case-001", issues=issues),
        evidence_index=EvidenceIndex(
            case_id="case-001",
            evidence=evidence or [_make_evidence("ev-001"), _make_evidence("ev-002")],
        ),
        amount_calculation_report=_make_amount_report(verdict_block),
        proponent_party_id="party-plaintiff",
    )


def _eval_entry(
    issue_id: str,
    outcome_impact: str = "medium",
    proponent_evidence_ids: list[str] | None = None,
    opponent_attack_evidence_ids: list[str] | None = None,
    **kwargs,
) -> dict:
    """构造一条合法 LLM 评估条目。
    None 表示使用默认值（["ev-001"]），显式传 [] 表示空列表（触发校验失败）。
    """
    return {
        "issue_id": issue_id,
        "outcome_impact": outcome_impact,
        "impact_targets": kwargs.get("impact_targets", ["principal"]),
        "proponent_evidence_strength": kwargs.get("proponent_evidence_strength", "medium"),
        "proponent_evidence_ids": ["ev-001"] if proponent_evidence_ids is None else proponent_evidence_ids,
        "opponent_attack_strength": kwargs.get("opponent_attack_strength", "medium"),
        "opponent_attack_evidence_ids": ["ev-002"] if opponent_attack_evidence_ids is None else opponent_attack_evidence_ids,
        "recommended_action": kwargs.get("recommended_action", "supplement_evidence"),
        "recommended_action_basis": kwargs.get(
            "recommended_action_basis", "基于证据 ev-001 评估"
        ),
        "recommended_action_evidence_ids": ["ev-001"],
    }


def _stub_response(evaluations: list[dict]) -> str:
    return json.dumps({"evaluations": evaluations})


# ---------------------------------------------------------------------------
# 测试：排序规则（直接调用 _sort_issues）
# ---------------------------------------------------------------------------


class TestSortIssues:
    """排序规则测试——不调用 LLM，直接测试 _sort_issues。"""

    def _ranker(self) -> IssueImpactRanker:
        return IssueImpactRanker(MockLLMClient("{}"))

    def test_high_before_medium_before_low(self):
        issues = [
            _make_issue("i-low", outcome_impact=OutcomeImpact.low),
            _make_issue("i-high", outcome_impact=OutcomeImpact.high),
            _make_issue("i-medium", outcome_impact=OutcomeImpact.medium),
        ]
        sorted_issues = self._ranker()._sort_issues(issues)
        assert [i.issue_id for i in sorted_issues] == ["i-high", "i-medium", "i-low"]

    def test_none_impact_goes_to_tail(self):
        issues = [
            _make_issue("i-none"),
            _make_issue("i-low", outcome_impact=OutcomeImpact.low),
        ]
        sorted_issues = self._ranker()._sort_issues(issues)
        assert sorted_issues[0].issue_id == "i-low"
        assert sorted_issues[1].issue_id == "i-none"

    def test_secondary_sort_by_attack_strength(self):
        issues = [
            _make_issue(
                "i-high-weak",
                outcome_impact=OutcomeImpact.high,
                opponent_attack_strength=AttackStrength.weak,
            ),
            _make_issue(
                "i-high-strong",
                outcome_impact=OutcomeImpact.high,
                opponent_attack_strength=AttackStrength.strong,
            ),
            _make_issue(
                "i-high-medium",
                outcome_impact=OutcomeImpact.high,
                opponent_attack_strength=AttackStrength.medium,
            ),
        ]
        sorted_issues = self._ranker()._sort_issues(issues)
        assert [i.issue_id for i in sorted_issues] == [
            "i-high-strong",
            "i-high-medium",
            "i-high-weak",
        ]

    def test_none_attack_goes_behind_weak(self):
        issues = [
            _make_issue("i-no-attack", outcome_impact=OutcomeImpact.high),
            _make_issue(
                "i-weak-attack",
                outcome_impact=OutcomeImpact.high,
                opponent_attack_strength=AttackStrength.weak,
            ),
        ]
        sorted_issues = self._ranker()._sort_issues(issues)
        assert sorted_issues[0].issue_id == "i-weak-attack"
        assert sorted_issues[1].issue_id == "i-no-attack"

    def test_stable_original_order_preserved(self):
        """同权重争点维持原始顺序（Python sorted 稳定保证）。"""
        issues = [
            _make_issue(
                "i-a",
                outcome_impact=OutcomeImpact.medium,
                opponent_attack_strength=AttackStrength.weak,
            ),
            _make_issue(
                "i-b",
                outcome_impact=OutcomeImpact.medium,
                opponent_attack_strength=AttackStrength.weak,
            ),
            _make_issue(
                "i-c",
                outcome_impact=OutcomeImpact.medium,
                opponent_attack_strength=AttackStrength.weak,
            ),
        ]
        sorted_issues = self._ranker()._sort_issues(issues)
        assert [i.issue_id for i in sorted_issues] == ["i-a", "i-b", "i-c"]

    def test_empty_list_returns_empty(self):
        assert self._ranker()._sort_issues([]) == []


# ---------------------------------------------------------------------------
# 测试：校验规则（通过 rank() + MockLLMClient）
# ---------------------------------------------------------------------------


class TestValidationRules:
    """规则层校验——通过 rank() + MockLLMClient 触发各种失败场景。"""

    @pytest.mark.asyncio
    async def test_invalid_outcome_impact_clears_field(self):
        """非法 outcome_impact 枚举值 → 该字段清空，争点进 unevaluated。"""
        issues = [_make_issue("i-001", evidence_ids=["ev-001"])]
        ev = _eval_entry("i-001", outcome_impact="INVALID_VALUE")
        client = MockLLMClient(_stub_response([ev]))
        ranker = IssueImpactRanker(client)
        result = await ranker.rank(_make_ranker_input(issues))

        ranked_issue = result.ranked_issue_tree.issues[0]
        assert ranked_issue.outcome_impact is None
        assert "i-001" in result.unevaluated_issue_ids

    @pytest.mark.asyncio
    async def test_proponent_strength_without_evidence_ids_clears_field(self):
        """proponent_evidence_ids 为空时，proponent_evidence_strength 被清空。"""
        issues = [_make_issue("i-001", evidence_ids=["ev-001"])]
        ev = _eval_entry("i-001", proponent_evidence_ids=[])
        client = MockLLMClient(_stub_response([ev]))
        ranker = IssueImpactRanker(client)
        result = await ranker.rank(_make_ranker_input(issues))

        ranked_issue = result.ranked_issue_tree.issues[0]
        assert ranked_issue.proponent_evidence_strength is None
        assert "i-001" in result.unevaluated_issue_ids

    @pytest.mark.asyncio
    async def test_opponent_strength_with_unknown_evidence_ids_clears_field(self):
        """opponent_attack_evidence_ids 含未知证据 ID → opponent_attack_strength 被清空。"""
        issues = [_make_issue("i-001", evidence_ids=["ev-001"])]
        ev = _eval_entry("i-001", opponent_attack_evidence_ids=["ev-unknown-999"])
        client = MockLLMClient(_stub_response([ev]))
        ranker = IssueImpactRanker(client)
        # evidence_index 只有 ev-001, ev-002，不含 ev-unknown-999
        result = await ranker.rank(_make_ranker_input(issues))

        ranked_issue = result.ranked_issue_tree.issues[0]
        assert ranked_issue.opponent_attack_strength is None
        assert "i-001" in result.unevaluated_issue_ids

    @pytest.mark.asyncio
    async def test_recommended_action_without_basis_clears_field(self):
        """recommended_action_basis 为空 → recommended_action 被清空。"""
        issues = [_make_issue("i-001", evidence_ids=["ev-001"])]
        ev = _eval_entry("i-001", recommended_action_basis="")
        client = MockLLMClient(_stub_response([ev]))
        ranker = IssueImpactRanker(client)
        result = await ranker.rank(_make_ranker_input(issues))

        ranked_issue = result.ranked_issue_tree.issues[0]
        assert ranked_issue.recommended_action is None
        assert ranked_issue.recommended_action_basis is None
        assert "i-001" in result.unevaluated_issue_ids

    @pytest.mark.asyncio
    async def test_unknown_issue_id_in_llm_output_is_ignored(self):
        """LLM 返回未知 issue_id → 对应评估条目被忽略，不影响结果。"""
        issues = [_make_issue("i-001", evidence_ids=["ev-001"])]
        ev_valid = _eval_entry("i-001")
        ev_unknown = _eval_entry("i-UNKNOWN-999")
        client = MockLLMClient(_stub_response([ev_valid, ev_unknown]))
        ranker = IssueImpactRanker(client)
        result = await ranker.rank(_make_ranker_input(issues))

        assert len(result.ranked_issue_tree.issues) == 1
        assert result.ranked_issue_tree.issues[0].issue_id == "i-001"


# ---------------------------------------------------------------------------
# 测试：完整 rank() 流程
# ---------------------------------------------------------------------------


class TestRankFullFlow:
    """完整 rank() 流程集成测试。"""

    @pytest.mark.asyncio
    async def test_valid_evaluation_enriches_issue(self):
        """合法评估结果正确富化到 Issue 对象。"""
        issues = [_make_issue("i-001", evidence_ids=["ev-001"])]
        ev = _eval_entry(
            "i-001",
            outcome_impact="high",
            impact_targets=["principal", "interest"],
            proponent_evidence_strength="weak",
            proponent_evidence_ids=["ev-001"],
            opponent_attack_strength="strong",
            opponent_attack_evidence_ids=["ev-002"],
            recommended_action="supplement_evidence",
            recommended_action_basis="借款凭证不足，建议补充书面协议",
        )
        client = MockLLMClient(_stub_response([ev]))
        ranker = IssueImpactRanker(client)
        result = await ranker.rank(_make_ranker_input(issues))

        assert result.unevaluated_issue_ids == []
        issue = result.ranked_issue_tree.issues[0]
        assert issue.outcome_impact == OutcomeImpact.high
        assert set(issue.impact_targets) == {ImpactTarget.principal, ImpactTarget.interest}
        assert issue.proponent_evidence_strength == EvidenceStrength.weak
        assert issue.opponent_attack_strength == AttackStrength.strong
        assert issue.recommended_action == RecommendedAction.supplement_evidence
        assert issue.recommended_action_basis == "借款凭证不足，建议补充书面协议"

    @pytest.mark.asyncio
    async def test_issues_sorted_by_outcome_impact(self):
        """输出争点按 outcome_impact 降序排列。"""
        issues = [
            _make_issue("i-low", evidence_ids=["ev-001"]),
            _make_issue("i-high", evidence_ids=["ev-001"]),
            _make_issue("i-medium", evidence_ids=["ev-001"]),
        ]
        evaluations = [
            _eval_entry("i-low", outcome_impact="low"),
            _eval_entry("i-high", outcome_impact="high"),
            _eval_entry("i-medium", outcome_impact="medium"),
        ]
        client = MockLLMClient(_stub_response(evaluations))
        ranker = IssueImpactRanker(client)
        result = await ranker.rank(_make_ranker_input(issues))

        ids = [i.issue_id for i in result.ranked_issue_tree.issues]
        assert ids == ["i-high", "i-medium", "i-low"]

    @pytest.mark.asyncio
    async def test_empty_issue_tree_returns_immediately(self):
        """空争点树不调用 LLM，直接返回空结果。"""
        client = MockLLMClient("{}")
        ranker = IssueImpactRanker(client)
        result = await ranker.rank(_make_ranker_input(issues=[]))

        assert client.call_count == 0
        assert result.ranked_issue_tree.issues == []
        assert result.unevaluated_issue_ids == []

    @pytest.mark.asyncio
    async def test_llm_failure_returns_original_tree_all_unevaluated(self):
        """LLM 整体失败：返回原始 issue_tree，所有争点进 unevaluated_issue_ids。"""
        issues = [_make_issue("i-001"), _make_issue("i-002")]
        client = MockLLMClient("{}", fail_times=999)
        ranker = IssueImpactRanker(client, max_retries=1)
        result = await ranker.rank(_make_ranker_input(issues))

        assert result.evaluation_metadata.get("failed") is True
        assert set(result.unevaluated_issue_ids) == {"i-001", "i-002"}
        # 原始顺序保留
        assert [i.issue_id for i in result.ranked_issue_tree.issues] == ["i-001", "i-002"]
        # 所有评估字段为 None
        for issue in result.ranked_issue_tree.issues:
            assert issue.outcome_impact is None

    @pytest.mark.asyncio
    async def test_amount_check_injected_in_prompt(self):
        """AmountConsistencyCheck 内容被注入到 user prompt。"""
        issues = [_make_issue("i-001", evidence_ids=["ev-001"])]
        ev = _eval_entry("i-001")
        client = MockLLMClient(_stub_response([ev]))
        ranker = IssueImpactRanker(client)
        # verdict_block=True 时 prompt 应包含相关信息
        await ranker.rank(_make_ranker_input(issues, verdict_block=True))

        assert client.last_user is not None
        assert "verdict_block_active: True" in client.last_user

    @pytest.mark.asyncio
    async def test_llm_called_once(self):
        """rank() 只调用一次 LLM（批量模式）。"""
        issues = [_make_issue(f"i-{i:03d}", evidence_ids=["ev-001"]) for i in range(5)]
        evaluations = [_eval_entry(f"i-{i:03d}") for i in range(5)]
        client = MockLLMClient(_stub_response(evaluations))
        ranker = IssueImpactRanker(client)
        await ranker.rank(_make_ranker_input(issues))

        assert client.call_count == 1

    @pytest.mark.asyncio
    async def test_llm_retry_on_transient_failure(self):
        """LLM 前 N 次失败后成功，触发重试机制。"""
        issues = [_make_issue("i-001", evidence_ids=["ev-001"])]
        ev = _eval_entry("i-001")
        client = MockLLMClient(_stub_response([ev]), fail_times=2)
        ranker = IssueImpactRanker(client, max_retries=3)
        result = await ranker.rank(_make_ranker_input(issues))

        assert client.call_count == 3  # 2 次失败 + 1 次成功
        assert result.unevaluated_issue_ids == []

    @pytest.mark.asyncio
    async def test_result_created_at_is_set(self):
        """返回结果包含 ISO-8601 时间戳。"""
        issues = [_make_issue("i-001", evidence_ids=["ev-001"])]
        ev = _eval_entry("i-001")
        client = MockLLMClient(_stub_response([ev]))
        ranker = IssueImpactRanker(client)
        result = await ranker.rank(_make_ranker_input(issues))

        assert result.created_at
        assert "T" in result.created_at  # ISO-8601 格式
