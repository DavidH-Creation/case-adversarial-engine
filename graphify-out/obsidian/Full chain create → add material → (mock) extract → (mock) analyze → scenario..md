---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\tests\test_end_to_end_flow.py"
type: "rationale"
community: "C: Users"
location: "L186"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# Full chain create → add material → (mock) extract → (mock) analyze → scenario.

## Connections
- [[.test_full_flow_create_extract_analyze_scenario()]] - `rationale_for` [EXTRACTED]
- [[AdversarialResult]] - `uses` [INFERRED]
- [[CaseStatus]] - `uses` [INFERRED]
- [[RoundPhase]] - `uses` [INFERRED]
- [[RoundState]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users