---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\issue_extractor\schemas.py"
type: "code"
community: "C: Users"
location: "L102"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# LLMExtractionOutput

## Connections
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[Build a complete civil_loan LLM JSON response.]] - `uses` [INFERRED]
- [[Build a labor_dispute LLM JSON response (no financials).]] - `uses` [INFERRED]
- [[Call LLM with structured output, falling back to text extraction.]] - `uses` [INFERRED]
- [[CaseExtractor]] - `uses` [INFERRED]
- [[Civil loan without financials → financials is None.]] - `uses` [INFERRED]
- [[Complete civil loan text → ExtractedCase with all fields.]] - `uses` [INFERRED]
- [[Convert LLM output to pipeline-compatible ExtractedCase.]] - `uses` [INFERRED]
- [[Convert text to a URL-friendly slug.]] - `uses` [INFERRED]
- [[Custom case_id overrides auto-generated one.]] - `uses` [INFERRED]
- [[Defense referencing non-existent claim → validation error.]] - `uses` [INFERRED]
- [[Empty document list → ValueError.]] - `uses` [INFERRED]
- [[Empty list produces empty string.]] - `uses` [INFERRED]
- [[End-to-end document with format braces → extraction succeeds.]] - `uses` [INFERRED]
- [[Extract structured case data from raw documents. Args d]] - `uses` [INFERRED]
- [[Extract structured case information from raw legal documents. Args]] - `uses` [INFERRED]
- [[Extracted YAML passes the same validation as _load_case().]] - `uses` [INFERRED]
- [[ExtractedCase with empty claims → validation error.]] - `uses` [INFERRED]
- [[Fully populated case has zero validation errors.]] - `uses` [INFERRED]
- [[Generated YAML can be parsed back and contains required keys.]] - `uses` [INFERRED]
- [[Generated YAML starts with header comments.]] - `uses` [INFERRED]
- [[IssueExtractor]] - `uses` [INFERRED]
- [[IssueExtractor 单元测试。 IssueExtractor unit tests. 使用 mock LLM 客户端验证： Validate]] - `uses` [INFERRED]
- [[LLM failures are retried (via call_llm_with_retry).]] - `uses` [INFERRED]
- [[LLM 完整提取结果 — call_structured_llm 返回后 model_validate 此模型。]] - `rationale_for` [EXTRACTED]
- [[LLM 提取的完整结构化输出。 临时ID由 IssueExtractor._build_issue_tree 替换为正式ID。]] - `rationale_for` [EXTRACTED]
- [[LLMExtractionOutput with financials=null.]] - `uses` [INFERRED]
- [[LLMExtractionOutput.model_validate on complete JSON.]] - `uses` [INFERRED]
- [[Labor dispute → no financials in output.]] - `uses` [INFERRED]
- [[Load a prompt module from the registry.]] - `uses` [INFERRED]
- [[Materials are correctly grouped into plaintiff defendant.]] - `uses` [INFERRED]
- [[Missing defendant party → validation error.]] - `uses` [INFERRED]
- [[Mock LLM client returning predefined JSON responses.]] - `uses` [INFERRED]
- [[MockLLMClient_1]] - `uses` [INFERRED]
- [[Multiple documents produce multiple XML blocks.]] - `uses` [INFERRED]
- [[Multiple input files are concatenated for extraction.]] - `uses` [INFERRED]
- [[No defenses (only complaint) → empty defenses list.]] - `uses` [INFERRED]
- [[Pure Chinese names → hash-based slug.]] - `uses` [INFERRED]
- [[Serialize ExtractedCase to YAML string. Args extracted]] - `uses` [INFERRED]
- [[TestEdgeCases]] - `uses` [INFERRED]
- [[TestErrors]] - `uses` [INFERRED]
- [[TestHappyPath_1]] - `uses` [INFERRED]
- [[TestPrompts]] - `uses` [INFERRED]
- [[TestSchemas_1]] - `uses` [INFERRED]
- [[TestSlugify]] - `uses` [INFERRED]
- [[TestValidation]] - `uses` [INFERRED]
- [[TestYAMLRoundTrip]] - `uses` [INFERRED]
- [[Unknown prompt name → ValueError.]] - `uses` [INFERRED]
- [[Validate extracted case against pipeline requirements. Returns]] - `uses` [INFERRED]
- [[YAML serialize → parse → same structure.]] - `uses` [INFERRED]
- [[format_documents escapes XML entities in filenames and content.]] - `uses` [INFERRED]
- [[schemas.py]] - `contains` [EXTRACTED]
- [[争点抽取器 Issue Extractor 将 Claims + Defenses + Evidence 通过 LLM 提取为结构化 I]] - `uses` [INFERRED]
- [[争点抽取器核心模块 Issue extractor core module 从 Claims + Defenses + Evidence 中提取争议焦点]] - `uses` [INFERRED]
- [[加载案由对应的 prompt 模板模块。 Load the prompt template module for the given case]] - `uses` [INFERRED]
- [[场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.]] - `uses` [INFERRED]
- [[将 LLM 提取的原始结构转化为规范化 IssueTree。 Transform raw LLM extraction output into]] - `uses` [INFERRED]
- [[将 LLM 返回的争点类型字符串解析为枚举值。 Resolve LLM-returned issue type string to IssueType]] - `uses` [INFERRED]
- [[将 LLM 返回的命题状态字符串解析为枚举值。 Resolve LLM-returned proposition status string to P]] - `uses` [INFERRED]
- [[应能从 markdown 代码块中提取 JSON 对象。]] - `uses` [INFERRED]
- [[执行争点抽取。 Execute issue extraction. Args claims]] - `uses` [INFERRED]
- [[调用 LLM 并返回结构化 dict（tool_use 优先，fallback 到 json_utils）。 Call LLM and ret]] - `uses` [INFERRED]
- [[超过最大重试次数（3）后应抛出 RuntimeError。]] - `uses` [INFERRED]
- [[验证输入数据合法性。 Validate input data validity. Raises]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users