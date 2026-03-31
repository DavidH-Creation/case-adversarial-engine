"""
AmountCalculator 单元测试。

测试策略：每条硬规则独立覆盖，使用最小 fixture 验证。
不依赖 LLM；所有输入为内联构造的 Pydantic 对象。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from engines.case_structuring.amount_calculator.calculator import AmountCalculator
from engines.case_structuring.amount_calculator.schemas import (
    AmountCalculatorInput,
    AmountClaimDescriptor,
)
from engines.shared.models import (
    ClaimType,
    DisputedAmountAttribution,
    DisputeResolutionStatus,
    LoanTransaction,
    RepaymentAttribution,
    RepaymentTransaction,
)


# ---------------------------------------------------------------------------
# 测试辅助工厂 / Test helpers
# ---------------------------------------------------------------------------


def _loan(tx_id: str, amount: str, is_principal: bool = True) -> LoanTransaction:
    return LoanTransaction(
        tx_id=tx_id,
        date="2024-01-15",
        amount=Decimal(amount),
        evidence_id=f"evidence-{tx_id}",
        principal_base_contribution=is_principal,
    )


def _repayment(
    tx_id: str,
    amount: str,
    attributed_to: RepaymentAttribution | None = RepaymentAttribution.principal,
) -> RepaymentTransaction:
    return RepaymentTransaction(
        tx_id=tx_id,
        date="2024-06-01",
        amount=Decimal(amount),
        evidence_id=f"evidence-{tx_id}",
        attributed_to=attributed_to,
        attribution_basis="合同约定",
    )


def _claim(
    claim_id: str,
    claim_type: ClaimType,
    amount: str,
) -> AmountClaimDescriptor:
    return AmountClaimDescriptor(
        claim_id=claim_id,
        claim_type=claim_type,
        claimed_amount=Decimal(amount),
        evidence_ids=[f"evidence-claim-{claim_id}"],
    )


def _base_input(**overrides) -> AmountCalculatorInput:
    """最小合法输入：一笔放款 5 万，一笔还款 1 万，一条本金诉请 4 万。"""
    defaults = dict(
        case_id="case-001",
        run_id="run-001",
        source_material_ids=["mat-001"],
        loan_transactions=[_loan("loan-001", "50000")],
        repayment_transactions=[_repayment("repay-001", "10000")],
        claim_entries=[_claim("claim-principal-001", ClaimType.principal, "40000")],
        disputed_amount_attributions=[],
    )
    defaults.update(overrides)
    return AmountCalculatorInput(**defaults)


# ---------------------------------------------------------------------------
# 基础路径测试 / Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    """所有规则通过、无冲突的正常路径。"""

    def test_returns_amount_calculation_report(self):
        """calculate() 应返回 AmountCalculationReport。"""
        from engines.shared.models import AmountCalculationReport

        calc = AmountCalculator()
        report = calc.calculate(_base_input())
        assert isinstance(report, AmountCalculationReport)

    def test_report_case_id_and_run_id(self):
        """report.case_id 和 run_id 与输入一致。"""
        calc = AmountCalculator()
        report = calc.calculate(_base_input())
        assert report.case_id == "case-001"
        assert report.run_id == "run-001"

    def test_four_tables_populated(self):
        """四张表均在报告中存在。"""
        calc = AmountCalculator()
        report = calc.calculate(_base_input())
        assert len(report.loan_transactions) == 1
        assert len(report.repayment_transactions) == 1
        assert isinstance(report.claim_calculation_table, list)
        assert isinstance(report.disputed_amount_attributions, list)

    def test_verdict_block_inactive_when_no_conflicts(self):
        """无冲突时 verdict_block_active 为 False。"""
        calc = AmountCalculator()
        report = calc.calculate(_base_input())
        assert report.consistency_check_result.verdict_block_active is False
        assert report.consistency_check_result.unresolved_conflicts == []


# ---------------------------------------------------------------------------
# Rule 1: principal_base_unique
# ---------------------------------------------------------------------------


class TestPrincipalBaseUnique:
    """本金基数唯一性校验。"""

    def test_unique_when_no_unresolved_disputes(self):
        inp = _base_input()
        report = AmountCalculator().calculate(inp)
        assert report.consistency_check_result.principal_base_unique is True

    def test_not_unique_when_unresolved_principal_dispute(self):
        """存在 unresolved 的争议归因条目时，principal_base_unique 为 False。"""
        disputed = DisputedAmountAttribution(
            item_id="dispute-001",
            amount=Decimal("5000"),
            dispute_description="此笔 5000 元是否计入本金存在争议",
            plaintiff_attribution="计入本金",
            defendant_attribution="不计入本金",
            resolution_status=DisputeResolutionStatus.unresolved,
        )
        inp = _base_input(disputed_amount_attributions=[disputed])
        report = AmountCalculator().calculate(inp)
        assert report.consistency_check_result.principal_base_unique is False

    def test_unique_when_dispute_is_resolved(self):
        """已解决的争议不影响 principal_base_unique。"""
        resolved = DisputedAmountAttribution(
            item_id="dispute-002",
            amount=Decimal("5000"),
            dispute_description="已解决的争议",
            plaintiff_attribution="计入本金",
            defendant_attribution="不计入本金",
            resolution_status=DisputeResolutionStatus.resolved,
        )
        inp = _base_input(disputed_amount_attributions=[resolved])
        report = AmountCalculator().calculate(inp)
        assert report.consistency_check_result.principal_base_unique is True


# ---------------------------------------------------------------------------
# Rule 2: all_repayments_attributed
# ---------------------------------------------------------------------------


class TestAllRepaymentsAttributed:
    """每笔还款唯一归因校验。"""

    def test_all_attributed_when_all_have_attribution(self):
        inp = _base_input()
        report = AmountCalculator().calculate(inp)
        assert report.consistency_check_result.all_repayments_attributed is True

    def test_not_all_attributed_when_one_missing(self):
        """任一还款 attributed_to 为 None 时，all_repayments_attributed 为 False。"""
        repayments = [
            _repayment("repay-001", "10000"),
            _repayment("repay-002", "5000", attributed_to=None),  # 未归因
        ]
        inp = _base_input(repayment_transactions=repayments)
        report = AmountCalculator().calculate(inp)
        assert report.consistency_check_result.all_repayments_attributed is False

    def test_all_attributed_when_no_repayments(self):
        """无还款时，all_repayments_attributed 为 True（空集合满足全称命题）。"""
        inp = _base_input(
            repayment_transactions=[],
            # 无还款时本金 = 50000，诉请需同步修正
            claim_entries=[_claim("claim-principal-001", ClaimType.principal, "50000")],
        )
        report = AmountCalculator().calculate(inp)
        assert report.consistency_check_result.all_repayments_attributed is True


# ---------------------------------------------------------------------------
# Rule 3: text_table_amount_consistent
# ---------------------------------------------------------------------------


class TestTextTableAmountConsistent:
    """文本与表格金额一致性校验。"""

    def test_consistent_when_principal_matches(self):
        """放款 5 万 - 还款 1 万 = 4 万 == claimed 4 万 → consistent。"""
        inp = _base_input()  # loan=50000, repayment=10000, claim=40000
        report = AmountCalculator().calculate(inp)
        assert report.consistency_check_result.text_table_amount_consistent is True

    def test_inconsistent_when_principal_mismatches(self):
        """放款 5 万 - 还款 1 万 = 4 万，但 claimed 3.5 万 → inconsistent。"""
        inp = _base_input(
            claim_entries=[_claim("claim-principal-001", ClaimType.principal, "35000")]
        )
        report = AmountCalculator().calculate(inp)
        assert report.consistency_check_result.text_table_amount_consistent is False

    def test_consistent_skips_non_principal_when_no_calc(self):
        """interest/penalty 类诉请 calculated_amount 为 None，不参与一致性校验。"""
        inp = _base_input(
            claim_entries=[
                _claim("claim-principal-001", ClaimType.principal, "40000"),
                _claim("claim-interest-001", ClaimType.interest, "3600"),  # 无法计算
            ]
        )
        report = AmountCalculator().calculate(inp)
        # principal delta=0, interest 跳过 → consistent
        assert report.consistency_check_result.text_table_amount_consistent is True


# ---------------------------------------------------------------------------
# Rule 4: duplicate_interest_penalty_claim
# ---------------------------------------------------------------------------


class TestDuplicateInterestPenaltyClaim:
    """利息/违约金重复请求检测。"""

    def test_no_duplicate_when_single_interest(self):
        inp = _base_input(
            claim_entries=[
                _claim("claim-principal-001", ClaimType.principal, "40000"),
                _claim("claim-interest-001", ClaimType.interest, "3600"),
            ]
        )
        report = AmountCalculator().calculate(inp)
        assert report.consistency_check_result.duplicate_interest_penalty_claim is False

    def test_duplicate_detected_for_interest(self):
        """两条 interest 诉请 → duplicate_interest_penalty_claim = True。"""
        inp = _base_input(
            claim_entries=[
                _claim("claim-principal-001", ClaimType.principal, "40000"),
                _claim("claim-interest-001", ClaimType.interest, "3600"),
                _claim("claim-interest-002", ClaimType.interest, "2400"),
            ]
        )
        report = AmountCalculator().calculate(inp)
        assert report.consistency_check_result.duplicate_interest_penalty_claim is True

    def test_duplicate_detected_for_penalty(self):
        """两条 penalty 诉请 → duplicate_interest_penalty_claim = True。"""
        inp = _base_input(
            claim_entries=[
                _claim("claim-principal-001", ClaimType.principal, "40000"),
                _claim("claim-penalty-001", ClaimType.penalty, "1000"),
                _claim("claim-penalty-002", ClaimType.penalty, "2000"),
            ]
        )
        report = AmountCalculator().calculate(inp)
        assert report.consistency_check_result.duplicate_interest_penalty_claim is True

    def test_no_duplicate_when_interest_and_penalty_each_once(self):
        """interest × 1 且 penalty × 1 → 不算重复。"""
        inp = _base_input(
            claim_entries=[
                _claim("claim-principal-001", ClaimType.principal, "40000"),
                _claim("claim-interest-001", ClaimType.interest, "3600"),
                _claim("claim-penalty-001", ClaimType.penalty, "1000"),
            ]
        )
        report = AmountCalculator().calculate(inp)
        assert report.consistency_check_result.duplicate_interest_penalty_claim is False


# ---------------------------------------------------------------------------
# Rule 5: claim_total_reconstructable
# ---------------------------------------------------------------------------


class TestClaimTotalReconstructable:
    """诉请总额可复算校验。"""

    def test_reconstructable_when_all_delta_zero(self):
        inp = _base_input()
        report = AmountCalculator().calculate(inp)
        assert report.consistency_check_result.claim_total_reconstructable is True

    def test_not_reconstructable_when_delta_nonzero(self):
        """principal 诉请 delta ≠ 0 → claim_total_reconstructable = False。"""
        inp = _base_input(
            claim_entries=[_claim("claim-principal-001", ClaimType.principal, "45000")]
        )
        report = AmountCalculator().calculate(inp)
        assert report.consistency_check_result.claim_total_reconstructable is False

    def test_reconstructable_skips_non_calculable(self):
        """interest 类 delta=None 不影响 claim_total_reconstructable。"""
        inp = _base_input(
            claim_entries=[
                _claim("claim-principal-001", ClaimType.principal, "40000"),
                _claim("claim-interest-001", ClaimType.interest, "9999"),  # 无法复算，跳过
            ]
        )
        report = AmountCalculator().calculate(inp)
        assert report.consistency_check_result.claim_total_reconstructable is True


# ---------------------------------------------------------------------------
# verdict_block_active
# ---------------------------------------------------------------------------


class TestVerdictBlockActive:
    """verdict_block_active 机制测试。"""

    def test_verdict_block_when_unresolved_dispute(self):
        """存在 unresolved 争议 → verdict_block_active = True。"""
        disputed = DisputedAmountAttribution(
            item_id="dispute-001",
            amount=Decimal("5000"),
            dispute_description="争议",
            plaintiff_attribution="A",
            defendant_attribution="B",
            resolution_status=DisputeResolutionStatus.unresolved,
        )
        inp = _base_input(disputed_amount_attributions=[disputed])
        report = AmountCalculator().calculate(inp)
        assert report.consistency_check_result.verdict_block_active is True
        assert len(report.consistency_check_result.unresolved_conflicts) > 0

    def test_verdict_block_when_principal_mismatch(self):
        """principal 金额不一致（delta ≠ 0）→ 生成冲突 → verdict_block_active = True。"""
        inp = _base_input(
            claim_entries=[_claim("claim-principal-001", ClaimType.principal, "99999")]
        )
        report = AmountCalculator().calculate(inp)
        assert report.consistency_check_result.verdict_block_active is True

    def test_no_verdict_block_clean_case(self):
        """干净案例：五条规则全部通过 → verdict_block_active = False。"""
        report = AmountCalculator().calculate(_base_input())
        assert report.consistency_check_result.verdict_block_active is False


# ---------------------------------------------------------------------------
# ClaimCalculationEntry 计算细节
# ---------------------------------------------------------------------------


class TestClaimCalculationEntries:
    """诉请计算表 delta 和 calculated_amount 的详细验证。"""

    def test_principal_calculated_amount_correct(self):
        """principal calculated_amount = sum(loans) - sum(repayments to principal)。"""
        inp = _base_input(
            loan_transactions=[_loan("loan-001", "50000")],
            repayment_transactions=[
                _repayment("repay-001", "10000", RepaymentAttribution.principal)
            ],
            claim_entries=[_claim("c1", ClaimType.principal, "40000")],
        )
        report = AmountCalculator().calculate(inp)
        entry = report.claim_calculation_table[0]
        assert entry.calculated_amount == Decimal("40000")
        assert entry.delta == Decimal("0")

    def test_principal_delta_nonzero(self):
        """claimed 45000 vs calculated 40000 → delta = 5000。"""
        inp = _base_input(
            loan_transactions=[_loan("loan-001", "50000")],
            repayment_transactions=[
                _repayment("repay-001", "10000", RepaymentAttribution.principal)
            ],
            claim_entries=[_claim("c1", ClaimType.principal, "45000")],
        )
        report = AmountCalculator().calculate(inp)
        entry = report.claim_calculation_table[0]
        assert entry.delta == Decimal("5000")

    def test_interest_claim_has_no_calculated_amount(self):
        """interest 类诉请无法从流水确定性计算 → calculated_amount = None，delta = None。"""
        inp = _base_input(
            claim_entries=[
                _claim("c1", ClaimType.principal, "40000"),
                _claim("c2", ClaimType.interest, "3600"),
            ]
        )
        report = AmountCalculator().calculate(inp)
        interest_entry = next(
            e for e in report.claim_calculation_table if e.claim_type == ClaimType.interest
        )
        assert interest_entry.calculated_amount is None
        assert interest_entry.delta is None

    def test_multiple_loans_summed(self):
        """多笔放款：calculated_amount = 总放款 - 总还款（principal 归因）。"""
        inp = _base_input(
            loan_transactions=[
                _loan("loan-001", "30000"),
                _loan("loan-002", "20000"),
            ],
            repayment_transactions=[
                _repayment("repay-001", "5000", RepaymentAttribution.principal),
                _repayment("repay-002", "5000", RepaymentAttribution.principal),
            ],
            claim_entries=[_claim("c1", ClaimType.principal, "40000")],
        )
        report = AmountCalculator().calculate(inp)
        entry = report.claim_calculation_table[0]
        assert entry.calculated_amount == Decimal("40000")
        assert entry.delta == Decimal("0")

    def test_repayment_to_interest_not_counted_in_principal(self):
        """归因 interest 的还款不影响本金计算。"""
        inp = _base_input(
            loan_transactions=[_loan("loan-001", "50000")],
            repayment_transactions=[
                _repayment("repay-001", "10000", RepaymentAttribution.principal),
                _repayment("repay-002", "3600", RepaymentAttribution.interest),  # 不影响本金
            ],
            claim_entries=[_claim("c1", ClaimType.principal, "40000")],
        )
        report = AmountCalculator().calculate(inp)
        entry = report.claim_calculation_table[0]
        # 本金 = 50000 - 10000（principal归因）= 40000，interest归因的3600不影响
        assert entry.calculated_amount == Decimal("40000")
        assert entry.delta == Decimal("0")


from engines.shared.rule_config import RuleThresholds

# ---------------------------------------------------------------------------
# Rule #6: 起诉金额/可核实交付比值 (claim_delivery_ratio_normal)
# ---------------------------------------------------------------------------


class TestRule6ClaimDeliveryRatio:
    """rule #6: total_claimed / total_principal_loans > threshold → 预警。"""

    def test_ratio_normal_within_threshold(self):
        """claimed 50000 / delivered 50000 = 1.0 → normal。"""
        inp = _base_input()
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        assert report.consistency_check_result.claim_delivery_ratio_normal is True

    def test_ratio_exceeds_threshold(self):
        """claimed 150000 / delivered 50000 = 3.0 > 2.0 → abnormal。"""
        inp = _base_input(
            claim_entries=[_claim("claim-principal-001", ClaimType.principal, "150000")],
        )
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        assert report.consistency_check_result.claim_delivery_ratio_normal is False

    def test_ratio_exactly_at_threshold(self):
        """claimed 100000 / delivered 50000 = 2.0 → still normal (<=)。"""
        inp = _base_input(
            claim_entries=[_claim("claim-principal-001", ClaimType.principal, "100000")],
        )
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        assert report.consistency_check_result.claim_delivery_ratio_normal is True

    def test_custom_threshold(self):
        """custom threshold 1.5: claimed 80000 / delivered 50000 = 1.6 > 1.5 → abnormal。"""
        inp = _base_input(
            claim_entries=[_claim("claim-principal-001", ClaimType.principal, "80000")],
        )
        calc = AmountCalculator(thresholds=RuleThresholds(false_litigation_ratio=Decimal("1.5")))
        report = calc.calculate(inp)
        assert report.consistency_check_result.claim_delivery_ratio_normal is False

    def test_generates_risk_flag_conflict(self):
        """ratio > threshold → generates AmountConflict。"""
        inp = _base_input(
            claim_entries=[_claim("claim-principal-001", ClaimType.principal, "150000")],
        )
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        ratio_conflicts = [
            c
            for c in report.consistency_check_result.unresolved_conflicts
            if "虚假诉讼" in c.conflict_description or "ratio" in c.conflict_description.lower()
        ]
        assert len(ratio_conflicts) >= 1

    def test_no_principal_loans_claimed_positive_flags_abnormal(self):
        """No principal_base_contribution=True loans + claimed>0 → ratio=∞, flagged abnormal。"""
        inp = _base_input(
            loan_transactions=[_loan("loan-001", "50000", is_principal=False)],
            claim_entries=[_claim("claim-interest-001", ClaimType.interest, "10000")],
        )
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        assert report.consistency_check_result.claim_delivery_ratio_normal is False
        ratio_conflicts = [
            c
            for c in report.consistency_check_result.unresolved_conflicts
            if "∞" in c.conflict_description or "为零" in c.conflict_description
        ]
        assert len(ratio_conflicts) >= 1

    def test_no_principal_loans_claimed_zero_skips(self):
        """No principal_base_contribution=True loans + claimed=0 → skip (both zero)。"""
        inp = _base_input(
            loan_transactions=[_loan("loan-001", "50000", is_principal=False)],
            claim_entries=[_claim("claim-interest-001", ClaimType.interest, "0")],
        )
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        assert report.consistency_check_result.claim_delivery_ratio_normal is True


