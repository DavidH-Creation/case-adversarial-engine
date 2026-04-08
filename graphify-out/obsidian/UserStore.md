---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\users.py"
type: "code"
community: "C: Users"
location: "L36"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# UserStore

## Connections
- [[.__init__()_7]] - `method` [EXTRACTED]
- [[._load()]] - `method` [EXTRACTED]
- [[.get_by_email()]] - `method` [EXTRACTED]
- [[.get_by_id()]] - `method` [EXTRACTED]
- [[.list_all()]] - `method` [EXTRACTED]
- [[API_SECRET_KEY set but no USERS_FILE → static Bearer still works.]] - `uses` [INFERRED]
- [[Issue a JWT for an authenticated user.]] - `uses` [INFERRED]
- [[JWT authentication with backward-compatible static Bearer fallback. Auth mode]] - `uses` [INFERRED]
- [[Load users from a JSON file into memory. File path comes from USERS_FILE]] - `rationale_for` [EXTRACTED]
- [[Resolve the current user from the Authorization header. Three modes]] - `uses` [INFERRED]
- [[Return a UserStore if USERS_FILE is configured, else None.]] - `uses` [INFERRED]
- [[TDD tests for Phase 4 JWT authentication + RBAC permission matrix. All tests w]] - `uses` [INFERRED]
- [[TokenRequest]] - `uses` [INFERRED]
- [[TokenResponse]] - `uses` [INFERRED]
- [[UserContext]] - `uses` [INFERRED]
- [[Validate credentials and return the User, or raise 401.]] - `uses` [INFERRED]
- [[users.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/C:_Users