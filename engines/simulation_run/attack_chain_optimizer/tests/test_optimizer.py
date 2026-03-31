"""
AttackChainOptimizer 单元测试。
Unit tests for AttackChainOptimizer.

测试策略：
- 不依赖真实 LLM；使用 stub LLM client 返回预定义 JSON
- 分层测试：规则层逻辑 → 完整 optimize() 流程
- 覆盖所有合约保证（见 spec P0.4 约束）
"""

from __future__ import annotations

import copy
import json

import pytest

from engines.shared.models import (
    AccessDomain,
    AttackStrength,
    Evidence,
    EvidenceIndex,
    EvidenceStatus,
    EvidenceStrength,
    EvidenceType,
    Issue,
    IssueStatus,
    IssueTree,
    IssueType,
    OptimalAttackChain,
    OutcomeImpact,
)
from engines.simulation_run.attack_chain_optimizer.optimizer import AttackChainOptimizer
from engines.simulation_run.attack_chain_optimizer.schemas import AttackChainOptimizerInput


# ---------------------------------------------------------------------------
# Mock LLM 客户端
# ---------------------------------------------------------------------------


class MockLLMClient:
    """返回预定义 JSON 响应的 mock LLM 客户端。"""

    def __init__(self, response: str, fail: bool = False) -> None:
        self._response = response
        self._fail = fail
        self.call_count = 0
        self.last_system: str | None = None
        self.last_user: str | None = None

    async def create_message(self, *, system: str, user: str, **kwargs) -> str:
        self.call_count += 1
        self.last_system = system
        self.last_user = user
        if self._fail:
            raise RuntimeError("模拟 LLM 调用失败")
        return self._response


# ---------------------------------------------------------------------------
# 测试辅助工厂
# ---------------------------------------------------------------------------


def _make_issue(
    issue_id: str,
    evidence_ids: list[str] | None = None,
    outcome_impact: OutcomeImpact = OutcomeImpact.high,
    proponent_strength: EvidenceStrength | None = None,
    opponent_attack: AttackStrength | None = None,
) -> Issue:
    return Issue(
        issue_id=issue_id,
        case_id="case-001",
        title=f"测试争点 {issue_id}",
        issue_type=IssueType.factual,
        status=IssueStatus.open,
        evidence_ids=evidence_ids or [],
        outcome_impact=outcome_impact,
        proponent_evidence_strength=proponent_strength,
        opponent_attack_strength=opponent_attack,
    )


def _make_evidence(evidence_id: str, status: EvidenceStatus = EvidenceStatus.submitted) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        case_id="case-001",
        owner_party_id="plaintiff-001",
        title=f"证据 {evidence_id}",
        source="测试来源",
        summary="测试证据摘要",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=["fact-001"],
        access_domain=AccessDomain.shared_common,
        status=status,
    )


def _make_issue_tree(
    issue_ids: list[str],
    evidence_ids: list[str] | None = None,
) -> IssueTree:
    issues = [_make_issue(iid, evidence_ids=evidence_ids or []) for iid in issue_ids]
    return IssueTree(case_id="case-001", issues=issues)


def _make_evidence_index(evidence_ids: list[str]) -> EvidenceIndex:
    return EvidenceIndex(
        case_id="case-001",
        evidence=[_make_evidence(eid) for eid in evidence_ids],
    )


def _make_input(
    issue_ids: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    owner_party_id: str = "plaintiff-001",
) -> AttackChainOptimizerInput:
    iids = issue_ids or ["issue-001", "issue-002", "issue-003"]
    eids = evidence_ids or ["ev-001", "ev-002", "ev-003"]
    return AttackChainOptimizerInput(
        case_id="case-001",
        run_id="run-001",
        owner_party_id=owner_party_id,
        issue_tree=_make_issue_tree(iids, evidence_ids=eids),
        evidence_index=_make_evidence_index(eids),
    )


def _make_attack_nodes_json(
    count: int = 3,
    *,
    issue_ids: list[str] | None = None,
    evidence_ids: list[str] | None = None,
) -> list[dict]:
    """生成测试用攻击节点 JSON 数据。"""
    iids = issue_ids or ["issue-001"]
    eids = evidence_ids or ["ev-001"]
    nodes = []
    for i in range(count):
        nodes.append(
            {
                "attack_node_id": f"atk-00{i + 1}",
                "target_issue_id": iids[i % len(iids)],
                "attack_description": f"攻击论点描述 {i + 1}",
                "success_conditions": f"攻击成功条件 {i + 1}",
                "supporting_evidence_ids": eids,
                "counter_measure": f"反制动作 {i + 1}",
                "adversary_pivot_strategy": f"策略切换说明 {i + 1}",
            }
        )
    return nodes


