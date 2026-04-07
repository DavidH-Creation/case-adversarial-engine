"""
民间借贷专属模型 / Civil-loan-specific models.

物理隔离原则 (Unit 22 Phase A):
本模块包含仅适用于"民间借贷 (civil_loan)"案件类型的金额计算与一致性校验数据结构，
将民间借贷专属逻辑从通用 pipeline 层物理隔离出来，避免引擎共享模型时被特定案件
类型的字段污染。其它案件类型 (劳动争议、房屋买卖等) 不应直接依赖本模块的类型，
而是应当在各自的 schemas 中描述其领域语义。

向后兼容：所有这些类仍可通过 `from engines.shared.models import X` 或
`from engines.shared.models.pipeline import X` 导入 — pipeline.py 提供
re-export 兼容旧路径。
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from engines.shared.models.core import (
    ClaimType,
    ContractValidity,
    DisputeResolutionStatus,
)


# ---------------------------------------------------------------------------
# 民间借贷专属枚举 / civil-loan-specific enums
# ---------------------------------------------------------------------------
#
# Unit 22 Phase C: physically isolated from engines.shared.models.core so that
# the generic core layer no longer carries 民间借贷-specific vocabulary. These
# enums remain importable as ``from engines.shared.models import X`` because
# ``engines/shared/models/__init__.py`` re-exports them. Direct deep imports
# of the form ``from engines.shared.models.core import RepaymentAttribution``
# are now broken by design.


class RepaymentAttribution(str, Enum):
    """还款归因类型 — 每笔还款必须唯一归因到某一类。"""

    principal = "principal"
    interest = "interest"
    penalty = "penalty"


# ---------------------------------------------------------------------------
# 金额计算层 / Amount calculation layer  (P0.2)
# ---------------------------------------------------------------------------


class LoanTransaction(BaseModel):
    """放款流水记录。每笔放款对应一条。"""

    tx_id: str = Field(..., min_length=1, description="流水唯一标识")
    date: str = Field(..., min_length=1, description="放款日期，格式 YYYY-MM-DD")
    amount: Decimal = Field(..., gt=0, description="放款金额，必须大于零")
    evidence_id: str = Field(..., min_length=1, description="关联放款凭证 evidence_id")
    principal_base_contribution: bool = Field(
        ..., description="是否计入本金基数；True 表示该笔放款为主张本金的组成部分"
    )


class RepaymentTransaction(BaseModel):
    """还款流水记录。每笔还款对应一条，必须唯一归因。"""

    tx_id: str = Field(..., min_length=1, description="流水唯一标识")
    date: str = Field(..., min_length=1, description="还款日期，格式 YYYY-MM-DD")
    amount: Decimal = Field(..., gt=0, description="还款金额，必须大于零")
    evidence_id: str = Field(..., min_length=1, description="关联还款凭证 evidence_id")
    attributed_to: Optional[RepaymentAttribution] = Field(
        None, description="归因类型；None 表示尚未归因（触发 all_repayments_attributed=False）"
    )
    attribution_basis: str = Field(default="", description="归因依据说明")


class DisputedAmountAttribution(BaseModel):
    """争议款项归因记录。记录原被告对同一笔款项的不同立场。"""

    item_id: str = Field(..., min_length=1, description="争议条目唯一标识")
    amount: Decimal = Field(..., gt=0, description="争议金额")
    dispute_description: str = Field(..., min_length=1, description="争议说明")
    plaintiff_attribution: str = Field(default="", description="原告立场")
    defendant_attribution: str = Field(default="", description="被告立场")
    resolution_status: DisputeResolutionStatus = DisputeResolutionStatus.unresolved


class ClaimCalculationEntry(BaseModel):
    """诉请计算表中的单行记录。"""

    claim_id: str = Field(..., min_length=1, description="关联 Claim.claim_id")
    claim_type: ClaimType
    claimed_amount: Decimal = Field(..., ge=0, description="诉请金额（由调用方提供）")
    calculated_amount: Optional[Decimal] = Field(
        None, description="系统可复算金额；None 表示该类型无法从流水确定性计算"
    )
    delta: Optional[Decimal] = Field(
        None, description="claimed_amount - calculated_amount；None 当 calculated_amount 为 None"
    )
    delta_explanation: str = Field(default="", description="差值说明")


class AmountConflict(BaseModel):
    """金额口径冲突记录。每个未解释冲突对应一条。"""

    conflict_id: str = Field(..., min_length=1, description="冲突唯一标识")
    conflict_description: str = Field(..., min_length=1, description="冲突描述")
    amount_a: Decimal = Field(..., description="第一种口径的金额")
    amount_b: Decimal = Field(..., description="第二种口径的金额")
    source_a_evidence_id: str = Field(default="", description="口径 A 的证据来源")
    source_b_evidence_id: str = Field(default="", description="口径 B 的证据来源")
    resolution_note: str = Field(default="", description="解释说明；空字符串表示无解释")


class AmountConsistencyCheck(BaseModel):
    """五条硬校验规则的聚合结果。"""

    principal_base_unique: bool = Field(
        ..., description="本金基数是否唯一确定：无未解决的本金口径冲突"
    )
    all_repayments_attributed: bool = Field(
        ..., description="每笔还款是否唯一归因：所有 RepaymentTransaction.attributed_to 非 None"
    )
    text_table_amount_consistent: bool = Field(
        ..., description="文本与表格金额是否一致：所有可复算诉请的 delta == 0"
    )
    duplicate_interest_penalty_claim: bool = Field(
        ..., description="是否存在利息/违约金重复请求：同类型诉请出现超过一条"
    )
    claim_total_reconstructable: bool = Field(
        ..., description="诉请总额是否可从流水复算：所有可复算诉请的 delta 均为零"
    )
    unresolved_conflicts: list[AmountConflict] = Field(
        default_factory=list,
        description="未解释的金额口径冲突列表；非空时触发 verdict_block_active",
    )
    verdict_block_active: bool = Field(
        ...,
        description="系统是否因未解释冲突阻断稳定裁判判断；硬规则：unresolved_conflicts 非空时必须为 True",
    )
    claim_delivery_ratio_normal: bool = Field(
        default=True,
        description="起诉金额与可核实交付金额比值是否正常（ratio <= 阈值）",
    )

    @model_validator(mode="after")
    def _enforce_verdict_block_rule(self) -> "AmountConsistencyCheck":
        """硬规则：unresolved_conflicts 非空时 verdict_block_active 必须为 True。"""
        if self.unresolved_conflicts and not self.verdict_block_active:
            raise ValueError("verdict_block_active 必须为 True 当 unresolved_conflicts 非空")
        return self


class InterestRecalculation(BaseModel):
    """利息重算记录 — 合同无效时的利率切换结果。

    注：interest_amount 字段为单期概念金额（principal × rate），用于对比利率切换
    前后的差额比例。如需精算利息金额，下游应结合实际借贷期限重新计算。
    """

    original_rate: Decimal = Field(..., description="原合同约定利率")
    effective_rate: Decimal = Field(..., description="重算后适用利率")
    rate_basis: str = Field(..., min_length=1, description="利率依据（如 LPR、LPR*4）")
    contract_validity: ContractValidity
    original_interest_amount: Decimal = Field(
        ..., description="单期概念利息 = principal × original_rate"
    )
    recalculated_interest_amount: Decimal = Field(
        ..., description="单期概念利息 = principal × effective_rate"
    )
    delta: Decimal = Field(..., description="利息差额 = original - recalculated（同期比较）")


class AmountCalculationReport(BaseModel):
    """金额/诉请一致性硬校验报告。P0.2 产物，纳入 CaseWorkspace.artifact_index。"""

    report_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    loan_transactions: list[LoanTransaction] = Field(..., description="放款流水表")
    repayment_transactions: list[RepaymentTransaction] = Field(..., description="还款流水表")
    disputed_amount_attributions: list[DisputedAmountAttribution] = Field(
        default_factory=list, description="争议款项归因表"
    )
    claim_calculation_table: list[ClaimCalculationEntry] = Field(..., description="诉请计算表")
    consistency_check_result: AmountConsistencyCheck = Field(
        ..., description="一致性校验结果（五条硬规则）"
    )
    interest_recalculation: Optional[InterestRecalculation] = Field(
        default=None, description="合同无效/争议时的利息重算记录"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


# ---------------------------------------------------------------------------
# 职业放贷人检测 / Professional lender detection (CRED-07 input)
# ---------------------------------------------------------------------------


class LitigationHistory(BaseModel):
    """当事人近期放贷诉讼统计 — 职业放贷人检测输入。

    民间借贷专属：仅 CRED-07 (credibility_scorer) 在原告方使用此结构判定职业
    放贷人。Party 上的对应字段已弱化为 dict[str, Any] 以避免通用模型耦合此
    案件类型；调用方可在序列化前后通过 `LitigationHistory.model_validate(d)` /
    `hist.model_dump()` 在 dict 与 BaseModel 之间互转。
    """

    lending_case_count: int = Field(default=0, ge=0, description="近期放贷诉讼数")
    distinct_borrower_count: int = Field(default=0, ge=0, description="不同借款人数")
    total_lending_amount: Decimal = Field(default=Decimal("0"), ge=0, description="累计放贷金额")
    time_span_months: int = Field(default=0, ge=0, description="统计时间跨度（月）")
    uniform_contract_detected: bool = Field(default=False, description="借条格式是否雷同")


__all__ = [
    "AmountCalculationReport",
    "AmountConflict",
    "AmountConsistencyCheck",
    "ClaimCalculationEntry",
    "DisputedAmountAttribution",
    "InterestRecalculation",
    "LitigationHistory",
    "LoanTransaction",
    "RepaymentAttribution",
    "RepaymentTransaction",
]
