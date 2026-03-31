"""
DefenseChainOptimizer 单元测试。
Unit tests for DefenseChainOptimizer.

测试策略：
- 使用 MockLLMClient，不依赖真实 LLM
- 分层测试：空输入 → 正常流程 → 证据校验 → 优先级排序 → LLM 失败降级
- 覆盖所有合约保证
"""

from __future__ import annotations

import json

import pytest

from engines.shared.models import (
    AccessDomain,
    Evidence,
    EvidenceIndex,
    EvidenceStatus,
    EvidenceType,
    Issue,
    IssueStatus,
    IssueType,
    OutcomeImpact,
)
from engines.simulation_run.defense_chain.models import DefensePoint, PlaintiffDefenseChain
from engines.simulation_run.defense_chain.optimizer import DefenseChainOptimizer
from engines.simulation_run.defense_chain.schemas import (
    DefenseChainInput,
    DefenseChainResult,
    LLMDefenseChainOutput,
    LLMDefensePointOutput,
)


# ---------------------------------------------------------------------------
# Mock LLM 客户端
# ---------------------------------------------------------------------------


class MockLLMClient:
    """返回预定义 JSON 响应的 mock LLM 客户端。"""

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
    outcome_impact: OutcomeImpact | None = None,
) -> Issue:
    return Issue(
        issue_id=issue_id,
        case_id="CASE-DC-001",
        title=f"争点 {issue_id}",
        issue_type=IssueType.factual,
        status=IssueStatus.open,
        outcome_impact=outcome_impact,
        evidence_ids=["EV-001"],
    )


def _make_evidence(evidence_id: str) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        case_id="CASE-DC-001",
        owner_party_id="PARTY-P-001",
        title=f"证据 {evidence_id}",
        source="测试来源",
        summary="测试证据",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=["FACT-001"],
        status=EvidenceStatus.submitted,
    )


def _make_evidence_index(evidence_ids: list[str]) -> EvidenceIndex:
    return EvidenceIndex(
        case_id="CASE-DC-001",
        evidence=[_make_evidence(eid) for eid in evidence_ids],
    )


def _make_input(
    issues: list[Issue],
    evidence_ids: list[str] | None = None,
) -> DefenseChainInput:
    return DefenseChainInput(
        case_id="CASE-DC-001",
        run_id="RUN-DC-001",
        issues=issues,
        evidence_index=_make_evidence_index(evidence_ids or ["EV-001", "EV-002"]),
        plaintiff_party_id="PARTY-P-001",
    )


def _mock_response(
    defense_points: list[dict],
    confidence: float = 0.8,
    strategic_summary: str = "整体防御策略摘要",
) -> str:
    return json.dumps(
        {
            "defense_points": defense_points,
            "confidence_score": confidence,
            "strategic_summary": strategic_summary,
        },
        ensure_ascii=False,
    )


def _make_point_dict(
    issue_id: str,
    strategy: str = "有效策略",
    argument: str = "有效论证",
    evidence_ids: list[str] | None = None,
    priority: int = 1,
) -> dict:
    return {
        "issue_id": issue_id,
        "defense_strategy": strategy,
        "supporting_argument": argument,
        "evidence_ids": evidence_ids or ["EV-001"],
        "priority": priority,
    }


# ---------------------------------------------------------------------------
# 合约保证：空输入
# ---------------------------------------------------------------------------


class TestEmptyInput:
    """空争点列表直接返回空链，不调用 LLM。"""

    @pytest.mark.asyncio
    async def test_empty_issues_no_llm_call(self):
        mock = MockLLMClient(response="")
        optimizer = DefenseChainOptimizer(llm_client=mock)
        result = await optimizer.optimize(_make_input([]))

        assert mock.call_count == 0

    @pytest.mark.asyncio
    async def test_empty_issues_returns_empty_defense_points(self):
        mock = MockLLMClient(response="")
        optimizer = DefenseChainOptimizer(llm_client=mock)
        result = await optimizer.optimize(_make_input([]))

        assert result.chain.defense_points == []
        assert result.chain.confidence_score == 0.0
        assert result.chain.case_id == "CASE-DC-001"


# ---------------------------------------------------------------------------
# 合约保证：正常流程
# ---------------------------------------------------------------------------


