---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\tests\test_e2e_lifecycle.py"
type: "rationale"
community: "C: Users"
location: "L478"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# Missing case_type should return 422 (Pydantic validation).

## Connections
- [[.test_create_case_missing_required_fields()]] - `rationale_for` [EXTRACTED]
- [[CaseRecord]] - `uses` [INFERRED]
- [[CaseStatus]] - `uses` [INFERRED]
- [[CaseStore]] - `uses` [INFERRED]
- [[Issue]] - `uses` [INFERRED]
- [[SSEProgressReporter]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users