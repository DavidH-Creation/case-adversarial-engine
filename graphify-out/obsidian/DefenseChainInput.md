---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\defense_chain\schemas.py"
type: "code"
community: "C: Users"
location: "L47"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# DefenseChainInput

## Connections
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[DefenseChainOptimizer]] - `uses` [INFERRED]
- [[DefenseChainOptimizer — 原告方防御链优化器（P2）。 Plaintiff Defense Chain Optimizer (P2).]] - `uses` [INFERRED]
- [[DefenseChainOptimizer 单元测试。 Unit tests for DefenseChainOptimizer. 测试策略： - 使]] - `uses` [INFERRED]
- [[DefenseChainOptimizer 单元测试。 Unit tests for DefenseChainOptimizer. 测试策略： - 使_1]] - `uses` [INFERRED]
- [[DefenseChainOptimizer 输入 wrapper。 Args case_id 案件 I]] - `rationale_for` [EXTRACTED]
- [[DefensePoint]] - `uses` [INFERRED]
- [[LLM 只返回部分争点时，遗漏的争点记入 unevaluated。]] - `uses` [INFERRED]
- [[LLM 调用失败时返回降级结果，不抛异常。]] - `uses` [INFERRED]
- [[LLM 返回未知 issue_id 被过滤，对应争点记入 unevaluated。]] - `uses` [INFERRED]
- [[LLM 返回未知 issue_id 被过滤，遗漏的争点记入 unevaluated。]] - `uses` [INFERRED]
- [[MockLLMClient_11]] - `uses` [INFERRED]
- [[MockLLMClient_17]] - `uses` [INFERRED]
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
- [[不支持的案由类型构造时抛出 ValueError。_1]] - `uses` [INFERRED]
- [[原告方防御链优化器。 Args llm_client 符合 LLMClient 协议的客户端实例 cas]] - `uses` [INFERRED]
- [[场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.]] - `uses` [INFERRED]
- [[多个论点按 priority 排序，最终编号连续从 1 开始。]] - `uses` [INFERRED]
- [[所有证据 ID 无效时论点仍保留（evidence_ids 被清空但论点不丢弃）。]] - `uses` [INFERRED]
- [[执行防御链优化。 Args inp 优化器输入（含争点列表、证据索引、原告方 ID）]] - `uses` [INFERRED]
- [[校验并构建 DefensePoint 列表。 - 过滤引用不存在 issue_id 的论点 - 过滤证据引用中的非法 e]] - `uses` [INFERRED]
- [[正常流程：LLM 返回有效防御论点，正确构建 DefenseChain。]] - `uses` [INFERRED]
- [[缺少 defense_strategy 或 supporting_argument 时标记为 unevaluated。]] - `uses` [INFERRED]
- [[缺少 defense_strategy 或 supporting_argument 的论点标记为 unevaluated。]] - `uses` [INFERRED]
- [[较小 priority 值的论点排在前面。]] - `uses` [INFERRED]
- [[返回预定义 JSON 响应的 mock LLM 客户端。_7]] - `uses` [INFERRED]
- [[非法证据 ID 被过滤，不因此丢弃整条论点。]] - `uses` [INFERRED]
- [[领域模型 DefensePoint 验证。]] - `uses` [INFERRED]
- [[领域模型 PlaintiffDefenseChain 验证。]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users