"""
DecisionPathTreeGenerator 单元测试。
Unit tests for DecisionPathTreeGenerator.

测试策略：
- 不依赖真实 LLM；使用 stub LLM client 返回预定义 JSON
- 分层测试：规则层逻辑 → 完整 generate() 流程
- 覆盖所有合约保证（见 spec P0.3 约束）
"""

from __future__ import annotations

import copy
import json
from decimal import Decimal

import pytest

from engines.shared.models import (
    AccessDomain,
    AmountCalculationReport,
    AmountConflict,
    AmountConsistencyCheck,
    BlockingConditionType,
    ClaimCalculationEntry,
    ClaimType,
    DecisionPathTree,
    Evidence,
    EvidenceIndex,
    EvidenceStatus,
    EvidenceType,
    Issue,
    IssueStatus,
    IssueTree,
    IssueType,
    LoanTransaction,
    OutcomeImpact,
    RepaymentTransaction,
)
from engines.simulation_run.decision_path_tree.generator import DecisionPathTreeGenerator
from engines.simulation_run.decision_path_tree.schemas import DecisionPathTreeInput


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


def _make_issue(issue_id: str, evidence_ids: list[str] | None = None) -> Issue:
    return Issue(
        issue_id=issue_id,
        case_id="case-001",
        title=f"测试争点 {issue_id}",
        issue_type=IssueType.factual,
        status=IssueStatus.open,
        evidence_ids=evidence_ids or [],
        outcome_impact=OutcomeImpact.high,
    )


def _make_evidence(
    evidence_id: str,
    status: EvidenceStatus = EvidenceStatus.admitted_for_discussion,
) -> Evidence:
    domain = (
        AccessDomain.admitted_record
        if status == EvidenceStatus.admitted_for_discussion
        else AccessDomain.shared_common
        if status in (EvidenceStatus.submitted, EvidenceStatus.challenged)
        else AccessDomain.owner_private
    )
    return Evidence(
        evidence_id=evidence_id,
        case_id="case-001",
        owner_party_id="plaintiff-001",
        title=f"证据 {evidence_id}",
        source="测试来源",
        summary="测试证据摘要",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=["fact-001"],
        access_domain=domain,
        status=status,
    )


def _make_issue_tree(issue_ids: list[str], evidence_ids: list[str] | None = None) -> IssueTree:
    issues = [_make_issue(iid, evidence_ids=evidence_ids or []) for iid in issue_ids]
    return IssueTree(case_id="case-001", issues=issues)


def _make_evidence_index(
    evidence_ids: list[str],
    status: EvidenceStatus = EvidenceStatus.admitted_for_discussion,
) -> EvidenceIndex:
    return EvidenceIndex(
        case_id="case-001",
        evidence=[_make_evidence(eid, status=status) for eid in evidence_ids],
    )


def _make_amount_report(
    *,
    verdict_block_active: bool = False,
    conflicts: list[AmountConflict] | None = None,
) -> AmountCalculationReport:
    unresolved = conflicts or []
    return AmountCalculationReport(
        report_id="report-001",
        case_id="case-001",
        run_id="run-001",
        loan_transactions=[
            LoanTransaction(
                tx_id="tx-001",
                date="2023-01-01",
                amount=Decimal("100000"),
                evidence_id="ev-001",
                principal_base_contribution=True,
            )
        ],
        repayment_transactions=[
            RepaymentTransaction(
                tx_id="rtx-001",
                date="2023-06-01",
                amount=Decimal("10000"),
                evidence_id="ev-002",
                attributed_to="principal",
                attribution_basis="按协议归入本金",
            )
        ],
        claim_calculation_table=[
            ClaimCalculationEntry(
                claim_id="claim-001",
                claim_type=ClaimType.principal,
                claimed_amount=Decimal("90000"),
                calculated_amount=Decimal("90000"),
                delta=Decimal("0"),
                delta_explanation="",
            )
        ],
        consistency_check_result=AmountConsistencyCheck(
            principal_base_unique=True,
            all_repayments_attributed=True,
            text_table_amount_consistent=True,
            duplicate_interest_penalty_claim=False,
            claim_total_reconstructable=True,
            unresolved_conflicts=unresolved,
            verdict_block_active=verdict_block_active,
        ),
    )


def _make_input(
    issue_ids: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    *,
    verdict_block_active: bool = False,
    conflicts: list[AmountConflict] | None = None,
    evidence_status: EvidenceStatus = EvidenceStatus.admitted_for_discussion,
) -> DecisionPathTreeInput:
    iids = issue_ids or ["issue-001", "issue-002", "issue-003"]
    eids = evidence_ids or ["ev-001", "ev-002", "ev-003"]
    return DecisionPathTreeInput(
        case_id="case-001",
        run_id="run-001",
        ranked_issue_tree=_make_issue_tree(iids, evidence_ids=eids),
        evidence_index=_make_evidence_index(eids, status=evidence_status),
        amount_calculation_report=_make_amount_report(
            verdict_block_active=verdict_block_active,
            conflicts=conflicts,
        ),
    )


