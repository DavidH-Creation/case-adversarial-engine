---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\interactive_followup\tests\test_responder.py"
type: "rationale"
community: "C: Users"
location: "L421"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 每次 respond() 应生成唯一的 turn_id。 Each respond() call should generate a unique t

## Connections
- [[FollowupResponder]] - `uses` [INFERRED]
- [[TurnValidationError]] - `uses` [INFERRED]
- [[ValidationReport]] - `uses` [INFERRED]
- [[test_turn_id_is_unique_across_calls()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users