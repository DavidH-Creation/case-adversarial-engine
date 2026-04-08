---
source_file: "C:\Users\david\dev\case-adversarial-engine\tests\acceptance\test_pipeline_structural.py"
type: "rationale"
community: "C: Users"
location: "L107"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# Every .yaml in cases must load without YAML syntax errors.

## Connections
- [[.test_all_yaml_files_loadable()]] - `rationale_for` [EXTRACTED]
- [[EvidenceIndexer]] - `uses` [INFERRED]
- [[IssueExtractor]] - `uses` [INFERRED]
- [[IssueImpactRanker]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users