def _make_paths_json(
    path_count: int = 3,
    *,
    with_confidence: bool = True,
    issue_ids: list[str] | None = None,
    evidence_ids: list[str] | None = None,
) -> list[dict]:
    iids = issue_ids or ["issue-001"]
    eids = evidence_ids or ["ev-001"]
    paths = []
    for i in range(path_count):
        path: dict = {
            "path_id": f"path-{chr(65 + i)}",
            "trigger_condition": f"触发条件 {i + 1}",
            "trigger_issue_ids": iids,
            "key_evidence_ids": eids,
            "possible_outcome": f"裁判结果描述 {i + 1}",
            "path_notes": "",
            "confidence_interval": {"lower": 0.2, "upper": 0.6} if with_confidence else None,
        }
        paths.append(path)
    return paths


def _llm_response(
    path_count: int = 3,
    *,
    with_confidence: bool = True,
    issue_ids: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    blocking_conditions: list[dict] | None = None,
) -> str:
    return json.dumps(
        {
            "paths": _make_paths_json(
                path_count,
                with_confidence=with_confidence,
                issue_ids=issue_ids,
                evidence_ids=evidence_ids,
            ),
            "blocking_conditions": blocking_conditions or [],
        },
        ensure_ascii=False,
    )


def _make_generator(response: str, *, fail: bool = False) -> DecisionPathTreeGenerator:
    return DecisionPathTreeGenerator(
        llm_client=MockLLMClient(response, fail=fail),
        case_type="civil_loan",
        model="claude-test",
        temperature=0.0,
        max_retries=1,
    )


# ---------------------------------------------------------------------------
# 合约保证测试
# ---------------------------------------------------------------------------


class TestVerdictBlockSuppression:
    """verdict_block_active=True 时 confidence_interval 必须被清空。"""

    @pytest.mark.asyncio
    async def test_verdict_block_active_clears_all_confidence_intervals(self):
        """verdict_block_active=True → 所有路径的 confidence_interval 为 None。"""
        generator = _make_generator(_llm_response(3, with_confidence=True))
        result = await generator.generate(_make_input(verdict_block_active=True))

        assert isinstance(result, DecisionPathTree)
        assert len(result.paths) == 3
        for path in result.paths:
            assert path.confidence_interval is None, (
                f"{path.path_id} should have confidence_interval=None when verdict_block_active"
            )

    @pytest.mark.asyncio
    async def test_verdict_block_inactive_confidence_interval_none(self):
        """v3: confidence_interval は verdict_block_active に関わらず常に None（偽精度排除）。"""
        generator = _make_generator(_llm_response(3, with_confidence=True))
        result = await generator.generate(_make_input(verdict_block_active=False))

        assert all(p.confidence_interval is None for p in result.paths)

    @pytest.mark.asyncio
    async def test_verdict_block_inactive_null_confidence_also_none(self):
        """v3: LLM が confidence_interval を返さない場合も None のまま（フォールバック不要）。"""
        generator = _make_generator(_llm_response(3, with_confidence=False))
        result = await generator.generate(_make_input(verdict_block_active=False))

        assert all(p.confidence_interval is None for p in result.paths)


class TestPathCountHandling:
    """路径数量处理：>6 截断，正常范围完整保留。"""

    @pytest.mark.asyncio
    async def test_paths_exceeding_6_are_truncated_to_6(self):
        """LLM 返回 7 条路径时截断至 6 条。"""
        result = await _make_generator(_llm_response(7)).generate(_make_input())
        assert len(result.paths) == 6

    @pytest.mark.asyncio
    async def test_exactly_6_paths_are_preserved(self):
        """LLM 返回 6 条路径时全部保留。"""
        result = await _make_generator(_llm_response(6)).generate(_make_input())
        assert len(result.paths) == 6

    @pytest.mark.asyncio
    async def test_exactly_3_paths_are_preserved(self):
        """LLM 返回 3 条路径时全部保留（spec 推荐下限）。"""
        result = await _make_generator(_llm_response(3)).generate(_make_input())
        assert len(result.paths) == 3

    @pytest.mark.asyncio
    async def test_fewer_than_3_paths_returned_as_is(self):
        """LLM 返回 2 条路径时原样返回（spec 建议不足但不硬阻断）。"""
        result = await _make_generator(_llm_response(2)).generate(_make_input())
        assert len(result.paths) == 2


