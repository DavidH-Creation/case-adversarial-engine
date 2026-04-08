---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\pretrial_conference\conference_engine.py"
type: "rationale"
community: "C: Users"
location: "L42"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 庭前会议编排器。 Args llm_client 符合 LLMClient 协议的客户端实例 model

## Connections
- [[CrossExaminationEngine]] - `uses` [INFERRED]
- [[CrossExaminationResult]] - `uses` [INFERRED]
- [[EvidenceStateMachine]] - `uses` [INFERRED]
- [[JudgeAgent]] - `uses` [INFERRED]
- [[JudgeQuestionSet]] - `uses` [INFERRED]
- [[PretrialConferenceEngine]] - `rationale_for` [EXTRACTED]
- [[PretrialConferenceResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users