def _llm_response(
    count: int = 3,
    *,
    issue_ids: list[str] | None = None,
    evidence_ids: list[str] | None = None,
) -> str:
    return json.dumps(
        {
            "top_attacks": _make_attack_nodes_json(
                count, issue_ids=issue_ids, evidence_ids=evidence_ids
            ),
        },
        ensure_ascii=False,
    )


def _make_optimizer(response: str, *, fail: bool = False) -> AttackChainOptimizer:
    return AttackChainOptimizer(
        llm_client=MockLLMClient(response, fail=fail),
        case_type="civil_loan",
        model="claude-test",
        temperature=0.0,
        max_retries=1,
    )


# ---------------------------------------------------------------------------
# 合约保证测试：top_attacks 数量
# ---------------------------------------------------------------------------


class TestTopAttackCount:
    """top_attacks 数量约束：规则层截断至 3。"""

    @pytest.mark.asyncio
    async def test_exactly_3_nodes_preserved(self):
        """LLM 返回恰好 3 个节点时全部保留。"""
        result = await _make_optimizer(_llm_response(3)).optimize(_make_input())

        assert isinstance(result, OptimalAttackChain)
        assert len(result.top_attacks) == 3

    @pytest.mark.asyncio
    async def test_more_than_3_nodes_truncated_to_3(self):
        """LLM 返回 5 个节点时截断至 3。"""
        result = await _make_optimizer(_llm_response(5)).optimize(_make_input())

        assert len(result.top_attacks) == 3

    @pytest.mark.asyncio
    async def test_fewer_than_3_valid_nodes_returned_as_is(self):
        """LLM 只返回 2 个有效节点时原样返回（不补充；调用方负责降级处理）。"""
        result = await _make_optimizer(_llm_response(2)).optimize(_make_input())

        assert len(result.top_attacks) == 2

    @pytest.mark.asyncio
    async def test_zero_nodes_returns_empty_chain(self):
        """LLM 返回空 top_attacks 列表时返回空链（不抛异常）。"""
        response = json.dumps({"top_attacks": []})
        result = await _make_optimizer(response).optimize(_make_input())

        assert isinstance(result, OptimalAttackChain)
        assert result.top_attacks == []
        assert result.recommended_order == []


# ---------------------------------------------------------------------------
# 合约保证测试：recommended_order 与 top_attacks 完全对应
# ---------------------------------------------------------------------------


class TestRecommendedOrder:
    """recommended_order 必须与 top_attacks 完全对应。"""

    @pytest.mark.asyncio
    async def test_recommended_order_matches_top_attacks(self):
        """recommended_order 中的 ID 与 top_attacks 的 attack_node_id 完全对应且顺序一致。"""
        result = await _make_optimizer(_llm_response(3)).optimize(_make_input())

        assert len(result.recommended_order) == len(result.top_attacks)
        expected_ids = [node.attack_node_id for node in result.top_attacks]
        assert result.recommended_order == expected_ids

    @pytest.mark.asyncio
    async def test_recommended_order_updates_after_truncation(self):
        """截断后 recommended_order 也随之截断（只包含保留的 3 个节点的 ID）。"""
        result = await _make_optimizer(_llm_response(5)).optimize(_make_input())

        expected_ids = [node.attack_node_id for node in result.top_attacks]
        assert result.recommended_order == expected_ids
        assert len(result.recommended_order) == 3


# ---------------------------------------------------------------------------
# 合约保证测试：target_issue_id 有效性
# ---------------------------------------------------------------------------


