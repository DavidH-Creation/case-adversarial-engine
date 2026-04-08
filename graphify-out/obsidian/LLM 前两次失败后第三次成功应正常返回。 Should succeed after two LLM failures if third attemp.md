---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\interactive_followup\tests\test_responder.py"
type: "rationale"
community: "C: Users"
location: "L387"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# LLM 前两次失败后第三次成功应正常返回。 Should succeed after two LLM failures if third attemp

## Connections
- [[FollowupResponder]] - `uses` [INFERRED]
- [[TurnValidationError]] - `uses` [INFERRED]
- [[ValidationReport]] - `uses` [INFERRED]
- [[test_llm_retry_succeeds_after_failures()_1]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users