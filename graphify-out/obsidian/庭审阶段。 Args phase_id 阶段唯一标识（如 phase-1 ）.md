---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\hearing_order\schemas.py"
type: "rationale"
community: "C: Users"
location: "L27"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/C:_Users
---

# 庭审阶段。 Args phase_id 阶段唯一标识（如 phase-1 ）

## Connections
- [[DefenseChainResult]] - `uses` [INFERRED]
- [[ExecutiveSummarizerInput]] - `rationale_for` [EXTRACTED]
- [[HearingPhase]] - `rationale_for` [EXTRACTED]
- [[IssueDependencyGraph]] - `uses` [INFERRED]
- [[NumberedItem]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/EXTRACTED #community/C:_Users