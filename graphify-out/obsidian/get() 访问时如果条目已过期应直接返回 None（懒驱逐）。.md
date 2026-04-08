---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\tests\test_analysis_endpoints.py"
type: "rationale"
community: "C: Users"
location: "L553"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# get() 访问时如果条目已过期应直接返回 None（懒驱逐）。

## Connections
- [[.test_case_store_get_evicts_lazily_on_access()]] - `rationale_for` [EXTRACTED]
- [[AdversarialResult]] - `uses` [INFERRED]
- [[CaseRecord]] - `uses` [INFERRED]
- [[CaseStatus]] - `uses` [INFERRED]
- [[CaseStore]] - `uses` [INFERRED]
- [[RoundPhase]] - `uses` [INFERRED]
- [[RoundState]] - `uses` [INFERRED]
- [[ScenarioService]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users