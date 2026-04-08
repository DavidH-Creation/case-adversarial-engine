---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\tests\test_analysis_endpoints.py"
type: "rationale"
community: "C: Users"
location: "L70"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 每个测试前后清空全局 store，确保测试隔离。

## Connections
- [[AdversarialResult]] - `uses` [INFERRED]
- [[CaseRecord]] - `uses` [INFERRED]
- [[CaseStatus]] - `uses` [INFERRED]
- [[CaseStore]] - `uses` [INFERRED]
- [[RoundPhase]] - `uses` [INFERRED]
- [[RoundState]] - `uses` [INFERRED]
- [[ScenarioService]] - `uses` [INFERRED]
- [[clear_store()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users