class TestTargetIssueIDValidation:
    """target_issue_id 必须是已知争点 ID，非法节点被丢弃。"""

    @pytest.mark.asyncio
    async def test_node_with_unknown_target_issue_id_filtered(self):
        """target_issue_id 引用了未知争点的节点被过滤。"""
        response = json.dumps(
            {
                "top_attacks": [
                    {
                        "attack_node_id": "atk-001",
                        "target_issue_id": "issue-001",  # 有效
                        "attack_description": "有效攻击",
                        "success_conditions": "成功条件",
                        "supporting_evidence_ids": ["ev-001"],
                        "counter_measure": "反制",
                        "adversary_pivot_strategy": "切换",
                    },
                    {
                        "attack_node_id": "atk-002",
                        "target_issue_id": "issue-GHOST",  # 未知争点
                        "attack_description": "无效攻击",
                        "success_conditions": "成功条件",
                        "supporting_evidence_ids": ["ev-001"],
                        "counter_measure": "反制",
                        "adversary_pivot_strategy": "切换",
                    },
                ],
            }
        )
        inp = _make_input(issue_ids=["issue-001", "issue-002", "issue-003"])
        result = await _make_optimizer(response).optimize(inp)

        assert len(result.top_attacks) == 1
        assert result.top_attacks[0].attack_node_id == "atk-001"

    @pytest.mark.asyncio
    async def test_node_with_empty_target_issue_id_filtered(self):
        """target_issue_id 为空字符串的节点被过滤。"""
        response = json.dumps(
            {
                "top_attacks": [
                    {
                        "attack_node_id": "atk-001",
                        "target_issue_id": "",  # 空值
                        "attack_description": "攻击",
                        "success_conditions": "成功条件",
                        "supporting_evidence_ids": ["ev-001"],
                        "counter_measure": "反制",
                        "adversary_pivot_strategy": "切换",
                    },
                ],
            }
        )
        result = await _make_optimizer(response).optimize(_make_input())

        assert len(result.top_attacks) == 0


# ---------------------------------------------------------------------------
# 合约保证测试：supporting_evidence_ids 有效性
# ---------------------------------------------------------------------------


class TestSupportingEvidenceIDValidation:
    """supporting_evidence_ids 必须绑定已知证据 ID，非法 ID 被过滤。"""

    @pytest.mark.asyncio
    async def test_unknown_evidence_ids_filtered_from_node(self):
        """supporting_evidence_ids 中未知证据 ID 被过滤，节点保留（仍有有效 ID）。"""
        response = json.dumps(
            {
                "top_attacks": [
                    {
                        "attack_node_id": "atk-001",
                        "target_issue_id": "issue-001",
                        "attack_description": "攻击",
                        "success_conditions": "成功条件",
                        "supporting_evidence_ids": ["ev-001", "ev-GHOST"],
                        "counter_measure": "反制",
                        "adversary_pivot_strategy": "切换",
                    },
                ],
            }
        )
        inp = _make_input(evidence_ids=["ev-001", "ev-002"])
        result = await _make_optimizer(response).optimize(inp)

        assert len(result.top_attacks) == 1
        assert "ev-GHOST" not in result.top_attacks[0].supporting_evidence_ids
        assert "ev-001" in result.top_attacks[0].supporting_evidence_ids

    @pytest.mark.asyncio
    async def test_node_with_all_invalid_evidence_ids_filtered(self):
        """supporting_evidence_ids 全部无效（过滤后为空）的节点被丢弃——零容忍。"""
        response = json.dumps(
            {
                "top_attacks": [
                    {
                        "attack_node_id": "atk-001",
                        "target_issue_id": "issue-001",
                        "attack_description": "攻击",
                        "success_conditions": "成功条件",
                        "supporting_evidence_ids": ["ev-GHOST-1", "ev-GHOST-2"],
                        "counter_measure": "反制",
                        "adversary_pivot_strategy": "切换",
                    },
                ],
            }
        )
        result = await _make_optimizer(response).optimize(_make_input(evidence_ids=["ev-001"]))

        assert len(result.top_attacks) == 0

    @pytest.mark.asyncio
    async def test_node_with_empty_evidence_ids_filtered(self):
        """supporting_evidence_ids 为空列表的节点被丢弃——零容忍。"""
        response = json.dumps(
            {
                "top_attacks": [
                    {
                        "attack_node_id": "atk-001",
                        "target_issue_id": "issue-001",
                        "attack_description": "攻击",
                        "success_conditions": "成功条件",
                        "supporting_evidence_ids": [],  # 空列表
                        "counter_measure": "反制",
                        "adversary_pivot_strategy": "切换",
                    },
                ],
            }
        )
        result = await _make_optimizer(response).optimize(_make_input())

        assert len(result.top_attacks) == 0


