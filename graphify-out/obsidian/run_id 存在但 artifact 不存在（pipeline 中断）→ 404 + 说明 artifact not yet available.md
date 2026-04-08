---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\tests\test_analysis_endpoints.py"
type: "rationale"
community: "C: Users"
location: "L139"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# run_id 存在但 artifact 不存在（pipeline 中断）→ 404 + 说明 artifact not yet available

## Connections
- [[.test_artifact_not_available_returns_404()]] - `rationale_for` [EXTRACTED]
- [[AdversarialResult]] - `uses` [INFERRED]
- [[CaseRecord]] - `uses` [INFERRED]
- [[CaseStatus]] - `uses` [INFERRED]
- [[CaseStore]] - `uses` [INFERRED]
- [[RoundPhase]] - `uses` [INFERRED]
- [[RoundState]] - `uses` [INFERRED]
- [[ScenarioService]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users