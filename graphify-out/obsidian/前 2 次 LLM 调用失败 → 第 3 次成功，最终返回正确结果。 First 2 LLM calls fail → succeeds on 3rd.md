---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\case_extraction\tests\test_extractor.py"
type: "rationale"
community: "C: Users"
location: "L217"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 前 2 次 LLM 调用失败 → 第 3 次成功，最终返回正确结果。 First 2 LLM calls fail → succeeds on 3rd

## Connections
- [[CaseExtractionResult]] - `uses` [INFERRED]
- [[CaseExtractor]] - `uses` [INFERRED]
- [[test_extract_retries_on_llm_failure()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users