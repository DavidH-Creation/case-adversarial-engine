---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\shared\models\core.py"
type: "code"
community: "C: Users"
location: "L295"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# ContractValidity

## Connections
- [[AmountCalculationReport]] - `uses` [INFERRED]
- [[AmountConflict]] - `uses` [INFERRED]
- [[AmountConsistencyCheck]] - `uses` [INFERRED]
- [[ClaimCalculationEntry]] - `uses` [INFERRED]
- [[ClaimType]] - `uses` [INFERRED]
- [[DisputedAmountAttribution]] - `uses` [INFERRED]
- [[Enum]] - `inherits` [EXTRACTED]
- [[ImpactTarget]] - `uses` [INFERRED]
- [[InterestRecalculation]] - `uses` [INFERRED]
- [[LitigationHistory]] - `uses` [INFERRED]
- [[LoanTransaction]] - `uses` [INFERRED]
- [[RepaymentAttribution]] - `uses` [INFERRED]
- [[RepaymentTransaction]] - `uses` [INFERRED]
- [[core.py]] - `contains` [EXTRACTED]
- [[str]] - `inherits` [EXTRACTED]
- [[争点影响的诉请对象（P0.1，民间借贷专属语义）。 含义对应 ClaimType + 'credibility'：principal intere]] - `uses` [INFERRED]
- [[争议款项归因记录。记录原被告对同一笔款项的不同立场。]] - `uses` [INFERRED]
- [[利息重算记录 — 合同无效时的利率切换结果。 注：interest_amount 字段为单期概念金额（principal × rate），用于对比]] - `uses` [INFERRED]
- [[场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.]] - `uses` [INFERRED]
- [[当事人近期放贷诉讼统计 — 职业放贷人检测输入。 民间借贷专属：仅 CRED-07 (credibility_scorer) 在原告方使用此结构判]] - `uses` [INFERRED]
- [[民间借贷（Civil Loan）案件类型的场景推演 LLM 提示模板。 LLM prompt templates for civil loan (民间借贷)]] - `uses` [INFERRED]
- [[硬规则：unresolved_conflicts 非空时 verdict_block_active 必须为 True。]] - `uses` [INFERRED]
- [[诉请类型 — 对应 ClaimCalculationEntry.claim_type。]] - `uses` [INFERRED]
- [[还款归因类型 — 每笔还款必须唯一归因到某一类。]] - `uses` [INFERRED]
- [[还款流水记录。每笔还款对应一条，必须唯一归因。]] - `uses` [INFERRED]
- [[金额 诉请一致性硬校验报告。P0.2 产物，纳入 CaseWorkspace.artifact_index。]] - `uses` [INFERRED]
- [[金额口径冲突记录。每个未解释冲突对应一条。]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users