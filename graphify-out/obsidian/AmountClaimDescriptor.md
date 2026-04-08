---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\amount_calculator\schemas.py"
type: "code"
community: "C: Users"
location: "L37"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# AmountClaimDescriptor

## Connections
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
- [[场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.]] - `uses` [INFERRED]
- [[多笔放款：calculated_amount = 总放款 - 总还款（principal 归因）。]] - `uses` [INFERRED]
- [[存在 unresolved 争议 → verdict_block_active = True。]] - `uses` [INFERRED]
- [[存在 unresolved 的争议归因条目时，principal_base_unique 为 False。]] - `uses` [INFERRED]
- [[已解决的争议不影响 principal_base_unique。]] - `uses` [INFERRED]
- [[干净案例：五条规则全部通过 → verdict_block_active = False。]] - `uses` [INFERRED]
- [[归因 interest 的还款不影响本金计算。]] - `uses` [INFERRED]
- [[放款 5 万 - 还款 1 万 = 4 万 == claimed 4 万 → consistent。]] - `uses` [INFERRED]
- [[放款 5 万 - 还款 1 万 = 4 万，但 claimed 3.5 万 → inconsistent。]] - `uses` [INFERRED]
- [[无冲突时 verdict_block_active 为 False。]] - `uses` [INFERRED]
- [[无还款时，all_repayments_attributed 为 True（空集合满足全称命题）。]] - `uses` [INFERRED]
- [[最小合法输入：一笔放款 5 万，一笔还款 1 万，一条本金诉请 4 万。]] - `uses` [INFERRED]
- [[诉请计算表 delta 和 calculated_amount 的详细验证。]] - `uses` [INFERRED]
- [[诉请金额描述符 — 调用方提供的结构化诉请信息。 由调用方（上游 LLM 提取或人工录入）将 Claim.claim_text 解析为结构化字段后]] - `rationale_for` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/C:_Users