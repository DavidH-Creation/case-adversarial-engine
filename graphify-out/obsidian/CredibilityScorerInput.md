---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\credibility_scorer\schemas.py"
type: "code"
community: "C: Users"
location: "L23"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# CredibilityScorerInput

## Connections
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[CRED-01 + CRED-02 同时触发，final_score = 100 - 20 - 10 = 70。]] - `uses` [INFERRED]
- [[CRED-01 存在未解释的金额口径冲突。]] - `uses` [INFERRED]
- [[CRED-02 关键证据仅有复印件，无原件（evidence.is_copy_only == True）。]] - `uses` [INFERRED]
- [[CRED-02 每类规则只触发一次（不重复扣分）。]] - `uses` [INFERRED]
- [[CRED-03 同一证据在不同文件中金额不一致。 实现映射：text_table_amount_consistent == False]] - `uses` [INFERRED]
- [[CRED-04 证人证言与书证存在明显矛盾。 触发条件：某 Issue 的 evidence_ids 中同时含有 witness_sta]] - `uses` [INFERRED]
- [[CRED-05 关键时间节点缺乏证据支撑。 触发条件：存在 proponent_evidence_strength == weak 且]] - `uses` [INFERRED]
- [[CRED-06 存在被质疑真实性但未给出解释的证据。 触发条件：evidence.status == challenged 且 admi]] - `uses` [INFERRED]
- [[CRED-07 原告放贷频次达标 → 扣分 -25。]] - `uses` [INFERRED]
- [[CRED-07 原告构成职业放贷人。 触发条件：原告方（side= plaintiff ）的 litigation_history 中，]] - `uses` [INFERRED]
- [[Coerce a dict-extracted value to int, treating None as 0. Phase B (Unit 2]] - `uses` [INFERRED]
- [[CredibilityScorecard model_validator 确保 final_score 等于 base_score + sum(deductio]] - `uses` [INFERRED]
- [[CredibilityScorer]] - `uses` [INFERRED]
- [[CredibilityScorer — 整体可信度折损引擎主类（P2.9）。 Credibility Scorer — rule-based credibil]] - `uses` [INFERRED]
- [[CredibilityScorer 单元测试（P2.9）。 测试策略： - 使用 Pydantic 模型构建测试数据（不用 Mock） - 每条规则（]] - `uses` [INFERRED]
- [[CredibilityScorer 输入 wrapper。 Args case_id 案件 ID]] - `rationale_for` [EXTRACTED]
- [[If some keys are None and some are present, the present ones must still]] - `uses` [INFERRED]
- [[Pydantic dictstr, Any accepts None values; CRED-07 must coerce safely.]] - `uses` [INFERRED]
- [[TestCRED07ProfessionalLender]] - `uses` [INFERRED]
- [[TestCred01]] - `uses` [INFERRED]
- [[TestCred02]] - `uses` [INFERRED]
- [[TestCred03]] - `uses` [INFERRED]
- [[TestCred04]] - `uses` [INFERRED]
- [[TestCred05]] - `uses` [INFERRED]
- [[TestCred06]] - `uses` [INFERRED]
- [[TestCredibilityScorerBasic]] - `uses` [INFERRED]
- [[TestCredibilityScorerIntegration]] - `uses` [INFERRED]
- [[final_score 60 时，summary 须包含可信度警告关键词。]] - `uses` [INFERRED]
- [[schemas.py]] - `contains` [EXTRACTED]
- [[全部 6 条规则同时触发，final_score = 100 - 20 - 10 - 15 - 10 - 10 - 5 = 30。]] - `uses` [INFERRED]
- [[执行可信度折损评分，返回 CredibilityScorecard。 Args inp 引擎输入（含 cas]] - `uses` [INFERRED]
- [[整体可信度折损引擎（P2.9）。 纯规则层，不持有外部状态，可安全复用同一实例。 使用方式 Usage sc]] - `uses` [INFERRED]
- [[无任何触发条件时，final_score == 100，deductions 为空。]] - `uses` [INFERRED]
- [[构造最简 AmountCalculationReport。]] - `uses` [INFERRED]
- [[生成可信度摘要说明。final_score 60 时包含可信度警告。]] - `uses` [INFERRED]
- [[空输入（无冲突、无特殊证据、无问题争点）时 final_score == 100。]] - `uses` [INFERRED]
- [[被告满足职业放贷人条件时不应触发 CRED-07（仅检查原告）。]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users