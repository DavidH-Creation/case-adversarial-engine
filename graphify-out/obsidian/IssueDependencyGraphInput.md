---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\issue_dependency_graph\schemas.py"
type: "code"
community: "C: Users"
location: "L44"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# IssueDependencyGraphInput

## Connections
- [[A → B → C 拓扑顺序 C 在 B 前，B 在 A 前。]] - `uses` [INFERRED]
- [[Add case_id and owner_party_id to claim dicts.]] - `uses` [INFERRED]
- [[Add case_id and owner_party_id to defense dicts.]] - `uses` [INFERRED]
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[Build EvidenceGapDescriptor list for P1.7 from two sources 1. Rule-based]] - `uses` [INFERRED]
- [[Convert YAML financials section to AmountCalculatorInput. Returns None if no fin]] - `uses` [INFERRED]
- [[Convert YAML material dicts to RawMaterial objects.]] - `uses` [INFERRED]
- [[DFS 查找一条包含 node_id 的环路。]] - `uses` [INFERRED]
- [[Derive evidence gap indicators from pretrial cross-examination results. U]] - `uses` [INFERRED]
- [[IssueDependencyGraphGenerator]] - `uses` [INFERRED]
- [[IssueDependencyGraphGenerator — 争点依赖图构建器（P2）。 Issue Dependency Graph Generator]] - `uses` [INFERRED]
- [[IssueDependencyGraphGenerator 单元测试。 Unit tests for IssueDependencyGraphGenerato]] - `uses` [INFERRED]
- [[IssueDependencyGraphGenerator 单元测试。 Unit tests for IssueDependencyGraphGenerato_1]] - `uses` [INFERRED]
- [[IssueDependencyGraphGenerator 输入 wrapper。 Args case_id 案件 I]] - `rationale_for` [EXTRACTED]
- [[Kahn 算法拓扑排序 + 环路检测。 排序语义：被依赖方（dependency）在前，依赖方（dependent）在后。]] - `uses` [INFERRED]
- [[Load and validate a YAML case file.]] - `uses` [INFERRED]
- [[Load pipeline section from config.yaml at project root. Returns {} if missing.]] - `uses` [INFERRED]
- [[Return True if step was already completed according to checkpoint.]] - `uses` [INFERRED]
- [[Run 3-round adversarial debate.]] - `uses` [INFERRED]
- [[Run post-debate analysis pipeline. Returns dict of all artifacts.]] - `uses` [INFERRED]
- [[TestCycleDetection]] - `uses` [INFERRED]
- [[TestDAG]] - `uses` [INFERRED]
- [[TestEdgeDirection]] - `uses` [INFERRED]
- [[TestEmptyInput_2]] - `uses` [INFERRED]
- [[TestInvalidReferenceFiltering]] - `uses` [INFERRED]
- [[TestIssueDependencyEdge]] - `uses` [INFERRED]
- [[TestIssueDependencyGraph]] - `uses` [INFERRED]
- [[TestIssueDependencyGraphInput]] - `uses` [INFERRED]
- [[TestIssueDependencyNode]] - `uses` [INFERRED]
- [[TestLinearChain]] - `uses` [INFERRED]
- [[TestMetadata_1]] - `uses` [INFERRED]
- [[TestNoDependencies]] - `uses` [INFERRED]
- [[depends_on 中引用不存在的 issue_id 被过滤。]] - `uses` [INFERRED]
- [[depends_on 中引用不存在的 issue_id 被过滤，不产生边。]] - `uses` [INFERRED]
- [[issue_dependency_graph schemas 单元测试。 Unit tests for issue_dependency_graph sche]] - `uses` [INFERRED]
- [[metadata 包含 issue_count 和 edge_count。]] - `uses` [INFERRED]
- [[schemas.py]] - `contains` [EXTRACTED]
- [[三节点环路 A → B → C → A。]] - `uses` [INFERRED]
- [[争点依赖图构建器。 纯规则层，不持有外部状态，可安全复用同一实例。 使用方式 Usage generator]] - `uses` [INFERRED]
- [[从环路节点集合中提取具体环路（DFS）。 简化实现：对每个未访问的环路节点做 DFS 找最短环， 用于 warning]] - `uses` [INFERRED]
- [[创建测试用 Issue（通过 model_copy 注入 depends_on 字段）。]] - `uses` [INFERRED]
- [[创建测试用 Issue（通过 object.__setattr__ 注入 depends_on 字段）。]] - `uses` [INFERRED]
- [[图产物包含 created_at 时间戳。]] - `uses` [INFERRED]
- [[构建争点依赖图。 Args inp 包含案件 ID 和争点列表的输入 Returns]] - `uses` [INFERRED]
- [[环路节点不出现在 topological_order。]] - `uses` [INFERRED]
- [[简单环路 A depends_on B, B depends_on A。]] - `uses` [INFERRED]
- [[线性链 A → B → C（A depends_on B, B depends_on C）。 拓扑顺序应为 C, B, A（被依赖方先出现）。]] - `uses` [INFERRED]
- [[菱形 D depends_on B,C; B,C depends_on A。]] - `uses` [INFERRED]
- [[菱形 DAG D depends_on B,C; B depends_on A; C depends_on A。 拓扑顺序中 A 必须在 B、C]] - `uses` [INFERRED]
- [[边的 from to 方向正确（from=依赖方，to=被依赖方）。]] - `uses` [INFERRED]
- [[部分有效、部分无效的 depends_on，只保留有效引用。]] - `uses` [INFERRED]
- [[部分节点成环，其余正常节点仍在拓扑排序中。]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users