# ---------------------------------------------------------------------------
# 合约保证测试：attack_node_id 非空
# ---------------------------------------------------------------------------


class TestAttackNodeIDValidation:
    """attack_node_id 为空的节点被丢弃。"""

    @pytest.mark.asyncio
    async def test_node_with_empty_attack_node_id_filtered(self):
        """attack_node_id 为空字符串的节点被过滤。"""
        response = json.dumps(
            {
                "top_attacks": [
                    {
                        "attack_node_id": "",  # 空 ID
                        "target_issue_id": "issue-001",
                        "attack_description": "攻击",
                        "success_conditions": "成功条件",
                        "supporting_evidence_ids": ["ev-001"],
                        "counter_measure": "反制",
                        "adversary_pivot_strategy": "切换",
                    },
                    {
                        "attack_node_id": "atk-002",
                        "target_issue_id": "issue-001",
                        "attack_description": "有效攻击",
                        "success_conditions": "成功条件",
                        "supporting_evidence_ids": ["ev-001"],
                        "counter_measure": "反制",
                        "adversary_pivot_strategy": "切换",
                    },
                ],
            }
        )
        result = await _make_optimizer(response).optimize(_make_input())

        assert len(result.top_attacks) == 1
        assert result.top_attacks[0].attack_node_id == "atk-002"


# ---------------------------------------------------------------------------
# 合约保证测试：attack_description 非空
# ---------------------------------------------------------------------------


class TestAttackNodeIDDeduplication:
    """attack_node_id 重复的节点被丢弃（只保留第一次出现）。"""

    @pytest.mark.asyncio
    async def test_duplicate_attack_node_id_filtered(self):
        """两个 attack_node_id 相同的节点只保留第一个。"""
        response = json.dumps(
            {
                "top_attacks": [
                    {
                        "attack_node_id": "atk-001",  # 第一次出现，保留
                        "target_issue_id": "issue-001",
                        "attack_description": "第一个攻击",
                        "success_conditions": "成功条件",
                        "supporting_evidence_ids": ["ev-001"],
                        "counter_measure": "反制",
                        "adversary_pivot_strategy": "切换",
                    },
                    {
                        "attack_node_id": "atk-001",  # 重复 ID，丢弃
                        "target_issue_id": "issue-002",
                        "attack_description": "重复 ID 的攻击",
                        "success_conditions": "成功条件",
                        "supporting_evidence_ids": ["ev-002"],
                        "counter_measure": "反制",
                        "adversary_pivot_strategy": "切换",
                    },
                    {
                        "attack_node_id": "atk-002",  # 有效节点
                        "target_issue_id": "issue-002",
                        "attack_description": "第三个攻击",
                        "success_conditions": "成功条件",
                        "supporting_evidence_ids": ["ev-002"],
                        "counter_measure": "反制",
                        "adversary_pivot_strategy": "切换",
                    },
                ],
            }
        )
        inp = _make_input(
            issue_ids=["issue-001", "issue-002", "issue-003"],
            evidence_ids=["ev-001", "ev-002"],
        )
        result = await _make_optimizer(response).optimize(inp)

        assert len(result.top_attacks) == 2
        ids = [n.attack_node_id for n in result.top_attacks]
        assert ids == ["atk-001", "atk-002"]
        # recommended_order 也应只含唯一 ID
        assert result.recommended_order == ["atk-001", "atk-002"]

    @pytest.mark.asyncio
    async def test_duplicate_ids_dont_fill_up_to_3(self):
        """重复 ID 被去重后剩余节点不足 3 个时按实际返回。"""
        response = json.dumps(
            {
                "top_attacks": [
                    {
                        "attack_node_id": "atk-dup",
                        "target_issue_id": "issue-001",
                        "attack_description": "攻击 1",
                        "success_conditions": "条件",
                        "supporting_evidence_ids": ["ev-001"],
                        "counter_measure": "反制",
                        "adversary_pivot_strategy": "切换",
                    },
                    {
                        "attack_node_id": "atk-dup",  # 重复，丢弃
                        "target_issue_id": "issue-002",
                        "attack_description": "攻击 2",
                        "success_conditions": "条件",
                        "supporting_evidence_ids": ["ev-002"],
                        "counter_measure": "反制",
                        "adversary_pivot_strategy": "切换",
                    },
                    {
                        "attack_node_id": "atk-dup",  # 重复，丢弃
                        "target_issue_id": "issue-003",
                        "attack_description": "攻击 3",
                        "success_conditions": "条件",
                        "supporting_evidence_ids": ["ev-001"],
                        "counter_measure": "反制",
                        "adversary_pivot_strategy": "切换",
                    },
                ],
            }
        )
        result = await _make_optimizer(response).optimize(_make_input())

        # 只有第一个保留
        assert len(result.top_attacks) == 1
        assert result.top_attacks[0].attack_node_id == "atk-dup"


