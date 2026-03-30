"""
ExecutiveSummarizer 双层输出单元测试（P2）。
Unit tests for ExecutiveSummarizer dual-layer structured output (P2).

测试策略：
- 纯规则层，无 LLM 依赖
- 覆盖：structured_output 字段存在性、内容正确性、置信度指标计算、降级情况
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from engines.report_generation.executive_summarizer import ExecutiveSummarizer
from engines.report_generation.executive_summarizer.schemas import ExecutiveSummarizerInput
from engines.shared.models import (
    AmountCalculationReport,
    AmountConsistencyCheck,
    AttackNode,
    ClaimCalculationEntry,
    ClaimType,
    ConfidenceMetrics,
    ExecutiveSummaryArtifact,
    ExecutiveSummaryStructuredOutput,
    Issue,
    IssueStatus,
    IssueType,
    OptimalAttackChain,
    OutcomeImpact,
)


# ---------------------------------------------------------------------------
# 辅助工厂（与 test_summarizer.py 保持独立）
# ---------------------------------------------------------------------------


def _make_issue(issue_id: str, outcome_impact: OutcomeImpact | None = None) -> Issue:
    return Issue(
        issue_id=issue_id,
        case_id="CASE-S-001",
        title=f"争点 {issue_id}",
        issue_type=IssueType.factual,
        status=IssueStatus.open,
        outcome_impact=outcome_impact,
    )


def _make_attack_chain() -> OptimalAttackChain:
    node = AttackNode(
        attack_node_id="ATK-001",
        target_issue_id="ISS-001",
        attack_description="攻击节点",
        supporting_evidence_ids=["EV-001"],
    )
    return OptimalAttackChain(
        chain_id="CHAIN-001",
        case_id="CASE-S-001",
        run_id="RUN-S-001",
        owner_party_id="PARTY-DEF",
        top_attacks=[node],
        recommended_order=["ATK-001"],
    )


def _make_amount_report() -> AmountCalculationReport:
    entry = ClaimCalculationEntry(
        claim_id="CLM-S-001",
        claim_type=ClaimType.principal,
        claimed_amount=Decimal("500000.00"),
        calculated_amount=Decimal("500000.00"),
        delta=Decimal("0"),
    )
    check = AmountConsistencyCheck(
        principal_base_unique=True,
        all_repayments_attributed=True,
        text_table_amount_consistent=True,
        duplicate_interest_penalty_claim=False,
        claim_total_reconstructable=True,
        unresolved_conflicts=[],
        verdict_block_active=False,
    )
    return AmountCalculationReport(
        report_id="RPT-S-001",
        case_id="CASE-S-001",
        run_id="RUN-S-001",
        loan_transactions=[],
        repayment_transactions=[],
        claim_calculation_table=[entry],
        consistency_check_result=check,
    )


def _make_input(
    issues: list[Issue],
    attack_chain: OptimalAttackChain | None = None,
    amount_report: AmountCalculationReport | None = None,
) -> ExecutiveSummarizerInput:
    return ExecutiveSummarizerInput(
        case_id="CASE-S-001",
        run_id="RUN-S-001",
        issue_list=issues,
        adversary_attack_chain=attack_chain or _make_attack_chain(),
        amount_calculation_report=amount_report or _make_amount_report(),
    )


def _summarize(
    issues: list[Issue],
    attack_chain: OptimalAttackChain | None = None,
    amount_report: AmountCalculationReport | None = None,
) -> ExecutiveSummaryArtifact:
    summarizer = ExecutiveSummarizer()
    return summarizer.summarize(_make_input(issues, attack_chain, amount_report))


# ---------------------------------------------------------------------------
# structured_output 存在性测试
# ---------------------------------------------------------------------------


def test_structured_output_field_present():
    """summarize() 返回的 artifact 包含 structured_output 字段。"""
    issues = [_make_issue("ISS-001", OutcomeImpact.high)]
    artifact = _summarize(issues)

    assert artifact.structured_output is not None
    assert isinstance(artifact.structured_output, ExecutiveSummaryStructuredOutput)


def test_structured_output_confidence_metrics_type():
    """structured_output.confidence_metrics 是 ConfidenceMetrics 实例。"""
    issues = [_make_issue("ISS-001", OutcomeImpact.medium)]
    artifact = _summarize(issues)

    assert isinstance(artifact.structured_output.confidence_metrics, ConfidenceMetrics)


# ---------------------------------------------------------------------------
# case_overview 测试
# ---------------------------------------------------------------------------


def test_case_overview_contains_issue_count():
    """case_overview 包含争点数量信息。"""
    issues = [
        _make_issue("ISS-001", OutcomeImpact.high),
        _make_issue("ISS-002", OutcomeImpact.low),
    ]
    artifact = _summarize(issues)
    assert "2" in artifact.structured_output.case_overview


def test_case_overview_contains_report_id():
    """case_overview 包含金额报告 ID 以保持可追溯性。"""
    issues = [_make_issue("ISS-001")]
    artifact = _summarize(issues)
    assert "RPT-S-001" in artifact.structured_output.case_overview


# ---------------------------------------------------------------------------
# key_findings 测试
# ---------------------------------------------------------------------------


def test_key_findings_one_per_top_issue():
    """key_findings 条数与 top5 争点数一致（issues 数 ≤ 5 时）。"""
    issues = [
        _make_issue("ISS-A", OutcomeImpact.high),
        _make_issue("ISS-B", OutcomeImpact.medium),
    ]
    artifact = _summarize(issues)
    assert len(artifact.structured_output.key_findings) == 2


def test_key_findings_contain_issue_titles():
    """key_findings 中包含争点标题信息。"""
    issues = [_make_issue("ISS-001", OutcomeImpact.high)]
    artifact = _summarize(issues)
    findings_text = " ".join(artifact.structured_output.key_findings)
    assert "ISS-001" in findings_text or "争点" in findings_text


# ---------------------------------------------------------------------------
# risk_assessment 测试
# ---------------------------------------------------------------------------


def test_risk_assessment_mentions_high_impact_count():
    """risk_assessment 在存在高影响争点时提及数量。"""
    issues = [
        _make_issue("ISS-H1", OutcomeImpact.high),
        _make_issue("ISS-H2", OutcomeImpact.high),
        _make_issue("ISS-L1", OutcomeImpact.low),
    ]
    artifact = _summarize(issues)
    assert "2" in artifact.structured_output.risk_assessment


def test_risk_assessment_no_high_impact():
    """无高影响争点时 risk_assessment 表明整体风险可控。"""
    issues = [
        _make_issue("ISS-M1", OutcomeImpact.medium),
        _make_issue("ISS-L1", OutcomeImpact.low),
    ]
    artifact = _summarize(issues)
    assert "可控" in artifact.structured_output.risk_assessment


# ---------------------------------------------------------------------------
# recommended_actions 测试
# ---------------------------------------------------------------------------


def test_recommended_actions_not_empty():
    """recommended_actions 非空（P1.8 未启用时有默认提示）。"""
    issues = [_make_issue("ISS-001")]
    artifact = _summarize(issues)
    assert len(artifact.structured_output.recommended_actions) >= 1


# ---------------------------------------------------------------------------
# confidence_metrics 测试
# ---------------------------------------------------------------------------


def test_confidence_metrics_in_valid_range():
    """所有置信度指标值在 [0.0, 1.0] 范围内。"""
    issues = [_make_issue("ISS-001", OutcomeImpact.high)]
    artifact = _summarize(issues)
    metrics = artifact.structured_output.confidence_metrics

    assert 0.0 <= metrics.overall_confidence <= 1.0
    assert 0.0 <= metrics.evidence_completeness <= 1.0
    assert 0.0 <= metrics.legal_clarity <= 1.0


def test_evidence_completeness_full_when_all_evaluated():
    """所有争点均有 outcome_impact 时 evidence_completeness = 1.0。"""
    issues = [
        _make_issue("ISS-A", OutcomeImpact.high),
        _make_issue("ISS-B", OutcomeImpact.medium),
    ]
    artifact = _summarize(issues)
    assert artifact.structured_output.confidence_metrics.evidence_completeness == pytest.approx(1.0)


def test_evidence_completeness_partial_when_some_unevaluated():
    """部分争点无 outcome_impact 时 evidence_completeness < 1.0。"""
    issues = [
        _make_issue("ISS-A", OutcomeImpact.high),
        _make_issue("ISS-B", None),  # 未评估
    ]
    artifact = _summarize(issues)
    ec = artifact.structured_output.confidence_metrics.evidence_completeness
    assert ec == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# 向后兼容性测试（existing fields 不变）
# ---------------------------------------------------------------------------


def test_existing_fields_unchanged_after_p2():
    """添加 structured_output 后，原有 artifact 字段不变。"""
    issues = [_make_issue("ISS-001", OutcomeImpact.high)]
    artifact = _summarize(issues)

    # 原有字段
    assert artifact.summary_id
    assert artifact.case_id == "CASE-S-001"
    assert artifact.run_id == "RUN-S-001"
    assert isinstance(artifact.top5_decisive_issues, list)
    assert artifact.amount_report_id == "RPT-S-001"
    assert artifact.adversary_attack_chain_id == "CHAIN-001"
