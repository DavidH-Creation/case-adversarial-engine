"""
流水线与基础设施模型 / Pipeline and infrastructure models.

包含运行快照、长任务、金额计算、裁判路径树和攻击链模型。
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional, Union  # Any needed for JobError.details

from pydantic import BaseModel, Field, model_validator

from engines.shared.models.core import (
    BlockingConditionType,
    ClaimType,
    ContractValidity,
    DisputeResolutionStatus,
    JobStatus,
    RepaymentAttribution,
)


# ---------------------------------------------------------------------------
# 索引引用模型 / Index reference models
# ---------------------------------------------------------------------------


class MaterialRef(BaseModel):
    """材料索引引用。"""
    index_name: str = Field(default="material_index")
    object_type: str
    object_id: str = Field(..., min_length=1)
    storage_ref: str = Field(..., min_length=1)


class ArtifactRef(BaseModel):
    """产物索引引用。"""
    index_name: str = Field(default="artifact_index")
    object_type: str
    object_id: str = Field(..., min_length=1)
    storage_ref: str = Field(..., min_length=1)


class InputSnapshot(BaseModel):
    """运行输入快照。"""
    material_refs: list[MaterialRef] = Field(default_factory=list)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 基础设施 / Infrastructure
# ---------------------------------------------------------------------------


class ExtractionMetadata(BaseModel):
    """提取过程元信息，prompt_profile 持久化于此以支持重放。"""
    model_used: str = Field(default="")
    temperature: float = Field(default=0.0)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    prompt_profile: str = Field(default="")
    prompt_version: str = Field(default="")
    total_tokens: int = Field(default=0)


class Run(BaseModel):
    """执行快照，对应 schemas/procedure/run.schema.json。
    output_refs 接受 material_ref | artifact_ref（per B7 schema fix）。
    """
    run_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    workspace_id: str = Field(..., min_length=1)
    scenario_id: Optional[str] = None
    trigger_type: str = Field(..., min_length=1)
    input_snapshot: InputSnapshot
    output_refs: list[Union[MaterialRef, ArtifactRef]] = Field(default_factory=list)
    started_at: str
    finished_at: Optional[str] = None
    status: str


# ---------------------------------------------------------------------------
# 长任务层 / Long-running job layer
# ---------------------------------------------------------------------------


class JobError(BaseModel):
    """长任务结构化错误。对应 schemas/indexing.schema.json#/$defs/job_error。"""
    code: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    details: Optional[dict[str, Any]] = None


class Job(BaseModel):
    """长任务状态与进度追踪。对应 schemas/procedure/job.schema.json。

    model_validator 强制以下 invariants：
    - created:   progress=0.0, result_ref=null, error=null
    - pending:   0 <= progress < 1, result_ref=null, error=null
    - running:   0 <= progress < 1, result_ref=null, error=null
    - completed: progress=1.0, result_ref≠null, error=null
    - failed:    progress < 1, result_ref=null, error≠null
    - cancelled: progress < 1, result_ref=null, error=null
    """
    job_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    workspace_id: str = Field(..., min_length=1)
    job_type: str = Field(..., min_length=1)
    job_status: JobStatus
    progress: float = Field(..., ge=0.0, le=1.0)
    message: Optional[str] = None
    result_ref: Optional[ArtifactRef] = None
    error: Optional[JobError] = None
    created_at: str
    updated_at: str

    @model_validator(mode="after")
    def _validate_status_invariants(self) -> "Job":
        s = self.job_status
        p = self.progress
        r = self.result_ref
        e = self.error

        if s == JobStatus.created:
            if p != 0.0:
                raise ValueError("created job must have progress=0.0")
            if r is not None:
                raise ValueError("created job must have result_ref=null")
            if e is not None:
                raise ValueError("created job must have error=null")

        elif s in (JobStatus.pending, JobStatus.running):
            if p >= 1.0:
                raise ValueError(f"{s.value} job progress must be < 1.0")
            if r is not None:
                raise ValueError(f"{s.value} job must have result_ref=null")
            if e is not None:
                raise ValueError(f"{s.value} job must have error=null")

        elif s == JobStatus.completed:
            if p != 1.0:
                raise ValueError("completed job must have progress=1.0")
            if r is None:
                raise ValueError("completed job must have a valid result_ref")
            if e is not None:
                raise ValueError("completed job must have error=null")

        elif s == JobStatus.failed:
            if p >= 1.0:
                raise ValueError("failed job progress must be < 1.0")
            if r is not None:
                raise ValueError("failed job must have result_ref=null")
            if e is None:
                raise ValueError("failed job must have a structured error")

        elif s == JobStatus.cancelled:
            if p >= 1.0:
                raise ValueError("cancelled job progress must be < 1.0")
            if r is not None:
                raise ValueError("cancelled job must have result_ref=null")
            if e is not None:
                raise ValueError("cancelled job must have error=null")

        return self


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
        description="未解释的金额口径冲突列表；非空时触发 verdict_block_active"
    )
    verdict_block_active: bool = Field(
        ..., description="系统是否因未解释冲突阻断稳定裁判判断；硬规则：unresolved_conflicts 非空时必须为 True"
    )
    claim_delivery_ratio_normal: bool = Field(
        default=True,
        description="起诉金额与可核实交付金额比值是否正常（ratio <= 阈值）",
    )

    @model_validator(mode="after")
    def _enforce_verdict_block_rule(self) -> "AmountConsistencyCheck":
        """硬规则：unresolved_conflicts 非空时 verdict_block_active 必须为 True。"""
        if self.unresolved_conflicts and not self.verdict_block_active:
            raise ValueError(
                "verdict_block_active 必须为 True 当 unresolved_conflicts 非空"
            )
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
    original_interest_amount: Decimal = Field(..., description="单期概念利息 = principal × original_rate")
    recalculated_interest_amount: Decimal = Field(..., description="单期概念利息 = principal × effective_rate")
    delta: Decimal = Field(..., description="利息差额 = original - recalculated（同期比较）")