class TestIDValidation:
    """非法 issue_id 和 evidence_id 过滤。"""

    @pytest.mark.asyncio
    async def test_unknown_evidence_ids_filtered_from_paths(self):
        """paths.key_evidence_ids 中不在证据索引的 ID 被过滤。"""
        response = json.dumps(
            {
                "paths": [
                    {
                        "path_id": "path-A",
                        "trigger_condition": "触发条件",
                        "trigger_issue_ids": ["issue-001"],
                        "key_evidence_ids": ["ev-001", "ev-UNKNOWN"],
                        "possible_outcome": "结果描述",
                        "confidence_interval": None,
                        "path_notes": "",
                    }
                ],
                "blocking_conditions": [],
            }
        )
        inp = _make_input(evidence_ids=["ev-001"])
        result = await _make_generator(response).generate(inp)

        assert len(result.paths) == 1
        assert "ev-UNKNOWN" not in result.paths[0].key_evidence_ids
        assert "ev-001" in result.paths[0].key_evidence_ids

    @pytest.mark.asyncio
    async def test_unknown_issue_ids_filtered_from_trigger(self):
        """trigger_issue_ids 中不在争点树的 ID 被过滤。"""
        response = json.dumps(
            {
                "paths": [
                    {
                        "path_id": "path-A",
                        "trigger_condition": "触发条件",
                        "trigger_issue_ids": ["issue-001", "issue-UNKNOWN"],
                        "key_evidence_ids": ["ev-001"],
                        "possible_outcome": "结果描述",
                        "confidence_interval": None,
                        "path_notes": "",
                    }
                ],
                "blocking_conditions": [],
            }
        )
        inp = _make_input(issue_ids=["issue-001"], evidence_ids=["ev-001"])
        result = await _make_generator(response).generate(inp)

        assert len(result.paths) == 1
        assert "issue-UNKNOWN" not in result.paths[0].trigger_issue_ids
        assert "issue-001" in result.paths[0].trigger_issue_ids

    @pytest.mark.asyncio
    async def test_unknown_ids_filtered_from_blocking_conditions(self):
        """blocking_conditions 中的非法 issue_id 和 evidence_id 被过滤。"""
        response = json.dumps(
            {
                "paths": _make_paths_json(3, issue_ids=["issue-001"], evidence_ids=["ev-001"]),
                "blocking_conditions": [
                    {
                        "condition_id": "bc-001",
                        "condition_type": "amount_conflict",
                        "description": "本金口径冲突",
                        "linked_issue_ids": ["issue-001", "issue-GHOST"],
                        "linked_evidence_ids": ["ev-001", "ev-GHOST"],
                    }
                ],
            }
        )
        inp = _make_input(
            issue_ids=["issue-001", "issue-002", "issue-003"],
            evidence_ids=["ev-001", "ev-002", "ev-003"],
        )
        result = await _make_generator(response).generate(inp)

        assert len(result.blocking_conditions) == 1
        bc = result.blocking_conditions[0]
        assert "issue-GHOST" not in bc.linked_issue_ids
        assert "ev-GHOST" not in bc.linked_evidence_ids
        assert "issue-001" in bc.linked_issue_ids
        assert "ev-001" in bc.linked_evidence_ids

    @pytest.mark.asyncio
    async def test_invalid_blocking_condition_type_is_skipped(self):
        """blocking_conditions 中 condition_type 不合法的条目被丢弃。"""
        response = json.dumps(
            {
                "paths": _make_paths_json(3, issue_ids=["issue-001"], evidence_ids=["ev-001"]),
                "blocking_conditions": [
                    {
                        "condition_id": "bc-valid",
                        "condition_type": "evidence_gap",
                        "description": "缺少关键证据",
                        "linked_issue_ids": [],
                        "linked_evidence_ids": [],
                    },
                    {
                        "condition_id": "bc-invalid",
                        "condition_type": "NONEXISTENT_TYPE",
                        "description": "非法枚举类型",
                        "linked_issue_ids": [],
                        "linked_evidence_ids": [],
                    },
                ],
            }
        )
        inp = _make_input(
            issue_ids=["issue-001", "issue-002", "issue-003"],
            evidence_ids=["ev-001", "ev-002", "ev-003"],
        )
        result = await _make_generator(response).generate(inp)

        assert len(result.blocking_conditions) == 1
        assert result.blocking_conditions[0].condition_id == "bc-valid"


class TestV15StrictAdmittedOnly:
    """v1.5: 只有 admitted_for_discussion 的证据进入裁判路径树。"""

    @pytest.mark.asyncio
    async def test_only_admitted_evidence_in_llm_prompt(self):
        """只有 admitted_for_discussion 的证据出现在传给 LLM 的证据集合中。"""
        mock = MockLLMClient(_llm_response(3))
        generator = DecisionPathTreeGenerator(
            llm_client=mock,
            case_type="civil_loan",
            model="claude-test",
            temperature=0.0,
            max_retries=1,
        )
        mixed_index = EvidenceIndex(
            case_id="case-001",
            evidence=[
                _make_evidence("ev-admitted", status=EvidenceStatus.admitted_for_discussion),
                _make_evidence("ev-private", status=EvidenceStatus.private),
                _make_evidence("ev-submitted", status=EvidenceStatus.submitted),
                _make_evidence("ev-challenged", status=EvidenceStatus.challenged),
            ],
        )
        inp = DecisionPathTreeInput(
            case_id="case-001",
            run_id="run-001",
            ranked_issue_tree=_make_issue_tree(["issue-001"]),
            evidence_index=mixed_index,
            amount_calculation_report=_make_amount_report(),
        )

        await generator.generate(inp)

        assert "ev-admitted" in mock.last_user
        assert "ev-private" not in mock.last_user
        assert "ev-submitted" not in mock.last_user
        assert "ev-challenged" not in mock.last_user

    @pytest.mark.asyncio
    async def test_non_admitted_evidence_id_filtered_from_known_ids(self):
        """非 admitted 证据的 ID 在规则层过滤中也被排除。"""
        response = json.dumps(
            {
                "paths": [
                    {
                        "path_id": "path-A",
                        "trigger_condition": "触发条件",
                        "trigger_issue_ids": [],
                        "key_evidence_ids": ["ev-admitted", "ev-submitted"],
                        "possible_outcome": "结果描述",
                        "confidence_interval": None,
                        "path_notes": "",
                    }
                ],
                "blocking_conditions": [],
            }
        )
        mixed_index = EvidenceIndex(
            case_id="case-001",
            evidence=[
                _make_evidence("ev-admitted", status=EvidenceStatus.admitted_for_discussion),
                _make_evidence("ev-submitted", status=EvidenceStatus.submitted),
            ],
        )
        inp = DecisionPathTreeInput(
            case_id="case-001",
            run_id="run-001",
            ranked_issue_tree=_make_issue_tree(["issue-001"]),
            evidence_index=mixed_index,
            amount_calculation_report=_make_amount_report(),
        )
        result = await _make_generator(response).generate(inp)

        assert len(result.paths) == 1
        assert "ev-submitted" not in result.paths[0].key_evidence_ids
        assert "ev-admitted" in result.paths[0].key_evidence_ids