class TestAttackDescriptionValidation:
    """attack_description 为空的节点被丢弃。"""

    @pytest.mark.asyncio
    async def test_node_with_empty_attack_description_filtered(self):
        """attack_description 为空字符串的节点被过滤。"""
        response = json.dumps(
            {
                "top_attacks": [
                    {
                        "attack_node_id": "atk-001",
                        "target_issue_id": "issue-001",
                        "attack_description": "",  # 空描述
                        "success_conditions": "成功条件",
                        "supporting_evidence_ids": ["ev-001"],
                        "counter_measure": "反制",
                        "adversary_pivot_strategy": "切换",
                    },
                ],
            }
        )
        result = await _make_optimizer(response).optimize(_make_input())

        assert len(result.top_attacks) == 0


# ---------------------------------------------------------------------------
# 合约保证测试：LLM 失败处理
# ---------------------------------------------------------------------------


class TestLLMFailureHandling:
    """LLM 调用失败时返回空 OptimalAttackChain，不抛异常。"""

    @pytest.mark.asyncio
    async def test_llm_failure_returns_empty_chain(self):
        """LLM 抛出异常时，optimize() 不抛异常，返回空 OptimalAttackChain。"""
        result = await _make_optimizer("", fail=True).optimize(_make_input())

        assert isinstance(result, OptimalAttackChain)
        assert result.top_attacks == []
        assert result.recommended_order == []
        assert result.case_id == "case-001"

    @pytest.mark.asyncio
    async def test_llm_invalid_json_returns_empty_chain(self):
        """LLM 返回非法 JSON 时，optimize() 返回空 OptimalAttackChain。"""
        result = await _make_optimizer("这不是 JSON").optimize(_make_input())

        assert isinstance(result, OptimalAttackChain)
        assert result.top_attacks == []

    @pytest.mark.asyncio
    async def test_llm_failure_retries_then_returns_empty(self):
        """max_retries=2 时 LLM 连续失败 3 次后返回空链。"""
        mock = MockLLMClient("", fail=True)
        optimizer = AttackChainOptimizer(
            llm_client=mock,
            case_type="civil_loan",
            model="claude-test",
            temperature=0.0,
            max_retries=2,
        )
        result = await optimizer.optimize(_make_input())

        assert result.top_attacks == []
        # max_retries=2 → 总调用次数 = 3
        assert mock.call_count == 3


# ---------------------------------------------------------------------------
# 合约保证测试：产物元信息
# ---------------------------------------------------------------------------


class TestOutputMetadata:
    """产物元信息正确性测试。"""

    @pytest.mark.asyncio
    async def test_result_contains_correct_metadata(self):
        """结果包含正确的 case_id、run_id、owner_party_id。"""
        result = await _make_optimizer(_llm_response(3)).optimize(
            _make_input(owner_party_id="defendant-001")
        )

        assert result.case_id == "case-001"
        assert result.run_id == "run-001"
        assert result.owner_party_id == "defendant-001"
        assert result.chain_id  # 非空
        assert result.created_at  # 非空

    @pytest.mark.asyncio
    async def test_unsupported_case_type_raises(self):
        """不支持的案件类型在构造时抛出 ValueError。"""
        with pytest.raises(ValueError, match="不支持的案件类型"):
            AttackChainOptimizer(
                llm_client=MockLLMClient(""),
                case_type="unsupported_type",
                model="claude-test",
                temperature=0.0,
                max_retries=0,
            )


# ---------------------------------------------------------------------------
# 合约保证测试：prompt 内容
# ---------------------------------------------------------------------------