class AmountCalculationReport(BaseModel):
    """金额/诉请一致性硬校验报告。P0.2 产物，纳入 CaseWorkspace.artifact_index。"""
    report_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    loan_transactions: list[LoanTransaction] = Field(
        ..., description="放款流水表"
    )
    repayment_transactions: list[RepaymentTransaction] = Field(
        ..., description="还款流水表"
    )
    disputed_amount_attributions: list[DisputedAmountAttribution] = Field(
        default_factory=list, description="争议款项归因表"
    )
    claim_calculation_table: list[ClaimCalculationEntry] = Field(
        ..., description="诉请计算表"
    )
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
# 裁判路径树 / Decision path tree  (P0.3)
# ---------------------------------------------------------------------------


class ConfidenceInterval(BaseModel):
    """置信度区间。仅在 verdict_block_active=False 时允许填写。"""
    lower: float = Field(..., ge=0.0, le=1.0, description="置信度区间下界 [0,1]")
    upper: float = Field(..., ge=0.0, le=1.0, description="置信度区间上界 [0,1]")

    @model_validator(mode="after")
    def _lower_le_upper(self) -> "ConfidenceInterval":
        if self.lower > self.upper:
            raise ValueError(f"lower ({self.lower}) must be <= upper ({self.upper})")
        return self


class PathRankingItem(BaseModel):
    """路径概率排序条目。DecisionPathTree.path_ranking 列表元素。"""
    path_id: str = Field(..., min_length=1, description="路径 ID")
    probability: float = Field(..., ge=0.0, le=1.0, description="路径触发概率")
    party_favored: str = Field(..., description="对哪方有利：plaintiff / defendant / neutral")
    key_conditions: list[str] = Field(
        default_factory=list, description="触发本路径需满足的关键条件（文字描述列表）"
    )


