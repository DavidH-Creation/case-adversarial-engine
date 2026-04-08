---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\case_extractor\extractor.py"
type: "code"
community: "C: Users"
location: "L57"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# CaseExtractor

## Connections
- [[.__init__()_17]] - `method` [EXTRACTED]
- [[._build_result()]] - `method` [EXTRACTED]
- [[._call_llm()_1]] - `method` [EXTRACTED]
- [[._to_extracted_case()]] - `method` [EXTRACTED]
- [[.extract()]] - `method` [EXTRACTED]
- [[.to_yaml()]] - `method` [EXTRACTED]
- [[Build a complete civil_loan LLM JSON response.]] - `uses` [INFERRED]
- [[Build a labor_dispute LLM JSON response (no financials).]] - `uses` [INFERRED]
- [[CaseExtractionResult]] - `uses` [INFERRED]
- [[Civil loan without financials → financials is None.]] - `uses` [INFERRED]
- [[Complete civil loan text → ExtractedCase with all fields.]] - `uses` [INFERRED]
- [[Custom case_id overrides auto-generated one.]] - `uses` [INFERRED]
- [[Defense referencing non-existent claim → validation error.]] - `uses` [INFERRED]
- [[DisputedAmount]] - `uses` [INFERRED]
- [[Empty document list → ValueError.]] - `uses` [INFERRED]
- [[Empty list produces empty string.]] - `uses` [INFERRED]
- [[End-to-end document with format braces → extraction succeeds.]] - `uses` [INFERRED]
- [[Extract structured case information from raw legal documents. Args]] - `rationale_for` [EXTRACTED]
- [[Extracted YAML passes the same validation as _load_case().]] - `uses` [INFERRED]
- [[ExtractedCase]] - `uses` [INFERRED]
- [[ExtractedCase with empty claims → validation error.]] - `uses` [INFERRED]
- [[ExtractionClaim]] - `uses` [INFERRED]
- [[ExtractionEvidence]] - `uses` [INFERRED]
- [[ExtractionParty]] - `uses` [INFERRED]
- [[Fully populated case has zero validation errors.]] - `uses` [INFERRED]
- [[Generated YAML can be parsed back and contains required keys.]] - `uses` [INFERRED]
- [[Generated YAML starts with header comments.]] - `uses` [INFERRED]
- [[IssueExtractor 单元测试。 IssueExtractor unit tests. 使用 mock LLM 客户端验证： Validate]] - `uses` [INFERRED]
- [[LLM failures are retried (via call_llm_with_retry).]] - `uses` [INFERRED]
- [[LLMCaseExtractionOutput]] - `uses` [INFERRED]
- [[LLMExtractionOutput]] - `uses` [INFERRED]
- [[LLMExtractionOutput with financials=null.]] - `uses` [INFERRED]
- [[LLMExtractionOutput.model_validate on complete JSON.]] - `uses` [INFERRED]
- [[Labor dispute → no financials in output.]] - `uses` [INFERRED]
- [[Materials are correctly grouped into plaintiff defendant.]] - `uses` [INFERRED]
- [[Missing defendant party → validation error.]] - `uses` [INFERRED]
- [[Mock LLM client returning predefined JSON responses.]] - `uses` [INFERRED]
- [[MockLLMClient_1]] - `uses` [INFERRED]
- [[Multiple documents produce multiple XML blocks.]] - `uses` [INFERRED]
- [[Multiple input files are concatenated for extraction.]] - `uses` [INFERRED]
- [[No defenses (only complaint) → empty defenses list.]] - `uses` [INFERRED]
- [[Pure Chinese names → hash-based slug.]] - `uses` [INFERRED]
- [[TestEdgeCases]] - `uses` [INFERRED]
- [[TestErrors]] - `uses` [INFERRED]
- [[TestHappyPath_1]] - `uses` [INFERRED]
- [[TestPrompts]] - `uses` [INFERRED]
- [[TestSchemas_1]] - `uses` [INFERRED]
- [[TestSlugify]] - `uses` [INFERRED]
- [[TestValidation]] - `uses` [INFERRED]
- [[TestYAMLRoundTrip]] - `uses` [INFERRED]
- [[Unknown prompt name → ValueError.]] - `uses` [INFERRED]
- [[YAML serialize → parse → same structure.]] - `uses` [INFERRED]
- [[extractor.py]] - `contains` [EXTRACTED]
- [[format_documents escapes XML entities in filenames and content.]] - `uses` [INFERRED]
- [[to_yaml 输出符合 cases schema 结构（含必要顶层字段）。 to_yaml output conforms to cases s]] - `uses` [INFERRED]
- [[unknown 值的行应自动追加  TODO verify 注释。 Lines with 'unknown' values get  TODO]] - `uses` [INFERRED]
- [[前 2 次 LLM 调用失败 → 第 3 次成功，最终返回正确结果。 First 2 LLM calls fail → succeeds on 3rd]] - `uses` [INFERRED]
- [[包含 3 份证据描述的文本 → evidence_list 有 3 条，含 description + document_type。 Text wit]] - `uses` [INFERRED]
- [[场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.]] - `uses` [INFERRED]
- [[多被告文本 → defendants 列表包含所有被告。 Multi-defendant text → defendants list contain]] - `uses` [INFERRED]
- [[完整文本 → parties（原被告各 1）+ disputed_amount 正确提取。 Full text → parties (1 plaint]] - `uses` [INFERRED]
- [[应能从 markdown 代码块中提取 JSON 对象。]] - `uses` [INFERRED]
- [[文本缺少被告信息 → defendant 值为 'unknown'，YAML 含  TODO verify 注释。 Missing defenda]] - `uses` [INFERRED]
- [[案件文本提取器 Case Text Extractor 从法律文本中提取案件结构化信息，输出兼容 cases schema 的 YAM]] - `rationale_for` [EXTRACTED]
- [[空输入 → 明确 ValueError，不生成空 YAML。 Empty input → ValueError raised, no empty YA]] - `uses` [INFERRED]
- [[超过最大重试次数（3）后应抛出 RuntimeError。]] - `uses` [INFERRED]
- [[返回预定义 JSON 响应的 mock LLM 客户端。 Mock LLM client returning predefined JSON resp]] - `uses` [INFERRED]
- [[金额出现两次且不一致 → disputed_amount 含两个候选值，标记 ambiguous。 Two different amounts → d]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users