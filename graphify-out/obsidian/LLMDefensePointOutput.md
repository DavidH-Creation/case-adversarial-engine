---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\defense_chain\schemas.py"
type: "code"
community: "C: Users"
location: "L24"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# LLMDefensePointOutput

## Connections
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[DefenseChainOptimizer 单元测试。 Unit tests for DefenseChainOptimizer. 测试策略： - 使]] - `uses` [INFERRED]
- [[DefensePoint]] - `uses` [INFERRED]
- [[LLM 只返回部分争点时，遗漏的争点记入 unevaluated。]] - `uses` [INFERRED]
- [[LLM 对单个争点生成的防御论点（中间模型）。]] - `rationale_for` [EXTRACTED]
- [[LLM 调用失败时返回降级结果，不抛异常。]] - `uses` [INFERRED]
- [[LLM 返回未知 issue_id 被过滤，遗漏的争点记入 unevaluated。]] - `uses` [INFERRED]
- [[MockLLMClient_11]] - `uses` [INFERRED]
- [[PlaintiffDefenseChain]] - `uses` [INFERRED]
- [[TestDefenseChainInput]] - `uses` [INFERRED]
- [[TestDefenseChainResult]] - `uses` [INFERRED]
- [[TestDefensePointModel]] - `uses` [INFERRED]
- [[TestEmptyInput]] - `uses` [INFERRED]
- [[TestEvidenceIDValidation]] - `uses` [INFERRED]
- [[TestHappyPath_2]] - `uses` [INFERRED]
- [[TestIssueIDValidation]] - `uses` [INFERRED]
- [[TestLLMDefenseChainOutput]] - `uses` [INFERRED]
- [[TestLLMDefensePointOutput]] - `uses` [INFERRED]
- [[TestLLMFailureHandling_2]] - `uses` [INFERRED]
- [[TestMetadata]] - `uses` [INFERRED]
- [[TestPlaintiffDefenseChainModel]] - `uses` [INFERRED]
- [[TestPriorityOrdering]] - `uses` [INFERRED]
- [[TestPromptContent_2]] - `uses` [INFERRED]
- [[TestStrategyArgumentValidation]] - `uses` [INFERRED]
- [[TestTargetIssuesMapping]] - `uses` [INFERRED]
- [[TestUnsupportedCaseType]] - `uses` [INFERRED]
- [[defense_points 按 priority 升序排列，编号连续从 1 开始。]] - `uses` [INFERRED]
- [[evidence_support 汇总所有论点的证据 ID 并去重。]] - `uses` [INFERRED]
- [[issue_dependency_graph schemas 单元测试。 Unit tests for issue_dependency_graph sche]] - `uses` [INFERRED]
- [[schemas.py]] - `contains` [EXTRACTED]
- [[target_issues 与 defense_points 中的 issue_id 一一对应。]] - `uses` [INFERRED]
- [[不支持的案由类型构造时抛出 ValueError。]] - `uses` [INFERRED]
- [[所有证据 ID 无效时论点仍保留（evidence_ids 被清空但论点不丢弃）。]] - `uses` [INFERRED]
- [[缺少 defense_strategy 或 supporting_argument 的论点标记为 unevaluated。]] - `uses` [INFERRED]
- [[较小 priority 值的论点排在前面。]] - `uses` [INFERRED]
- [[返回预定义 JSON 响应的 mock LLM 客户端。_7]] - `uses` [INFERRED]
- [[领域模型 DefensePoint 验证。]] - `uses` [INFERRED]
- [[领域模型 PlaintiffDefenseChain 验证。]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users