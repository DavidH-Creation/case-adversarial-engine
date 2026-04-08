---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\issue_category_classifier\schemas.py"
type: "code"
community: "C: Users"
location: "L74"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# IssueCategoryClassificationResult

## Connections
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[IssueCategoryClassifier]] - `uses` [INFERRED]
- [[IssueCategoryClassifier — 争点类型分类模块主类。 Issue Category Classifier — main class fo]] - `uses` [INFERRED]
- [[IssueCategoryClassifier 单元测试。 Unit tests for IssueCategoryClassifier. 测试策略：]] - `uses` [INFERRED]
- [[LLM 前 N 次失败后成功，触发重试机制。]] - `uses` [INFERRED]
- [[LLM 整体失败：返回原始 issue_tree，所有争点进 unclassified_issue_ids。]] - `uses` [INFERRED]
- [[LLM 未返回某争点的分类 → 该争点进 unclassified_issue_ids。]] - `uses` [INFERRED]
- [[LLM 返回未知 issue_id → 对应条目被忽略，不影响已知争点结果。]] - `uses` [INFERRED]
- [[MockLLMClient_12]] - `uses` [INFERRED]
- [[TestClassifyFullFlow]] - `uses` [INFERRED]
- [[TestValidationRules]] - `uses` [INFERRED]
- [[calculation_issue 且 related_claim_entry_ids 含有效 claim_id → 通过。]] - `uses` [INFERRED]
- [[calculation_issue 但 related_claim_entry_ids 为空列表 → 清空，进 unclassified。]] - `uses` [INFERRED]
- [[calculation_issue 但 related_claim_entry_ids 无有效 claim_id → 清空，进 unclassified。]] - `uses` [INFERRED]
- [[category_basis 为空 → issue_category 被清空，进 unclassified。]] - `uses` [INFERRED]
- [[classify() 只调用一次 LLM（批量模式）。]] - `uses` [INFERRED]
- [[schemas.py]] - `contains` [EXTRACTED]
- [[不支持的案由类型在初始化时抛出 ValueError。]] - `uses` [INFERRED]
- [[争点类型分类器。 Args llm_client 符合 LLMClient 协议的客户端实例 case_]] - `uses` [INFERRED]
- [[争点类型分类结果产物。纳入 CaseWorkspace.artifact_index。 classified_issue_tree i]] - `rationale_for` [EXTRACTED]
- [[分类后 issue_type 保持原值，不被覆盖（两字段并列）。]] - `uses` [INFERRED]
- [[合法 fact_issue 分类正确富化到 Issue 对象。]] - `uses` [INFERRED]
- [[完整 classify() 流程集成测试。]] - `uses` [INFERRED]
- [[将 LLM 分类结果校验后富化到 Issue 对象。 校验失败规则（任一失败 → 清空 issue_category，记入 unclass]] - `uses` [INFERRED]
- [[执行争点类型分类。 Args inp 分类器输入（含争点树、证据索引、金额报告） Re]] - `uses` [INFERRED]
- [[规则层校验——通过 classify() + MockLLMClient 触发各种失败场景。]] - `uses` [INFERRED]
- [[调用 LLM（结构化输出），失败时抛出异常由 classify() 捕获。]] - `uses` [INFERRED]
- [[返回预定义 JSON 响应的 mock LLM 客户端。 Mock LLM client that returns predefined JSON r_3]] - `uses` [INFERRED]
- [[金额报告诉请条目被注入到 user prompt（供 LLM 引用）。]] - `uses` [INFERRED]
- [[非法 issue_category 枚举值 → 字段清空，进 unclassified。]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users