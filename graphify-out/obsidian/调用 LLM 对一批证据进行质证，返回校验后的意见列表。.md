---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\pretrial_conference\cross_examination_engine.py"
type: "rationale"
community: "C: Users"
location: "L166"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 调用 LLM 对一批证据进行质证，返回校验后的意见列表。

## Connections
- [[._examine_batch()]] - `rationale_for` [EXTRACTED]
- [[CrossExaminationDimension]] - `uses` [INFERRED]
- [[CrossExaminationFocusItem]] - `uses` [INFERRED]
- [[CrossExaminationOpinion]] - `uses` [INFERRED]
- [[CrossExaminationRecord]] - `uses` [INFERRED]
- [[CrossExaminationResult]] - `uses` [INFERRED]
- [[CrossExaminationVerdict]] - `uses` [INFERRED]
- [[EvidenceStateMachine]] - `uses` [INFERRED]
- [[LLMCrossExaminationOutput]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users