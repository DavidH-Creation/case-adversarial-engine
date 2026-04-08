---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\issue_category_classifier\classifier.py"
type: "rationale"
community: "C: Users"
location: "L249"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 调用 LLM（结构化输出），失败时抛出异常由 classify() 捕获。

## Connections
- [[._call_llm_structured()_5]] - `rationale_for` [EXTRACTED]
- [[IssueCategoryClassificationResult]] - `uses` [INFERRED]
- [[IssueCategoryClassifierInput]] - `uses` [INFERRED]
- [[LLMIssueCategoryItem]] - `uses` [INFERRED]
- [[LLMIssueCategoryOutput]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users