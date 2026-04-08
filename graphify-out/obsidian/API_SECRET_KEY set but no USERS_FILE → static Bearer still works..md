---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\tests\test_auth_jwt.py"
type: "rationale"
community: "C: Users"
location: "L202"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# API_SECRET_KEY set but no USERS_FILE → static Bearer still works.

## Connections
- [[Action]] - `uses` [INFERRED]
- [[UserRole]] - `uses` [INFERRED]
- [[UserStore]] - `uses` [INFERRED]
- [[test_static_bearer_accepted_when_no_users_file()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users