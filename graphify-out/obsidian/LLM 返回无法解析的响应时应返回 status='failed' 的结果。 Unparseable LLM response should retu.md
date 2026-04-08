---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\procedure_setup\tests\test_planner.py"
type: "rationale"
community: "C: Users"
location: "L682"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# LLM 返回无法解析的响应时应返回 status='failed' 的结果。 Unparseable LLM response should retu

## Connections
- [[PartyInfo]] - `uses` [INFERRED]
- [[ProcedurePlanner]] - `uses` [INFERRED]
- [[ProcedureSetupInput]] - `uses` [INFERRED]
- [[ProcedureSetupResult]] - `uses` [INFERRED]
- [[test_parse_failure_returns_failed_result()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users