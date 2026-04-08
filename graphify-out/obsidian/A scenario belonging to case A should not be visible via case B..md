---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\tests\test_case_scenario_endpoints.py"
type: "rationale"
community: "C: Users"
location: "L296"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# A scenario belonging to case A should not be visible via case B.

## Connections
- [[.test_scenario_from_different_case_returns_404()]] - `rationale_for` [EXTRACTED]
- [[CaseStatus]] - `uses` [INFERRED]
- [[ScenarioStatus]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users