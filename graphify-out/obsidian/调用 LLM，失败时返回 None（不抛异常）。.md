---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\admissibility_evaluator\evaluator.py"
type: "rationale"
community: "C: Users"
location: "L130"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 调用 LLM，失败时返回 None（不抛异常）。

## Connections
- [[._call_llm()]] - `rationale_for` [EXTRACTED]
- [[AdmissibilityEvaluatorInput]] - `uses` [INFERRED]
- [[EvidenceStateMachine]] - `uses` [INFERRED]
- [[LLMAdmissibilityItem]] - `uses` [INFERRED]
- [[LLMAdmissibilityOutput]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users