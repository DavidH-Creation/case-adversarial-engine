"""
amount_calculator 引擎专用数据模型。
Engine-specific schemas for amount_calculator.

共享类型从 engines.shared.models 导入；本模块只保留：
- AmountClaimDescriptor：调用方提供的诉请金额描述符
- AmountCalculatorInput：计算器输入 wrapper
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

# 从共享模块导入所有共享类型 / Import all shared types
from engines.shared.models import (  # noqa: F401
    AmountCalculationReport,
    AmountConsistencyCheck,
    AmountConflict,
    ClaimCalculationEntry,
    ClaimType,
    ContractValidity,
    DisputedAmountAttribution,
    DisputeResolutionStatus,
    LoanTransaction,
    RepaymentAttribution,
    RepaymentTransaction,
)


# ---------------------------------------------------------------------------
# 引擎专用 wrapper / Engine-specific wrappers
# ---------------------------------------------------------------------------


class AmountClaimDescriptor(BaseModel):
    """
    诉请金额描述符 — 调用方提供的结构化诉请信息。

    由调用方（上游 LLM 提取或人工录入）将 Claim.claim_text 解析为结构化字段后传入，
    保证 amount_calculator 本身不依赖文本解析。

    Args:
        claim_id: 对应 Claim.claim_id
        claim_type: 诉请类型枚举
        claimed_amount: 诉请金额（调用方解析自 claim_text）
        evidence_ids: 支撑该诉请的证据 ID 列表
    """
    claim_id: str = Field(..., min_length=1, description="对应 Claim.claim_id")
    claim_type: ClaimType
    claimed_amount: Decimal = Field(..., ge=0, description="诉请金额，由调用方提供")
    evidence_ids: list[str] = Field(default_factory=list, description="支撑证据 ID 列表")


class AmountCalculatorInput(BaseModel):
    """
    AmountCalculator 输入 wrapper。

    Args:
        case_id: 案件 ID
        run_id: 运行快照 ID（写入报告）
        source_material_ids: 参与计算的 material_index 引用 ID 列表（用于追溯）
        claim_entries: 诉请金额描述符列表（对应诉请计算表的行）
        loan_transactions: 放款流水（调用方提供）
        repayment_transactions: 还款流水（调用方提供）
        disputed_amount_attributions: 争议款项归因表（调用方提供，可为空）
    """
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    source_material_ids: list[str] = Field(
        default_factory=list,
        description="material_index 引用 ID，用于报告溯源",
    )
    claim_entries: list[AmountClaimDescriptor] = Field(
        ..., min_length=1, description="诉请金额描述符列表，至少一条"
    )
    loan_transactions: list[LoanTransaction] = Field(
        ..., min_length=1, description="放款流水表，至少一条"
    )
    repayment_transactions: list[RepaymentTransaction] = Field(
        default_factory=list, description="还款流水表，可为空（全部款项未还）"
    )
    disputed_amount_attributions: list[DisputedAmountAttribution] = Field(
        default_factory=list, description="争议款项归因表，可为空"
    )
    contract_validity: ContractValidity = Field(
        default=ContractValidity.valid,
        description="合同效力状态；非 valid 时触发利息重算",
    )
    contractual_interest_rate: Decimal | None = Field(
        default=None, ge=0,
        description="合同约定年利率；None 时跳过利息重算",
    )
    lpr_rate: Decimal | None = Field(
        default=None, gt=0,
        description="当期 LPR 利率（由调用方传入）；合同无效时必需",
    )
