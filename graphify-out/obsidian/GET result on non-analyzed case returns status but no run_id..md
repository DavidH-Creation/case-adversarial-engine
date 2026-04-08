---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\tests\test_e2e_lifecycle.py"
type: "rationale"
community: "C: Users"
location: "L444"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# GET result on non-analyzed case returns status but no run_id.

## Connections
- [[.test_result_before_analysis_has_no_run_id()]] - `rationale_for` [EXTRACTED]
- [[CaseRecord]] - `uses` [INFERRED]
- [[CaseStatus]] - `uses` [INFERRED]
- [[CaseStore]] - `uses` [INFERRED]
- [[Issue]] - `uses` [INFERRED]
- [[SSEProgressReporter]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users