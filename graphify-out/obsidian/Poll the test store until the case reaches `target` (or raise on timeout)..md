---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\tests\test_e2e_lifecycle.py"
type: "rationale"
community: "C: Users"
location: "L244"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# Poll the test store until the case reaches `target` (or raise on timeout).

## Connections
- [[CaseRecord]] - `uses` [INFERRED]
- [[CaseStatus]] - `uses` [INFERRED]
- [[CaseStore]] - `uses` [INFERRED]
- [[Issue]] - `uses` [INFERRED]
- [[SSEProgressReporter]] - `uses` [INFERRED]
- [[_wait_for_status()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users