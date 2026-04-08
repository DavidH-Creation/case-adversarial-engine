---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\procedure_setup\tests\test_planner.py"
type: "rationale"
community: "C: Users"
location: "L866"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# judge_questions 阶段应清除 owner_private。 owner_private should be removed from j

## Connections
- [[PartyInfo]] - `uses` [INFERRED]
- [[ProcedurePlanner]] - `uses` [INFERRED]
- [[ProcedureSetupInput]] - `uses` [INFERRED]
- [[ProcedureSetupResult]] - `uses` [INFERRED]
- [[test_sanitize_access_domains_removes_owner_private_from_judge_questions()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users