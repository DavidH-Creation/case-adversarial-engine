---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\interactive_followup\tests\test_responder.py"
type: "rationale"
community: "C: Users"
location: "L328"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 多轮追问时，previous_turns 应传入 LLM 的 user prompt。 For multi-turn, previous_turns

## Connections
- [[FollowupResponder]] - `uses` [INFERRED]
- [[TurnValidationError]] - `uses` [INFERRED]
- [[ValidationReport]] - `uses` [INFERRED]
- [[test_multi_turn_includes_previous_turns_in_prompt()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users