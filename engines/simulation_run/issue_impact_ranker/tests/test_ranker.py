"""
IssueImpactRanker 单元测试。
Unit tests for IssueImpactRanker.

测试策略：
- 不依赖真实 LLM；使用 MockLLMClient 返回预定义 JSON
- 分层测试：排序规则 → 校验规则 → 完整 rank() 流程
- 覆盖所有合约保证（见 spec P0.1 约束表）
"""

from __future__ import annotations

import copy
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
    FactProposition,
    Issue,
    IssueStatus,
    IssueTree,
    IssueType,
    LoanTransaction,
    OutcomeImpact,
    PropositionStatus,
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
        "proponent_evidence_ids": ["ev-001"]
        if proponent_evidence_ids is None
        else proponent_evidence_ids,
        "opponent_attack_strength": kwargs.get("opponent_attack_strength", "medium"),
        "opponent_attack_evidence_ids": ["ev-002"]
        if opponent_attack_evidence_ids is None
        else opponent_attack_evidence_ids,
        "recommended_action": kwargs.get("recommended_action", "supplement_evidence"),
        "recommended_action_basis": kwargs.get("recommended_action_basis", "基于证据 ev-001 评估"),
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

    def test_swing_score_tiebreaker_when_composite_equal(self):
        """When composite_score and outcome_impact are equal, swing_score DESC breaks the tie."""
        issues = [
            _make_issue("i-low-swing", composite_score=50.0, swing_score=20),
            _make_issue("i-high-swing", composite_score=50.0, swing_score=80),
            _make_issue("i-mid-swing", composite_score=50.0, swing_score=50),
        ]
        sorted_issues = self._ranker()._sort_issues(issues)
        assert [i.issue_id for i in sorted_issues] == ["i-high-swing", "i-mid-swing", "i-low-swing"]

    def test_evidence_strength_gap_tiebreaker(self):
        """When composite_score and swing_score are equal, abs(evidence_strength_gap) DESC breaks the tie."""
        issues = [
            _make_issue(
                "i-small-gap", composite_score=50.0, swing_score=50, evidence_strength_gap=10
            ),
            _make_issue(
                "i-large-gap-neg", composite_score=50.0, swing_score=50, evidence_strength_gap=-80
            ),
            _make_issue(
                "i-mid-gap", composite_score=50.0, swing_score=50, evidence_strength_gap=40
            ),
        ]
        sorted_issues = self._ranker()._sort_issues(issues)
        # |−80| = 80 > |40| = 40 > |10| = 10
        assert [i.issue_id for i in sorted_issues] == [
            "i-large-gap-neg",
            "i-mid-gap",
            "i-small-gap",
        ]

    def test_id_order_not_used_as_tiebreaker(self):
        """Issues with equal composite_score are NOT sorted by issue_id / insertion order when
        swing_score differs — prevents the regression where 001,002,003,... bubbled to the top."""
        issues = [
            _make_issue("issue-001", composite_score=60.0, swing_score=10),  # undisputed-ish
            _make_issue("issue-002", composite_score=60.0, swing_score=90),  # highly contested
            _make_issue("issue-003", composite_score=60.0, swing_score=50),
        ]
        sorted_issues = self._ranker()._sort_issues(issues)
        # issue-002 (swing=90) must beat issue-001 (swing=10) despite lower ID
        assert sorted_issues[0].issue_id == "issue-002"
        assert sorted_issues[-1].issue_id == "issue-001"


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
        assert set(issue.impact_targets) == {"principal", "interest"}
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
    async def test_fact_dispute_ratio_injected_in_prompt(self):
        """fact_dispute_ratio 字段被注入 user prompt，为 swing_score 提供争议信号。"""
        # Issue with 2 disputed + 1 supported propositions
        issue = _make_issue(
            "i-001",
            evidence_ids=["ev-001"],
            fact_propositions=[
                FactProposition(
                    proposition_id="fp-001",
                    text="命题A",
                    status=PropositionStatus.disputed,
                    linked_evidence_ids=[],
                ),
                FactProposition(
                    proposition_id="fp-002",
                    text="命题B",
                    status=PropositionStatus.disputed,
                    linked_evidence_ids=[],
                ),
                FactProposition(
                    proposition_id="fp-003",
                    text="命题C",
                    status=PropositionStatus.supported,
                    linked_evidence_ids=["ev-001"],
                ),
            ],
        )
        ev = _eval_entry("i-001")
        client = MockLLMClient(_stub_response([ev]))
        ranker = IssueImpactRanker(client)
        await ranker.rank(_make_ranker_input([issue]))

        assert client.last_user is not None
        # Prompt must contain fact_dispute_ratio with correct counts
        assert "fact_dispute_ratio" in client.last_user
        assert "2/3" in client.last_user  # 2 disputed out of 3

    @pytest.mark.asyncio
    async def test_undisputed_issue_fact_dispute_ratio_shows_zero(self):
        """Issue where all propositions are 'supported' → 0 disputed shown in prompt."""
        issue = _make_issue(
            "i-undisputed",
            evidence_ids=["ev-001"],
            fact_propositions=[
                FactProposition(
                    proposition_id="fp-001",
                    text="银行转账10万元",
                    status=PropositionStatus.supported,
                    linked_evidence_ids=["ev-001"],
                ),
                FactProposition(
                    proposition_id="fp-002",
                    text="收款已确认",
                    status=PropositionStatus.supported,
                    linked_evidence_ids=["ev-001"],
                ),
            ],
        )
        ev = _eval_entry("i-undisputed")
        client = MockLLMClient(_stub_response([ev]))
        ranker = IssueImpactRanker(client)
        await ranker.rank(_make_ranker_input([issue]))

        assert client.last_user is not None
        assert "fact_dispute_ratio" in client.last_user
        assert "0/2" in client.last_user  # 0 disputed out of 2

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