class TestAutoInjectBlockingConditions:
    """从 AmountConsistencyCheck.unresolved_conflicts 自动注入 BlockingCondition。"""

    @pytest.mark.asyncio
    async def test_auto_inject_amount_conflict_from_unresolved(self):
        """unresolved_conflicts 有 1 条，LLM 未生成 blocking_condition，规则层自动注入 1 条。"""
        conflict = AmountConflict(
            conflict_id="conflict-001",
            conflict_description="本金基数口径冲突：借款合同写 10 万，但转账记录实际 9.5 万",
            amount_a=Decimal("100000"),
            amount_b=Decimal("95000"),
            source_a_evidence_id="ev-001",
            source_b_evidence_id="ev-002",
            resolution_note="",
        )
        # LLM 没有生成任何 blocking_condition
        response = json.dumps(
            {
                "paths": _make_paths_json(3, issue_ids=["issue-001"], evidence_ids=["ev-001"]),
                "blocking_conditions": [],
            }
        )
        inp = _make_input(
            evidence_ids=["ev-001", "ev-002", "ev-003"],
            verdict_block_active=True,
            conflicts=[conflict],
        )
        result = await _make_generator(response).generate(inp)

        amount_conflicts = [
            bc
            for bc in result.blocking_conditions
            if bc.condition_type == BlockingConditionType.amount_conflict
        ]
        assert len(amount_conflicts) == 1
        auto_bc = amount_conflicts[0]
        assert "ev-001" in auto_bc.linked_evidence_ids
        assert "ev-002" in auto_bc.linked_evidence_ids

    @pytest.mark.asyncio
    async def test_llm_generated_and_auto_injected_both_present(self):
        """LLM 已生成 1 条 amount_conflict，规则层再自动注入 1 条不同的（共 2 条）。"""
        conflict = AmountConflict(
            conflict_id="conflict-001",
            conflict_description="口径冲突",
            amount_a=Decimal("100000"),
            amount_b=Decimal("95000"),
            source_a_evidence_id="ev-001",
            source_b_evidence_id="ev-002",
            resolution_note="",
        )
        # LLM 生成了一条，但 condition_id 与自动注入的不同
        response = json.dumps(
            {
                "paths": _make_paths_json(3, issue_ids=["issue-001"], evidence_ids=["ev-001"]),
                "blocking_conditions": [
                    {
                        "condition_id": "bc-llm-001",  # 不以 "bc-auto-" 开头，不冲突
                        "condition_type": "amount_conflict",
                        "description": "LLM 发现的本金冲突",
                        "linked_issue_ids": [],
                        "linked_evidence_ids": ["ev-001"],
                    }
                ],
            }
        )
        inp = _make_input(
            evidence_ids=["ev-001", "ev-002", "ev-003"],
            verdict_block_active=True,
            conflicts=[conflict],
        )
        result = await _make_generator(response).generate(inp)

        # LLM 1 条 + 自动注入 1 条 = 2 条
        amount_conflicts = [
            bc
            for bc in result.blocking_conditions
            if bc.condition_type == BlockingConditionType.amount_conflict
        ]
        assert len(amount_conflicts) == 2
        ids = {bc.condition_id for bc in amount_conflicts}
        assert "bc-llm-001" in ids
        assert "bc-auto-conflict-001" in ids


class TestLLMFailureHandling:
    """LLM 调用失败时返回空 DecisionPathTree，不抛异常。"""

    @pytest.mark.asyncio
    async def test_llm_failure_returns_empty_tree(self):
        """LLM 抛出异常时，generate() 不抛异常，返回空 DecisionPathTree。"""
        result = await _make_generator("", fail=True).generate(_make_input())

        assert isinstance(result, DecisionPathTree)
        assert result.paths == []
        assert result.case_id == "case-001"

    @pytest.mark.asyncio
    async def test_llm_invalid_json_returns_empty_tree(self):
        """LLM 返回非法 JSON 时，generate() 返回空 DecisionPathTree。"""
        result = await _make_generator("这不是 JSON").generate(_make_input())

        assert isinstance(result, DecisionPathTree)
        assert result.paths == []


class TestConfidenceIntervalValidation:
    """置信度区間バリデーション（v3: CI は常に None）。"""

    @pytest.mark.asyncio
    async def test_confidence_interval_always_none_regardless_of_llm_input(self):
        """v3: LLM が無効な confidence_interval を返しても常に None（偽精度排除）。"""
        response = json.dumps(
            {
                "paths": [
                    {
                        "path_id": "path-A",
                        "trigger_condition": "触发条件",
                        "trigger_issue_ids": ["issue-001"],
                        "key_evidence_ids": ["ev-001"],
                        "possible_outcome": "结果描述",
                        "confidence_interval": {
                            "lower": 0.8,
                            "upper": 0.2,
                        },  # invalid: lower > upper — ignored anyway in v3
                        "path_notes": "",
                    }
                ],
                "blocking_conditions": [],
            }
        )
        result = await _make_generator(response).generate(_make_input(verdict_block_active=False))

        assert result.paths[0].confidence_interval is None

    @pytest.mark.asyncio
    async def test_valid_confidence_interval_also_none(self):
        """v3: 有効な CI でも None になる（偽精度排除）。"""
        response = json.dumps(
            {
                "paths": [
                    {
                        "path_id": "path-A",
                        "trigger_condition": "触发条件",
                        "trigger_issue_ids": ["issue-001"],
                        "key_evidence_ids": ["ev-001"],
                        "possible_outcome": "结果描述",
                        "confidence_interval": {"lower": 0.3, "upper": 0.7},
                        "path_notes": "",
                    }
                ],
                "blocking_conditions": [],
            }
        )
        result = await _make_generator(response).generate(_make_input(verdict_block_active=False))

        assert result.paths[0].confidence_interval is None


