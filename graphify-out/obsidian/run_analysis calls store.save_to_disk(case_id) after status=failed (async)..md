---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\tests\test_case_store_persistence.py"
type: "rationale"
community: "C: Users"
location: "L759"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# run_analysis calls store.save_to_disk(case_id) after status=failed (async).

## Connections
- [[AdversarialResult]] - `uses` [INFERRED]
- [[CaseRecord]] - `uses` [INFERRED]
- [[CaseStatus]] - `uses` [INFERRED]
- [[CaseStore]] - `uses` [INFERRED]
- [[Issue]] - `uses` [INFERRED]
- [[WorkspaceManager]] - `uses` [INFERRED]
- [[test_run_analysis_saves_after_failed()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users