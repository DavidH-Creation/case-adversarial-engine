---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\tests\test_e2e_lifecycle.py"
type: "rationale"
community: "C: Users"
location: "L625"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# GET progress on case with no progress queue returns 404.

## Connections
- [[.test_progress_stream_nonexistent_returns_404()]] - `rationale_for` [EXTRACTED]
- [[CaseRecord]] - `uses` [INFERRED]
- [[CaseStatus]] - `uses` [INFERRED]
- [[CaseStore]] - `uses` [INFERRED]
- [[Issue]] - `uses` [INFERRED]
- [[SSEProgressReporter]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users