class DecisionPath(BaseModel):
    """单条裁判路径。"""
    path_id: str = Field(..., min_length=1)
    trigger_condition: str = Field(..., min_length=1, description="触发本路径的关键条件描述")
    trigger_issue_ids: list[str] = Field(default_factory=list, description="触发条件关联的争点 ID 列表")
    key_evidence_ids: list[str] = Field(
        default_factory=list,
        description="本路径依赖的关键证据 ID 列表（仅含支持本路径结论的证据）",
    )
    counter_evidence_ids: list[str] = Field(
        default_factory=list,
        description="与本路径结论相悖的证据 ID 列表（反驳/对立证据，不得与 key_evidence_ids 重叠）",
    )
    possible_outcome: str = Field(..., min_length=1, description="可能的裁判结果描述")
    confidence_interval: Optional[ConfidenceInterval] = Field(
        default=None, description="置信度区间；verdict_block_active=True 时必须为 None"
    )
    path_notes: str = Field(default="", description="路径备注")
    # v1.5: 路径可执行化扩展字段
    admissibility_gate: list[str] = Field(
        default_factory=list,
        description="本路径成立前提：哪些证据必须被法庭采信（evidence_id 列表）",
    )
    result_scope: list[str] = Field(
        default_factory=list,
        description="裁判范围标签：principal/interest/liability_allocation 等",
    )
    fallback_path_id: Optional[str] = Field(
        default=None, description="本路径失败时降级到哪条路径的 path_id"
    )
    # v1.6: 概率评分
    probability: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="路径触发概率（0-1），基于证据支撑度、阻断条件可满足性及法律先例对齐度",
    )
    probability_rationale: str = Field(
        default="", description="概率评估依据（支撑证据质量、阻断条件满足情况等）"
    )
    party_favored: str = Field(
        default="neutral",
        description="本路径结果对哪方有利：plaintiff / defendant / neutral",
    )


class BlockingCondition(BaseModel):
    """阻断稳定判断的条件。"""
    condition_id: str = Field(..., min_length=1)
    condition_type: BlockingConditionType
    description: str = Field(..., min_length=1)
    linked_issue_ids: list[str] = Field(default_factory=list)
    linked_evidence_ids: list[str] = Field(default_factory=list)


class DecisionPathTree(BaseModel):
    """裁判路径树。P0.3 产物，纳入 CaseWorkspace.artifact_index（由调用方负责注册，同 P0.1/P0.2）。
    替代 AdversarialSummary.overall_assessment 的段落式综合评估。
    overall_assessment 的汇总填充（各路径 possible_outcome 摘要）由调用方负责，不在本模块实现。
    """
    tree_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    paths: list[DecisionPath] = Field(default_factory=list, description="裁判路径列表（建议 3-6 条）")
    blocking_conditions: list[BlockingCondition] = Field(
        default_factory=list, description="当前阻断稳定判断的条件列表"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    # v1.6: 路径概率比较结果
    most_likely_path: Optional[str] = Field(
        default=None, description="概率最高的路径 ID"
    )
    plaintiff_best_path: Optional[str] = Field(
        default=None, description="对原告最有利的路径 ID（plaintiff_favored 路径中概率最高）"
    )
    defendant_best_path: Optional[str] = Field(
        default=None, description="对被告最有利的路径 ID（defendant_favored 路径中概率最高）"
    )
    path_ranking: list[PathRankingItem] = Field(
        default_factory=list, description="路径按概率降序排列的排名列表"
    )


# ---------------------------------------------------------------------------
# P0.4：最强攻击链
# ---------------------------------------------------------------------------


class AttackNode(BaseModel):
    """单个攻击节点。OptimalAttackChain.top_attacks 列表元素（规则层保证恰好 3 个）。"""
    attack_node_id: str = Field(..., min_length=1, description="攻击节点唯一标识")
    target_issue_id: str = Field(..., min_length=1, description="攻击目标争点 ID")
    attack_description: str = Field(..., min_length=1, description="攻击论点描述")
    success_conditions: str = Field(default="", description="攻击成功条件")
    supporting_evidence_ids: list[str] = Field(
        ..., min_length=1, description="支撑此攻击点的证据 ID 列表（不得为空）"
    )
    counter_measure: str = Field(default="", description="我方对此攻击点的反制动作")
    adversary_pivot_strategy: str = Field(
        default="", description="对方补证后我方策略切换说明"
    )


class OptimalAttackChain(BaseModel):
    """某一方的最优攻击顺序与反制准备。P0.4 产物，纳入 CaseWorkspace.artifact_index。
    为原告和被告各生成一份。
    """
    chain_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    owner_party_id: str = Field(..., min_length=1, description="生成方当事人 ID")
    top_attacks: list[AttackNode] = Field(
        default_factory=list,
        description="最优攻击点，规则层保证恰好 3 个；LLM 失败时为空列表",
    )
    recommended_order: list[str] = Field(
        default_factory=list,
        description="推荐攻击顺序（有序 attack_node_id 列表），与 top_attacks 完全对应",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
