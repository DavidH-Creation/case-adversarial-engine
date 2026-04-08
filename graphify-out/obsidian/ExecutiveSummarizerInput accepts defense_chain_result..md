---
source_file: "C:\Users\david\dev\case-adversarial-engine\tests\integration\test_data_flow.py"
type: "rationale"
community: "C: Users"
location: "L343"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# ExecutiveSummarizerInput accepts defense_chain_result.

## Connections
- [[.test_exec_summarizer_receives_defense_chain()]] - `rationale_for` [EXTRACTED]
- [[ActionRecommenderInput]] - `uses` [INFERRED]
- [[CrossExaminationDimension]] - `uses` [INFERRED]
- [[CrossExaminationFocusItem]] - `uses` [INFERRED]
- [[CrossExaminationResult]] - `uses` [INFERRED]
- [[DefenseChainResult]] - `uses` [INFERRED]
- [[DefensePoint]] - `uses` [INFERRED]
- [[ExecutiveSummarizerInput]] - `uses` [INFERRED]
- [[JudgeQuestionSet]] - `uses` [INFERRED]
- [[PlaintiffDefenseChain]] - `uses` [INFERRED]
- [[PretrialConferenceResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users