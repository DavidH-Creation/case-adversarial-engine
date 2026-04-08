---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\procedure_setup\planner.py"
type: "rationale"
community: "C: Users"
location: "L63"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 根据阶段顺序生成 next_state_ids（终止阶段返回空列表）。 Build next_state_ids based on phase ord

## Connections
- [[LLMProcedureConfig]] - `uses` [INFERRED]
- [[LLMProcedureOutput]] - `uses` [INFERRED]
- [[LLMProcedureState]] - `uses` [INFERRED]
- [[ProcedureConfig]] - `uses` [INFERRED]
- [[ProcedureSetupInput]] - `uses` [INFERRED]
- [[ProcedureSetupResult]] - `uses` [INFERRED]
- [[ProcedureState]] - `uses` [INFERRED]
- [[TimelineEvent]] - `uses` [INFERRED]
- [[_build_next_state_ids()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users