class TestHappyPath:
    """正常流程：LLM 返回有效防御论点。"""

    @pytest.mark.asyncio
    async def test_single_valid_point_preserved(self):
        issues = [_make_issue("ISS-001", OutcomeImpact.high)]
        response = _mock_response([_make_point_dict("ISS-001")])
        optimizer = DefenseChainOptimizer(llm_client=MockLLMClient(response))
        result = await optimizer.optimize(_make_input(issues))

        assert len(result.chain.defense_points) == 1
        point = result.chain.defense_points[0]
        assert point.issue_id == "ISS-001"
        assert point.defense_strategy == "有效策略"
        assert "EV-001" in point.evidence_ids

    @pytest.mark.asyncio
    async def test_multiple_valid_points_all_preserved(self):
        issues = [_make_issue("ISS-A"), _make_issue("ISS-B")]
        response = _mock_response(
            [
                _make_point_dict("ISS-A", priority=1),
                _make_point_dict("ISS-B", priority=2),
            ]
        )
        optimizer = DefenseChainOptimizer(llm_client=MockLLMClient(response))
        result = await optimizer.optimize(_make_input(issues))

        assert len(result.chain.defense_points) == 2
        ids = [p.issue_id for p in result.chain.defense_points]
        assert "ISS-A" in ids
        assert "ISS-B" in ids

    @pytest.mark.asyncio
    async def test_confidence_score_preserved(self):
        issues = [_make_issue("ISS-001")]
        response = _mock_response([_make_point_dict("ISS-001")], confidence=0.92)
        optimizer = DefenseChainOptimizer(llm_client=MockLLMClient(response))
        result = await optimizer.optimize(_make_input(issues))

        assert result.chain.confidence_score == pytest.approx(0.92)

    @pytest.mark.asyncio
    async def test_strategic_summary_preserved(self):
        issues = [_make_issue("ISS-001")]
        response = _mock_response(
            [_make_point_dict("ISS-001")],
            strategic_summary="先攻击借贷合意",
        )
        optimizer = DefenseChainOptimizer(llm_client=MockLLMClient(response))
        result = await optimizer.optimize(_make_input(issues))

        assert result.chain.strategic_summary == "先攻击借贷合意"

    @pytest.mark.asyncio
    async def test_unevaluated_empty_on_full_coverage(self):
        issues = [_make_issue("ISS-001")]
        response = _mock_response([_make_point_dict("ISS-001")])
        optimizer = DefenseChainOptimizer(llm_client=MockLLMClient(response))
        result = await optimizer.optimize(_make_input(issues))

        assert result.unevaluated_issue_ids == []


# ---------------------------------------------------------------------------
# 合约保证：issue_id 校验
# ---------------------------------------------------------------------------


class TestIssueIDValidation:
    """LLM 返回未知 issue_id 被过滤，遗漏的争点记入 unevaluated。"""

    @pytest.mark.asyncio
    async def test_unknown_issue_id_filtered(self):
        issues = [_make_issue("ISS-REAL")]
        response = _mock_response([_make_point_dict("ISS-FAKE-999")])
        optimizer = DefenseChainOptimizer(llm_client=MockLLMClient(response))
        result = await optimizer.optimize(_make_input(issues))

        assert result.chain.defense_points == []
        assert "ISS-REAL" in result.unevaluated_issue_ids

    @pytest.mark.asyncio
    async def test_llm_omitted_issue_marked_unevaluated(self):
        """LLM 只返回部分争点时，遗漏的争点记入 unevaluated。"""
        issues = [_make_issue("ISS-A"), _make_issue("ISS-B")]
        response = _mock_response([_make_point_dict("ISS-A")])
        optimizer = DefenseChainOptimizer(llm_client=MockLLMClient(response))
        result = await optimizer.optimize(_make_input(issues))

        assert len(result.chain.defense_points) == 1
        assert "ISS-B" in result.unevaluated_issue_ids


# ---------------------------------------------------------------------------
# 合约保证：evidence_id 校验
# ---------------------------------------------------------------------------


