---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\amount_calculator\schemas.py"
type: "code"
community: "C: Users"
location: "L57"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# AmountCalculatorInput

## Connections
- [[AmountCalculator]] - `uses` [INFERRED]
- [[AmountCalculator — 金额 诉请一致性硬校验模块。 Amount claim consistency hard validation modu]] - `uses` [INFERRED]
- [[AmountCalculator 单元测试。 测试策略：每条硬规则独立覆盖，使用最小 fixture 验证。 不依赖 LLM；所有输入为内联构造的 Py]] - `uses` [INFERRED]
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[No principal_base_contribution=True loans + claimed 0 → ratio=∞, flagged abnorma]] - `uses` [INFERRED]
- [[No principal_base_contribution=True loans + claimed=0 → skip (both zero)。]] - `uses` [INFERRED]
- [[TestAllRepaymentsAttributed]] - `uses` [INFERRED]
- [[TestClaimCalculationEntries]] - `uses` [INFERRED]
- [[TestClaimTotalReconstructable]] - `uses` [INFERRED]
- [[TestDuplicateInterestPenaltyClaim]] - `uses` [INFERRED]
- [[TestHappyPath]] - `uses` [INFERRED]
- [[TestPrincipalBaseUnique]] - `uses` [INFERRED]
- [[TestRule6ClaimDeliveryRatio]] - `uses` [INFERRED]
- [[TestRule7InterestRecalculation]] - `uses` [INFERRED]
- [[TestTextTableAmountConsistent]] - `uses` [INFERRED]
- [[TestVerdictBlockActive]] - `uses` [INFERRED]
- [[calculate() 应返回 AmountCalculationReport。]] - `uses` [INFERRED]
- [[claimed 100000 delivered 50000 = 2.0 → still normal ( =)。]] - `uses` [INFERRED]
- [[claimed 150000 delivered 50000 = 3.0 2.0 → abnormal。]] - `uses` [INFERRED]
- [[claimed 45000 vs calculated 40000 → delta = 5000。]] - `uses` [INFERRED]
- [[claimed 50000 delivered 50000 = 1.0 → normal。]] - `uses` [INFERRED]
- [[contract_validity=invalid but no contractual_interest_rate → skip + conflict war]] - `uses` [INFERRED]
- [[contract_validity=invalid but no lpr_rate → skip + conflict warning。]] - `uses` [INFERRED]
- [[custom threshold 1.5 claimed 80000 delivered 50000 = 1.6 1.5 → abnormal。]] - `uses` [INFERRED]
- [[interest penalty 类诉请 calculated_amount 为 None，不参与一致性校验。]] - `uses` [INFERRED]
- [[interest × 1 且 penalty × 1 → 不算重复。]] - `uses` [INFERRED]
- [[interest 类 delta=None 不影响 claim_total_reconstructable。]] - `uses` [INFERRED]
- [[interest 类诉请无法从流水确定性计算 → calculated_amount = None，delta = None。]] - `uses` [INFERRED]
- [[principal calculated_amount = sum(loans) - sum(repayments to principal)。]] - `uses` [INFERRED]
- [[principal 诉请 delta ≠ 0 → claim_total_reconstructable = False。]] - `uses` [INFERRED]
- [[principal 金额不一致（delta ≠ 0）→ 生成冲突 → verdict_block_active = True。]] - `uses` [INFERRED]
- [[ratio threshold → generates AmountConflict。]] - `uses` [INFERRED]
- [[report.case_id 和 run_id 与输入一致。]] - `uses` [INFERRED]
- [[rule 6 total_claimed total_principal_loans threshold → 预警。]] - `uses` [INFERRED]
- [[rule 7 contract invalid → interest recalculated at LPR。]] - `uses` [INFERRED]
- [[schemas.py]] - `contains` [EXTRACTED]
- [[verdict_block_active 机制测试。]] - `uses` [INFERRED]
- [[两条 interest 诉请 → duplicate_interest_penalty_claim = True。]] - `uses` [INFERRED]
- [[两条 penalty 诉请 → duplicate_interest_penalty_claim = True。]] - `uses` [INFERRED]
- [[任一还款 attributed_to 为 None 时，all_repayments_attributed 为 False。]] - `uses` [INFERRED]
- [[同一类型（interest 或 penalty）出现超过一条诉请时返回 True。]] - `uses` [INFERRED]
- [[场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.]] - `uses` [INFERRED]
- [[多笔放款：calculated_amount = 总放款 - 总还款（principal 归因）。]] - `uses` [INFERRED]
- [[存在 unresolved 争议 → verdict_block_active = True。]] - `uses` [INFERRED]
- [[存在 unresolved 的争议归因条目时，principal_base_unique 为 False。]] - `uses` [INFERRED]
- [[已解决的争议不影响 principal_base_unique。]] - `uses` [INFERRED]
- [[干净案例：五条规则全部通过 → verdict_block_active = False。]] - `uses` [INFERRED]
- [[归因 interest 的还款不影响本金计算。]] - `uses` [INFERRED]
- [[当事方庭审立场（用于争点优先级判断）。 Args party_id 当事方 ID role]] - `rationale_for` [EXTRACTED]
- [[所有可复算诉请（calculated_amount 非 None）的 delta 均为零时返回 True。 无法计算的诉请（delta = N]] - `uses` [INFERRED]
- [[所有可复算诉请（delta 非 None）的 delta 均为零时返回 True。 注：v1.2 中与 text_table_amount]] - `uses` [INFERRED]
- [[所有还款均已归因（attributed_to 非 None）时返回 True。]] - `uses` [INFERRED]
- [[执行金额一致性校验，返回完整报告。 Args inp 计算器输入，包含四类结构化数据]] - `uses` [INFERRED]
- [[放款 5 万 - 还款 1 万 = 4 万 == claimed 4 万 → consistent。]] - `uses` [INFERRED]
- [[放款 5 万 - 还款 1 万 = 4 万，但 claimed 3.5 万 → inconsistent。]] - `uses` [INFERRED]
- [[无冲突时 verdict_block_active 为 False。]] - `uses` [INFERRED]
- [[无还款时，all_repayments_attributed 为 True（空集合满足全称命题）。]] - `uses` [INFERRED]
- [[最小合法输入：一笔放款 5 万，一笔还款 1 万，一条本金诉请 4 万。]] - `uses` [INFERRED]
- [[本金基数唯一性：当且仅当不存在 unresolved 的争议归因条目时返回 True。 逻辑：若存在任何 resolution_statu]] - `uses` [INFERRED]
- [[构建诉请计算表。 principal 类诉请：calculated_amount = 总放款基数 - 总还款（归因 principal）。]] - `uses` [INFERRED]
- [[生成 AmountConflict 列表。三类来源： 1. 诉请计算 delta ≠ 0（claimed vs calculated 不一]] - `uses` [INFERRED]
- [[规则 6 起诉总额 可核实交付总额 = 阈值时返回 True。 若无 principal_base_contribution 放款且]] - `uses` [INFERRED]
- [[规则 7 合同无效 争议时，利息按 LPR 重算。 - invalid 强制 LPR - disputed mi]] - `uses` [INFERRED]
- [[计算 principal_base_contribution=True 的放款总额。]] - `uses` [INFERRED]
- [[计算应还本金 = principal 放款总额 - 已还本金总额。]] - `uses` [INFERRED]
- [[计算归因 principal 的已还款总额。]] - `uses` [INFERRED]
- [[诉请计算表 delta 和 calculated_amount 的详细验证。]] - `uses` [INFERRED]
- [[金额 诉请一致性确定性计算器。 所有方法均为同步纯函数，不持有外部状态，可安全复用同一实例。 使用方式 Usage]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users