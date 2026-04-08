---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\tests\test_end_to_end_flow.py"
type: "rationale"
community: "C: Users"
location: "L178"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# Step 1 POST api cases → 201 + case_id.

## Connections
- [[.test_create_returns_case_id_and_status_created()]] - `rationale_for` [EXTRACTED]
- [[AdversarialResult]] - `uses` [INFERRED]
- [[CaseStatus]] - `uses` [INFERRED]
- [[RoundPhase]] - `uses` [INFERRED]
- [[RoundState]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users