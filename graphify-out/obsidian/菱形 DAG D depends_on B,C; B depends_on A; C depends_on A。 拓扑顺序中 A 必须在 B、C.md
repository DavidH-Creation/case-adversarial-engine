---
source_file: "C:\Users\david\dev\case-adversarial-engine\tests\test_issue_dependency_graph.py"
type: "rationale"
community: "C: Users"
location: "L104"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 菱形 DAG D depends_on B,C; B depends_on A; C depends_on A。 拓扑顺序中 A 必须在 B、C

## Connections
- [[IssueDependencyGraph]] - `uses` [INFERRED]
- [[IssueDependencyGraphGenerator]] - `uses` [INFERRED]
- [[IssueDependencyGraphInput]] - `uses` [INFERRED]
- [[test_dag_diamond()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users