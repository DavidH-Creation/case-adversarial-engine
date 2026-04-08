---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\credibility_scorer\scorer.py"
type: "code"
community: "C: Users"
location: "L75"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# CredibilityScorer

## Connections
- [[.__init__()_69]] - `method` [EXTRACTED]
- [[._check_cred01()]] - `method` [EXTRACTED]
- [[._check_cred02()]] - `method` [EXTRACTED]
- [[._check_cred03()]] - `method` [EXTRACTED]
- [[._check_cred04()]] - `method` [EXTRACTED]
- [[._check_cred05()]] - `method` [EXTRACTED]
- [[._check_cred06()]] - `method` [EXTRACTED]
- [[._check_cred07()]] - `method` [EXTRACTED]
- [[.score()_1]] - `method` [EXTRACTED]
- [[CRED-01 + CRED-02 同时触发，final_score = 100 - 20 - 10 = 70。]] - `uses` [INFERRED]
- [[CRED-02 每类规则只触发一次（不重复扣分）。]] - `uses` [INFERRED]
- [[CRED-07 原告放贷频次达标 → 扣分 -25。]] - `uses` [INFERRED]
- [[CredibilityScorecard model_validator 确保 final_score 等于 base_score + sum(deductio]] - `uses` [INFERRED]
- [[CredibilityScorer 单元测试（P2.9）。 测试策略： - 使用 Pydantic 模型构建测试数据（不用 Mock） - 每条规则（]] - `uses` [INFERRED]
- [[CredibilityScorerInput]] - `uses` [INFERRED]
- [[If some keys are None and some are present, the present ones must still]] - `uses` [INFERRED]
- [[Pydantic dictstr, Any accepts None values; CRED-07 must coerce safely.]] - `uses` [INFERRED]
- [[RuleThresholds]] - `uses` [INFERRED]
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
- [[scorer.py]] - `contains` [EXTRACTED]
- [[全部 6 条规则同时触发，final_score = 100 - 20 - 10 - 15 - 10 - 10 - 5 = 30。]] - `uses` [INFERRED]
- [[场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.]] - `uses` [INFERRED]
- [[整体可信度折损引擎（P2.9）。 纯规则层，不持有外部状态，可安全复用同一实例。 使用方式 Usage sc]] - `rationale_for` [EXTRACTED]
- [[无任何触发条件时，final_score == 100，deductions 为空。]] - `uses` [INFERRED]
- [[构造最简 AmountCalculationReport。]] - `uses` [INFERRED]
- [[空输入（无冲突、无特殊证据、无问题争点）时 final_score == 100。]] - `uses` [INFERRED]
- [[被告满足职业放贷人条件时不应触发 CRED-07（仅检查原告）。]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users