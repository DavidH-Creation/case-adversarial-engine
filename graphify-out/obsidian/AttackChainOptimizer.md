---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\attack_chain_optimizer\optimizer.py"
type: "code"
community: "C: Users"
location: "L63"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# AttackChainOptimizer

## Connections
- [[.__init__()_67]] - `method` [EXTRACTED]
- [[._call_llm()_4]] - `method` [EXTRACTED]
- [[._empty_chain()]] - `method` [EXTRACTED]
- [[._parse_llm_output()_1]] - `method` [EXTRACTED]
- [[._process_attack_nodes()]] - `method` [EXTRACTED]
- [[.optimize()]] - `method` [EXTRACTED]
- [[AttackChainOptimizerInput]] - `uses` [INFERRED]
- [[DefenseChainOptimizer 单元测试。 Unit tests for DefenseChainOptimizer. 测试策略： - 使]] - `uses` [INFERRED]
- [[EvidenceStateMachine]] - `uses` [INFERRED]
- [[Full optimize() flow with Opus-style output produces non-empty attacks.]] - `uses` [INFERRED]
- [[LLM 只返回 2 个有效节点时原样返回（不补充；调用方负责降级处理）。]] - `uses` [INFERRED]
- [[LLM 抛出异常时，optimize() 不抛异常，返回空 OptimalAttackChain。]] - `uses` [INFERRED]
- [[LLM 调用失败时返回空 OptimalAttackChain，不抛异常。]] - `uses` [INFERRED]
- [[LLM 返回空 top_attacks 列表时返回空链（不抛异常）。]] - `uses` [INFERRED]
- [[LLM 返回非法 JSON 时，optimize() 返回空 OptimalAttackChain。]] - `uses` [INFERRED]
- [[LLMAttackChainOutput]] - `uses` [INFERRED]
- [[LLMAttackNodeItem]] - `uses` [INFERRED]
- [[MockLLMClient_11]] - `uses` [INFERRED]
- [[TestAttackDescriptionValidation]] - `uses` [INFERRED]
- [[TestAttackNodeIDDeduplication]] - `uses` [INFERRED]
- [[TestAttackNodeIDValidation]] - `uses` [INFERRED]
- [[TestLLMFailureHandling_2]] - `uses` [INFERRED]
- [[TestMixedValidInvalidNodes]] - `uses` [INFERRED]
- [[TestOpusStyleNormalization]] - `uses` [INFERRED]
- [[TestOutputMetadata]] - `uses` [INFERRED]
- [[TestPromptContent_2]] - `uses` [INFERRED]
- [[TestRecommendedOrder]] - `uses` [INFERRED]
- [[TestSupportingEvidenceIDValidation]] - `uses` [INFERRED]
- [[TestTargetIssueIDValidation]] - `uses` [INFERRED]
- [[TestTopAttackCount]] - `uses` [INFERRED]
- [[attack_chain → top_attacks]] - `uses` [INFERRED]
- [[attack_description 为空字符串的节点被过滤。]] - `uses` [INFERRED]
- [[attack_description 为空的节点被丢弃。]] - `uses` [INFERRED]
- [[attack_label + core_logic → attack_description]] - `uses` [INFERRED]
- [[attack_node_id 为空字符串的节点被过滤。]] - `uses` [INFERRED]
- [[attack_node_id 为空的节点被丢弃。]] - `uses` [INFERRED]
- [[attack_node_id 重复的节点被丢弃（只保留第一次出现）。]] - `uses` [INFERRED]
- [[max_retries=2 时 LLM 连续失败 3 次后返回空链。]] - `uses` [INFERRED]
- [[optimizer.py]] - `contains` [EXTRACTED]
- [[prompt 内容测试——确认关键信息传入 LLM。_2]] - `uses` [INFERRED]
- [[recommended_order 中的 ID 与 top_attacks 的 attack_node_id 完全对应且顺序一致。]] - `uses` [INFERRED]
- [[recommended_order 必须与 top_attacks 完全对应。]] - `uses` [INFERRED]
- [[supporting_evidence_ids 中未知证据 ID 被过滤，节点保留（仍有有效 ID）。]] - `uses` [INFERRED]
- [[supporting_evidence_ids 为空列表的节点被丢弃——零容忍。]] - `uses` [INFERRED]
- [[supporting_evidence_ids 全部无效（过滤后为空）的节点被丢弃——零容忍。]] - `uses` [INFERRED]
- [[supporting_evidence_ids 必须绑定已知证据 ID，非法 ID 被过滤。]] - `uses` [INFERRED]
- [[target_issue_id 为空字符串的节点被过滤。]] - `uses` [INFERRED]
- [[target_issue_id 引用了未知争点的节点被过滤。]] - `uses` [INFERRED]
- [[target_issue_id 必须是已知争点 ID，非法节点被丢弃。]] - `uses` [INFERRED]
- [[top_attacks 数量约束：规则层截断至 3。]] - `uses` [INFERRED]
- [[user prompt 中包含 owner_party_id。]] - `uses` [INFERRED]
- [[user prompt 中包含争点 ID 信息。]] - `uses` [INFERRED]
- [[user prompt 中包含证据 ID 信息。]] - `uses` [INFERRED]
- [[不支持的案件类型在构造时抛出 ValueError。_2]] - `uses` [INFERRED]
- [[两个 attack_node_id 相同的节点只保留第一个。]] - `uses` [INFERRED]
- [[同时包含有效和无效节点时，只保留有效节点（最多 3 个）。]] - `uses` [INFERRED]
- [[场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.]] - `uses` [INFERRED]
- [[截断后 recommended_order 也随之截断（只包含保留的 3 个节点的 ID）。]] - `uses` [INFERRED]
- [[最强攻击链生成器。 Args llm_client 符合 LLMClient 协议的客户端实例 case]] - `rationale_for` [EXTRACTED]
- [[测试 Opus 风格 LLM 输出归一化。]] - `uses` [INFERRED]
- [[结果包含正确的 case_id、run_id、owner_party_id。]] - `uses` [INFERRED]
- [[返回预定义 JSON 响应的 mock LLM 客户端。_6]] - `uses` [INFERRED]
- [[重复 ID 被去重后剩余节点不足 3 个时按实际返回。]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users