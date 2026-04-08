---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\interactive_followup\tests\test_responder.py"
type: "rationale"
community: "C: Users"
location: "L652"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# respond_safe() 对无效输入（空问题）仍应抛出 ValueError。 respond_safe() should still raise

## Connections
- [[FollowupResponder]] - `uses` [INFERRED]
- [[TurnValidationError]] - `uses` [INFERRED]
- [[ValidationReport]] - `uses` [INFERRED]
- [[test_respond_safe_still_raises_on_invalid_input()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users