class TestGeneratorMetadata:
    """产物元信息测试。"""

    @pytest.mark.asyncio
    async def test_result_contains_case_and_run_ids(self):
        """结果包含正确的 case_id 和 run_id。"""
        result = await _make_generator(_llm_response(3)).generate(_make_input())

        assert result.case_id == "case-001"
        assert result.run_id == "run-001"
        assert result.tree_id  # non-empty
        assert result.created_at  # non-empty

    @pytest.mark.asyncio
    async def test_prompt_includes_verdict_block_status(self):
        """user prompt 中包含 verdict_block_active 状态信息。"""
        mock = MockLLMClient(_llm_response(3))
        generator = DecisionPathTreeGenerator(
            llm_client=mock,
            case_type="civil_loan",
            model="claude-test",
            temperature=0.0,
            max_retries=1,
        )
        await generator.generate(_make_input(verdict_block_active=True))

        assert "verdict_block_active: True" in mock.last_user


class TestEvidencePolarity:
    """证据极性分离：key_evidence_ids（支持）vs counter_evidence_ids（反驳）。"""

    @pytest.mark.asyncio
    async def test_counter_evidence_ids_populated_and_filtered(self):
        """LLM 返回 counter_evidence_ids → 过滤非法 ID 后保留在结果中。"""
        response = json.dumps(
            {
                "paths": [
                    {
                        "path_id": "path-A",
                        "trigger_condition": "法院认定借贷关系成立",
                        "trigger_issue_ids": ["issue-001"],
                        "key_evidence_ids": ["ev-001"],
                        "counter_evidence_ids": ["ev-002", "ev-UNKNOWN"],
                        "possible_outcome": "支持原告",
                        "confidence_interval": {"lower": 0.3, "upper": 0.6},
                        "path_notes": "",
                    }
                ],
                "blocking_conditions": [],
            }
        )
        inp = _make_input(evidence_ids=["ev-001", "ev-002", "ev-003"])
        result = await _make_generator(response).generate(inp)

        assert len(result.paths) == 1
        path = result.paths[0]
        assert "ev-001" in path.key_evidence_ids
        assert "ev-002" in path.counter_evidence_ids
        assert "ev-UNKNOWN" not in path.counter_evidence_ids

    @pytest.mark.asyncio
    async def test_overlap_between_key_and_counter_removed(self):
        """同一证据不得同时出现在 key_evidence_ids 和 counter_evidence_ids 中。"""
        response = json.dumps(
            {
                "paths": [
                    {
                        "path_id": "path-A",
                        "trigger_condition": "法院认定借贷关系成立",
                        "trigger_issue_ids": ["issue-001"],
                        "key_evidence_ids": ["ev-001", "ev-002"],
                        "counter_evidence_ids": ["ev-002", "ev-003"],  # ev-002 重叠
                        "possible_outcome": "支持原告",
                        "confidence_interval": {"lower": 0.3, "upper": 0.6},
                        "path_notes": "",
                    }
                ],
                "blocking_conditions": [],
            }
        )
        inp = _make_input(evidence_ids=["ev-001", "ev-002", "ev-003"])
        result = await _make_generator(response).generate(inp)

        assert len(result.paths) == 1
        path = result.paths[0]
        # ev-002 is in key_evidence_ids → must NOT be in counter_evidence_ids
        assert "ev-002" in path.key_evidence_ids
        assert "ev-002" not in path.counter_evidence_ids
        # ev-003 is only in counter → should be there
        assert "ev-003" in path.counter_evidence_ids

    @pytest.mark.asyncio
    async def test_counter_evidence_ids_empty_by_default(self):
        """LLM 未返回 counter_evidence_ids 时，结果中该字段为空列表。"""
        inp = _make_input(evidence_ids=["ev-001", "ev-002", "ev-003"])
        result = await _make_generator(_llm_response(3)).generate(inp)

        for path in result.paths:
            assert path.counter_evidence_ids == []

    @pytest.mark.asyncio
    async def test_counter_evidence_alias_normalization(self):
        """LLM 使用别名 'counter_evidence' → 归一化为 counter_evidence_ids。"""
        response = json.dumps(
            {
                "paths": [
                    {
                        "path_id": "path-A",
                        "trigger_condition": "法院认定借贷关系成立",
                        "trigger_issue_ids": ["issue-001"],
                        "key_evidence_ids": ["ev-001"],
                        "counter_evidence": ["ev-002"],  # alias, not counter_evidence_ids
                        "possible_outcome": "支持原告",
                        "confidence_interval": {"lower": 0.3, "upper": 0.6},
                        "path_notes": "",
                    }
                ],
                "blocking_conditions": [],
            }
        )
        inp = _make_input(evidence_ids=["ev-001", "ev-002", "ev-003"])
        result = await _make_generator(response).generate(inp)

        assert len(result.paths) == 1
        assert "ev-002" in result.paths[0].counter_evidence_ids

    @pytest.mark.asyncio
    async def test_key_evidence_not_contaminated_by_counter(self):
        """key_evidence_ids 只含支持证据，LLM 误放的反驳证据不污染 key_evidence_ids。"""
        # Simulates the v07 bug: path-D had ev-defendant-006 (contradicting evidence)
        # listed in key_evidence_ids. With proper prompting, LLM should put it in
        # counter_evidence_ids instead. Here we test that if LLM correctly separates them,
        # the generator preserves the separation.
        response = json.dumps(
            {
                "paths": [
                    {
                        "path_id": "path-D",
                        "trigger_condition": "法院认定三方当面达成借款合意",
                        "trigger_issue_ids": ["issue-001"],
                        "key_evidence_ids": ["ev-001", "ev-002"],  # supporting evidence
                        "counter_evidence_ids": [
                            "ev-defendant-006"
                        ],  # ev-defendant-006: 小陈已离场，反驳三方面谈
                        "possible_outcome": "部分支持原告，连带责任",
                        "confidence_interval": {"lower": 0.1, "upper": 0.25},
                        "path_notes": "",
                    }
                ],
                "blocking_conditions": [],
            }
        )
        inp = _make_input(
            evidence_ids=["ev-001", "ev-002", "ev-defendant-006"],
        )
        result = await _make_generator(response).generate(inp)

        assert len(result.paths) == 1
        path = result.paths[0]
        assert "ev-defendant-006" not in path.key_evidence_ids
        assert "ev-defendant-006" in path.counter_evidence_ids