class TestPromptContent:
    """prompt 内容测试——确认关键信息传入 LLM。"""

    @pytest.mark.asyncio
    async def test_prompt_contains_owner_party_id(self):
        """user prompt 中包含 owner_party_id。"""
        mock = MockLLMClient(_llm_response(3))
        optimizer = AttackChainOptimizer(
            llm_client=mock,
            case_type="civil_loan",
            model="claude-test",
            temperature=0.0,
            max_retries=0,
        )
        await optimizer.optimize(_make_input(owner_party_id="plaintiff-999"))

        assert "plaintiff-999" in mock.last_user

    @pytest.mark.asyncio
    async def test_prompt_contains_issue_ids(self):
        """user prompt 中包含争点 ID 信息。"""
        mock = MockLLMClient(_llm_response(3, issue_ids=["issue-001", "issue-002", "issue-003"]))
        optimizer = AttackChainOptimizer(
            llm_client=mock,
            case_type="civil_loan",
            model="claude-test",
            temperature=0.0,
            max_retries=0,
        )
        await optimizer.optimize(_make_input(issue_ids=["issue-001", "issue-002", "issue-003"]))

        assert "issue-001" in mock.last_user

    @pytest.mark.asyncio
    async def test_prompt_contains_evidence_ids(self):
        """user prompt 中包含证据 ID 信息。"""
        mock = MockLLMClient(_llm_response(3, evidence_ids=["ev-001", "ev-002", "ev-003"]))
        optimizer = AttackChainOptimizer(
            llm_client=mock,
            case_type="civil_loan",
            model="claude-test",
            temperature=0.0,
            max_retries=0,
        )
        await optimizer.optimize(_make_input(evidence_ids=["ev-001", "ev-002", "ev-003"]))

        assert "ev-001" in mock.last_user


# ---------------------------------------------------------------------------
# 合约保证测试：混合有效/无效节点的完整流程
# ---------------------------------------------------------------------------


class TestMixedValidInvalidNodes:
    """混合有效/无效节点时规则层行为。"""

    @pytest.mark.asyncio
    async def test_mixed_nodes_only_valid_ones_kept(self):
        """同时包含有效和无效节点时，只保留有效节点（最多 3 个）。"""
        response = json.dumps(
            {
                "top_attacks": [
                    {  # 有效节点 1
                        "attack_node_id": "atk-001",
                        "target_issue_id": "issue-001",
                        "attack_description": "有效攻击 1",
                        "success_conditions": "条件 1",
                        "supporting_evidence_ids": ["ev-001"],
                        "counter_measure": "反制 1",
                        "adversary_pivot_strategy": "切换 1",
                    },
                    {  # 无效：未知 target_issue_id
                        "attack_node_id": "atk-002",
                        "target_issue_id": "issue-GHOST",
                        "attack_description": "无效攻击",
                        "success_conditions": "条件",
                        "supporting_evidence_ids": ["ev-001"],
                        "counter_measure": "反制",
                        "adversary_pivot_strategy": "切换",
                    },
                    {  # 有效节点 2
                        "attack_node_id": "atk-003",
                        "target_issue_id": "issue-002",
                        "attack_description": "有效攻击 3",
                        "success_conditions": "条件 3",
                        "supporting_evidence_ids": ["ev-002"],
                        "counter_measure": "反制 3",
                        "adversary_pivot_strategy": "切换 3",
                    },
                    {  # 无效：空 supporting_evidence_ids
                        "attack_node_id": "atk-004",
                        "target_issue_id": "issue-003",
                        "attack_description": "无效攻击 4",
                        "success_conditions": "条件 4",
                        "supporting_evidence_ids": [],
                        "counter_measure": "反制 4",
                        "adversary_pivot_strategy": "切换 4",
                    },
                    {  # 有效节点 3
                        "attack_node_id": "atk-005",
                        "target_issue_id": "issue-003",
                        "attack_description": "有效攻击 5",
                        "success_conditions": "条件 5",
                        "supporting_evidence_ids": ["ev-001", "ev-002"],
                        "counter_measure": "反制 5",
                        "adversary_pivot_strategy": "切换 5",
                    },
                ],
            }
        )
        inp = _make_input(
            issue_ids=["issue-001", "issue-002", "issue-003"],
            evidence_ids=["ev-001", "ev-002"],
        )
        result = await _make_optimizer(response).optimize(inp)

        assert len(result.top_attacks) == 3
        ids = [n.attack_node_id for n in result.top_attacks]
        assert "atk-001" in ids
        assert "atk-003" in ids
        assert "atk-005" in ids
        assert "atk-002" not in ids  # unknown issue
        assert "atk-004" not in ids  # empty evidence
        # recommended_order 与 top_attacks 一致
        assert result.recommended_order == ids


