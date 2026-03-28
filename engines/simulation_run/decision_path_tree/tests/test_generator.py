"""
DecisionPathTreeGenerator 单元测试。
Unit tests for DecisionPathTreeGenerator.

测试策略：
- 不依赖真实 LLM；使用 stub LLM client 返回预定义 JSON
- 分层测试：规则层逻辑 → 完整 generate() 流程
- 覆盖所有合约保证（见 spec P0.3 约束）
"""
from __future__ import annotations

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
    return json.dumps({
        "paths": _make_paths_json(
            path_count,
            with_confidence=with_confidence,
            issue_ids=issue_ids,
            evidence_ids=evidence_ids,
        ),
        "blocking_conditions": blocking_conditions or [],
    }, ensure_ascii=False)


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
    async def test_verdict_block_inactive_preserves_confidence_interval(self):
        """verdict_block_active=False → confidence_interval 保留。"""
        generator = _make_generator(_llm_response(3, with_confidence=True))
        result = await generator.generate(_make_input(verdict_block_active=False))

        assert all(p.confidence_interval is not None for p in result.paths)

    @pytest.mark.asyncio
    async def test_verdict_block_inactive_null_confidence_stays_null(self):
        """verdict_block_active=False 时 LLM 返回 null confidence 不被覆盖。"""
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
        response = json.dumps({
            "paths": [{
                "path_id": "path-A",
                "trigger_condition": "触发条件",
                "trigger_issue_ids": ["issue-001"],
                "key_evidence_ids": ["ev-001", "ev-UNKNOWN"],
                "possible_outcome": "结果描述",
                "confidence_interval": None,
                "path_notes": "",
            }],
            "blocking_conditions": [],
        })
        inp = _make_input(evidence_ids=["ev-001"])
        result = await _make_generator(response).generate(inp)

        assert len(result.paths) == 1
        assert "ev-UNKNOWN" not in result.paths[0].key_evidence_ids
        assert "ev-001" in result.paths[0].key_evidence_ids

    @pytest.mark.asyncio
    async def test_unknown_issue_ids_filtered_from_trigger(self):
        """trigger_issue_ids 中不在争点树的 ID 被过滤。"""
        response = json.dumps({
            "paths": [{
                "path_id": "path-A",
                "trigger_condition": "触发条件",
                "trigger_issue_ids": ["issue-001", "issue-UNKNOWN"],
                "key_evidence_ids": ["ev-001"],
                "possible_outcome": "结果描述",
                "confidence_interval": None,
                "path_notes": "",
            }],
            "blocking_conditions": [],
        })
        inp = _make_input(issue_ids=["issue-001"], evidence_ids=["ev-001"])
        result = await _make_generator(response).generate(inp)

        assert len(result.paths) == 1
        assert "issue-UNKNOWN" not in result.paths[0].trigger_issue_ids
        assert "issue-001" in result.paths[0].trigger_issue_ids

    @pytest.mark.asyncio
    async def test_unknown_ids_filtered_from_blocking_conditions(self):
        """blocking_conditions 中的非法 issue_id 和 evidence_id 被过滤。"""
        response = json.dumps({
            "paths": _make_paths_json(3, issue_ids=["issue-001"], evidence_ids=["ev-001"]),
            "blocking_conditions": [{
                "condition_id": "bc-001",
                "condition_type": "amount_conflict",
                "description": "本金口径冲突",
                "linked_issue_ids": ["issue-001", "issue-GHOST"],
                "linked_evidence_ids": ["ev-001", "ev-GHOST"],
            }],
        })
        inp = _make_input(issue_ids=["issue-001", "issue-002", "issue-003"], evidence_ids=["ev-001", "ev-002", "ev-003"])
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
        response = json.dumps({
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
        })
        inp = _make_input(issue_ids=["issue-001", "issue-002", "issue-003"], evidence_ids=["ev-001", "ev-002", "ev-003"])
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
        response = json.dumps({
            "paths": [{
                "path_id": "path-A",
                "trigger_condition": "触发条件",
                "trigger_issue_ids": [],
                "key_evidence_ids": ["ev-admitted", "ev-submitted"],
                "possible_outcome": "结果描述",
                "confidence_interval": None,
                "path_notes": "",
            }],
            "blocking_conditions": [],
        })
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
        response = json.dumps({
            "paths": _make_paths_json(3, issue_ids=["issue-001"], evidence_ids=["ev-001"]),
            "blocking_conditions": [],
        })
        inp = _make_input(
            evidence_ids=["ev-001", "ev-002", "ev-003"],
            verdict_block_active=True,
            conflicts=[conflict],
        )
        result = await _make_generator(response).generate(inp)

        amount_conflicts = [
            bc for bc in result.blocking_conditions
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
        response = json.dumps({
            "paths": _make_paths_json(3, issue_ids=["issue-001"], evidence_ids=["ev-001"]),
            "blocking_conditions": [{
                "condition_id": "bc-llm-001",  # 不以 "bc-auto-" 开头，不冲突
                "condition_type": "amount_conflict",
                "description": "LLM 发现的本金冲突",
                "linked_issue_ids": [],
                "linked_evidence_ids": ["ev-001"],
            }],
        })
        inp = _make_input(
            evidence_ids=["ev-001", "ev-002", "ev-003"],
            verdict_block_active=True,
            conflicts=[conflict],
        )
        result = await _make_generator(response).generate(inp)

        # LLM 1 条 + 自动注入 1 条 = 2 条
        amount_conflicts = [
            bc for bc in result.blocking_conditions
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
    """置信度区间有效性校验。"""

    @pytest.mark.asyncio
    async def test_invalid_confidence_lower_gt_upper_cleared(self):
        """lower > upper 时 confidence_interval 被清空。"""
        response = json.dumps({
            "paths": [{
                "path_id": "path-A",
                "trigger_condition": "触发条件",
                "trigger_issue_ids": ["issue-001"],
                "key_evidence_ids": ["ev-001"],
                "possible_outcome": "结果描述",
                "confidence_interval": {"lower": 0.8, "upper": 0.2},  # invalid: lower > upper
                "path_notes": "",
            }],
            "blocking_conditions": [],
        })
        result = await _make_generator(response).generate(_make_input(verdict_block_active=False))

        assert result.paths[0].confidence_interval is None

    @pytest.mark.asyncio
    async def test_valid_confidence_interval_preserved(self):
        """有效的置信度区间（lower <= upper）被保留。"""
        response = json.dumps({
            "paths": [{
                "path_id": "path-A",
                "trigger_condition": "触发条件",
                "trigger_issue_ids": ["issue-001"],
                "key_evidence_ids": ["ev-001"],
                "possible_outcome": "结果描述",
                "confidence_interval": {"lower": 0.3, "upper": 0.7},
                "path_notes": "",
            }],
            "blocking_conditions": [],
        })
        result = await _make_generator(response).generate(_make_input(verdict_block_active=False))

        ci = result.paths[0].confidence_interval
        assert ci is not None
        assert ci.lower == pytest.approx(0.3)
        assert ci.upper == pytest.approx(0.7)


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