class TestPathProbabilityRanking:
    """v1.6: 路径概率排名测试。"""

    def _llm_response_with_probabilities(
        self,
        paths_spec: list[dict],
    ) -> str:
        """构造带有概率字段的 LLM 响应 JSON。"""
        paths = []
        for i, spec in enumerate(paths_spec):
            paths.append(
                {
                    "path_id": spec.get("path_id", f"path-{chr(65 + i)}"),
                    "trigger_condition": spec.get("trigger_condition", f"触发条件 {i + 1}"),
                    "trigger_issue_ids": spec.get("trigger_issue_ids", ["issue-001"]),
                    "key_evidence_ids": spec.get("key_evidence_ids", ["ev-001"]),
                    "possible_outcome": spec.get("possible_outcome", f"裁判结果 {i + 1}"),
                    "confidence_interval": {"lower": 0.2, "upper": 0.6},
                    "path_notes": "",
                    "probability": spec.get("probability", 0.5),
                    "probability_rationale": spec.get("probability_rationale", "测试依据"),
                    "party_favored": spec.get("party_favored", "neutral"),
                }
            )
        return json.dumps({"paths": paths, "blocking_conditions": []}, ensure_ascii=False)

    @pytest.mark.asyncio
    async def test_most_likely_path_is_first_ranked(self):
        """v3: most_likely_path は新ソート（plaintiff優先→証拠数→path_id）の先頭パス。"""
        response = self._llm_response_with_probabilities(
            [
                {"path_id": "path-A", "probability": 0.3, "party_favored": "plaintiff"},
                {"path_id": "path-B", "probability": 0.6, "party_favored": "defendant"},
                {"path_id": "path-C", "probability": 0.1, "party_favored": "neutral"},
            ]
        )
        result = await _make_generator(response).generate(_make_input())

        # plaintiff paths rank first → path-A
        assert result.most_likely_path == "path-A"

    @pytest.mark.asyncio
    async def test_plaintiff_best_path_is_first_plaintiff_in_ranked_order(self):
        """v3: plaintiff_best_path は ranked リスト中の最初の plaintiff パス。"""
        response = self._llm_response_with_probabilities(
            [
                {"path_id": "path-A", "probability": 0.4, "party_favored": "plaintiff"},
                {"path_id": "path-B", "probability": 0.7, "party_favored": "defendant"},
                {"path_id": "path-C", "probability": 0.55, "party_favored": "plaintiff"},
            ]
        )
        result = await _make_generator(response).generate(_make_input())

        # Both path-A and path-C are plaintiff; equal evidence count → alphabetical → path-A first
        assert result.plaintiff_best_path == "path-A"

    @pytest.mark.asyncio
    async def test_defendant_best_path_is_first_defendant_in_ranked_order(self):
        """v3: defendant_best_path は ranked リスト中の最初の defendant パス。"""
        response = self._llm_response_with_probabilities(
            [
                {"path_id": "path-A", "probability": 0.4, "party_favored": "plaintiff"},
                {"path_id": "path-B", "probability": 0.5, "party_favored": "defendant"},
                {"path_id": "path-C", "probability": 0.3, "party_favored": "defendant"},
            ]
        )
        result = await _make_generator(response).generate(_make_input())

        # path-B and path-C both defendant; equal evidence → alphabetical → path-B first
        assert result.defendant_best_path == "path-B"

    @pytest.mark.asyncio
    async def test_path_ranking_sorted_by_party_then_evidence_then_id(self):
        """v3: path_ranking は plaintiff→defendant→neutral、次に証拠数降順、次に path_id 昇順。"""
        response = self._llm_response_with_probabilities(
            [
                {"path_id": "path-A", "probability": 0.2, "party_favored": "plaintiff"},
                {"path_id": "path-B", "probability": 0.7, "party_favored": "defendant"},
                {"path_id": "path-C", "probability": 0.5, "party_favored": "neutral"},
            ]
        )
        result = await _make_generator(response).generate(_make_input())

        assert len(result.path_ranking) == 3
        # plaintiff first, then defendant, then neutral
        assert result.path_ranking[0].path_id == "path-A"
        assert result.path_ranking[1].path_id == "path-B"
        assert result.path_ranking[2].path_id == "path-C"

    @pytest.mark.asyncio
    async def test_path_ranking_contains_correct_party_favored(self):
        """path_ranking 条目的 party_favored 与路径一致。"""
        response = self._llm_response_with_probabilities(
            [
                {"path_id": "path-A", "probability": 0.4, "party_favored": "plaintiff"},
                {"path_id": "path-B", "probability": 0.6, "party_favored": "defendant"},
            ]
        )
        result = await _make_generator(response).generate(_make_input())

        by_id = {r.path_id: r for r in result.path_ranking}
        assert by_id["path-A"].party_favored == "plaintiff"
        assert by_id["path-B"].party_favored == "defendant"

    @pytest.mark.asyncio
    async def test_plaintiff_best_path_none_when_no_plaintiff_paths(self):
        """没有 plaintiff 路径时 plaintiff_best_path 为 None。"""
        response = self._llm_response_with_probabilities(
            [
                {"path_id": "path-A", "probability": 0.6, "party_favored": "defendant"},
                {"path_id": "path-B", "probability": 0.4, "party_favored": "neutral"},
            ]
        )
        result = await _make_generator(response).generate(_make_input())

        assert result.plaintiff_best_path is None

    @pytest.mark.asyncio
    async def test_path_probability_rationale_always_empty(self):
        """v3: probability_rationale は常に空文字列（偽精度排除）。"""
        response = self._llm_response_with_probabilities(
            [
                {
                    "path_id": "path-A",
                    "probability": 0.6,
                    "party_favored": "plaintiff",
                    "probability_rationale": "直接转账凭证支撑，主体认定清晰",
                },
            ]
        )
        result = await _make_generator(response).generate(_make_input())

        assert len(result.paths) == 1
        assert result.paths[0].probability_rationale == ""

    @pytest.mark.asyncio
    async def test_party_favored_normalised_to_known_values(self):
        """party_favored 归一化：'原告' → 'plaintiff', '被告' → 'defendant', 其他 → 'neutral'。"""
        response = json.dumps(
            {
                "paths": [
                    {
                        "path_id": "path-A",
                        "trigger_condition": "触发",
                        "trigger_issue_ids": ["issue-001"],
                        "key_evidence_ids": ["ev-001"],
                        "possible_outcome": "结果",
                        "confidence_interval": {"lower": 0.2, "upper": 0.6},
                        "path_notes": "",
                        "probability": 0.5,
                        "probability_rationale": "",
                        "party_favored": "原告",
                    },
                    {
                        "path_id": "path-B",
                        "trigger_condition": "触发",
                        "trigger_issue_ids": ["issue-001"],
                        "key_evidence_ids": ["ev-001"],
                        "possible_outcome": "结果",
                        "confidence_interval": {"lower": 0.2, "upper": 0.6},
                        "path_notes": "",
                        "probability": 0.3,
                        "probability_rationale": "",
                        "party_favored": "被告",
                    },
                    {
                        "path_id": "path-C",
                        "trigger_condition": "触发",
                        "trigger_issue_ids": ["issue-001"],
                        "key_evidence_ids": ["ev-001"],
                        "possible_outcome": "结果",
                        "confidence_interval": {"lower": 0.2, "upper": 0.6},
                        "path_notes": "",
                        "probability": 0.2,
                        "probability_rationale": "",
                        "party_favored": "unknown_value",
                    },
                ],
                "blocking_conditions": [],
            },
            ensure_ascii=False,
        )
        result = await _make_generator(response).generate(_make_input())

        by_id = {p.path_id: p for p in result.paths}
        assert by_id["path-A"].party_favored == "plaintiff"
        assert by_id["path-B"].party_favored == "defendant"
        assert by_id["path-C"].party_favored == "neutral"

    @pytest.mark.asyncio
    async def test_empty_paths_produces_empty_ranking(self):
        """LLM 失败时路径为空，ranking 也为空，比较字段为 None。"""
        result = await _make_generator("", fail=True).generate(_make_input())

        assert result.most_likely_path is None
        assert result.plaintiff_best_path is None
        assert result.defendant_best_path is None
        assert result.path_ranking == []

    @pytest.mark.asyncio
    async def test_compute_path_ranking_static_method_directly(self):
        """v3: _compute_path_ranking — plaintiff paths rank before defendant paths."""
        from engines.shared.models import DecisionPath

        paths = [
            DecisionPath(
                path_id="p1",
                trigger_condition="条件1",
                possible_outcome="结果1",
                probability=0.3,
                party_favored="plaintiff",
            ),
            DecisionPath(
                path_id="p2",
                trigger_condition="条件2",
                possible_outcome="结果2",
                probability=0.7,
                party_favored="defendant",
            ),
        ]
        ranking = DecisionPathTreeGenerator._compute_path_ranking(paths)

        # plaintiff-favored path ranks first regardless of old probability values
        assert ranking["most_likely_path"] == "p1"
        assert ranking["plaintiff_best_path"] == "p1"
        assert ranking["defendant_best_path"] == "p2"
        assert ranking["path_ranking"][0].path_id == "p1"
        assert ranking["path_ranking"][1].path_id == "p2"


