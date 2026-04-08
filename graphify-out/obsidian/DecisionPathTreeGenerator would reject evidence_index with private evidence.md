---
source_file: "C:\Users\david\dev\case-adversarial-engine\tests\integration\test_pretrial_pipeline.py"
type: "rationale"
community: "C: Users"
location: "L364"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# DecisionPathTreeGenerator would reject evidence_index with private evidence

## Connections
- [[EvidenceStateMachine]] - `uses` [INFERRED]
- [[EvidenceStatusViolation]] - `uses` [INFERRED]
- [[MockLLMClient_16]] - `uses` [INFERRED]
- [[PretrialConferenceEngine]] - `uses` [INFERRED]
- [[PretrialConferenceResult]] - `uses` [INFERRED]
- [[SequentialMockLLMClient]] - `uses` [INFERRED]
- [[test_enforce_blocks_private_evidence_in_generator()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users