class TestEvidenceIDValidation:
    """非法证据 ID 被过滤，不丢弃整条论点。"""

    @pytest.mark.asyncio
    async def test_invalid_evidence_id_filtered_point_kept(self):
        issues = [_make_issue("ISS-001")]
        response = _mock_response(
            [
                _make_point_dict("ISS-001", evidence_ids=["EV-001", "EV-GHOST"]),
            ]
        )
        optimizer = DefenseChainOptimizer(llm_client=MockLLMClient(response))
        result = await optimizer.optimize(_make_input(issues))

        assert len(result.chain.defense_points) == 1
        assert result.chain.defense_points[0].evidence_ids == ["EV-001"]

    @pytest.mark.asyncio
    async def test_all_evidence_ids_invalid_point_still_kept(self):
        """所有证据 ID 无效时论点仍保留（evidence_ids 被清空但论点不丢弃）。"""
        issues = [_make_issue("ISS-001")]
        response = _mock_response(
            [
                _make_point_dict("ISS-001", evidence_ids=["EV-GHOST-1", "EV-GHOST-2"]),
            ]
        )
        optimizer = DefenseChainOptimizer(llm_client=MockLLMClient(response))
        result = await optimizer.optimize(_make_input(issues))

        assert len(result.chain.defense_points) == 1
        assert result.chain.defense_points[0].evidence_ids == []

    @pytest.mark.asyncio
    async def test_evidence_support_aggregated_and_deduplicated(self):
        """evidence_support 汇总所有论点的证据 ID 并去重。"""
        issues = [_make_issue("ISS-A"), _make_issue("ISS-B")]
        response = _mock_response(
            [
                _make_point_dict("ISS-A", evidence_ids=["EV-001", "EV-002"], priority=1),
                _make_point_dict("ISS-B", evidence_ids=["EV-001"], priority=2),
            ]
        )
        optimizer = DefenseChainOptimizer(llm_client=MockLLMClient(response))
        result = await optimizer.optimize(_make_input(issues))

        assert sorted(result.chain.evidence_support) == ["EV-001", "EV-002"]


# ---------------------------------------------------------------------------
# 合约保证：strategy/argument 校验
# ---------------------------------------------------------------------------


class TestStrategyArgumentValidation:
    """缺少 defense_strategy 或 supporting_argument 的论点标记为 unevaluated。"""

    @pytest.mark.asyncio
    async def test_empty_strategy_marks_unevaluated(self):
        issues = [_make_issue("ISS-001")]
        response = _mock_response(
            [
                _make_point_dict("ISS-001", strategy="", argument="有论证"),
            ]
        )
        optimizer = DefenseChainOptimizer(llm_client=MockLLMClient(response))
        result = await optimizer.optimize(_make_input(issues))

        assert result.chain.defense_points == []
        assert "ISS-001" in result.unevaluated_issue_ids

    @pytest.mark.asyncio
    async def test_empty_argument_marks_unevaluated(self):
        issues = [_make_issue("ISS-001")]
        response = _mock_response(
            [
                _make_point_dict("ISS-001", strategy="有策略", argument=""),
            ]
        )
        optimizer = DefenseChainOptimizer(llm_client=MockLLMClient(response))
        result = await optimizer.optimize(_make_input(issues))

        assert result.chain.defense_points == []
        assert "ISS-001" in result.unevaluated_issue_ids


# ---------------------------------------------------------------------------
# 合约保证：priority 排序与重编号
# ---------------------------------------------------------------------------


class TestPriorityOrdering:
    """defense_points 按 priority 升序排列，编号连续从 1 开始。"""

    @pytest.mark.asyncio
    async def test_priority_renumbered_consecutively(self):
        issues = [_make_issue("ISS-A"), _make_issue("ISS-B"), _make_issue("ISS-C")]
        response = _mock_response(
            [
                _make_point_dict("ISS-B", priority=5),
                _make_point_dict("ISS-A", priority=2),
                _make_point_dict("ISS-C", priority=10),
            ]
        )
        optimizer = DefenseChainOptimizer(llm_client=MockLLMClient(response))
        result = await optimizer.optimize(_make_input(issues))

        priorities = [p.priority for p in result.chain.defense_points]
        assert priorities == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_priority_sorting_preserves_relative_order(self):
        """较小 priority 值的论点排在前面。"""
        issues = [_make_issue("ISS-A"), _make_issue("ISS-B")]
        response = _mock_response(
            [
                _make_point_dict("ISS-B", priority=10),
                _make_point_dict("ISS-A", priority=1),
            ]
        )
        optimizer = DefenseChainOptimizer(llm_client=MockLLMClient(response))
        result = await optimizer.optimize(_make_input(issues))

        issue_ids = [p.issue_id for p in result.chain.defense_points]
        assert issue_ids[0] == "ISS-A"
        assert issue_ids[1] == "ISS-B"


# ---------------------------------------------------------------------------
# 合约保证：target_issues 与 defense_points 对应
# ---------------------------------------------------------------------------


