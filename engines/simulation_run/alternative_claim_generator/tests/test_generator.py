"""
AlternativeClaimGenerator 单元测试（P2.11）。

测试策略：
- 使用 Pydantic 模型构建测试数据（不用 Mock）
- 验证三个触发条件各自独立触发
- 验证同一 claim_id 的多触发器合并（每个 original_claim_id 只输出一条建议）
- 验证合约保证：零 LLM 调用（纯规则层）、instability_issue_ids 非空、文本非空
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from engines.shared.models import (
    AlternativeClaimSuggestion,
    AmountCalculationReport,
    AmountConsistencyCheck,
    AttackStrength,
    ClaimCalculationEntry,
    ClaimType,
    EvidenceStrength,
    Issue,
    IssueType,
    RecommendedAction,
)
from engines.simulation_run.alternative_claim_generator.generator import AlternativeClaimGenerator
from engines.simulation_run.alternative_claim_generator.schemas import (
    AlternativeClaimGeneratorInput,
)


# ---------------------------------------------------------------------------
# 测试辅助函数 / Test helpers
# ---------------------------------------------------------------------------


def make_issue(
    issue_id: str,
    related_claim_ids: list[str] | None = None,
    recommended_action: RecommendedAction | None = None,
    proponent_evidence_strength: EvidenceStrength | None = None,
    opponent_attack_strength: AttackStrength | None = None,
    evidence_ids: list[str] | None = None,
    title: str = "测试争点",
) -> Issue:
    return Issue(
        issue_id=issue_id,
        case_id="case1",
        title=title,
        issue_type=IssueType.factual,
        related_claim_ids=related_claim_ids or [],
        evidence_ids=evidence_ids or [],
        recommended_action=recommended_action,
        proponent_evidence_strength=proponent_evidence_strength,
        opponent_attack_strength=opponent_attack_strength,
    )


def make_amount_report(
    claim_entries: list[ClaimCalculationEntry] | None = None,
) -> AmountCalculationReport:
    return AmountCalculationReport(
        report_id="rpt1",
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
    claim_id: str,
    claimed_amount: str,
    calculated_amount: str | None = None,
) -> ClaimCalculationEntry:
    calc = Decimal(calculated_amount) if calculated_amount is not None else None
    claimed = Decimal(claimed_amount)
    delta = (claimed - calc) if calc is not None else None
    return ClaimCalculationEntry(
        claim_id=claim_id,
        claim_type=ClaimType.principal,
        claimed_amount=claimed,
        calculated_amount=calc,
        delta=delta,
    )


def make_input(
    issues: list[Issue] | None = None,
    claim_entries: list[ClaimCalculationEntry] | None = None,
) -> AlternativeClaimGeneratorInput:
    return AlternativeClaimGeneratorInput(
        case_id="case1",
        run_id="run1",
        issue_list=issues or [],
        amount_report=make_amount_report(claim_entries),
    )


# ---------------------------------------------------------------------------
# 基础行为 / Basic behavior
# ---------------------------------------------------------------------------


class TestBasicBehavior:
    def test_empty_input_returns_empty_list(self):
        result = AlternativeClaimGenerator().generate(make_input())
        assert result == []

    def test_returns_list_of_alternative_claim_suggestions(self):
        issues = [make_issue("i1", ["c1"], recommended_action=RecommendedAction.amend_claim)]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert all(isinstance(s, AlternativeClaimSuggestion) for s in result)

    def test_suggestion_has_correct_case_and_run_id(self):
        issues = [make_issue("i1", ["c1"], recommended_action=RecommendedAction.amend_claim)]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert result[0].case_id == "case1"
        assert result[0].run_id == "run1"

    def test_suggestion_id_is_non_empty(self):
        issues = [make_issue("i1", ["c1"], recommended_action=RecommendedAction.amend_claim)]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert result[0].suggestion_id


# ---------------------------------------------------------------------------
# 触发条件1：recommended_action = amend_claim
# ---------------------------------------------------------------------------


class TestCondition1AmendClaim:
    def test_amend_claim_issue_triggers_suggestion(self):
        issues = [make_issue("i1", ["c1"], recommended_action=RecommendedAction.amend_claim)]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert len(result) == 1
        assert result[0].original_claim_id == "c1"

    def test_amend_claim_issue_without_claims_no_suggestion(self):
        issues = [make_issue("i1", [], recommended_action=RecommendedAction.amend_claim)]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert result == []

    def test_non_amend_claim_action_no_trigger(self):
        issues = [make_issue("i1", ["c1"], recommended_action=RecommendedAction.abandon)]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert result == []

    def test_supplement_evidence_action_no_trigger(self):
        issues = [
            make_issue("i1", ["c1"], recommended_action=RecommendedAction.supplement_evidence)
        ]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert result == []

    def test_explain_in_trial_action_no_trigger(self):
        issues = [make_issue("i1", ["c1"], recommended_action=RecommendedAction.explain_in_trial)]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert result == []

    def test_issue_with_multiple_claims_generates_multiple_suggestions(self):
        issues = [make_issue("i1", ["c1", "c2"], recommended_action=RecommendedAction.amend_claim)]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        claim_ids = {s.original_claim_id for s in result}
        assert claim_ids == {"c1", "c2"}

    def test_condition1_binds_issue_id(self):
        issues = [make_issue("i1", ["c1"], recommended_action=RecommendedAction.amend_claim)]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert "i1" in result[0].instability_issue_ids

    def test_condition1_propagates_evidence_ids(self):
        issues = [
            make_issue(
                "i1",
                ["c1"],
                recommended_action=RecommendedAction.amend_claim,
                evidence_ids=["e1", "e2"],
            )
        ]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert set(result[0].instability_evidence_ids) >= {"e1", "e2"}

    def test_condition1_alternative_text_non_empty(self):
        issues = [make_issue("i1", ["c1"], recommended_action=RecommendedAction.amend_claim)]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert result[0].alternative_claim_text

    def test_condition1_stability_rationale_non_empty(self):
        issues = [make_issue("i1", ["c1"], recommended_action=RecommendedAction.amend_claim)]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert result[0].stability_rationale


# ---------------------------------------------------------------------------
# 触发条件2：proponent_evidence_strength=weak 且 opponent_attack_strength=strong
# ---------------------------------------------------------------------------


class TestCondition2WeakStrongCombination:
    def test_weak_proponent_strong_opponent_triggers_suggestion(self):
        issues = [
            make_issue(
                "i1",
                ["c1"],
                proponent_evidence_strength=EvidenceStrength.weak,
                opponent_attack_strength=AttackStrength.strong,
            )
        ]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert len(result) == 1
        assert result[0].original_claim_id == "c1"

    def test_weak_proponent_only_no_trigger(self):
        """只有 weak proponent 没有 strong opponent，不触发。"""
        issues = [
            make_issue(
                "i1",
                ["c1"],
                proponent_evidence_strength=EvidenceStrength.weak,
                opponent_attack_strength=AttackStrength.medium,
            )
        ]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert result == []

    def test_strong_opponent_only_no_trigger(self):
        """只有 strong opponent 没有 weak proponent，不触发。"""
        issues = [
            make_issue(
                "i1",
                ["c1"],
                proponent_evidence_strength=EvidenceStrength.medium,
                opponent_attack_strength=AttackStrength.strong,
            )
        ]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert result == []

    def test_both_strong_no_trigger(self):
        issues = [
            make_issue(
                "i1",
                ["c1"],
                proponent_evidence_strength=EvidenceStrength.strong,
                opponent_attack_strength=AttackStrength.strong,
            )
        ]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert result == []

    def test_condition2_without_claims_no_suggestion(self):
        issues = [
            make_issue(
                "i1",
                [],
                proponent_evidence_strength=EvidenceStrength.weak,
                opponent_attack_strength=AttackStrength.strong,
            )
        ]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert result == []

    def test_condition2_binds_issue_id(self):
        issues = [
            make_issue(
                "i1",
                ["c1"],
                proponent_evidence_strength=EvidenceStrength.weak,
                opponent_attack_strength=AttackStrength.strong,
            )
        ]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert "i1" in result[0].instability_issue_ids

    def test_condition2_no_strength_fields_no_trigger(self):
        """两个字段都为 None 时不触发条件2。"""
        issues = [make_issue("i1", ["c1"])]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert result == []


# ---------------------------------------------------------------------------
# 触发条件3：ClaimCalculationEntry.delta 超过 10%
# ---------------------------------------------------------------------------


class TestCondition3DeltaThreshold:
    def test_delta_over_10_percent_triggers_suggestion(self):
        """claimed=1000, calculated=800, delta=200, 200/1000=20% — 超过阈值，触发。"""
        entry = make_claim_entry("c1", "1000", "800")
        issues = [make_issue("i1", ["c1"])]
        result = AlternativeClaimGenerator().generate(
            make_input(issues=issues, claim_entries=[entry])
        )
        assert len(result) == 1
        assert result[0].original_claim_id == "c1"

    def test_delta_exactly_10_percent_no_trigger(self):
        """delta = 100/1000 = 10%，等于阈值，不超过，不触发。"""
        entry = make_claim_entry("c1", "1000", "900")  # delta=100, 100/1000 = 10%
        issues = [make_issue("i1", ["c1"])]
        result = AlternativeClaimGenerator().generate(
            make_input(issues=issues, claim_entries=[entry])
        )
        assert result == []

    def test_delta_under_10_percent_no_trigger(self):
        entry = make_claim_entry("c1", "1000", "950")  # delta=50, 5%
        issues = [make_issue("i1", ["c1"])]
        result = AlternativeClaimGenerator().generate(
            make_input(issues=issues, claim_entries=[entry])
        )
        assert result == []

    def test_calculated_amount_none_no_trigger(self):
        """calculated_amount 为 None（无法复算）时，不触发条件3。"""
        entry = make_claim_entry("c1", "1000", None)
        issues = [make_issue("i1", ["c1"])]
        result = AlternativeClaimGenerator().generate(
            make_input(issues=issues, claim_entries=[entry])
        )
        assert result == []

    def test_condition3_negative_delta_over_threshold_triggers(self):
        """delta 为负（算出来比诉请多），绝对值超过阈值也触发。"""
        entry = make_claim_entry("c1", "800", "1000")  # delta=-200, |delta|/800 = 25%
        issues = [make_issue("i1", ["c1"])]
        result = AlternativeClaimGenerator().generate(
            make_input(issues=issues, claim_entries=[entry])
        )
        assert len(result) == 1

    def test_condition3_binds_related_issue(self):
        """条件3触发时，绑定引用了该 claim 的争点 issue_id。"""
        entry = make_claim_entry("c1", "1000", "800")
        issues = [make_issue("i1", ["c1"])]
        result = AlternativeClaimGenerator().generate(
            make_input(issues=issues, claim_entries=[entry])
        )
        assert "i1" in result[0].instability_issue_ids

    def test_condition3_no_related_issue_no_suggestion(self):
        """无争点引用该 claim 时，条件3不生成建议（无法绑定 issue_id）。"""
        entry = make_claim_entry("c1", "1000", "800")
        result = AlternativeClaimGenerator().generate(make_input(claim_entries=[entry]))
        assert result == []

    def test_condition3_zero_claimed_amount_no_trigger(self):
        """claimed_amount=0 时不触发（避免除零）。"""
        entry = ClaimCalculationEntry(
            claim_id="c1",
            claim_type=ClaimType.principal,
            claimed_amount=Decimal("0"),
            calculated_amount=Decimal("100"),
            delta=Decimal("-100"),
        )
        issues = [make_issue("i1", ["c1"])]
        result = AlternativeClaimGenerator().generate(
            make_input(issues=issues, claim_entries=[entry])
        )
        assert result == []


# ---------------------------------------------------------------------------
# 去重：同一 original_claim_id 只输出一条建议
# ---------------------------------------------------------------------------


class TestDeduplication:
    def test_two_conditions_on_same_claim_one_suggestion(self):
        """条件1和条件2同时命中同一 claim，只输出一条建议。"""
        issues = [
            make_issue(
                "i1",
                ["c1"],
                recommended_action=RecommendedAction.amend_claim,
                proponent_evidence_strength=EvidenceStrength.weak,
                opponent_attack_strength=AttackStrength.strong,
            )
        ]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert len(result) == 1
        assert result[0].original_claim_id == "c1"

    def test_two_issues_both_condition1_same_claim_one_suggestion(self):
        """两个争点均 amend_claim 且都关联同一 claim，只输出一条。"""
        issues = [
            make_issue("i1", ["c1"], recommended_action=RecommendedAction.amend_claim),
            make_issue("i2", ["c1"], recommended_action=RecommendedAction.amend_claim),
        ]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert len(result) == 1
        assert result[0].original_claim_id == "c1"

    def test_merged_suggestion_has_all_issue_ids(self):
        """合并后的建议包含所有触发争点的 issue_id。"""
        issues = [
            make_issue("i1", ["c1"], recommended_action=RecommendedAction.amend_claim),
            make_issue("i2", ["c1"], recommended_action=RecommendedAction.amend_claim),
        ]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert "i1" in result[0].instability_issue_ids
        assert "i2" in result[0].instability_issue_ids

    def test_different_claims_produce_separate_suggestions(self):
        issues = [
            make_issue("i1", ["c1"], recommended_action=RecommendedAction.amend_claim),
            make_issue("i2", ["c2"], recommended_action=RecommendedAction.amend_claim),
        ]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        claim_ids = {s.original_claim_id for s in result}
        assert claim_ids == {"c1", "c2"}

    def test_suggestion_ids_unique_across_results(self):
        issues = [
            make_issue("i1", ["c1"], recommended_action=RecommendedAction.amend_claim),
            make_issue("i2", ["c2"], recommended_action=RecommendedAction.amend_claim),
        ]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        ids = [s.suggestion_id for s in result]
        assert len(ids) == len(set(ids)), "suggestion_id 必须唯一"


# ---------------------------------------------------------------------------
# 合约保证 / Contract guarantees
# ---------------------------------------------------------------------------


class TestContractGuarantees:
    def test_instability_issue_ids_always_non_empty(self):
        """所有生成的建议 instability_issue_ids 必须非空。"""
        issues = [
            make_issue("i1", ["c1"], recommended_action=RecommendedAction.amend_claim),
            make_issue(
                "i2",
                ["c2"],
                proponent_evidence_strength=EvidenceStrength.weak,
                opponent_attack_strength=AttackStrength.strong,
            ),
        ]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        for s in result:
            assert s.instability_issue_ids, f"instability_issue_ids 不允许为空: {s}"

    def test_alternative_claim_text_always_non_empty(self):
        issues = [make_issue("i1", ["c1"], recommended_action=RecommendedAction.amend_claim)]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert all(s.alternative_claim_text for s in result)

    def test_stability_rationale_always_non_empty(self):
        issues = [make_issue("i1", ["c1"], recommended_action=RecommendedAction.amend_claim)]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert all(s.stability_rationale for s in result)

    def test_instability_reason_always_non_empty(self):
        issues = [make_issue("i1", ["c1"], recommended_action=RecommendedAction.amend_claim)]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert all(s.instability_reason for s in result)

    def test_original_claim_id_matches_trigger_claim(self):
        issues = [make_issue("i1", ["claim-abc"], recommended_action=RecommendedAction.amend_claim)]
        result = AlternativeClaimGenerator().generate(make_input(issues=issues))
        assert result[0].original_claim_id == "claim-abc"


# ---------------------------------------------------------------------------
# 混合场景 / Mixed scenario
# ---------------------------------------------------------------------------


class TestMixedScenario:
    def test_all_three_conditions_different_claims(self):
        """三个条件各自触发不同 claim，输出三条建议。"""
        issues = [
            make_issue("i1", ["c1"], recommended_action=RecommendedAction.amend_claim),
            make_issue(
                "i2",
                ["c2"],
                proponent_evidence_strength=EvidenceStrength.weak,
                opponent_attack_strength=AttackStrength.strong,
            ),
            make_issue("i3", ["c3"]),  # 用于绑定条件3的 c3
        ]
        entry = make_claim_entry("c3", "1000", "800")  # 20% delta
        result = AlternativeClaimGenerator().generate(
            make_input(issues=issues, claim_entries=[entry])
        )
        claim_ids = {s.original_claim_id for s in result}
        assert claim_ids == {"c1", "c2", "c3"}

    def test_no_llm_dependency(self):
        """验证 AlternativeClaimGenerator 不依赖外部 LLM（可正常实例化并运行）。"""
        gen = AlternativeClaimGenerator()
        result = gen.generate(make_input())
        assert isinstance(result, list)