from engines.shared.models import ContractValidity, InterestRecalculation

# ---------------------------------------------------------------------------
# Rule #7: 合同无效后利息重算 (interest recalculation)
# ---------------------------------------------------------------------------


class TestRule7InterestRecalculation:
    """rule #7: contract invalid → interest recalculated at LPR。"""

    def test_valid_contract_no_recalculation(self):
        inp = _base_input()
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        assert report.interest_recalculation is None

    def test_invalid_contract_forces_lpr(self):
        inp = _base_input(
            contract_validity=ContractValidity.invalid,
            contractual_interest_rate=Decimal("0.24"),
            lpr_rate=Decimal("0.0385"),
        )
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        assert report.interest_recalculation is not None
        ir = report.interest_recalculation
        assert ir.effective_rate == Decimal("0.0385")
        assert ir.rate_basis == "LPR"
        assert ir.contract_validity == ContractValidity.invalid

    def test_disputed_contract_caps_at_lpr_x4(self):
        inp = _base_input(
            contract_validity=ContractValidity.disputed,
            contractual_interest_rate=Decimal("0.24"),
            lpr_rate=Decimal("0.0385"),
        )
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        assert report.interest_recalculation is not None
        ir = report.interest_recalculation
        expected_cap = Decimal("0.0385") * Decimal("4.0")
        assert ir.effective_rate == min(Decimal("0.24"), expected_cap)
        assert ir.rate_basis == "LPR*4"

    def test_disputed_rate_already_below_cap(self):
        inp = _base_input(
            contract_validity=ContractValidity.disputed,
            contractual_interest_rate=Decimal("0.10"),
            lpr_rate=Decimal("0.0385"),
        )
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        ir = report.interest_recalculation
        assert ir.effective_rate == Decimal("0.10")  # below cap, no reduction

    def test_interest_delta_calculated(self):
        inp = _base_input(
            contract_validity=ContractValidity.invalid,
            contractual_interest_rate=Decimal("0.24"),
            lpr_rate=Decimal("0.0385"),
        )
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        ir = report.interest_recalculation
        assert ir.delta == ir.original_interest_amount - ir.recalculated_interest_amount
        assert ir.delta > 0  # 24% > 3.85%, so delta must be positive

    def test_no_recalculation_without_interest_rate(self):
        """contract_validity=invalid but no contractual_interest_rate → skip + conflict warning。"""
        inp = _base_input(
            contract_validity=ContractValidity.invalid,
            lpr_rate=Decimal("0.0385"),
        )
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        assert report.interest_recalculation is None
        missing_conflicts = [
            c
            for c in report.consistency_check_result.unresolved_conflicts
            if "利息重算缺失" in c.conflict_description
        ]
        assert len(missing_conflicts) == 1
        assert "contractual_interest_rate" in missing_conflicts[0].conflict_description

    def test_no_recalculation_without_lpr_rate(self):
        """contract_validity=invalid but no lpr_rate → skip + conflict warning。"""
        inp = _base_input(
            contract_validity=ContractValidity.invalid,
            contractual_interest_rate=Decimal("0.24"),
        )
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        assert report.interest_recalculation is None
        missing_conflicts = [
            c
            for c in report.consistency_check_result.unresolved_conflicts
            if "利息重算缺失" in c.conflict_description
        ]
        assert len(missing_conflicts) == 1
        assert "lpr_rate" in missing_conflicts[0].conflict_description
