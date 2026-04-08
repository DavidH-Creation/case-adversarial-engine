---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\interactive_followup\tests\test_responder.py"
type: "rationale"
community: "C: Users"
location: "L405"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# LLM 所有重试均失败应抛出 RuntimeError。 Exhausted retries should raise RuntimeError.

## Connections
- [[FollowupResponder]] - `uses` [INFERRED]
- [[TurnValidationError]] - `uses` [INFERRED]
- [[ValidationReport]] - `uses` [INFERRED]
- [[test_llm_retry_exhausted_raises_runtime_error()_1]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users