---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\tests\test_unit15_endpoints.py"
type: "rationale"
community: "C: Users"
location: "L295"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# A job belonging to case A should not be accessible via case B.

## Connections
- [[.test_404_for_job_on_wrong_case()]] - `rationale_for` [EXTRACTED]
- [[CaseStatus]] - `uses` [INFERRED]
- [[FollowupStatus]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users