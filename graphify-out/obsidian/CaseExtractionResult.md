---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\case_extraction\schemas.py"
type: "code"
community: "C: Users"
location: "L120"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# CaseExtractionResult

## Connections
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[CaseExtractor]] - `uses` [INFERRED]
- [[Custom case_id overrides auto-generated one.]] - `uses` [INFERRED]
- [[IssueExtractor 单元测试。 IssueExtractor unit tests. 使用 mock LLM 客户端验证： Validate]] - `uses` [INFERRED]
- [[MockLLMClient_1]] - `uses` [INFERRED]
- [[schemas.py]] - `contains` [EXTRACTED]
- [[to_yaml 输出符合 cases schema 结构（含必要顶层字段）。 to_yaml output conforms to cases s]] - `uses` [INFERRED]
- [[unknown 值的行应自动追加  TODO verify 注释。 Lines with 'unknown' values get  TODO]] - `uses` [INFERRED]
- [[争点抽取器核心模块 Issue extractor core module 从 Claims + Defenses + Evidence 中提取争议焦点]] - `uses` [INFERRED]
- [[从文本中提取案件信息。 Extract case information from text. Args]] - `uses` [INFERRED]
- [[前 2 次 LLM 调用失败 → 第 3 次成功，最终返回正确结果。 First 2 LLM calls fail → succeeds on 3rd]] - `uses` [INFERRED]
- [[包含 3 份证据描述的文本 → evidence_list 有 3 条，含 description + document_type。 Text wit]] - `uses` [INFERRED]
- [[去重并保留顺序。Remove duplicates while preserving order.]] - `uses` [INFERRED]
- [[在含 unknown ambiguous 值的行后注入 TODO 注释。 Inject TODO ambiguous comments after l]] - `uses` [INFERRED]
- [[场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.]] - `uses` [INFERRED]
- [[多被告文本 → defendants 列表包含所有被告。 Multi-defendant text → defendants list contain]] - `uses` [INFERRED]
- [[完整文本 → parties（原被告各 1）+ disputed_amount 正确提取。 Full text → parties (1 plaint]] - `uses` [INFERRED]
- [[完整案件提取结果，可序列化为 YAML。 Complete case extraction result, serializable to YAML.]] - `rationale_for` [EXTRACTED]
- [[将 CaseExtractionResult 序列化为兼容 cases schema 的 YAML 字符串。 Serialize CaseE]] - `uses` [INFERRED]
- [[将 LLM 输出组装为 CaseExtractionResult。 Assemble CaseExtractionResult from LL]] - `uses` [INFERRED]
- [[文本缺少被告信息 → defendant 值为 'unknown'，YAML 含  TODO verify 注释。 Missing defenda]] - `uses` [INFERRED]
- [[案件文本提取器 Case Text Extractor 从法律文本中提取案件结构化信息，输出兼容 cases schema 的 YAM]] - `uses` [INFERRED]
- [[空输入 → 明确 ValueError，不生成空 YAML。 Empty input → ValueError raised, no empty YA]] - `uses` [INFERRED]
- [[返回预定义 JSON 响应的 mock LLM 客户端。 Mock LLM client returning predefined JSON resp]] - `uses` [INFERRED]
- [[金额出现两次且不一致 → disputed_amount 含两个候选值，标记 ambiguous。 Two different amounts → d]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users