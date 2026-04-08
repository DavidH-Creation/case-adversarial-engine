---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\tests\test_analysis_endpoints.py"
type: "rationale"
community: "C: Users"
location: "L83"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# run_id 存在 + artifacts 已填充 → 200 + 文件名列表

## Connections
- [[.test_happy_path_returns_artifact_names()]] - `rationale_for` [EXTRACTED]
- [[AdversarialResult]] - `uses` [INFERRED]
- [[CaseRecord]] - `uses` [INFERRED]
- [[CaseStatus]] - `uses` [INFERRED]
- [[CaseStore]] - `uses` [INFERRED]
- [[RoundPhase]] - `uses` [INFERRED]
- [[RoundState]] - `uses` [INFERRED]
- [[ScenarioService]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users