class TestTargetIssuesMapping:
    """target_issues 与 defense_points 中的 issue_id 一一对应。"""

    @pytest.mark.asyncio
    async def test_target_issues_match_defense_points(self):
        issues = [_make_issue("ISS-A"), _make_issue("ISS-B")]
        response = _mock_response(
            [
                _make_point_dict("ISS-A", priority=1),
                _make_point_dict("ISS-B", priority=2),
            ]
        )
        optimizer = DefenseChainOptimizer(llm_client=MockLLMClient(response))
        result = await optimizer.optimize(_make_input(issues))

        expected = [p.issue_id for p in result.chain.defense_points]
        assert result.chain.target_issues == expected


# ---------------------------------------------------------------------------
# 合约保证：LLM 失败降级
# ---------------------------------------------------------------------------


class TestLLMFailureHandling:
    """LLM 调用失败时返回降级结果，不抛异常。"""

    @pytest.mark.asyncio
    async def test_llm_failure_returns_degraded_result(self):
        issues = [_make_issue("ISS-FAIL")]
        mock = MockLLMClient(response="", fail_times=10)
        optimizer = DefenseChainOptimizer(llm_client=mock, max_retries=1)
        result = await optimizer.optimize(_make_input(issues))

        assert result.chain.defense_points == []
        assert result.chain.confidence_score == 0.0
        assert result.metadata.get("failed") is True
        assert "ISS-FAIL" in result.unevaluated_issue_ids

    @pytest.mark.asyncio
    async def test_llm_invalid_json_returns_degraded_result(self):
        issues = [_make_issue("ISS-BAD")]
        mock = MockLLMClient(response="这不是 JSON")
        optimizer = DefenseChainOptimizer(llm_client=mock, max_retries=0)
        result = await optimizer.optimize(_make_input(issues))

        assert result.chain.defense_points == []
        assert result.metadata.get("failed") is True


# ---------------------------------------------------------------------------
# 合约保证：不支持的案由类型
# ---------------------------------------------------------------------------


class TestUnsupportedCaseType:
    """不支持的案由类型构造时抛出 ValueError。"""

    def test_unsupported_case_type_raises(self):
        with pytest.raises(ValueError, match="不支持的案由类型"):
            DefenseChainOptimizer(
                llm_client=MockLLMClient(""),
                case_type="unsupported_type",
            )


# ---------------------------------------------------------------------------
# 合约保证：prompt 内容
# ---------------------------------------------------------------------------


class TestPromptContent:
    """user prompt 中包含关键信息。"""

    @pytest.mark.asyncio
    async def test_prompt_contains_plaintiff_party_id(self):
        issues = [_make_issue("ISS-001")]
        mock = MockLLMClient(_mock_response([_make_point_dict("ISS-001")]))
        optimizer = DefenseChainOptimizer(llm_client=mock)
        await optimizer.optimize(_make_input(issues))

        assert "PARTY-P-001" in mock.last_user

    @pytest.mark.asyncio
    async def test_prompt_contains_issue_id(self):
        issues = [_make_issue("ISS-PROMPT-TEST")]
        mock = MockLLMClient(_mock_response([_make_point_dict("ISS-PROMPT-TEST")]))
        optimizer = DefenseChainOptimizer(llm_client=mock)
        await optimizer.optimize(_make_input(issues))

        assert "ISS-PROMPT-TEST" in mock.last_user


# ---------------------------------------------------------------------------
# 合约保证：元信息
# ---------------------------------------------------------------------------


class TestMetadata:
    """结果包含正确的元信息。"""

    @pytest.mark.asyncio
    async def test_metadata_contains_model_and_counts(self):
        issues = [_make_issue("ISS-001")]
        response = _mock_response([_make_point_dict("ISS-001")])
        optimizer = DefenseChainOptimizer(llm_client=MockLLMClient(response))
        result = await optimizer.optimize(_make_input(issues))

        assert "model" in result.metadata
        assert result.metadata["total_count"] == 1
        assert result.metadata["evaluated_count"] == 1

    @pytest.mark.asyncio
    async def test_chain_id_and_created_at_populated(self):
        issues = [_make_issue("ISS-001")]
        response = _mock_response([_make_point_dict("ISS-001")])
        optimizer = DefenseChainOptimizer(llm_client=MockLLMClient(response))
        result = await optimizer.optimize(_make_input(issues))

        assert result.chain.chain_id
        assert result.chain.created_at
        assert "T" in result.chain.created_at
