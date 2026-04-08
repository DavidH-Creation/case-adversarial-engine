---
source_file: "C:\Users\david\dev\case-adversarial-engine\tests\integration\test_pretrial_pipeline.py"
type: "rationale"
community: "C: Users"
location: "L274"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# Pretrial LLM failure → conference returns partial results without raising.

## Connections
- [[EvidenceStateMachine]] - `uses` [INFERRED]
- [[EvidenceStatusViolation]] - `uses` [INFERRED]
- [[MockLLMClient_16]] - `uses` [INFERRED]
- [[PretrialConferenceEngine]] - `uses` [INFERRED]
- [[PretrialConferenceResult]] - `uses` [INFERRED]
- [[SequentialMockLLMClient]] - `uses` [INFERRED]
- [[test_pretrial_llm_failure_graceful()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users