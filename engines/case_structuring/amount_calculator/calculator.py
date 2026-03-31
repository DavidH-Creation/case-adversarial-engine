"""
AmountCalculator — 金额/诉请一致性硬校验模块。
Amount/claim consistency hard validation module.

纯规则层（deterministic），不调用 LLM。
Pure rule layer (deterministic), no LLM calls.

职责 / Responsibilities:
1. 接收调用方提供的四类结构化输入（放款流水、还款流水、争议归因、诉请描述符）
2. 计算 principal 类诉请的 calculated_amount（其他类型返回 None）
3. 执行七条硬校验规则
4. 生成 AmountConflict 列表
5. 激活 verdict_block_active（当 unresolved_conflicts 非空时）
6. 返回 AmountCalculationReport
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterator
from uuid import uuid4

from engines.shared.models import (
    AmountCalculationReport,
    AmountConflict,
    AmountConsistencyCheck,
    ClaimCalculationEntry,
    ClaimType,
    ContractValidity,
    DisputeResolutionStatus,
    InterestRecalculation,
    LoanTransaction,
    RepaymentAttribution,
    RepaymentTransaction,
)
from engines.shared.rule_config import RuleThresholds

from .schemas import AmountCalculatorInput


class AmountCalculator:
    """
    金额/诉请一致性确定性计算器。

    所有方法均为同步纯函数，不持有外部状态，可安全复用同一实例。

    使用方式 / Usage:
        calc = AmountCalculator()
        report = calc.calculate(inp)
    """

    def __init__(self, thresholds: RuleThresholds | None = None) -> None:
        self._thresholds = thresholds or RuleThresholds()

    def calculate(self, inp: AmountCalculatorInput) -> AmountCalculationReport:
        """
        执行金额一致性校验，返回完整报告。

        Args:
            inp: 计算器输入，包含四类结构化数据

        Returns:
            AmountCalculationReport — 含四张表和五条硬规则结果
        """
        # 规则 #7：合同无效/争议时利息重算（需要 conflicts 列表传入以记录缺失警告）
        principal_base = self._sum_principal_loans(inp.loan_transactions)

        # 1. 构建诉请计算表
        claim_table = self._build_claim_calculation_table(
            inp.claim_entries,
            inp.loan_transactions,
            inp.repayment_transactions,
        )

        # 2. 执行五条硬规则
        principal_base_unique = self._check_principal_base_unique(inp.disputed_amount_attributions)
        all_attributed = self._check_all_repayments_attributed(inp.repayment_transactions)
        text_table_consistent = self._check_text_table_consistent(claim_table)
        duplicate_claim = self._check_duplicate_interest_penalty(inp.claim_entries)
        total_reconstructable = self._check_total_reconstructable(claim_table)

        # 规则 #6：起诉总额 / 可核实交付总额 比值校验
        claim_delivery_ratio_normal = self._check_claim_delivery_ratio(
            inp.claim_entries, inp.loan_transactions
        )

        # 3. 生成冲突列表
        conflicts = list(
            self._generate_conflicts(
                claim_table=claim_table,
                disputed_attributions=inp.disputed_amount_attributions,
                loan_transactions=inp.loan_transactions,
            )
        )

        # 来源 3：起诉金额/可核实交付比值异常（rule #6）
        if not claim_delivery_ratio_normal:
            delivered = self._sum_principal_loans(inp.loan_transactions)
            total_claimed = sum(c.claimed_amount for c in inp.claim_entries)
            if delivered == Decimal("0"):
                ratio_desc = "∞（可核实交付为零）"
            else:
                ratio_desc = f"{total_claimed / delivered:.2f}"
            conflicts.append(
                AmountConflict(
                    conflict_id=f"conflict-{len(conflicts) + 1:03d}",
                    conflict_description=(
                        f"【虚假诉讼预警】起诉总额 {total_claimed} / 可核实交付 {delivered}"
                        f" = {ratio_desc}，超出预警阈值 {self._thresholds.false_litigation_ratio}"
                    ),
                    amount_a=total_claimed,
                    amount_b=delivered,
                    source_a_evidence_id="",
                    source_b_evidence_id="",
                    resolution_note="",
                )
            )

        # 规则 #7：合同无效/争议时利息重算（传入 conflicts 以记录缺失警告）
        interest_recalc = self._recalculate_interest(inp, principal_base, conflicts)

        # 4. verdict_block_active 硬规则：unresolved_conflicts 非空时必须为 True
        verdict_block_active = len(conflicts) > 0

        consistency = AmountConsistencyCheck(
            principal_base_unique=principal_base_unique,
            all_repayments_attributed=all_attributed,
            text_table_amount_consistent=text_table_consistent,
            duplicate_interest_penalty_claim=duplicate_claim,
            claim_total_reconstructable=total_reconstructable,
            unresolved_conflicts=conflicts,
            verdict_block_active=verdict_block_active,
            claim_delivery_ratio_normal=claim_delivery_ratio_normal,
        )

        return AmountCalculationReport(
            report_id=f"amount-report-{uuid4().hex[:8]}",
            case_id=inp.case_id,
            run_id=inp.run_id,
            loan_transactions=inp.loan_transactions,
            repayment_transactions=inp.repayment_transactions,
            disputed_amount_attributions=inp.disputed_amount_attributions,
            claim_calculation_table=claim_table,
            consistency_check_result=consistency,
            interest_recalculation=interest_recalc,
        )

    # ------------------------------------------------------------------
    # 诉请计算表构建 / Claim calculation table
    # ------------------------------------------------------------------

    def _build_claim_calculation_table(
        self,
        claim_entries,
        loan_transactions: list[LoanTransaction],
        repayment_transactions: list[RepaymentTransaction],
    ) -> list[ClaimCalculationEntry]:
        """
        构建诉请计算表。

        principal 类诉请：calculated_amount = 总放款基数 - 总还款（归因 principal）。
        其他类型：calculated_amount = None（无法从流水确定性计算）。
        delta = claimed_amount - calculated_amount（若 calculated_amount 为 None 则 delta = None）。
        """
        principal_calculated = self._compute_principal_amount(
            loan_transactions, repayment_transactions
        )

        entries: list[ClaimCalculationEntry] = []
        for descriptor in claim_entries:
            if descriptor.claim_type == ClaimType.principal:
                calc_amt = principal_calculated
                delta = descriptor.claimed_amount - calc_amt
                principal_loans = self._sum_principal_loans(loan_transactions)
                principal_repaid = self._sum_principal_repayments(repayment_transactions)
                explanation = (
                    f"计算值：总放款基数 {principal_loans} "
                    f"- 已还本金 {principal_repaid} "
                    f"= {calc_amt}"
                )
                if delta != Decimal("0"):
                    explanation += (
                        f"；差值 {delta}"
                        f"（claimed {descriptor.claimed_amount} vs calculated {calc_amt}）"
                    )
            else:
                calc_amt = None
                delta = None
                explanation = (
                    f"{descriptor.claim_type.value} 类诉请无法从流水确定性计算，"
                    "需结合合同利率/违约金条款"
                )

            entries.append(
                ClaimCalculationEntry(
                    claim_id=descriptor.claim_id,
                    claim_type=descriptor.claim_type,
                    claimed_amount=descriptor.claimed_amount,
                    calculated_amount=calc_amt,
                    delta=delta,
                    delta_explanation=explanation,
                )
            )

        return entries

    def _sum_principal_loans(self, loans: list[LoanTransaction]) -> Decimal:
        """计算 principal_base_contribution=True 的放款总额。"""
        return sum(
            (loan.amount for loan in loans if loan.principal_base_contribution),
            Decimal("0"),
        )

    def _sum_principal_repayments(self, repayments: list[RepaymentTransaction]) -> Decimal:
        """计算归因 principal 的已还款总额。"""
        return sum(
            (r.amount for r in repayments if r.attributed_to == RepaymentAttribution.principal),
            Decimal("0"),
        )

    def _compute_principal_amount(
        self,
        loans: list[LoanTransaction],
        repayments: list[RepaymentTransaction],
    ) -> Decimal:
        """计算应还本金 = principal 放款总额 - 已还本金总额。"""
        return self._sum_principal_loans(loans) - self._sum_principal_repayments(repayments)

    # ------------------------------------------------------------------
    # 硬规则 1：本金基数唯一性 / principal_base_unique
    # ------------------------------------------------------------------

    def _check_principal_base_unique(self, disputed_attributions) -> bool:
        """
        本金基数唯一性：当且仅当不存在 unresolved 的争议归因条目时返回 True。

        逻辑：若存在任何 resolution_status = unresolved 的争议项，
        表示本金基数存在未解决的口径分歧，无法唯一确定。
        """
        return not any(
            d.resolution_status == DisputeResolutionStatus.unresolved for d in disputed_attributions
        )

    # ------------------------------------------------------------------
    # 硬规则 2：每笔还款唯一归因 / all_repayments_attributed
    # ------------------------------------------------------------------

    def _check_all_repayments_attributed(self, repayments: list[RepaymentTransaction]) -> bool:
        """所有还款均已归因（attributed_to 非 None）时返回 True。"""
        return all(r.attributed_to is not None for r in repayments)

    # ------------------------------------------------------------------
    # 硬规则 3：文本与表格金额一致性 / text_table_consistent
    # ------------------------------------------------------------------

    def _check_text_table_consistent(self, claim_table: list[ClaimCalculationEntry]) -> bool:
        """
        所有可复算诉请（calculated_amount 非 None）的 delta 均为零时返回 True。
        无法计算的诉请（delta = None）不参与本项校验。
        """
        return all(entry.delta == Decimal("0") for entry in claim_table if entry.delta is not None)

    # ------------------------------------------------------------------
    # 硬规则 4：利息/违约金重复请求 / duplicate_interest_penalty
    # ------------------------------------------------------------------

    def _check_duplicate_interest_penalty(self, claim_entries) -> bool:
        """
        同一类型（interest 或 penalty）出现超过一条诉请时返回 True。
        """
        interest_count = sum(1 for c in claim_entries if c.claim_type == ClaimType.interest)
        penalty_count = sum(1 for c in claim_entries if c.claim_type == ClaimType.penalty)
        return interest_count > 1 or penalty_count > 1

    # ------------------------------------------------------------------
    # 硬规则 5：诉请总额可复算 / claim_total_reconstructable
    # ------------------------------------------------------------------

    def _check_total_reconstructable(self, claim_table: list[ClaimCalculationEntry]) -> bool:
        """
        所有可复算诉请（delta 非 None）的 delta 均为零时返回 True。

        注：v1.2 中与 text_table_amount_consistent 使用相同逻辑；
        分开命名以对应 spec 的两个独立语义字段，便于未来独立演化。
        """
        return self._check_text_table_consistent(claim_table)

    # ------------------------------------------------------------------
    # 硬规则 6：起诉金额/可核实交付比值 / claim_delivery_ratio
    # ------------------------------------------------------------------

    def _check_claim_delivery_ratio(
        self,
        claim_entries,
        loan_transactions: list[LoanTransaction],
    ) -> bool:
        """规则 #6: 起诉总额 / 可核实交付总额 <= 阈值时返回 True。
        若无 principal_base_contribution 放款且 claimed=0，跳过；
        若 delivered=0 但 claimed>0，直接视为异常（比值无穷大）。
        """
        delivered = self._sum_principal_loans(loan_transactions)
        total_claimed = sum(c.claimed_amount for c in claim_entries)
        if delivered == Decimal("0"):
            return total_claimed == Decimal("0")
        ratio = total_claimed / delivered
        return ratio <= self._thresholds.false_litigation_ratio

    # ------------------------------------------------------------------
    # 硬规则 7：合同无效/争议利息重算 / interest recalculation
    # ------------------------------------------------------------------

    def _recalculate_interest(
        self,
        inp: AmountCalculatorInput,
        principal_base: Decimal,
        conflicts: list[AmountConflict],
    ) -> InterestRecalculation | None:
        """规则 #7: 合同无效/争议时，利息按 LPR 重算。

        - invalid: 强制 LPR
        - disputed: min(contractual_rate, LPR * lpr_multiplier_cap)
        - valid: 返回 None
        - 缺少利率输入: 生成 warning conflict 并返回 None
        """
        if inp.contract_validity == ContractValidity.valid:
            return None
        if inp.contractual_interest_rate is None or inp.lpr_rate is None:
            missing = []
            if inp.contractual_interest_rate is None:
                missing.append("contractual_interest_rate")
            if inp.lpr_rate is None:
                missing.append("lpr_rate")
            conflicts.append(
                AmountConflict(
                    conflict_id=f"conflict-{len(conflicts) + 1:03d}",
                    conflict_description=(
                        f"【利息重算缺失】合同效力为 {inp.contract_validity.value}，"
                        f"但缺少 {', '.join(missing)}，无法执行利息重算"
                    ),
                    amount_a=Decimal("0"),
                    amount_b=Decimal("0"),
                    source_a_evidence_id="",
                    source_b_evidence_id="",
                    resolution_note="",
                )
            )
            return None

        original_rate = inp.contractual_interest_rate
        lpr = inp.lpr_rate

        if inp.contract_validity == ContractValidity.invalid:
            effective_rate = lpr
            basis = "LPR"
        else:  # disputed
            cap = lpr * self._thresholds.lpr_multiplier_cap
            effective_rate = min(original_rate, cap)
            basis = "LPR*4" if effective_rate == cap else f"合同约定（{original_rate}，未超上限）"

        # 注：以下为"单期概念金额"（principal × rate），用于对比利率切换前后的
        # 差额比例，不是精算利息（未乘期限因子）。下游如需实际利息金额应结合借贷期限计算。
        original_interest = principal_base * original_rate
        recalculated_interest = principal_base * effective_rate
        delta = original_interest - recalculated_interest

        return InterestRecalculation(
            original_rate=original_rate,
            effective_rate=effective_rate,
            rate_basis=basis,
            contract_validity=inp.contract_validity,
            original_interest_amount=original_interest,
            recalculated_interest_amount=recalculated_interest,
            delta=delta,
        )

    # ------------------------------------------------------------------
    # 冲突生成 / Conflict generation
    # ------------------------------------------------------------------

    def _generate_conflicts(
        self,
        claim_table: list[ClaimCalculationEntry],
        disputed_attributions,
        loan_transactions: list[LoanTransaction],
    ) -> Iterator[AmountConflict]:
        """
        生成 AmountConflict 列表。三类来源：

        1. 诉请计算 delta ≠ 0（claimed vs calculated 不一致）
        2. 未解决的争议归因（resolution_status = unresolved）
        3. 起诉金额/可核实交付比值异常（rule #6，在 calculate() 中追加）
        """
        conflict_index = 0

        # 来源 1：诉请计算 delta ≠ 0
        for entry in claim_table:
            if entry.delta is not None and entry.delta != Decimal("0"):
                conflict_index += 1
                # 从放款流水取第一条 evidence_id 作为计算依据来源
                source_b = loan_transactions[0].evidence_id if loan_transactions else ""
                yield AmountConflict(
                    conflict_id=f"conflict-{conflict_index:03d}",
                    conflict_description=(
                        f"诉请 {entry.claim_id}（{entry.claim_type.value}）"
                        f"：claimed {entry.claimed_amount} vs calculated {entry.calculated_amount}"
                    ),
                    amount_a=entry.claimed_amount,
                    amount_b=entry.calculated_amount,
                    source_a_evidence_id="",  # 来自 claim text，无单一证据 ID
                    source_b_evidence_id=source_b,
                    resolution_note="",
                )

        # 来源 2：unresolved 争议归因
        for disputed in disputed_attributions:
            if disputed.resolution_status == DisputeResolutionStatus.unresolved:
                conflict_index += 1
                yield AmountConflict(
                    conflict_id=f"conflict-{conflict_index:03d}",
                    conflict_description=(
                        f"争议归因 {disputed.item_id}：{disputed.dispute_description}"
                        f"（原告：{disputed.plaintiff_attribution}；"
                        f"被告：{disputed.defendant_attribution}）"
                    ),
                    amount_a=disputed.amount,
                    amount_b=Decimal("0"),
                    source_a_evidence_id="",
                    source_b_evidence_id="",
                    resolution_note="",
                )
