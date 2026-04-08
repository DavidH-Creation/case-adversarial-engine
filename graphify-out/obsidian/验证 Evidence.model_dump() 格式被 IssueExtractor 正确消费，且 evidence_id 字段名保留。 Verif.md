---
source_file: "C:\Users\david\dev\case-adversarial-engine\tests\integration\test_full_pipeline.py"
type: "rationale"
community: "C: Users"
location: "L499"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 验证 Evidence.model_dump() 格式被 IssueExtractor 正确消费，且 evidence_id 字段名保留。 Verif

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
- [[test_evidence_to_issue_data_compat()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users