---
source_file: "C:\Users\david\dev\case-adversarial-engine\tests\integration\test_full_pipeline.py"
type: "rationale"
community: "C: Users"
location: "L547"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 验证从 list[Evidence] 手动构建 EvidenceIndex 后，ReportGenerator 零悬空引用。 Verifies zer

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
- [[test_evidence_index_construction()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users