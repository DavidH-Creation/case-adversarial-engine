---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\tests\test_e2e_lifecycle.py"
type: "rationale"
community: "C: Users"
location: "L263"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# Push a case through the full lifecycle to analyzed state. Returns case_id.

## Connections
- [[CaseRecord]] - `uses` [INFERRED]
- [[CaseStatus]] - `uses` [INFERRED]
- [[CaseStore]] - `uses` [INFERRED]
- [[Issue]] - `uses` [INFERRED]
- [[SSEProgressReporter]] - `uses` [INFERRED]
- [[_drive_to_analyzed()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users