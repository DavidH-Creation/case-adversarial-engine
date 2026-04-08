---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\tests\test_analysis_endpoints.py"
type: "rationale"
community: "C: Users"
location: "L526"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# load_from_workspace must return None for a case_id that was never created.

## Connections
- [[.test_load_from_workspace_returns_none_for_unknown_case()]] - `rationale_for` [EXTRACTED]
- [[AdversarialResult]] - `uses` [INFERRED]
- [[CaseRecord]] - `uses` [INFERRED]
- [[CaseStatus]] - `uses` [INFERRED]
- [[CaseStore]] - `uses` [INFERRED]
- [[RoundPhase]] - `uses` [INFERRED]
- [[RoundState]] - `uses` [INFERRED]
- [[ScenarioService]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users