# ---------------------------------------------------------------------------
# 测试：Opus 风格 LLM 输出归一化
# ---------------------------------------------------------------------------


class TestOpusStyleNormalization:
    """测试 Opus 风格 LLM 输出归一化（dimensions 嵌套 + D0X_ 前缀）。"""

    OPUS_FIXTURE = {
        "case_id": "case-001",
        "analysis_timestamp": "2026-03-29T14:00:00Z",
        "issue_assessments": [
            {
                "issue_id": "issue-001",
                "dimensions": {
                    "D01_verdict_impact_weight": {"score": 90, "rationale": "核心争点"},
                    "D02_factual_determination_difficulty": {"score": 75, "rationale": "证据对立"},
                    "D03_evidence_chain_completeness": {"score": 60, "rationale": "链条较完整"},
                    "D04_related_issue_dependency": {"score": 0, "rationale": "根争点"},
                    "D05_risk_exposure": {"score": 80, "rationale": "可信度高度相关"},
                    "outcome_impact": "high",
                    "proponent_evidence_strength": "medium",
                    "opponent_attack_strength": "strong",
                },
                "proponent_evidence_ids": ["ev-001"],
                "opponent_attack_evidence_ids": ["ev-002"],
                "recommended_action": "supplement_evidence",
                "recommended_action_basis": "需补充借贷合意直接证据",
            },
            {
                "issue_id": "issue-002",
                "dimensions": {
                    "D01_verdict_impact_weight": {"score": 50, "rationale": "派生争点"},
                    "D02_factual_determination_difficulty": {
                        "score": 40,
                        "rationale": "事实较明确",
                    },
                    "D03_evidence_chain_completeness": {"score": 30, "rationale": "证据薄弱"},
                    "D04_related_issue_dependency": {"score": 1, "rationale": "依赖争点001"},
                    "D05_risk_exposure": {"score": 20, "rationale": "低可信度影响"},
                    "outcome_impact": "medium",
                    "proponent_evidence_strength": "weak",
                    "opponent_attack_strength": "medium",
                },
                "proponent_evidence_ids": ["ev-001"],
                "opponent_attack_evidence_ids": ["ev-002"],
                "recommended_action": "explain_in_trial",
                "recommended_action_basis": "庭审中说明即可",
            },
        ],
    }

    def test_normalize_evaluation_keys_maps_issue_assessments(self):
        """issue_assessments → evaluations"""
        data = copy.deepcopy(self.OPUS_FIXTURE)
        result = IssueImpactRanker._normalize_evaluation_keys(data)
        assert "evaluations" in result
        assert len(result["evaluations"]) == 2

    def test_normalize_single_eval_flattens_dimensions(self):
        """dimensions dict → flat scoring fields"""
        data = copy.deepcopy(self.OPUS_FIXTURE)
        IssueImpactRanker._normalize_evaluation_keys(data)
        item = data["evaluations"][0]
        result = IssueImpactRanker._normalize_single_eval(item)
        # importance_score should be set from D01_verdict_impact_weight
        assert result.get("importance_score", 0) > 0, (
            f"importance_score not extracted: {result.get('importance_score')}"
        )

    def test_normalize_strips_d0x_prefix(self):
        """D01_xxx → stripped to xxx → mapped to field"""
        data = copy.deepcopy(self.OPUS_FIXTURE)
        IssueImpactRanker._normalize_evaluation_keys(data)
        item = data["evaluations"][0]
        result = IssueImpactRanker._normalize_single_eval(item)
        # D01_verdict_impact_weight → importance_score = 90
        assert result.get("importance_score") == 90
        # D02_factual_determination_difficulty → swing_score = 75
        assert result.get("swing_score") == 75
        # D04_related_issue_dependency → dependency_depth = 0
        assert result.get("dependency_depth") == 0
        # D05_risk_exposure → credibility_impact = 80
        assert result.get("credibility_impact") == 80

    def test_normalize_extracts_enums_from_inside_dimensions(self):
        """outcome_impact inside dimensions → extracted to top level"""
        data = copy.deepcopy(self.OPUS_FIXTURE)
        IssueImpactRanker._normalize_evaluation_keys(data)
        item = data["evaluations"][0]
        result = IssueImpactRanker._normalize_single_eval(item)
        assert result.get("outcome_impact") == "high"

    @pytest.mark.asyncio
    async def test_full_rank_with_opus_output_produces_scores(self):
        """Full rank() flow with Opus-style output produces non-zero composite scores."""
        fixture = copy.deepcopy(self.OPUS_FIXTURE)
        response = json.dumps(fixture, ensure_ascii=False)

        ranker = IssueImpactRanker(
            llm_client=MockLLMClient(response),
            model="test",
            temperature=0.0,
            max_retries=1,
        )
        issues = [
            _make_issue("issue-001", evidence_ids=["ev-001"]),
            _make_issue("issue-002", evidence_ids=["ev-001"]),
        ]
        evidence = [_make_evidence("ev-001"), _make_evidence("ev-002")]
        inp = _make_ranker_input(issues, evidence=evidence)
        result = await ranker.rank(inp)
        assert isinstance(result, IssueImpactRankingResult)
        # At least some issues should have non-zero composite scores
        issues = result.ranked_issue_tree.issues
        scored = [i for i in issues if i.composite_score and i.composite_score > 0]
        assert len(scored) >= 1, (
            f"Expected some scored issues, got {len(scored)} out of {len(issues)}"
        )
        # Issue-001 should score higher than issue-002 (90 vs 50 importance)
        if len(scored) >= 2:
            scores = {i.issue_id: i.composite_score for i in issues}
            assert scores.get("issue-001", 0) > scores.get("issue-002", 0)

    @pytest.mark.asyncio
    async def test_unevaluated_issue_has_no_composite_score(self):
        """LLM 未返回评估的争点不应有 composite_score（避免默认值污染排序）。"""
        issues = [
            _make_issue("i-evaluated", evidence_ids=["ev-001"]),
            _make_issue("i-unevaluated", evidence_ids=["ev-001"]),
        ]
        # LLM 只返回 i-evaluated 的评估
        evaluations = [_eval_entry("i-evaluated", outcome_impact="high")]
        client = MockLLMClient(_stub_response(evaluations))
        ranker = IssueImpactRanker(client)
        result = await ranker.rank(_make_ranker_input(issues))

        assert "i-unevaluated" in result.unevaluated_issue_ids

        by_id = {i.issue_id: i for i in result.ranked_issue_tree.issues}
        # 已评估争点有 composite_score
        assert by_id["i-evaluated"].composite_score is not None
        # 未评估争点 composite_score 为 None，排在末尾
        assert by_id["i-unevaluated"].composite_score is None


