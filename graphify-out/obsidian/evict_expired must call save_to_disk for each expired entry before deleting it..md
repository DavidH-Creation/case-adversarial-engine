---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\tests\test_case_store_persistence.py"
type: "rationale"
community: "C: Users"
location: "L362"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# evict_expired must call save_to_disk for each expired entry before deleting it.

## Connections
- [[AdversarialResult]] - `uses` [INFERRED]
- [[CaseRecord]] - `uses` [INFERRED]
- [[CaseStatus]] - `uses` [INFERRED]
- [[CaseStore]] - `uses` [INFERRED]
- [[Issue]] - `uses` [INFERRED]
- [[WorkspaceManager]] - `uses` [INFERRED]
- [[test_evict_expired_calls_save_to_disk_before_removing()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users