# Amount Calculator Contract

**Engine:** `case_structuring`
**Component:** `amount_calculator`
**Version:** v1.2
**Spec:** `docs/06_v1.2_spec.md#P0.2`

---

## Purpose

纯规则层（deterministic）金额/诉请一致性硬校验模块。在 `case_structuring` 阶段、
`simulation_run` 开始之前完成，确保金额口径一致性不依赖 LLM。

---

## I/O Contract

### Input: `AmountCalculatorInput`

| Field | Type | Required | Description |
|---|---|---|---|
| `case_id` | `str` | Yes | 案件 ID |
| `run_id` | `str` | Yes | 运行快照 ID（写入报告） |
| `source_material_ids` | `list[str]` | No | material_index 溯源引用 |
| `claim_entries` | `AmountClaimDescriptor[]` | Yes ≥1 | 诉请金额描述符 |
| `loan_transactions` | `LoanTransaction[]` | Yes ≥1 | 放款流水 |
| `repayment_transactions` | `RepaymentTransaction[]` | No | 还款流水 |
| `disputed_amount_attributions` | `DisputedAmountAttribution[]` | No | 争议归因表 |

`AmountClaimDescriptor` 由调用方提供：

| Field | Type | Description |
|---|---|---|
| `claim_id` | `str` | 对应 `Claim.claim_id` |
| `claim_type` | `ClaimType` | principal / interest / penalty / attorney_fee / other |
| `claimed_amount` | `Decimal` | 诉请金额（调用方解析自 claim_text） |
| `evidence_ids` | `list[str]` | 支撑证据 ID（可为空） |

### Output: `AmountCalculationReport`

四张表：

| Table | Type | Description |
|---|---|---|
| `loan_transactions` | `LoanTransaction[]` | 放款流水表（透传自输入） |
| `repayment_transactions` | `RepaymentTransaction[]` | 还款流水表（透传自输入） |
| `disputed_amount_attributions` | `DisputedAmountAttribution[]` | 争议归因表（透传自输入） |
| `claim_calculation_table` | `ClaimCalculationEntry[]` | 诉请计算表（计算器填写） |

一致性校验：`consistency_check_result`（`AmountConsistencyCheck`）

---

## Hard Rules

| Rule | Field | Logic |
|---|---|---|
| 本金基数唯一性 | `principal_base_unique` | 无 unresolved 争议归因 → True |
| 每笔还款唯一归因 | `all_repayments_attributed` | 所有 `attributed_to` 非 None → True |
| 文本表格金额一致 | `text_table_amount_consistent` | 所有可算 `delta == 0` → True |
| 利息/违约金重复 | `duplicate_interest_penalty_claim` | 同类 interest/penalty > 1 → True |
| 诉请总额可复算 | `claim_total_reconstructable` | 所有可算 `delta == 0` → True |
| 阻断机制 | `verdict_block_active` | `unresolved_conflicts` 非空 → True（**强制**，由 model_validator 保障） |

---

## Calculated Amount Logic

| `claim_type` | `calculated_amount` 计算方式 |
|---|---|
| `principal` | `Σ(loan.amount where principal_base_contribution=True)` − `Σ(repayment.amount where attributed_to=principal)` |
| `interest` | `None`（需合同利率，超出规则层范围） |
| `penalty` | `None`（需违约金条款，超出规则层范围） |
| `attorney_fee` | `None` |
| `other` | `None` |

当 `calculated_amount = None` 时，`delta = None`，该条目不参与一致性校验。

---

## Constraints

1. **纯规则层**：`AmountCalculator` 不得调用 LLM 或发起任何外部 I/O。
2. **Decimal 金额**：所有金额计算使用 `decimal.Decimal`，禁止 float 精度问题。
3. **verdict_block_active 强制**：由 `AmountConsistencyCheck.model_validator` 在模型层面强制，计算器层也主动设置。
4. **阶段约束**：必须在 `case_structuring` 阶段（`simulation_run` 之前）完成；法律程序层对应 `case_intake` phase，两者不得混淆。
5. **产物注册**：`AmountCalculationReport` 必须纳入 `CaseWorkspace.artifact_index`（由调用方完成）。
6. **重跑语义**：修改诉请或新增证据后，调用方必须重新运行 `amount_calculator`。

---

## P0.3 依赖关系

`verdict_block_active = True` 时，`DecisionPathTree`（P0.3）中所有 `confidence_interval` 字段不允许填写。
`DecisionPathTree` 实现时必须检查 `AmountCalculationReport.consistency_check_result.verdict_block_active`。

---

## Out of Scope (v1.2)

- 利息/违约金的确定性计算（依赖合同利率/违约金条款，留待后续扩展）
- 多期还款的分期摊销计算
- 与 LLM agent 的集成（只暴露纯 Python API）
- JSON Schema 外部校验（Pydantic v2 已满足校验需求）
