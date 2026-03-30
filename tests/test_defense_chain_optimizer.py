"""
DefenseChainOptimizer 单元测试。
Unit tests for DefenseChainOptimizer.

测试策略：
- 使用 MockLLMClient，不依赖真实 LLM
- 覆盖：空争点、正常流程、证据 ID 校验、LLM 失败降级、优先级排序
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
from engines.simulation_run.defense_chain.schemas import DefenseChainInput, DefenseChainResult


# ---------------------------------------------------------------------------
# Mock LLM 客户端
# ---------------------------------------------------------------------------


class MockLLMClient:
    def __init__(self, response: str, fail_times: int = 0) -> None:
        self._response = response
        self._fail_times = fail_times
        self.call_count = 0

    async def create_message(self, *, system: str, user: str, **kwargs) -> str:
        self.call_count += 1
        if self._fail_times > 0:
            self._fail_times -= 1
            raise RuntimeError("模拟 LLM 调用失败")
        return self._response


# ---------------------------------------------------------------------------
# 辅助工厂
# ---------------------------------------------------------------------------


def _make_issue(issue_id: str, outcome_impact: OutcomeImpact | None = None) -> Issue:
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


def _mock_response(defense_points: list[dict], confidence: float = 0.8) -> str:
    return json.dumps({
        "defense_points": defense_points,
        "confidence_score": confidence,
        "strategic_summary": "整体防御策略摘要",
    }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 基础测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_issues_returns_empty_chain():
    """空争点列表直接返回空链，不调用 LLM。"""
    mock = MockLLMClient(response="")
    optimizer = DefenseChainOptimizer(llm_client=mock)
    result = await optimizer.optimize(_make_input([]))
    assert mock.call_count == 0
    assert result.chain.defense_points == []
    assert result.chain.confidence_score == 0.0


@pytest.mark.asyncio
async def test_happy_path_basic():
    """正常流程：LLM 返回有效防御论点，正确构建 DefenseChain。"""
    issues = [_make_issue("ISS-001", OutcomeImpact.high)]
    mock = MockLLMClient(response=_mock_response([
        {
            "issue_id": "ISS-001",
            "defense_strategy": "主张借贷关系成立",
            "supporting_argument": "借条原件 + 银行转账回单证明本金交付",
            "evidence_ids": ["EV-001"],
            "priority": 1,
        }
    ]))
    optimizer = DefenseChainOptimizer(llm_client=mock)
    result = await optimizer.optimize(_make_input(issues))

    assert mock.call_count == 1
    assert len(result.chain.defense_points) == 1
    point = result.chain.defense_points[0]
    assert point.issue_id == "ISS-001"
    assert point.defense_strategy == "主张借贷关系成立"
    assert "EV-001" in point.evidence_ids
    assert result.chain.confidence_score == pytest.approx(0.8)
    assert result.unevaluated_issue_ids == []


@pytest.mark.asyncio
async def test_unknown_issue_id_filtered():
    """LLM 返回未知 issue_id 被过滤，对应争点记入 unevaluated。"""
    issues = [_make_issue("ISS-REAL")]
    mock = MockLLMClient(response=_mock_response([
        {
            "issue_id": "ISS-FAKE-999",
            "defense_strategy": "不存在的争点",
            "supporting_argument": "无效",
            "evidence_ids": [],
            "priority": 1,
        }
    ]))
    optimizer = DefenseChainOptimizer(llm_client=mock)
    result = await optimizer.optimize(_make_input(issues))

    assert result.chain.defense_points == []
    assert "ISS-REAL" in result.unevaluated_issue_ids


@pytest.mark.asyncio
async def test_invalid_evidence_ids_filtered():
    """非法证据 ID 被过滤，不因此丢弃整条论点。"""
    issues = [_make_issue("ISS-002")]
    mock = MockLLMClient(response=_mock_response([
        {
            "issue_id": "ISS-002",
            "defense_strategy": "有效策略",
            "supporting_argument": "有效论证",
            "evidence_ids": ["EV-001", "EV-FAKE-999"],  # EV-FAKE-999 不存在
            "priority": 1,
        }
    ]))
    optimizer = DefenseChainOptimizer(llm_client=mock)
    result = await optimizer.optimize(_make_input(issues))

    assert len(result.chain.defense_points) == 1
    assert result.chain.defense_points[0].evidence_ids == ["EV-001"]


@pytest.mark.asyncio
async def test_missing_strategy_marks_unevaluated():
    """缺少 defense_strategy 或 supporting_argument 时标记为 unevaluated。"""
    issues = [_make_issue("ISS-003")]
    mock = MockLLMClient(response=_mock_response([
        {
            "issue_id": "ISS-003",
            "defense_strategy": "",  # 空值
            "supporting_argument": "有论证",
            "evidence_ids": [],
            "priority": 1,
        }
    ]))
    optimizer = DefenseChainOptimizer(llm_client=mock)
    result = await optimizer.optimize(_make_input(issues))

    assert result.chain.defense_points == []
    assert "ISS-003" in result.unevaluated_issue_ids


@pytest.mark.asyncio
async def test_priority_renumbered_consecutively():
    """多个论点按 priority 排序，最终编号连续从 1 开始。"""
    issues = [
        _make_issue("ISS-A"),
        _make_issue("ISS-B"),
        _make_issue("ISS-C"),
    ]
    mock = MockLLMClient(response=_mock_response([
        {"issue_id": "ISS-B", "defense_strategy": "B策略", "supporting_argument": "B论证",
         "evidence_ids": [], "priority": 5},
        {"issue_id": "ISS-A", "defense_strategy": "A策略", "supporting_argument": "A论证",
         "evidence_ids": [], "priority": 2},
        {"issue_id": "ISS-C", "defense_strategy": "C策略", "supporting_argument": "C论证",
         "evidence_ids": [], "priority": 10},
    ]))
    optimizer = DefenseChainOptimizer(llm_client=mock)
    result = await optimizer.optimize(_make_input(issues))

    priorities = [p.priority for p in result.chain.defense_points]
    assert priorities == sorted(priorities)  # 升序
    assert priorities[0] == 1  # 从 1 开始
    assert priorities == list(range(1, len(priorities) + 1))  # 连续


# ---------------------------------------------------------------------------
# 降级测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_returns_degraded_result():
    """LLM 持续失败返回降级结果，不抛异常。"""
    issues = [_make_issue("ISS-FAIL")]
    mock = MockLLMClient(response="", fail_times=10)
    optimizer = DefenseChainOptimizer(llm_client=mock, max_retries=1)
    result = await optimizer.optimize(_make_input(issues))

    assert result.chain.defense_points == []
    assert result.chain.confidence_score == 0.0
    assert result.metadata.get("failed") is True
    assert "ISS-FAIL" in result.unevaluated_issue_ids


# ---------------------------------------------------------------------------
# 不支持案由类型测试
# ---------------------------------------------------------------------------


def test_unsupported_case_type_raises():
    """不支持的案由类型构造时抛出 ValueError。"""
    mock = MockLLMClient(response="")
    with pytest.raises(ValueError, match="不支持的案由类型"):
        DefenseChainOptimizer(llm_client=mock, case_type="unsupported_type")
