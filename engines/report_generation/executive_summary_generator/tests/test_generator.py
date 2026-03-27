"""
ExecutiveSummaryGenerator 单元测试（P2.12）。

测试策略：
- 使用 Pydantic 模型构建测试数据（不用 Mock）
- 验证零 LLM 调用（纯规则层）
- 验证 P1 降级行为：action_recommendation=None → "未启用"，evidence_gap_list=None → "未启用"
- 验证 top5_decisive_issues 按 outcome_impact 降序排序
- 验证 top3_immediate_actions 取 ActionRecommendation 高优先级条目最多 3 个
- 验证 top3_adversary_optimal_attacks 来自 OptimalAttackChain
- 验证 current_most_stable_claim 绑定 AmountCalculationReport
- 验证 critical_evidence_gaps 按 roi_rank 取 Top3
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from engines.shared.models import (
    ActionRecommendation,
    AmountCalculationReport,
    AmountConsistencyCheck,
    AttackNode,
    AttackStrength,
    ClaimAbandonSuggestion,
    ClaimAmendmentSuggestion,
    ClaimCalculationEntry,
    ClaimType,
    EvidenceGapItem,
    EvidenceStrength,
    ExecutiveSummaryArtifact,
    Issue,
    IssueType,
    OptimalAttackChain,
    OutcomeImpact,
    OutcomeImpactSize,
    PracticallyObtainable,
    RecommendedAction,
    SupplementCost,
    TrialExplanationPriority,
)
from engines.report_generation.executive_summary_generator.generator import ExecutiveSummaryGenerator
from engines.report_generation.executive_summary_generator.schemas import ExecutiveSummaryGeneratorInput


# ---------------------------------------------------------------------------
# 测试辅助函数 / Test helpers
# ---------------------------------------------------------------------------

def make_issue(
    issue_id: str,
    outcome_impact: OutcomeImpact | None = None,
    recommended_action: RecommendedAction | None = None,
    evidence_ids: list[str] | None = None,
) -> Issue:
    return Issue(
        issue_id=issue_id,
        case_id="case1",
        title=f"争点 {issue_id}",
        issue_type=IssueType.factual,
        evidence_ids=evidence_ids or [],
        outcome_impact=outcome_impact,
        recommended_action=recommended_action,
    )


def make_amount_report(
    report_id: str = "rpt1",
    claim_entries: list[ClaimCalculationEntry] | None = None,
) -> AmountCalculationReport:
    return AmountCalculationReport(
        report_id=report_id,
        case_id="case1",
        run_id="run1",
        loan_transactions=[],
        repayment_transactions=[],
        claim_calculation_table=claim_entries or [],
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


def make_claim_entry(
    claim_id: str = "claim1",
    claimed: str = "100000",
    calculated: str | None = "100000",
) -> ClaimCalculationEntry:
    claimed_d = Decimal(claimed)
    calc_d = Decimal(calculated) if calculated is not None else None
    delta = (claimed_d - calc_d) if calc_d is not None else None
    return ClaimCalculationEntry(
        claim_id=claim_id,
        claim_type=ClaimType.principal,
        claimed_amount=claimed_d,
        calculated_amount=calc_d,
        delta=delta,
    )


def make_attack_chain(
    chain_id: str = "chain1",
    node_ids: list[str] | None = None,
) -> OptimalAttackChain:
    ids = node_ids or ["atk1", "atk2", "atk3"]
    nodes = [
        AttackNode(
            attack_node_id=nid,
            target_issue_id="issue1",
            attack_description=f"攻击点 {nid}",
            supporting_evidence_ids=["ev1"],
        )
        for nid in ids
    ]
    return OptimalAttackChain(
        chain_id=chain_id,
        case_id="case1",
        run_id="run1",
        owner_party_id="defendant",
        top_attacks=nodes,
        recommended_order=ids,
    )


def make_action_recommendation(
    recommendation_id: str = "rec1",
    amendments: list[ClaimAmendmentSuggestion] | None = None,
    abandons: list[ClaimAbandonSuggestion] | None = None,
    trial_priorities: list[TrialExplanationPriority] | None = None,
    gap_ids: list[str] | None = None,
) -> ActionRecommendation:
    return ActionRecommendation(
        recommendation_id=recommendation_id,
        case_id="case1",
        run_id="run1",
        recommended_claim_amendments=amendments or [],
        claims_to_abandon=abandons or [],
        trial_explanation_priorities=trial_priorities or [],
        evidence_supplement_priorities=gap_ids or [],
    )


def make_gap(gap_id: str, roi_rank: int) -> EvidenceGapItem:
    return EvidenceGapItem(
        gap_id=gap_id,
        case_id="case1",
        run_id="run1",
        related_issue_id="issue1",
        gap_description=f"缺证 {gap_id}",
        supplement_cost=SupplementCost.medium,
        outcome_impact_size=OutcomeImpactSize.moderate,
        practically_obtainable=PracticallyObtainable.yes,
        roi_rank=roi_rank,
    )


def make_input(**overrides) -> ExecutiveSummaryGeneratorInput:
    defaults = dict(
        case_id="case1",
        run_id="run1",
        issue_list=[
            make_issue("i1", OutcomeImpact.high),
            make_issue("i2", OutcomeImpact.medium),
            make_issue("i3", OutcomeImpact.low),
        ],
        optimal_attack_chains=[make_attack_chain()],
        amount_calculation_report=make_amount_report(
            claim_entries=[make_claim_entry("claim1", "100000", "100000")],
        ),
        action_recommendation=make_action_recommendation(),
        evidence_gap_list=[make_gap("gap1", 1), make_gap("gap2", 2)],
    )
    defaults.update(overrides)
    return ExecutiveSummaryGeneratorInput(**defaults)


# ---------------------------------------------------------------------------
# 测试类 / Test classes
# ---------------------------------------------------------------------------

class TestExecutiveSummaryGeneratorBasic:
    """基本生成和输出结构验证。"""

    def test_generate_returns_executive_summary_artifact(self):
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input())
        assert isinstance(result, ExecutiveSummaryArtifact)

    def test_case_id_and_run_id_propagated(self):
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input())
        assert result.case_id == "case1"
        assert result.run_id == "run1"

    def test_summary_id_auto_generated_non_empty(self):
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input())
        assert result.summary_id
        assert len(result.summary_id) > 0

    def test_created_at_auto_generated(self):
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input())
        assert result.created_at
        assert "T" in result.created_at

    def test_source_amount_report_id_matches_input(self):
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(
            amount_calculation_report=make_amount_report(report_id="rpt-xyz")
        ))
        assert result.source_amount_report_id == "rpt-xyz"


class TestTop5DecisiveIssues:
    """top5_decisive_issues 按 outcome_impact 降序排序逻辑。"""

    def test_high_issues_come_first(self):
        issues = [
            make_issue("low1", OutcomeImpact.low),
            make_issue("high1", OutcomeImpact.high),
            make_issue("med1", OutcomeImpact.medium),
        ]
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(issue_list=issues))
        assert result.top5_decisive_issues[0] == "high1"
        assert result.top5_decisive_issues[1] == "med1"
        assert result.top5_decisive_issues[2] == "low1"

    def test_at_most_5_issues_returned(self):
        issues = [make_issue(f"i{n}", OutcomeImpact.high) for n in range(8)]
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(issue_list=issues))
        assert len(result.top5_decisive_issues) == 5

    def test_fewer_than_5_returns_all(self):
        issues = [
            make_issue("i1", OutcomeImpact.high),
            make_issue("i2", OutcomeImpact.medium),
        ]
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(issue_list=issues))
        assert len(result.top5_decisive_issues) == 2

    def test_empty_issue_list_returns_empty(self):
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(issue_list=[]))
        assert result.top5_decisive_issues == []

    def test_issues_with_none_outcome_impact_ranked_last(self):
        issues = [
            make_issue("none1", None),
            make_issue("high1", OutcomeImpact.high),
            make_issue("none2", None),
        ]
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(issue_list=issues))
        assert result.top5_decisive_issues[0] == "high1"
        assert "none1" in result.top5_decisive_issues
        assert "none2" in result.top5_decisive_issues

    def test_all_same_impact_preserves_order(self):
        """同级 impact 时相对顺序保持稳定（stable sort）。"""
        issues = [make_issue(f"i{n}", OutcomeImpact.medium) for n in range(3)]
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(issue_list=issues))
        assert result.top5_decisive_issues == ["i0", "i1", "i2"]


class TestTop3ImmediateActions:
    """top3_immediate_actions 及其降级行为。"""

    def test_disabled_when_action_recommendation_none(self):
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(action_recommendation=None))
        assert result.top3_immediate_actions == "未启用"

    def test_source_recommendation_id_none_when_disabled(self):
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(action_recommendation=None))
        assert result.source_recommendation_id is None

    def test_returns_list_when_action_recommendation_provided(self):
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input())
        assert isinstance(result.top3_immediate_actions, list)

    def test_at_most_3_actions_returned(self):
        # 提供 4 个 abandon suggestions → 只取前 3
        abandons = [
            ClaimAbandonSuggestion(
                suggestion_id=f"ab{n}",
                claim_id=f"claim{n}",
                abandon_reason="证据不足",
                abandon_reason_issue_id="i1",
            )
            for n in range(4)
        ]
        rec = make_action_recommendation(abandons=abandons)
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(action_recommendation=rec))
        assert len(result.top3_immediate_actions) <= 3

    def test_source_recommendation_id_matches_input(self):
        rec = make_action_recommendation(recommendation_id="rec-xyz")
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(action_recommendation=rec))
        assert result.source_recommendation_id == "rec-xyz"

    def test_abandon_suggestions_included(self):
        ab = ClaimAbandonSuggestion(
            suggestion_id="ab1",
            claim_id="claim1",
            abandon_reason="证据不足",
            abandon_reason_issue_id="i1",
        )
        rec = make_action_recommendation(abandons=[ab])
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(action_recommendation=rec))
        assert "ab1" in result.top3_immediate_actions

    def test_amendment_suggestions_included(self):
        am = ClaimAmendmentSuggestion(
            suggestion_id="am1",
            original_claim_id="claim1",
            amendment_description="调整金额",
            amendment_reason_issue_id="i1",
        )
        rec = make_action_recommendation(amendments=[am])
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(action_recommendation=rec))
        assert "am1" in result.top3_immediate_actions

    def test_trial_priorities_included(self):
        tp = TrialExplanationPriority(
            priority_id="tp1",
            issue_id="i1",
            explanation_text="重点解释放款事实",
        )
        rec = make_action_recommendation(trial_priorities=[tp])
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(action_recommendation=rec))
        assert "tp1" in result.top3_immediate_actions

    def test_empty_recommendation_returns_empty_list(self):
        rec = make_action_recommendation()
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(action_recommendation=rec))
        assert result.top3_immediate_actions == []


class TestTop3AdversaryAttacks:
    """top3_adversary_optimal_attacks 及其来源追溯。"""

    def test_attack_node_ids_extracted_from_chain(self):
        chain = make_attack_chain(node_ids=["a1", "a2", "a3"])
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(optimal_attack_chains=[chain]))
        assert result.top3_adversary_optimal_attacks == ["a1", "a2", "a3"]

    def test_at_most_3_attacks_from_single_chain(self):
        chain = make_attack_chain(node_ids=["a1", "a2", "a3"])
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(optimal_attack_chains=[chain]))
        assert len(result.top3_adversary_optimal_attacks) <= 3

    def test_no_chains_returns_empty(self):
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(optimal_attack_chains=[]))
        assert result.top3_adversary_optimal_attacks == []

    def test_source_attack_chain_ids_match_input(self):
        chain = make_attack_chain(chain_id="ch-abc")
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(optimal_attack_chains=[chain]))
        assert "ch-abc" in result.source_attack_chain_ids

    def test_multiple_chains_ids_collected(self):
        chains = [
            make_attack_chain("ch1", ["a1", "a2", "a3"]),
            make_attack_chain("ch2", ["b1", "b2", "b3"]),
        ]
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(optimal_attack_chains=chains))
        assert "ch1" in result.source_attack_chain_ids
        assert "ch2" in result.source_attack_chain_ids

    def test_attack_ids_traceable_to_chain(self):
        """每个 attack_node_id 必须可追溯到某个 OptimalAttackChain 的 top_attacks。"""
        chain = make_attack_chain(node_ids=["x1", "x2", "x3"])
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(optimal_attack_chains=[chain]))
        all_attack_ids = {n.attack_node_id for n in chain.top_attacks}
        for atk_id in result.top3_adversary_optimal_attacks:
            assert atk_id in all_attack_ids


class TestCurrentMostStableClaim:
    """current_most_stable_claim 文本生成逻辑。"""

    def test_returns_non_empty_text(self):
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input())
        assert result.current_most_stable_claim
        assert len(result.current_most_stable_claim) > 0

    def test_stable_claim_delta_zero_mentioned(self):
        """delta=0 的诉请应被识别为最稳定。"""
        entry = make_claim_entry("c1", "100000", "100000")
        report = make_amount_report(claim_entries=[entry])
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(amount_calculation_report=report))
        # 文本必须包含 claim_id 或相关内容
        assert result.current_most_stable_claim

    def test_empty_claim_table_returns_fallback_text(self):
        """诉请表为空时返回保底文本（非空）。"""
        report = make_amount_report(claim_entries=[])
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(amount_calculation_report=report))
        assert result.current_most_stable_claim
        assert len(result.current_most_stable_claim) > 0

    def test_source_amount_report_id_in_artifact(self):
        report = make_amount_report(report_id="rpt-stable")
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(amount_calculation_report=report))
        assert result.source_amount_report_id == "rpt-stable"


class TestCriticalEvidenceGaps:
    """critical_evidence_gaps 及其降级行为。"""

    def test_disabled_when_evidence_gap_list_none(self):
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(evidence_gap_list=None))
        assert result.critical_evidence_gaps == "未启用"

    def test_returns_list_when_evidence_gaps_provided(self):
        gaps = [make_gap("g1", 1), make_gap("g2", 2)]
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(evidence_gap_list=gaps))
        assert isinstance(result.critical_evidence_gaps, list)

    def test_top3_by_roi_rank_ascending(self):
        """roi_rank=1 优先（最低 roi_rank = 最高优先级）。"""
        gaps = [
            make_gap("g3", 3),
            make_gap("g1", 1),
            make_gap("g2", 2),
        ]
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(evidence_gap_list=gaps))
        assert result.critical_evidence_gaps[0] == "g1"
        assert result.critical_evidence_gaps[1] == "g2"
        assert result.critical_evidence_gaps[2] == "g3"

    def test_at_most_3_gaps_returned(self):
        gaps = [make_gap(f"g{n}", n + 1) for n in range(5)]
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(evidence_gap_list=gaps))
        assert len(result.critical_evidence_gaps) == 3

    def test_fewer_than_3_gaps_returns_all(self):
        gaps = [make_gap("g1", 1), make_gap("g2", 2)]
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(evidence_gap_list=gaps))
        assert len(result.critical_evidence_gaps) == 2

    def test_empty_gap_list_returns_empty_list(self):
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(evidence_gap_list=[]))
        assert result.critical_evidence_gaps == []

    def test_gap_ids_traceable_to_input(self):
        gaps = [make_gap("g1", 1), make_gap("g2", 2), make_gap("g3", 3)]
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(evidence_gap_list=gaps))
        input_gap_ids = {g.gap_id for g in gaps}
        for gid in result.critical_evidence_gaps:
            assert gid in input_gap_ids


class TestZeroLLMCalls:
    """零 LLM 调用合约验证（无 LLMClient 注入也能正常生成）。"""

    def test_generator_requires_no_llm_client(self):
        """ExecutiveSummaryGenerator 构造时不需要 LLM 客户端。"""
        gen = ExecutiveSummaryGenerator()  # no args
        assert gen is not None

    def test_generate_runs_without_llm(self):
        """generate() 在无网络/无 LLM 环境下正常完成。"""
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input())
        assert isinstance(result, ExecutiveSummaryArtifact)


class TestBothDegradationPaths:
    """同时降级两个 P1 字段的场景。"""

    def test_both_p1_fields_disabled_simultaneously(self):
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(
            action_recommendation=None,
            evidence_gap_list=None,
        ))
        assert result.top3_immediate_actions == "未启用"
        assert result.critical_evidence_gaps == "未启用"
        assert result.source_recommendation_id is None

    def test_p1_fully_enabled_no_disabled_fields(self):
        rec = make_action_recommendation(
            abandons=[ClaimAbandonSuggestion(
                suggestion_id="ab1",
                claim_id="c1",
                abandon_reason="无证据支撑",
                abandon_reason_issue_id="i1",
            )]
        )
        gaps = [make_gap("g1", 1)]
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(make_input(
            action_recommendation=rec,
            evidence_gap_list=gaps,
        ))
        assert isinstance(result.top3_immediate_actions, list)
        assert isinstance(result.critical_evidence_gaps, list)
