---
source_file: "C:\Users\david\dev\case-adversarial-engine\tests\acceptance\test_pipeline_structural.py"
type: "rationale"
community: "C: Users"
location: "L215"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# Each engine must instantiate without error for all 3 case types.

## Connections
- [[EvidenceIndexer]] - `uses` [INFERRED]
- [[IssueExtractor]] - `uses` [INFERRED]
- [[IssueImpactRanker]] - `uses` [INFERRED]
- [[TestEngineConstructorSmoke]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users