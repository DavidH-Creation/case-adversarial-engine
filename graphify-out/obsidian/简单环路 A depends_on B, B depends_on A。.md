---
source_file: "C:\Users\david\dev\case-adversarial-engine\tests\test_issue_dependency_graph.py"
type: "rationale"
community: "C: Users"
location: "L143"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 简单环路 A depends_on B, B depends_on A。

## Connections
- [[IssueDependencyGraph]] - `uses` [INFERRED]
- [[IssueDependencyGraphGenerator]] - `uses` [INFERRED]
- [[IssueDependencyGraphInput]] - `uses` [INFERRED]
- [[test_simple_cycle_detected()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users