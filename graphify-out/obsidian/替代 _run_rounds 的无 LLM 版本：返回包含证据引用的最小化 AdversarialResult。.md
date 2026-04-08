---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\tests\test_e2e_api_flow.py"
type: "rationale"
community: "C: Users"
location: "L134"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 替代 _run_rounds 的无 LLM 版本：返回包含证据引用的最小化 AdversarialResult。

## Connections
- [[AdversarialResult]] - `uses` [INFERRED]
- [[CaseRecord]] - `uses` [INFERRED]
- [[CaseStatus]] - `uses` [INFERRED]
- [[CaseStore]] - `uses` [INFERRED]
- [[Issue]] - `uses` [INFERRED]
- [[RoundPhase]] - `uses` [INFERRED]
- [[RoundState]] - `uses` [INFERRED]
- [[WorkspaceManager]] - `uses` [INFERRED]
- [[_fake_run_rounds()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users