# ---------------------------------------------------------------------------
# Opus 风格 LLM 输出归一化测试
# ---------------------------------------------------------------------------


class TestOpusStyleNormalization:
    """测试 Opus 风格 LLM 输出归一化。"""

    OPUS_FIXTURE = {
        "owner_party_id": "party-defendant-chen",
        "generated_at": "2026-03-29T14:01:00Z",
        "attack_chain": [
            {
                "attack_node_id": "atk-chen-001",
                "priority": 1,
                "attack_label": "实际借款人身份错位攻击",
                "attack_type": "factual_challenge",
                "core_logic": "真正借款人为老庄而非小陈，证据表明款项系老庄经营所需",
                "counter_to_plaintiff_evidence": {
                    "ev-plaintiff-001": "转账仅证明资金流向，不证明借贷合意"
                },
                "legal_basis": "民间借贷司法解释第十七条",
                "target_issue_id": "issue-001",
                "supporting_evidence_ids": ["ev-001", "ev-002"],
                "success_conditions": "法院采信老庄为实际借款人",
                "counter_measure": "原告可能补充借贷合意直接证据",
            },
            {
                "attack_node_id": "atk-chen-002",
                "priority": 2,
                "attack_label": "录音证据攻击——催款对象为老庄",
                "attack_type": "evidence_challenge",
                "core_logic": "催款短信和录音显示原告催款对象是老庄而非小陈",
                "counter_to_plaintiff_evidence": {},
                "legal_basis": "最高法证据规定",
                "target_issue_id": "issue-002",
                "supporting_evidence_ids": ["ev-002", "ev-003"],
                "success_conditions": "录音证据被法庭采信",
                "counter_measure": "原告可能质疑录音真实性",
            },
        ],
        "chain_synergy_note": "两个攻击节点形成递进关系",
    }

    def test_normalize_maps_attack_chain_to_top_attacks(self):
        """attack_chain → top_attacks"""
        data = copy.deepcopy(self.OPUS_FIXTURE)
        result = AttackChainOptimizer._normalize_llm_json(data)
        assert "top_attacks" in result
        assert len(result["top_attacks"]) == 2

    def test_normalize_combines_label_and_logic_to_description(self):
        """attack_label + core_logic → attack_description"""
        data = copy.deepcopy(self.OPUS_FIXTURE)
        result = AttackChainOptimizer._normalize_llm_json(data)
        desc = result["top_attacks"][0].get("attack_description", "")
        assert desc, "attack_description should be non-empty"
        # Should contain the core_logic text (the detailed description)
        assert "老庄" in desc or "借款人" in desc

    def test_normalize_preserves_target_issue_id(self):
        data = copy.deepcopy(self.OPUS_FIXTURE)
        result = AttackChainOptimizer._normalize_llm_json(data)
        assert result["top_attacks"][0]["target_issue_id"] == "issue-001"

    def test_normalize_preserves_supporting_evidence_ids(self):
        data = copy.deepcopy(self.OPUS_FIXTURE)
        result = AttackChainOptimizer._normalize_llm_json(data)
        assert result["top_attacks"][0]["supporting_evidence_ids"] == ["ev-001", "ev-002"]

    @pytest.mark.asyncio
    async def test_full_optimize_with_opus_output(self):
        """Full optimize() flow with Opus-style output produces non-empty attacks."""
        fixture = copy.deepcopy(self.OPUS_FIXTURE)
        response = json.dumps(fixture, ensure_ascii=False)
        inp = _make_input(
            issue_ids=["issue-001", "issue-002", "issue-003"],
            evidence_ids=["ev-001", "ev-002", "ev-003"],
        )
        opt = _make_optimizer(response)
        result = await opt.optimize(inp)
        assert isinstance(result, OptimalAttackChain)
        assert len(result.top_attacks) >= 1, (
            f"Expected non-empty attacks, got {len(result.top_attacks)}"
        )
        for node in result.top_attacks:
            assert node.attack_description, f"Node {node.attack_node_id} missing attack_description"