class TestOpusStyleNormalization:
    """测试 Opus 风格 LLM 输出归一化。"""

    # The Opus-style fixture as a class-level constant
    OPUS_FIXTURE = {
        "case_id": "case-civil-loan-wang-v-chen-zhuang-2025",
        "generation_timestamp": "2026-03-29T14:01:00Z",
        "meta": {"model": "claude-opus-4-6"},
        "decision_paths": [
            {
                "path_id": "DP-001",
                "probability_label": "中等",
                "outcome_type": "全额支持",
                "narrative": "法院认定小陈系实际借款人，判令返还全部本金200000元及资金占用利息。",
                "branch_sequence": [
                    {
                        "step": 1,
                        "issue_id": "issue-001",
                        "evidence": ["ev-001", "ev-002"],
                        "reasoning": "借贷合意成立",
                    },
                    {
                        "step": 2,
                        "issue_id": "issue-002",
                        "evidence": ["ev-003"],
                        "reasoning": "款项交付确认",
                    },
                ],
                "judgment_projection": {
                    "principal": 200000,
                    "interest": True,
                    "costs_borne_by": "defendant",
                },
                "trigger_condition": "全额支持——小陈系实际借款人，返还本金20万元并赔偿资金占用损失",
            },
            {
                "path_id": "DP-002",
                "probability_label": "较高",
                "outcome_type": "驳回全部诉请",
                "narrative": "法院认定实际借款人为老庄，小陈仅为代收款人。",
                "branch_sequence": [
                    {
                        "step": 1,
                        "issue_id": "issue-002",
                        "evidence": ["ev-002"],
                        "reasoning": "主体不适格",
                    },
                ],
                "judgment_projection": {"principal": 0},
                "trigger_condition": "驳回全部诉请——实际借款人系老庄，小陈仅为代收款人",
            },
        ],
        "path_comparison_matrix": {},
        "strategic_advisory": "建议原告补强借贷合意直接证据",
    }

    def test_normalize_llm_json_maps_decision_paths(self):
        """decision_paths → paths"""
        data = copy.deepcopy(self.OPUS_FIXTURE)
        result = DecisionPathTreeGenerator._normalize_llm_json(data)
        assert "paths" in result
        assert len(result["paths"]) == 2

    def test_normalize_maps_narrative_to_possible_outcome(self):
        """narrative → possible_outcome"""
        data = copy.deepcopy(self.OPUS_FIXTURE)
        result = DecisionPathTreeGenerator._normalize_llm_json(data)
        assert result["paths"][0].get("possible_outcome")
        assert "实际借款人" in result["paths"][0]["possible_outcome"]

    def test_normalize_maps_probability_label_to_confidence_interval(self):
        """probability_label → confidence_interval"""
        data = copy.deepcopy(self.OPUS_FIXTURE)
        result = DecisionPathTreeGenerator._normalize_llm_json(data)
        ci = result["paths"][0].get("confidence_interval")
        assert ci is not None
        assert "lower" in ci and "upper" in ci

    def test_normalize_extracts_issue_ids_from_branch_sequence(self):
        """branch_sequence[].issue_id → trigger_issue_ids"""
        data = copy.deepcopy(self.OPUS_FIXTURE)
        result = DecisionPathTreeGenerator._normalize_llm_json(data)
        # Should extract issue IDs from branch_sequence
        issue_ids = result["paths"][0].get("trigger_issue_ids", [])
        assert len(issue_ids) >= 1  # at least some extracted

    def test_normalize_extracts_evidence_ids_from_branch_sequence(self):
        """branch_sequence[].evidence → key_evidence_ids"""
        data = copy.deepcopy(self.OPUS_FIXTURE)
        result = DecisionPathTreeGenerator._normalize_llm_json(data)
        ev_ids = result["paths"][0].get("key_evidence_ids", [])
        assert len(ev_ids) >= 1

    @pytest.mark.asyncio
    async def test_full_generate_with_opus_output(self):
        """Full generate() flow with Opus-style output produces non-empty paths."""
        fixture = copy.deepcopy(self.OPUS_FIXTURE)
        response = json.dumps(fixture, ensure_ascii=False)
        # Use issue/evidence IDs that match the fixture
        inp = _make_input(
            issue_ids=["issue-001", "issue-002", "issue-003"],
            evidence_ids=["ev-001", "ev-002", "ev-003"],
        )
        gen = DecisionPathTreeGenerator(
            llm_client=MockLLMClient(response),
            case_type="civil_loan",
            model="test",
            temperature=0.0,
            max_retries=1,
        )
        result = await gen.generate(inp)
        assert isinstance(result, DecisionPathTree)
        assert len(result.paths) >= 1, f"Expected non-empty paths, got {len(result.paths)}"
        # Each path should have trigger_condition and possible_outcome
        for path in result.paths:
            assert path.trigger_condition, f"Path {path.path_id} missing trigger_condition"
            assert path.possible_outcome, f"Path {path.path_id} missing possible_outcome"
