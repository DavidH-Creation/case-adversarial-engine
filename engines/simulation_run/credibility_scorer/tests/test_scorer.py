"""
CredibilityScorer 单元测试（P2.9）。

测试策略：
- 使用 Pydantic 模型构建测试数据（不用 Mock）
- 每条规则（CRED-01~06）独立验证触发和不触发两个场景
- 边界条件：空输入（无证据、无争点）、多规则同时触发、满分场景
- 合约保证：零 LLM 调用（纯规则层）、final_score 一致性校验
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from engines.shared.models import (
    AmountCalculationReport,
    AmountConflict,
    AmountConsistencyCheck,
    AttackStrength,
    ClaimCalculationEntry,
    ClaimType,
    CredibilityDeduction,
    CredibilityScorecard,
    Evidence,
    EvidenceStatus,
    EvidenceStrength,
    EvidenceType,
    Issue,
    IssueType,
    RecommendedAction,
)
from engines.simulation_run.credibility_scorer.scorer import CredibilityScorer
from engines.simulation_run.credibility_scorer.schemas import CredibilityScorerInput


# ---------------------------------------------------------------------------
# 测试辅助函数 / Test helpers
# ---------------------------------------------------------------------------


def make_amount_report(
    case_id: str = "case1",
    run_id: str = "run1",
    unresolved_conflicts: list[AmountConflict] | None = None,
    text_table_consistent: bool = True,
) -> AmountCalculationReport:
    """构造最简 AmountCalculationReport。"""
    conflicts = unresolved_conflicts or []
    return AmountCalculationReport(
        report_id="rpt1",
        case_id=case_id,
        run_id=run_id,
        loan_transactions=[],
        repayment_transactions=[],
        claim_calculation_table=[
            ClaimCalculationEntry(
                entry_id="e1",
                claim_id="claim1",
                claim_type=ClaimType.principal,
                claimed_amount=Decimal("100000"),
                calculated_amount=Decimal("100000") if text_table_consistent else Decimal("90000"),
                delta=Decimal("0") if text_table_consistent else Decimal("10000"),
                delta_explanation="" if text_table_consistent else "文本与表格金额不一致",
            )
        ],
        consistency_check_result=AmountConsistencyCheck(
            principal_base_unique=True,
            all_repayments_attributed=True,
            text_table_amount_consistent=text_table_consistent,
            duplicate_interest_penalty_claim=False,
            claim_total_reconstructable=text_table_consistent,
            unresolved_conflicts=conflicts,
            verdict_block_active=len(conflicts) > 0,
        ),
    )


def make_conflict(
    conflict_id: str = "c1",
    source_a: str = "ev1",
    source_b: str = "ev2",
) -> AmountConflict:
    return AmountConflict(
        conflict_id=conflict_id,
        conflict_description="金额口径冲突",
        amount_a=Decimal("100000"),
        amount_b=Decimal("80000"),
        source_a_evidence_id=source_a,
        source_b_evidence_id=source_b,
        resolution_note="",
    )


def make_evidence(
    evidence_id: str,
    evidence_type: EvidenceType = EvidenceType.documentary,
    status: EvidenceStatus = EvidenceStatus.submitted,
    admissibility_notes: str | None = None,
    is_copy_only: bool = False,
    target_issue_ids: list[str] | None = None,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        case_id="case1",
        owner_party_id="party1",
        title=f"证据-{evidence_id}",
        source="测试来源",
        summary="测试摘要",
        evidence_type=evidence_type,
        target_fact_ids=["fact1"],
        target_issue_ids=target_issue_ids or [],
        status=status,
        admissibility_notes=admissibility_notes,
        is_copy_only=is_copy_only,
    )


def make_issue(
    issue_id: str,
    evidence_ids: list[str] | None = None,
    proponent_evidence_strength: EvidenceStrength | None = None,
    opponent_attack_strength: AttackStrength | None = None,
    recommended_action: RecommendedAction | None = None,
) -> Issue:
    return Issue(
        issue_id=issue_id,
        case_id="case1",
        title=f"争点-{issue_id}",
        issue_type=IssueType.factual,
        evidence_ids=evidence_ids or [],
        proponent_evidence_strength=proponent_evidence_strength,
        opponent_attack_strength=opponent_attack_strength,
        recommended_action=recommended_action,
    )


def make_input(
    case_id: str = "case1",
    run_id: str = "run1",
    amount_report: AmountCalculationReport | None = None,
    evidence_list: list[Evidence] | None = None,
    issue_list: list[Issue] | None = None,
) -> CredibilityScorerInput:
    return CredibilityScorerInput(
        case_id=case_id,
        run_id=run_id,
        amount_report=amount_report or make_amount_report(),
        evidence_list=evidence_list or [],
        issue_list=issue_list or [],
    )


# ---------------------------------------------------------------------------
# 基础结构测试 / Basic structure tests
# ---------------------------------------------------------------------------


class TestCredibilityScorerBasic:
    def test_returns_scorecard(self):
        scorer = CredibilityScorer()
        result = scorer.score(make_input())
        assert isinstance(result, CredibilityScorecard)

    def test_scorecard_ids_set(self):
        scorer = CredibilityScorer()
        result = scorer.score(make_input())
        assert result.scorecard_id
        assert result.case_id == "case1"
        assert result.run_id == "run1"

    def test_base_score_is_100(self):
        scorer = CredibilityScorer()
        result = scorer.score(make_input())
        assert result.base_score == 100

    def test_perfect_score_no_deductions(self):
        """无任何触发条件时，final_score == 100，deductions 为空。"""
        scorer = CredibilityScorer()
        result = scorer.score(make_input())
        assert result.deductions == []
        assert result.final_score == 100

    def test_summary_not_empty(self):
        scorer = CredibilityScorer()
        result = scorer.score(make_input())
        assert result.summary

    def test_final_score_consistency_validated(self):
        """CredibilityScorecard model_validator 确保 final_score 等于 base_score + sum(deductions)。"""
        with pytest.raises(Exception):
            CredibilityScorecard(
                scorecard_id="s1",
                case_id="c1",
                run_id="r1",
                base_score=100,
                deductions=[],
                final_score=90,  # 错误：应为 100
                summary="test",
            )


# ---------------------------------------------------------------------------
# CRED-01: 未解释金额口径冲突
# ---------------------------------------------------------------------------


class TestCred01:
    def test_triggers_when_unresolved_conflicts_exist(self):
        conflict = make_conflict(source_a="ev1", source_b="ev2")
        inp = make_input(amount_report=make_amount_report(unresolved_conflicts=[conflict]))
        result = CredibilityScorer().score(inp)
        rule_ids = [d.rule_id for d in result.deductions]
        assert "CRED-01" in rule_ids

    def test_deduction_points_minus_20(self):
        conflict = make_conflict()
        inp = make_input(amount_report=make_amount_report(unresolved_conflicts=[conflict]))
        result = CredibilityScorer().score(inp)
        d = next(d for d in result.deductions if d.rule_id == "CRED-01")
        assert d.deduction_points == -20

    def test_trigger_evidence_ids_from_conflict(self):
        conflict = make_conflict(source_a="ev-a", source_b="ev-b")
        inp = make_input(amount_report=make_amount_report(unresolved_conflicts=[conflict]))
        result = CredibilityScorer().score(inp)
        d = next(d for d in result.deductions if d.rule_id == "CRED-01")
        assert "ev-a" in d.trigger_evidence_ids
        assert "ev-b" in d.trigger_evidence_ids

    def test_not_triggered_when_no_conflicts(self):
        inp = make_input(amount_report=make_amount_report(unresolved_conflicts=[]))
        result = CredibilityScorer().score(inp)
        assert all(d.rule_id != "CRED-01" for d in result.deductions)


# ---------------------------------------------------------------------------
# CRED-02: 关键证据仅有复印件无原件
# ---------------------------------------------------------------------------


class TestCred02:
    def test_triggers_when_copy_only_evidence(self):
        ev = make_evidence("ev1", is_copy_only=True)
        inp = make_input(evidence_list=[ev])
        result = CredibilityScorer().score(inp)
        assert any(d.rule_id == "CRED-02" for d in result.deductions)

    def test_deduction_points_minus_10(self):
        ev = make_evidence("ev1", is_copy_only=True)
        inp = make_input(evidence_list=[ev])
        result = CredibilityScorer().score(inp)
        d = next(d for d in result.deductions if d.rule_id == "CRED-02")
        assert d.deduction_points == -10

    def test_trigger_evidence_ids_contains_copy_evidence(self):
        ev = make_evidence("copy-ev", is_copy_only=True)
        inp = make_input(evidence_list=[ev])
        result = CredibilityScorer().score(inp)
        d = next(d for d in result.deductions if d.rule_id == "CRED-02")
        assert "copy-ev" in d.trigger_evidence_ids

    def test_not_triggered_when_no_copy_evidence(self):
        ev = make_evidence("ev1", is_copy_only=False)
        inp = make_input(evidence_list=[ev])
        result = CredibilityScorer().score(inp)
        assert all(d.rule_id != "CRED-02" for d in result.deductions)

    def test_multiple_copy_evidence_still_one_deduction(self):
        """CRED-02 每类规则只触发一次（不重复扣分）。"""
        ev1 = make_evidence("ev1", is_copy_only=True)
        ev2 = make_evidence("ev2", is_copy_only=True)
        inp = make_input(evidence_list=[ev1, ev2])
        result = CredibilityScorer().score(inp)
        assert sum(1 for d in result.deductions if d.rule_id == "CRED-02") == 1


# ---------------------------------------------------------------------------
# CRED-03: 文本与表格金额不一致
# ---------------------------------------------------------------------------


class TestCred03:
    def test_triggers_when_text_table_inconsistent(self):
        inp = make_input(amount_report=make_amount_report(text_table_consistent=False))
        result = CredibilityScorer().score(inp)
        assert any(d.rule_id == "CRED-03" for d in result.deductions)

    def test_deduction_points_minus_15(self):
        inp = make_input(amount_report=make_amount_report(text_table_consistent=False))
        result = CredibilityScorer().score(inp)
        d = next(d for d in result.deductions if d.rule_id == "CRED-03")
        assert d.deduction_points == -15

    def test_not_triggered_when_consistent(self):
        inp = make_input(amount_report=make_amount_report(text_table_consistent=True))
        result = CredibilityScorer().score(inp)
        assert all(d.rule_id != "CRED-03" for d in result.deductions)


# ---------------------------------------------------------------------------
# CRED-04: 证人证言与书证存在明显矛盾
# ---------------------------------------------------------------------------


class TestCred04:
    def test_triggers_when_witness_doc_conflict_strong_attack(self):
        witness_ev = make_evidence("wev", evidence_type=EvidenceType.witness_statement)
        doc_ev = make_evidence("dev", evidence_type=EvidenceType.documentary)
        issue = make_issue(
            "i1",
            evidence_ids=["wev", "dev"],
            opponent_attack_strength=AttackStrength.strong,
        )
        inp = make_input(
            evidence_list=[witness_ev, doc_ev],
            issue_list=[issue],
        )
        result = CredibilityScorer().score(inp)
        assert any(d.rule_id == "CRED-04" for d in result.deductions)

    def test_deduction_points_minus_10(self):
        witness_ev = make_evidence("wev", evidence_type=EvidenceType.witness_statement)
        doc_ev = make_evidence("dev", evidence_type=EvidenceType.documentary)
        issue = make_issue(
            "i1",
            evidence_ids=["wev", "dev"],
            opponent_attack_strength=AttackStrength.strong,
        )
        inp = make_input(evidence_list=[witness_ev, doc_ev], issue_list=[issue])
        result = CredibilityScorer().score(inp)
        d = next(d for d in result.deductions if d.rule_id == "CRED-04")
        assert d.deduction_points == -10

    def test_not_triggered_when_attack_not_strong(self):
        witness_ev = make_evidence("wev", evidence_type=EvidenceType.witness_statement)
        doc_ev = make_evidence("dev", evidence_type=EvidenceType.documentary)
        issue = make_issue(
            "i1",
            evidence_ids=["wev", "dev"],
            opponent_attack_strength=AttackStrength.weak,
        )
        inp = make_input(evidence_list=[witness_ev, doc_ev], issue_list=[issue])
        result = CredibilityScorer().score(inp)
        assert all(d.rule_id != "CRED-04" for d in result.deductions)

    def test_not_triggered_when_only_documentary(self):
        doc_ev1 = make_evidence("dev1", evidence_type=EvidenceType.documentary)
        doc_ev2 = make_evidence("dev2", evidence_type=EvidenceType.documentary)
        issue = make_issue(
            "i1",
            evidence_ids=["dev1", "dev2"],
            opponent_attack_strength=AttackStrength.strong,
        )
        inp = make_input(evidence_list=[doc_ev1, doc_ev2], issue_list=[issue])
        result = CredibilityScorer().score(inp)
        assert all(d.rule_id != "CRED-04" for d in result.deductions)

    def test_trigger_includes_issue_id(self):
        witness_ev = make_evidence("wev", evidence_type=EvidenceType.witness_statement)
        doc_ev = make_evidence("dev", evidence_type=EvidenceType.documentary)
        issue = make_issue(
            "issue-x",
            evidence_ids=["wev", "dev"],
            opponent_attack_strength=AttackStrength.strong,
        )
        inp = make_input(evidence_list=[witness_ev, doc_ev], issue_list=[issue])
        result = CredibilityScorer().score(inp)
        d = next(d for d in result.deductions if d.rule_id == "CRED-04")
        assert "issue-x" in d.trigger_issue_ids


# ---------------------------------------------------------------------------
# CRED-05: 关键时间节点缺乏证据支撑
# ---------------------------------------------------------------------------


class TestCred05:
    def test_triggers_when_weak_evidence_and_supplement_needed(self):
        issue = make_issue(
            "i1",
            proponent_evidence_strength=EvidenceStrength.weak,
            recommended_action=RecommendedAction.supplement_evidence,
        )
        inp = make_input(issue_list=[issue])
        result = CredibilityScorer().score(inp)
        assert any(d.rule_id == "CRED-05" for d in result.deductions)

    def test_deduction_points_minus_10(self):
        issue = make_issue(
            "i1",
            proponent_evidence_strength=EvidenceStrength.weak,
            recommended_action=RecommendedAction.supplement_evidence,
        )
        inp = make_input(issue_list=[issue])
        result = CredibilityScorer().score(inp)
        d = next(d for d in result.deductions if d.rule_id == "CRED-05")
        assert d.deduction_points == -10

    def test_not_triggered_when_evidence_not_weak(self):
        issue = make_issue(
            "i1",
            proponent_evidence_strength=EvidenceStrength.strong,
            recommended_action=RecommendedAction.supplement_evidence,
        )
        inp = make_input(issue_list=[issue])
        result = CredibilityScorer().score(inp)
        assert all(d.rule_id != "CRED-05" for d in result.deductions)

    def test_not_triggered_when_action_not_supplement(self):
        issue = make_issue(
            "i1",
            proponent_evidence_strength=EvidenceStrength.weak,
            recommended_action=RecommendedAction.amend_claim,
        )
        inp = make_input(issue_list=[issue])
        result = CredibilityScorer().score(inp)
        assert all(d.rule_id != "CRED-05" for d in result.deductions)

    def test_trigger_includes_issue_id(self):
        issue = make_issue(
            "issue-y",
            proponent_evidence_strength=EvidenceStrength.weak,
            recommended_action=RecommendedAction.supplement_evidence,
        )
        inp = make_input(issue_list=[issue])
        result = CredibilityScorer().score(inp)
        d = next(d for d in result.deductions if d.rule_id == "CRED-05")
        assert "issue-y" in d.trigger_issue_ids


# ---------------------------------------------------------------------------
# CRED-06: 被质疑真实性但未给出解释的证据
# ---------------------------------------------------------------------------


class TestCred06:
    def test_triggers_when_challenged_no_notes(self):
        ev = make_evidence(
            "ev1",
            status=EvidenceStatus.challenged,
            admissibility_notes=None,
        )
        inp = make_input(evidence_list=[ev])
        result = CredibilityScorer().score(inp)
        assert any(d.rule_id == "CRED-06" for d in result.deductions)

    def test_triggers_when_challenged_empty_notes(self):
        ev = make_evidence(
            "ev1",
            status=EvidenceStatus.challenged,
            admissibility_notes="",
        )
        inp = make_input(evidence_list=[ev])
        result = CredibilityScorer().score(inp)
        assert any(d.rule_id == "CRED-06" for d in result.deductions)

    def test_deduction_points_minus_5(self):
        ev = make_evidence("ev1", status=EvidenceStatus.challenged)
        inp = make_input(evidence_list=[ev])
        result = CredibilityScorer().score(inp)
        d = next(d for d in result.deductions if d.rule_id == "CRED-06")
        assert d.deduction_points == -5

    def test_not_triggered_when_challenged_with_notes(self):
        ev = make_evidence(
            "ev1",
            status=EvidenceStatus.challenged,
            admissibility_notes="已提供解释说明",
        )
        inp = make_input(evidence_list=[ev])
        result = CredibilityScorer().score(inp)
        assert all(d.rule_id != "CRED-06" for d in result.deductions)

    def test_not_triggered_when_status_not_challenged(self):
        ev = make_evidence("ev1", status=EvidenceStatus.submitted)
        inp = make_input(evidence_list=[ev])
        result = CredibilityScorer().score(inp)
        assert all(d.rule_id != "CRED-06" for d in result.deductions)


# ---------------------------------------------------------------------------
# 综合测试 / Integration tests
# ---------------------------------------------------------------------------


class TestCredibilityScorerIntegration:
    def test_multiple_rules_cumulative_score(self):
        """CRED-01 + CRED-02 同时触发，final_score = 100 - 20 - 10 = 70。"""
        conflict = make_conflict()
        copy_ev = make_evidence("ev-copy", is_copy_only=True)
        inp = make_input(
            amount_report=make_amount_report(unresolved_conflicts=[conflict]),
            evidence_list=[copy_ev],
        )
        result = CredibilityScorer().score(inp)
        rule_ids = {d.rule_id for d in result.deductions}
        assert "CRED-01" in rule_ids
        assert "CRED-02" in rule_ids
        assert result.final_score == 70

    def test_all_six_rules_trigger(self):
        """全部 6 条规则同时触发，final_score = 100 - 20 - 10 - 15 - 10 - 10 - 5 = 30。"""
        conflict = make_conflict(source_a="ev1", source_b="ev2")
        copy_ev = make_evidence("copy-ev", is_copy_only=True)
        challenged_ev = make_evidence("challenged-ev", status=EvidenceStatus.challenged)
        witness_ev = make_evidence("wev", evidence_type=EvidenceType.witness_statement)
        doc_ev = make_evidence("dev", evidence_type=EvidenceType.documentary)
        issue_cred04 = make_issue(
            "i-cred04",
            evidence_ids=["wev", "dev"],
            opponent_attack_strength=AttackStrength.strong,
        )
        issue_cred05 = make_issue(
            "i-cred05",
            proponent_evidence_strength=EvidenceStrength.weak,
            recommended_action=RecommendedAction.supplement_evidence,
        )
        inp = make_input(
            amount_report=make_amount_report(
                unresolved_conflicts=[conflict],
                text_table_consistent=False,
            ),
            evidence_list=[copy_ev, challenged_ev, witness_ev, doc_ev],
            issue_list=[issue_cred04, issue_cred05],
        )
        result = CredibilityScorer().score(inp)
        rule_ids = {d.rule_id for d in result.deductions}
        assert rule_ids == {"CRED-01", "CRED-02", "CRED-03", "CRED-04", "CRED-05", "CRED-06"}
        assert result.final_score == 30

    def test_low_score_warning_in_summary(self):
        """final_score < 60 时，summary 须包含可信度警告关键词。"""
        # CRED-01(-20) + CRED-02(-10) + CRED-03(-15) + CRED-04(-10) + CRED-05(-10) = -65 → 35
        conflict = make_conflict()
        copy_ev = make_evidence("copy-ev", is_copy_only=True)
        witness_ev = make_evidence("wev", evidence_type=EvidenceType.witness_statement)
        doc_ev = make_evidence("dev", evidence_type=EvidenceType.documentary)
        issue_cred04 = make_issue(
            "i1", evidence_ids=["wev", "dev"], opponent_attack_strength=AttackStrength.strong
        )
        issue_cred05 = make_issue(
            "i2",
            proponent_evidence_strength=EvidenceStrength.weak,
            recommended_action=RecommendedAction.supplement_evidence,
        )
        inp = make_input(
            amount_report=make_amount_report(
                unresolved_conflicts=[conflict], text_table_consistent=False
            ),
            evidence_list=[copy_ev, witness_ev, doc_ev],
            issue_list=[issue_cred04, issue_cred05],
        )
        result = CredibilityScorer().score(inp)
        assert result.final_score < 60
        assert (
            "警告" in result.summary
            or "WARNING" in result.summary.upper()
            or "低" in result.summary
        )

    def test_deduction_ids_are_unique(self):
        conflict = make_conflict()
        copy_ev = make_evidence("ev1", is_copy_only=True)
        inp = make_input(
            amount_report=make_amount_report(unresolved_conflicts=[conflict]),
            evidence_list=[copy_ev],
        )
        result = CredibilityScorer().score(inp)
        ids = [d.deduction_id for d in result.deductions]
        assert len(ids) == len(set(ids))

    def test_empty_input_perfect_score(self):
        """空输入（无冲突、无特殊证据、无问题争点）时 final_score == 100。"""
        inp = make_input()
        result = CredibilityScorer().score(inp)
        assert result.final_score == 100
        assert result.deductions == []


# ---------------------------------------------------------------------------
# CRED-07: 职业放贷人检测
# ---------------------------------------------------------------------------

from engines.shared.models import LitigationHistory, Party
from engines.shared.rule_config import RuleThresholds


class TestCRED07ProfessionalLender:
    """CRED-07: 原告放贷频次达标 → 扣分 -25。"""

    @staticmethod
    def _make_party(
        case_count: int = 0,
        borrowers: int = 0,
        months: int = 24,
        uniform: bool = False,
    ) -> Party:
        return Party(
            party_id="plaintiff-1",
            case_id="case1",
            name="郭某",
            party_type="natural_person",
            role_code="plaintiff_agent",
            side="plaintiff",
            litigation_history=LitigationHistory(
                lending_case_count=case_count,
                distinct_borrower_count=borrowers,
                time_span_months=months,
                uniform_contract_detected=uniform,
            ),
        )

    def test_triggers_when_all_thresholds_met(self):
        party = self._make_party(case_count=8, borrowers=8, months=24, uniform=True)
        inp = CredibilityScorerInput(
            case_id="case1",
            run_id="run1",
            amount_report=make_amount_report(),
            party_list=[party],
        )
        scorer = CredibilityScorer(thresholds=RuleThresholds())
        result = scorer.score(inp)
        cred07 = [d for d in result.deductions if d.rule_id == "CRED-07"]
        assert len(cred07) == 1
        assert cred07[0].deduction_points == -25

    def test_not_triggered_below_case_threshold(self):
        party = self._make_party(case_count=2, borrowers=5, months=24)
        inp = CredibilityScorerInput(
            case_id="case1",
            run_id="run1",
            amount_report=make_amount_report(),
            party_list=[party],
        )
        scorer = CredibilityScorer(thresholds=RuleThresholds())
        result = scorer.score(inp)
        cred07 = [d for d in result.deductions if d.rule_id == "CRED-07"]
        assert len(cred07) == 0

    def test_not_triggered_below_borrower_threshold(self):
        party = self._make_party(case_count=5, borrowers=2, months=24)
        inp = CredibilityScorerInput(
            case_id="case1",
            run_id="run1",
            amount_report=make_amount_report(),
            party_list=[party],
        )
        scorer = CredibilityScorer(thresholds=RuleThresholds())
        result = scorer.score(inp)
        cred07 = [d for d in result.deductions if d.rule_id == "CRED-07"]
        assert len(cred07) == 0

    def test_not_triggered_without_litigation_history(self):
        party = Party(
            party_id="p1",
            case_id="case1",
            name="A",
            party_type="natural_person",
            role_code="plaintiff_agent",
            side="plaintiff",
        )
        inp = CredibilityScorerInput(
            case_id="case1",
            run_id="run1",
            amount_report=make_amount_report(),
            party_list=[party],
        )
        scorer = CredibilityScorer(thresholds=RuleThresholds())
        result = scorer.score(inp)
        cred07 = [d for d in result.deductions if d.rule_id == "CRED-07"]
        assert len(cred07) == 0

    def test_custom_thresholds(self):
        party = self._make_party(case_count=5, borrowers=5, months=24)
        cfg = RuleThresholds(prof_lender_min_cases=5, prof_lender_min_borrowers=5)
        inp = CredibilityScorerInput(
            case_id="case1",
            run_id="run1",
            amount_report=make_amount_report(),
            party_list=[party],
        )
        scorer = CredibilityScorer(thresholds=cfg)
        result = scorer.score(inp)
        cred07 = [d for d in result.deductions if d.rule_id == "CRED-07"]
        assert len(cred07) == 1

    def test_empty_party_list(self):
        inp = CredibilityScorerInput(
            case_id="case1",
            run_id="run1",
            amount_report=make_amount_report(),
            party_list=[],
        )
        scorer = CredibilityScorer(thresholds=RuleThresholds())
        result = scorer.score(inp)
        cred07 = [d for d in result.deductions if d.rule_id == "CRED-07"]
        assert len(cred07) == 0

    def test_score_reduction_correct(self):
        party = self._make_party(case_count=8, borrowers=8, months=24, uniform=True)
        inp = CredibilityScorerInput(
            case_id="case1",
            run_id="run1",
            amount_report=make_amount_report(),
            party_list=[party],
        )
        scorer = CredibilityScorer(thresholds=RuleThresholds())
        result = scorer.score(inp)
        assert result.final_score == 100 - 25

    def test_defendant_matching_thresholds_not_triggered(self):
        """被告满足职业放贷人条件时不应触发 CRED-07（仅检查原告）。"""
        defendant = Party(
            party_id="defendant-1",
            case_id="case1",
            name="被告某",
            party_type="natural_person",
            role_code="defendant_agent",
            side="defendant",
            litigation_history=LitigationHistory(
                lending_case_count=10,
                distinct_borrower_count=10,
                time_span_months=12,
                uniform_contract_detected=True,
            ),
        )
        inp = CredibilityScorerInput(
            case_id="case1",
            run_id="run1",
            amount_report=make_amount_report(),
            party_list=[defendant],
        )
        scorer = CredibilityScorer(thresholds=RuleThresholds())
        result = scorer.score(inp)
        cred07 = [d for d in result.deductions if d.rule_id == "CRED-07"]
        assert len(cred07) == 0