# ---------------------------------------------------------------------------
# 测试：Phase C.5a 案由专属词汇过滤（_resolve_impact_targets）
# Phase C.5a regression: per-case-type impact_targets vocabulary filter
# ---------------------------------------------------------------------------


class TestImpactTargetsVocabularyFilter:
    """Unit 22 Phase C.5a/C.5b 回归测试。

    Issue.impact_targets 是 list[str]，没有 enum 校验。LLM 一旦幻想出
    civil_loan 词汇（如 'principal'）但 ranker 配置为 labor_dispute，过滤器
    必须静默丢弃这些值，使 Issue.impact_targets 仍然为案由词汇的子集。这是
    Phase C 的核心保证之一，必须有运行时回归测试覆盖。
    """

    def test_civil_loan_drops_labor_and_real_estate_vocab(self):
        """civil_loan ranker 必须丢弃 labor_dispute / real_estate / 完全未知值。"""
        ranker = IssueImpactRanker(MockLLMClient("{}"), case_type="civil_loan")
        out = ranker._resolve_impact_targets(
            [
                "principal",  # civil_loan ✓
                "interest",  # civil_loan ✓
                "wages",  # labor_dispute ✗
                "specific_performance",  # real_estate ✗
                "BOGUS_TARGET",  # 完全未知 ✗
                "credibility",  # 案由中立 pivot ✓
            ]
        )
        assert out == ["principal", "interest", "credibility"]

    def test_labor_dispute_drops_civil_loan_and_real_estate_vocab(self):
        """labor_dispute ranker 必须丢弃 civil_loan / real_estate / 未知值。"""
        ranker = IssueImpactRanker(MockLLMClient("{}"), case_type="labor_dispute")
        out = ranker._resolve_impact_targets(
            [
                "principal",  # civil_loan ✗
                "interest",  # civil_loan ✗
                "wages",  # labor_dispute ✓
                "economic_compensation",  # labor_dispute ✓
                "specific_performance",  # real_estate ✗
                "credibility",  # 案由中立 pivot ✓
            ]
        )
        assert out == ["wages", "economic_compensation", "credibility"]

    def test_real_estate_drops_civil_loan_and_labor_vocab(self):
        """real_estate ranker 必须丢弃 civil_loan / labor_dispute / 未知值。"""
        ranker = IssueImpactRanker(MockLLMClient("{}"), case_type="real_estate")
        out = ranker._resolve_impact_targets(
            [
                "principal",  # civil_loan ✗
                "wages",  # labor_dispute ✗
                "specific_performance",  # real_estate ✓
                "liquidated_damages",  # real_estate ✓
                "BOGUS_TARGET",  # 未知 ✗
                "credibility",  # 案由中立 pivot ✓
            ]
        )
        assert out == ["specific_performance", "liquidated_damages", "credibility"]

    def test_filter_normalizes_whitespace_and_case(self):
        """过滤前先做 strip + lower（保留 Phase C 之前的合约）。"""
        ranker = IssueImpactRanker(MockLLMClient("{}"), case_type="civil_loan")
        out = ranker._resolve_impact_targets(
            ["  PRINCIPAL  ", "Interest", "PENALTY"]
        )
        assert out == ["principal", "interest", "penalty"]

    def test_empty_list_returns_empty(self):
        """空输入返回空列表，不报错。"""
        ranker = IssueImpactRanker(MockLLMClient("{}"), case_type="civil_loan")
        assert ranker._resolve_impact_targets([]) == []

    @pytest.mark.asyncio
    async def test_full_rank_drops_out_of_vocab_from_llm_output(self):
        """端到端：LLM 返回混合词汇，rank() 后 Issue.impact_targets 仅含案由合法值。

        这是覆盖 ranker.py:686 ``updates['impact_targets'] = self._resolve_impact_targets(...)``
        的端到端回归 — 单元测试覆盖纯函数，这条测试覆盖通过 rank() 流程的实际写入。
        """
        issues = [_make_issue("i-001", evidence_ids=["ev-001"])]
        ev = _eval_entry(
            "i-001",
            impact_targets=[
                "principal",  # ✓
                "wages",  # ✗ labor_dispute leak
                "specific_performance",  # ✗ real_estate leak
                "credibility",  # ✓ pivot
                "GARBAGE",  # ✗ unknown
            ],
        )
        client = MockLLMClient(_stub_response([ev]))
        ranker = IssueImpactRanker(client, case_type="civil_loan")
        result = await ranker.rank(_make_ranker_input(issues))

        ranked = result.ranked_issue_tree.issues[0]
        # 仅 civil_loan 词汇被保留；过滤是宽松的（不降级整条评估）
        assert set(ranked.impact_targets) == {"principal", "credibility"}
        # 关键：丢弃非法值不应导致整条评估被降级到 unevaluated
        assert "i-001" not in result.unevaluated_issue_ids
