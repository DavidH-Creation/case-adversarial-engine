---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\procedure_setup\planner.py"
type: "rationale"
community: "C: Users"
location: "L90"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 清理证据状态列表，强制执行 output_branching 约束。 Sanitize evidence status list, enforcing

## Connections
- [[LLMProcedureConfig]] - `uses` [INFERRED]
- [[LLMProcedureOutput]] - `uses` [INFERRED]
- [[LLMProcedureState]] - `uses` [INFERRED]
- [[ProcedureConfig]] - `uses` [INFERRED]
- [[ProcedureSetupInput]] - `uses` [INFERRED]
- [[ProcedureSetupResult]] - `uses` [INFERRED]
- [[ProcedureState]] - `uses` [INFERRED]
- [[TimelineEvent]] - `uses` [INFERRED]
- [[_sanitize_evidence_statuses()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users