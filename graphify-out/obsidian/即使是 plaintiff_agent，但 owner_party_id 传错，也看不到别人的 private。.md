---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\shared\tests\test_access_controller.py"
type: "rationale"
community: "C: Users"
location: "L272"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 即使是 plaintiff_agent，但 owner_party_id 传错，也看不到别人的 private。

## Connections
- [[.test_party_agent_cannot_see_own_private_with_wrong_owner_party_id()]] - `rationale_for` [EXTRACTED]
- [[AccessController]] - `uses` [INFERRED]
- [[AccessViolationError]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users