---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\procedure_setup\tests\test_planner.py"
type: "rationale"
community: "C: Users"
location: "L660"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# LLM 所有重试均失败应返回 status='failed' 的结果，不抛出异常。 Exhausted retries should return a

## Connections
- [[PartyInfo]] - `uses` [INFERRED]
- [[ProcedurePlanner]] - `uses` [INFERRED]
- [[ProcedureSetupInput]] - `uses` [INFERRED]
- [[ProcedureSetupResult]] - `uses` [INFERRED]
- [[test_llm_retry_exhausted_returns_failed_result()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users