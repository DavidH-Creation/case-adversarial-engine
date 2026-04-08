---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\tests\test_case_store_persistence.py"
type: "rationale"
community: "C: Users"
location: "L320"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# evict_expired must flush to disk before removing from memory.

## Connections
- [[AdversarialResult]] - `uses` [INFERRED]
- [[CaseRecord]] - `uses` [INFERRED]
- [[CaseStatus]] - `uses` [INFERRED]
- [[CaseStore]] - `uses` [INFERRED]
- [[Issue]] - `uses` [INFERRED]
- [[WorkspaceManager]] - `uses` [INFERRED]
- [[test_evict_expired_saves_before_eviction()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users