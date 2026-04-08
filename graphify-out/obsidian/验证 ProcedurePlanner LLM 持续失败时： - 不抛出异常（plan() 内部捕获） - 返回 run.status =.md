---
source_file: "C:\Users\david\dev\case-adversarial-engine\tests\integration\test_full_pipeline.py"
type: "rationale"
community: "C: Users"
location: "L749"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 验证 ProcedurePlanner LLM 持续失败时： - 不抛出异常（plan() 内部捕获） - 返回 run.status =

## Connections
- [[EvidenceIndexer]] - `uses` [INFERRED]
- [[FollowupResponder]] - `uses` [INFERRED]
- [[IssueExtractor]] - `uses` [INFERRED]
- [[MockLLMClient_16]] - `uses` [INFERRED]
- [[PartyInfo]] - `uses` [INFERRED]
- [[ProcedurePlanner]] - `uses` [INFERRED]
- [[ProcedureSetupInput]] - `uses` [INFERRED]
- [[ReportGenerator]] - `uses` [INFERRED]
- [[ScenarioInput]] - `uses` [INFERRED]
- [[ScenarioSimulator]] - `uses` [INFERRED]
- [[SequentialMockLLMClient]] - `uses` [INFERRED]
- [[test_procedure_planner_failure_degradation()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users