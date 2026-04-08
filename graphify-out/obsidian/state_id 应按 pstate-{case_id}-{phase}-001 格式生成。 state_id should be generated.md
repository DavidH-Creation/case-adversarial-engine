---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\procedure_setup\tests\test_planner.py"
type: "rationale"
community: "C: Users"
location: "L301"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# state_id 应按 pstate-{case_id}-{phase}-001 格式生成。 state_id should be generated

## Connections
- [[PartyInfo]] - `uses` [INFERRED]
- [[ProcedurePlanner]] - `uses` [INFERRED]
- [[ProcedureSetupInput]] - `uses` [INFERRED]
- [[ProcedureSetupResult]] - `uses` [INFERRED]
- [[test_state_ids_are_deterministic()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users