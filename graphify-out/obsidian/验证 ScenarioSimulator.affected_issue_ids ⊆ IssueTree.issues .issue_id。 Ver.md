---
source_file: "C:\Users\david\dev\case-adversarial-engine\tests\integration\test_full_pipeline.py"
type: "rationale"
community: "C: Users"
location: "L599"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 验证 ScenarioSimulator.affected_issue_ids ⊆ IssueTree.issues[ ].issue_id。 Ver

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
- [[test_simulation_run_issue_id_consistency()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users