---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\procedure_setup\tests\test_planner.py"
type: "rationale"
community: "C: Users"
location: "L514"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 每个 ProcedureState.case_id 必须与 setup_input.case_id 一致。 Every ProcedureState.

## Connections
- [[PartyInfo]] - `uses` [INFERRED]
- [[ProcedurePlanner]] - `uses` [INFERRED]
- [[ProcedureSetupInput]] - `uses` [INFERRED]
- [[ProcedureSetupResult]] - `uses` [INFERRED]
- [[test_procedure_states_have_correct_case_id()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users