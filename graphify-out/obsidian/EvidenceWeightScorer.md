---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\evidence_weight_scorer\scorer.py"
type: "code"
community: "C: Users"
location: "L60"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# EvidenceWeightScorer

## Connections
- [[.__init__()_25]] - `method` [EXTRACTED]
- [[._build_scored_map()]] - `method` [EXTRACTED]
- [[._call_llm()_2]] - `method` [EXTRACTED]
- [[.score()]] - `method` [EXTRACTED]
- [[AuthenticityRisk 枚举包含三个合法值。]] - `uses` [INFERRED]
- [[CredibilityScorer 单元测试（P2.9）。 测试策略： - 使用 Pydantic 模型构建测试数据（不用 Mock） - 每条规则（]] - `uses` [INFERRED]
- [[Evidence 模型具备四个权重字段，默认均为 None；evidence_weight_scored 默认 False。]] - `uses` [INFERRED]
- [[Evidence 的权重字段接受对应枚举值。]] - `uses` [INFERRED]
- [[EvidenceWeightScorerInput]] - `uses` [INFERRED]
- [[EvidenceWeightScorerInput 需要 case_id、run_id 和 evidence_index。]] - `uses` [INFERRED]
- [[LLM 失败时：返回原始 EvidenceIndex，不抛异常。_1]] - `uses` [INFERRED]
- [[LLM 抛出异常时返回原始 EvidenceIndex，不抛异常。]] - `uses` [INFERRED]
- [[LLM 提供的 admissibility_notes 写入 Evidence.admissibility_notes 字段。]] - `uses` [INFERRED]
- [[LLM 输出了未知 evidence_id → 该条被忽略，已知证据正常处理。]] - `uses` [INFERRED]
- [[LLM 输出重复 evidence_id 时，最后一条覆盖前一条（last wins）。]] - `uses` [INFERRED]
- [[LLM 返回空字符串时返回原始 EvidenceIndex。]] - `uses` [INFERRED]
- [[LLM 返回非法 JSON 时返回原始 EvidenceIndex。_1]] - `uses` [INFERRED]
- [[LLMEvidenceWeightItem]] - `uses` [INFERRED]
- [[LLMEvidenceWeightItem 所有字段都有默认值（LLM 可能不输出完整字段）。]] - `uses` [INFERRED]
- [[LLMEvidenceWeightOutput]] - `uses` [INFERRED]
- [[LLMEvidenceWeightOutput 默认 evidence_weights 为空列表。]] - `uses` [INFERRED]
- [[MockLLMClient_4]] - `uses` [INFERRED]
- [[PROMPT_REGISTRY 包含 civil_loan 键及所需函数。_1]] - `uses` [INFERRED]
- [[ProbativeValue 枚举包含三个合法值。]] - `uses` [INFERRED]
- [[RelevanceScore 枚举包含三个合法值。]] - `uses` [INFERRED]
- [[TestAdmissibilityNotesEnforcement]] - `uses` [INFERRED]
- [[TestConstructorValidation_1]] - `uses` [INFERRED]
- [[TestInvalidEnumFiltering]] - `uses` [INFERRED]
- [[TestLLMFailureHandling_1]] - `uses` [INFERRED]
- [[TestMixedValidInvalid]] - `uses` [INFERRED]
- [[TestPromptContent_1]] - `uses` [INFERRED]
- [[TestSuccessfulScoring]] - `uses` [INFERRED]
- [[Vulnerability 枚举包含三个合法值。]] - `uses` [INFERRED]
- [[authenticity_risk=high 且 admissibility_notes 为空字符串（非 None）→ 同样被跳过。]] - `uses` [INFERRED]
- [[authenticity_risk=high 且 vulnerability=high，有 notes → 正常更新。]] - `uses` [INFERRED]
- [[authenticity_risk=high 且有 admissibility_notes → 正常更新。]] - `uses` [INFERRED]
- [[authenticity_risk=high 但无 admissibility_notes → 不更新该条证据权重字段。]] - `uses` [INFERRED]
- [[civil_loan 案件类型正常构造，不抛异常。]] - `uses` [INFERRED]
- [[max_retries=2 时 LLM 连续失败 3 次（1 次初始 + 2 次重试）后返回原始索引。]] - `uses` [INFERRED]
- [[prompt 内容测试——确认关键信息传入 LLM。_1]] - `uses` [INFERRED]
- [[scorer.py]] - `contains` [EXTRACTED]
- [[system prompt 必须提到四个评分维度的字段名。]] - `uses` [INFERRED]
- [[system prompt 非空并传递给 LLM。_1]] - `uses` [INFERRED]
- [[user prompt 包含待评分的证据 ID。]] - `uses` [INFERRED]
- [[user prompt 包含待评分证据的 ID。]] - `uses` [INFERRED]
- [[user prompt 包含证据数量提示，供 LLM 校验输出数量。]] - `uses` [INFERRED]
- [[user prompt 告知 LLM 高风险时须提供 admissibility_notes。]] - `uses` [INFERRED]
- [[vulnerability=high 且有 admissibility_notes → 正常更新。]] - `uses` [INFERRED]
- [[vulnerability=high 但无 admissibility_notes → 不更新该条证据权重字段。]] - `uses` [INFERRED]
- [[一条高风险缺 notes（跳过），一条正常（更新）。]] - `uses` [INFERRED]
- [[不支持的案件类型在构造时抛出 ValueError。_1]] - `uses` [INFERRED]
- [[低风险时 admissibility_notes 为 None 也正常更新。]] - `uses` [INFERRED]
- [[场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.]] - `uses` [INFERRED]
- [[成功评分后，evidence 的四个字段全部非 None。]] - `uses` [INFERRED]
- [[成功评分后，evidence_weight_scored = True。]] - `uses` [INFERRED]
- [[枚举值正确映射到 AuthenticityRisk 等类型。]] - `uses` [INFERRED]
- [[混合有效 无效条目时，只有有效的被标记 scored=True。]] - `uses` [INFERRED]
- [[空证据列表时不调用 LLM，直接返回空 EvidenceIndex。]] - `uses` [INFERRED]
- [[规则层强制：高风险证据必须有 admissibility_notes。]] - `uses` [INFERRED]
- [[证据权重评分器。 Args llm_client 符合 LLMClient 协议的客户端实例 case_]] - `rationale_for` [EXTRACTED]
- [[评分后原有字段（title, summary 等）不受影响。]] - `uses` [INFERRED]
- [[输出 EvidenceIndex 的 case_id 与输入一致。_1]] - `uses` [INFERRED]
- [[返回预定义 JSON 响应的 mock LLM 客户端。_2]] - `uses` [INFERRED]
- [[部分证据有效、部分枚举非法时，只有有效的被标记 scored=True。]] - `uses` [INFERRED]
- [[非法 authenticity_risk 值（自由文本）的证据被跳过。]] - `uses` [INFERRED]
- [[非法 relevance_score 值的证据被跳过。]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users