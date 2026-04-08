---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\tests\test_e2e_api_flow.py"
type: "rationale"
community: "C: Users"
location: "L106"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 构造引用了 cited_ev_id 的 AgentOutput，用于触发证据状态提升。

## Connections
- [[AdversarialResult]] - `uses` [INFERRED]
- [[CaseRecord]] - `uses` [INFERRED]
- [[CaseStatus]] - `uses` [INFERRED]
- [[CaseStore]] - `uses` [INFERRED]
- [[Issue]] - `uses` [INFERRED]
- [[RoundPhase]] - `uses` [INFERRED]
- [[RoundState]] - `uses` [INFERRED]
- [[WorkspaceManager]] - `uses` [INFERRED]
- [[_make_agent_output()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users