---
source_file: "C:\Users\david\dev\case-adversarial-engine\tests\test_issue_dependency_graph.py"
type: "rationale"
community: "C: Users"
location: "L88"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 线性链 A → B → C（A depends_on B, B depends_on C）。 拓扑顺序应为 [C, B, A]（被依赖方先出现）。

## Connections
- [[IssueDependencyGraph]] - `uses` [INFERRED]
- [[IssueDependencyGraphGenerator]] - `uses` [INFERRED]
- [[IssueDependencyGraphInput]] - `uses` [INFERRED]
- [[test_linear_chain_topo_order()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users