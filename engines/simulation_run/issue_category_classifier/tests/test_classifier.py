"""
IssueCategoryClassifier 单元测试。
Unit tests for IssueCategoryClassifier.

测试策略：
- 不依赖真实 LLM；使用 MockLLMClient 返回预定义 JSON
- 分层测试：校验规则 → 完整 classify() 流程
- 覆盖所有合约保证（见 spec P1.6 约束）
"""
from __future__ import annotations

import json
from decimal import Decimal

import pytest

from engines.shared.models import (
    AccessDomain,
    AmountCalculationReport,
    AmountConsistencyCheck,
    ClaimCalculationEntry,
    ClaimType,
    Evidence,
    EvidenceIndex,
    EvidenceStatus,
    EvidenceType,
    Issue,
    IssueCategory,
    IssueStatus,
    IssueTree,
    IssueType,
    LoanTransaction,
)
from engines.simulation_run.issue_category_classifier.classifier import IssueCategoryClassifier
from engines.simulation_run.issue_category_classifier.schemas import (
    IssueCategoryClassifierInput,
    IssueCategoryClassificationResult,
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
    issue_type: IssueType = IssueType.factual,
    related_claim_ids: list[str] | None = None,
    **kwargs,
) -> Issue:
    return Issue(
        issue_id=issue_id,
        case_id="case-001",
        title=title,
        issue_type=issue_type,
        related_claim_ids=related_claim_ids or [],
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


def _make_amount_report(
    claim_ids: list[str] | None = None,
) -> AmountCalculationReport:
    ids = claim_ids or ["claim-001"]
    return AmountCalculationReport(
        report_id="report-001",
        case_id="case-001",
        run_id="run-001",
        loan_transactions=[
            LoanTransaction(
                tx_id="loan-001",
                date="2024-01-01",
                amount=Decimal("100000"),
                evidence_id="ev-001",
                principal_base_contribution=True,
            )
        ],
        repayment_transactions=[],
        disputed_amount_attributions=[],
        claim_calculation_table=[
            ClaimCalculationEntry(
                claim_id=cid,
                claim_type=ClaimType.principal,
                claimed_amount=Decimal("100000"),
                calculated_amount=Decimal("100000"),
                delta=Decimal("0"),
                delta_explanation="一致",
            )
            for cid in ids
        ],
        consistency_check_result=AmountConsistencyCheck(
            principal_base_unique=True,
            all_repayments_attributed=True,
            text_table_amount_consistent=True,
            duplicate_interest_penalty_claim=False,
            claim_total_reconstructable=True,
            unresolved_conflicts=[],
            verdict_block_active=False,
        ),
    )


def _make_classifier_input(
    issues: list[Issue],
    evidence: list[Evidence] | None = None,
    claim_ids: list[str] | None = None,
) -> IssueCategoryClassifierInput:
    return IssueCategoryClassifierInput(
        case_id="case-001",
        run_id="run-test-001",
        issue_tree=IssueTree(case_id="case-001", issues=issues),
        evidence_index=EvidenceIndex(
            case_id="case-001",
            evidence=evidence or [_make_evidence("ev-001")],
        ),
        amount_calculation_report=_make_amount_report(claim_ids),
    )


def _cls_item(
    issue_id: str,
    issue_category: str = "fact_issue",
    related_claim_entry_ids: list[str] | None = None,
    category_basis: str = "测试分类依据",
) -> dict:
    return {
        "issue_id": issue_id,
        "issue_category": issue_category,
        "related_claim_entry_ids": related_claim_entry_ids or [],
        "category_basis": category_basis,
    }


def _stub_response(classifications: list[dict]) -> str:
    return json.dumps({"classifications": classifications})


# ---------------------------------------------------------------------------
# 测试：校验规则（通过 classify() + MockLLMClient）
# ---------------------------------------------------------------------------


class TestValidationRules:
    """规则层校验——通过 classify() + MockLLMClient 触发各种失败场景。"""

    @pytest.mark.asyncio
    async def test_invalid_category_clears_field(self):
        """非法 issue_category 枚举值 → 字段清空，进 unclassified。"""
        issues = [_make_issue("i-001")]
        item = _cls_item("i-001", issue_category="INVALID_VALUE")
        client = MockLLMClient(_stub_response([item]))
        classifier = IssueCategoryClassifier(client)
        result = await classifier.classify(_make_classifier_input(issues))

        assert result.classified_issue_tree.issues[0].issue_category is None
        assert "i-001" in result.unclassified_issue_ids

    @pytest.mark.asyncio
    async def test_calculation_issue_without_valid_claim_entry_clears_field(self):
        """calculation_issue 但 related_claim_entry_ids 无有效 claim_id → 清空，进 unclassified。"""
        issues = [_make_issue("i-001")]
        item = _cls_item(
            "i-001",
            issue_category="calculation_issue",
            related_claim_entry_ids=["claim-UNKNOWN-999"],
        )
        client = MockLLMClient(_stub_response([item]))
        classifier = IssueCategoryClassifier(client)
        # 报告中只有 claim-001，不含 claim-UNKNOWN-999
        result = await classifier.classify(_make_classifier_input(issues, claim_ids=["claim-001"]))

        assert result.classified_issue_tree.issues[0].issue_category is None
        assert "i-001" in result.unclassified_issue_ids

    @pytest.mark.asyncio
    async def test_calculation_issue_with_empty_claim_entry_ids_clears_field(self):
        """calculation_issue 但 related_claim_entry_ids 为空列表 → 清空，进 unclassified。"""
        issues = [_make_issue("i-001")]
        item = _cls_item(
            "i-001",
            issue_category="calculation_issue",
            related_claim_entry_ids=[],
        )
        client = MockLLMClient(_stub_response([item]))
        classifier = IssueCategoryClassifier(client)
        result = await classifier.classify(_make_classifier_input(issues, claim_ids=["claim-001"]))

        assert result.classified_issue_tree.issues[0].issue_category is None
        assert "i-001" in result.unclassified_issue_ids

    @pytest.mark.asyncio
    async def test_calculation_issue_with_valid_claim_entry_passes(self):
        """calculation_issue 且 related_claim_entry_ids 含有效 claim_id → 通过。"""
        issues = [_make_issue("i-001")]
        item = _cls_item(
            "i-001",
            issue_category="calculation_issue",
            related_claim_entry_ids=["claim-001"],
        )
        client = MockLLMClient(_stub_response([item]))
        classifier = IssueCategoryClassifier(client)
        result = await classifier.classify(_make_classifier_input(issues, claim_ids=["claim-001"]))

        assert result.classified_issue_tree.issues[0].issue_category == IssueCategory.calculation_issue
        assert "i-001" not in result.unclassified_issue_ids

    @pytest.mark.asyncio
    async def test_category_without_basis_clears_field(self):
        """category_basis 为空 → issue_category 被清空，进 unclassified。"""
        issues = [_make_issue("i-001")]
        item = _cls_item("i-001", category_basis="")
        client = MockLLMClient(_stub_response([item]))
        classifier = IssueCategoryClassifier(client)
        result = await classifier.classify(_make_classifier_input(issues))

        assert result.classified_issue_tree.issues[0].issue_category is None
        assert "i-001" in result.unclassified_issue_ids

    @pytest.mark.asyncio
    async def test_unknown_issue_id_in_llm_output_is_ignored(self):
        """LLM 返回未知 issue_id → 对应条目被忽略，不影响已知争点结果。"""
        issues = [_make_issue("i-001")]
        item_valid = _cls_item("i-001")
        item_unknown = _cls_item("i-UNKNOWN-999")
        client = MockLLMClient(_stub_response([item_valid, item_unknown]))
        classifier = IssueCategoryClassifier(client)
        result = await classifier.classify(_make_classifier_input(issues))

        assert len(result.classified_issue_tree.issues) == 1
        assert result.classified_issue_tree.issues[0].issue_id == "i-001"


# ---------------------------------------------------------------------------
# 测试：完整 classify() 流程
# ---------------------------------------------------------------------------


class TestClassifyFullFlow:
    """完整 classify() 流程集成测试。"""

    @pytest.mark.asyncio
    async def test_valid_fact_issue_classification(self):
        """合法 fact_issue 分类正确富化到 Issue 对象。"""
        issues = [_make_issue("i-001")]
        item = _cls_item("i-001", issue_category="fact_issue")
        client = MockLLMClient(_stub_response([item]))
        classifier = IssueCategoryClassifier(client)
        result = await classifier.classify(_make_classifier_input(issues))

        assert result.unclassified_issue_ids == []
        assert result.classified_issue_tree.issues[0].issue_category == IssueCategory.fact_issue

    @pytest.mark.asyncio
    async def test_all_four_categories_accepted(self):
        """四种合法分类均被接受。"""
        issues = [
            _make_issue("i-fact"),
            _make_issue("i-legal"),
            _make_issue("i-calc"),
            _make_issue("i-proc"),
        ]
        items = [
            _cls_item("i-fact", issue_category="fact_issue"),
            _cls_item("i-legal", issue_category="legal_issue"),
            _cls_item(
                "i-calc",
                issue_category="calculation_issue",
                related_claim_entry_ids=["claim-001"],
            ),
            _cls_item("i-proc", issue_category="procedure_credibility_issue"),
        ]
        client = MockLLMClient(_stub_response(items))
        classifier = IssueCategoryClassifier(client)
        result = await classifier.classify(_make_classifier_input(issues, claim_ids=["claim-001"]))

        assert result.unclassified_issue_ids == []
        cats = {i.issue_id: i.issue_category for i in result.classified_issue_tree.issues}
        assert cats["i-fact"] == IssueCategory.fact_issue
        assert cats["i-legal"] == IssueCategory.legal_issue
        assert cats["i-calc"] == IssueCategory.calculation_issue
        assert cats["i-proc"] == IssueCategory.procedure_credibility_issue

    @pytest.mark.asyncio
    async def test_empty_issue_tree_returns_immediately(self):
        """空争点树不调用 LLM，直接返回空结果。"""
        client = MockLLMClient("{}")
        classifier = IssueCategoryClassifier(client)
        result = await classifier.classify(_make_classifier_input(issues=[]))

        assert client.call_count == 0
        assert result.classified_issue_tree.issues == []
        assert result.unclassified_issue_ids == []

    @pytest.mark.asyncio
    async def test_llm_failure_returns_original_tree_all_unclassified(self):
        """LLM 整体失败：返回原始 issue_tree，所有争点进 unclassified_issue_ids。"""
        issues = [_make_issue("i-001"), _make_issue("i-002")]
        client = MockLLMClient("{}", fail_times=999)
        classifier = IssueCategoryClassifier(client, max_retries=1)
        result = await classifier.classify(_make_classifier_input(issues))

        assert result.classification_metadata.get("failed") is True
        assert set(result.unclassified_issue_ids) == {"i-001", "i-002"}
        assert [i.issue_id for i in result.classified_issue_tree.issues] == ["i-001", "i-002"]
        for issue in result.classified_issue_tree.issues:
            assert issue.issue_category is None

    @pytest.mark.asyncio
    async def test_llm_called_once(self):
        """classify() 只调用一次 LLM（批量模式）。"""
        issues = [_make_issue(f"i-{i:03d}") for i in range(5)]
        items = [_cls_item(f"i-{i:03d}") for i in range(5)]
        client = MockLLMClient(_stub_response(items))
        classifier = IssueCategoryClassifier(client)
        await classifier.classify(_make_classifier_input(issues))

        assert client.call_count == 1

    @pytest.mark.asyncio
    async def test_llm_retry_on_transient_failure(self):
        """LLM 前 N 次失败后成功，触发重试机制。"""
        issues = [_make_issue("i-001")]
        item = _cls_item("i-001")
        client = MockLLMClient(_stub_response([item]), fail_times=2)
        classifier = IssueCategoryClassifier(client, max_retries=3)
        result = await classifier.classify(_make_classifier_input(issues))

        assert client.call_count == 3  # 2 次失败 + 1 次成功
        assert result.unclassified_issue_ids == []

    @pytest.mark.asyncio
    async def test_result_created_at_is_set(self):
        """返回结果包含 ISO-8601 时间戳。"""
        issues = [_make_issue("i-001")]
        item = _cls_item("i-001")
        client = MockLLMClient(_stub_response([item]))
        classifier = IssueCategoryClassifier(client)
        result = await classifier.classify(_make_classifier_input(issues))

        assert result.created_at
        assert "T" in result.created_at  # ISO-8601 格式

    @pytest.mark.asyncio
    async def test_issue_type_preserved_after_classification(self):
        """分类后 issue_type 保持原值，不被覆盖（两字段并列）。"""
        issues = [_make_issue("i-001", issue_type=IssueType.legal)]
        item = _cls_item("i-001", issue_category="legal_issue")
        client = MockLLMClient(_stub_response([item]))
        classifier = IssueCategoryClassifier(client)
        result = await classifier.classify(_make_classifier_input(issues))

        classified = result.classified_issue_tree.issues[0]
        assert classified.issue_type == IssueType.legal
        assert classified.issue_category == IssueCategory.legal_issue

    @pytest.mark.asyncio
    async def test_claim_entries_included_in_prompt(self):
        """金额报告诉请条目被注入到 user prompt（供 LLM 引用）。"""
        issues = [_make_issue("i-001")]
        item = _cls_item("i-001")
        client = MockLLMClient(_stub_response([item]))
        classifier = IssueCategoryClassifier(client)
        await classifier.classify(
            _make_classifier_input(issues, claim_ids=["claim-special-001"])
        )

        assert client.last_user is not None
        assert "claim-special-001" in client.last_user

    @pytest.mark.asyncio
    async def test_unsupported_case_type_raises(self):
        """不支持的案由类型在初始化时抛出 ValueError。"""
        with pytest.raises(ValueError, match="不支持的案由类型"):
            IssueCategoryClassifier(MockLLMClient("{}"), case_type="unknown_type")

    @pytest.mark.asyncio
    async def test_llm_missing_issue_goes_to_unclassified(self):
        """LLM 未返回某争点的分类 → 该争点进 unclassified_issue_ids。"""
        issues = [_make_issue("i-001"), _make_issue("i-002")]
        # LLM 只返回 i-001，缺少 i-002
        items = [_cls_item("i-001")]
        client = MockLLMClient(_stub_response(items))
        classifier = IssueCategoryClassifier(client)
        result = await classifier.classify(_make_classifier_input(issues))

        assert "i-002" in result.unclassified_issue_ids
        assert result.classified_issue_tree.issues[1].issue_category is None
