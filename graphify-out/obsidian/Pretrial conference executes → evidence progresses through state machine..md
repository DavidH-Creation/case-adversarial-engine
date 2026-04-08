---
source_file: "C:\Users\david\dev\case-adversarial-engine\tests\integration\test_pretrial_pipeline.py"
type: "rationale"
community: "C: Users"
location: "L135"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# Pretrial conference executes → evidence progresses through state machine.

## Connections
- [[EvidenceStateMachine]] - `uses` [INFERRED]
- [[EvidenceStatusViolation]] - `uses` [INFERRED]
- [[MockLLMClient_16]] - `uses` [INFERRED]
- [[PretrialConferenceEngine]] - `uses` [INFERRED]
- [[PretrialConferenceResult]] - `uses` [INFERRED]
- [[SequentialMockLLMClient]] - `uses` [INFERRED]
- [[test_pretrial_happy_path()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users