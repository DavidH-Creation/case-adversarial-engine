---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\auth.py"
type: "rationale"
community: "C: Users"
location: "L51"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# Return a UserStore if USERS_FILE is configured, else None.

## Connections
- [[User]] - `uses` [INFERRED]
- [[UserRole]] - `uses` [INFERRED]
- [[UserStore]] - `uses` [INFERRED]
- [[_get_user_store()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users