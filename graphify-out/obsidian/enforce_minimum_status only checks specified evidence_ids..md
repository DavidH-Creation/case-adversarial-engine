---
source_file: "C:\Users\david\dev\case-adversarial-engine\tests\integration\test_pretrial_pipeline.py"
type: "rationale"
community: "C: Users"
location: "L336"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# enforce_minimum_status only checks specified evidence_ids.

## Connections
- [[EvidenceStateMachine]] - `uses` [INFERRED]
- [[EvidenceStatusViolation]] - `uses` [INFERRED]
- [[MockLLMClient_16]] - `uses` [INFERRED]
- [[PretrialConferenceEngine]] - `uses` [INFERRED]
- [[PretrialConferenceResult]] - `uses` [INFERRED]
- [[SequentialMockLLMClient]] - `uses` [INFERRED]
- [[test_enforce_minimum_status_filtered()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users