---
source_file: "C:\Users\david\dev\case-adversarial-engine\tests\integration\test_full_pipeline.py"
type: "rationale"
community: "C: Users"
location: "L673"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 验证两轮追问： - 第二轮 previous_turns 正确传入（体现在 LLM user prompt 中） - issue_ids 始

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
- [[test_multi_turn_followup_after_report()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users