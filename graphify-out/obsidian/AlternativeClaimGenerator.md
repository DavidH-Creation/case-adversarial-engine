---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\alternative_claim_generator\generator.py"
type: "code"
community: "C: Users"
location: "L57"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# AlternativeClaimGenerator

## Connections
- [[._apply_condition_1()]] - `method` [EXTRACTED]
- [[._apply_condition_2()]] - `method` [EXTRACTED]
- [[._apply_condition_3()]] - `method` [EXTRACTED]
- [[._build_suggestion()]] - `method` [EXTRACTED]
- [[.generate()_3]] - `method` [EXTRACTED]
- [[AlternativeClaimGeneratorInput]] - `uses` [INFERRED]
- [[IssueDependencyGraphGenerator 单元测试。 Unit tests for IssueDependencyGraphGenerato]] - `uses` [INFERRED]
- [[TestBasicBehavior_1]] - `uses` [INFERRED]
- [[TestCondition1AmendClaim]] - `uses` [INFERRED]
- [[TestCondition2WeakStrongCombination]] - `uses` [INFERRED]
- [[TestCondition3DeltaThreshold]] - `uses` [INFERRED]
- [[TestContractGuarantees]] - `uses` [INFERRED]
- [[TestDeduplication]] - `uses` [INFERRED]
- [[TestMixedScenario_1]] - `uses` [INFERRED]
- [[calculated_amount 为 None（无法复算）时，不触发条件3。]] - `uses` [INFERRED]
- [[claimed=1000, calculated=800, delta=200, 200 1000=20% — 超过阈值，触发。]] - `uses` [INFERRED]
- [[claimed_amount=0 时不触发（避免除零）。]] - `uses` [INFERRED]
- [[delta = 100 1000 = 10%，等于阈值，不超过，不触发。]] - `uses` [INFERRED]
- [[delta 为负（算出来比诉请多），绝对值超过阈值也触发。]] - `uses` [INFERRED]
- [[generator.py]] - `contains` [EXTRACTED]
- [[三个条件各自触发不同 claim，输出三条建议。]] - `uses` [INFERRED]
- [[两个争点均 amend_claim 且都关联同一 claim，只输出一条。]] - `uses` [INFERRED]
- [[只有 strong opponent 没有 weak proponent，不触发。]] - `uses` [INFERRED]
- [[只有 weak proponent 没有 strong opponent，不触发。]] - `uses` [INFERRED]
- [[合并后的建议包含所有触发争点的 issue_id。]] - `uses` [INFERRED]
- [[所有生成的建议 instability_issue_ids 必须非空。]] - `uses` [INFERRED]
- [[无争点引用该 claim 时，条件3不生成建议（无法绑定 issue_id）。]] - `uses` [INFERRED]
- [[替代主张自动生成引擎（P2.11）。 纯规则层，不持有外部状态，可安全复用同一实例。 使用方式 Usage]] - `rationale_for` [EXTRACTED]
- [[条件1和条件2同时命中同一 claim，只输出一条建议。]] - `uses` [INFERRED]
- [[条件3触发时，绑定引用了该 claim 的争点 issue_id。]] - `uses` [INFERRED]
- [[验证 AlternativeClaimGenerator 不依赖外部 LLM（可正常实例化并运行）。]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users