---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\hearing_order\schemas.py"
type: "code"
community: "C: Users"
location: "L87"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# HearingOrderResult

## Connections
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[HearingOrderGenerator]] - `uses` [INFERRED]
- [[HearingOrderGenerator 单元测试。 Unit tests for HearingOrderGenerator. 测试策略： - 纯]] - `uses` [INFERRED]
- [[IssueDependencyGraph]] - `uses` [INFERRED]
- [[IssueDependencyGraphGenerator — 争点依赖图构建器（P2）。 Issue Dependency Graph Generator]] - `uses` [INFERRED]
- [[IssueDependencyGraphGenerator 单元测试。 Unit tests for IssueDependencyGraphGenerato]] - `uses` [INFERRED]
- [[TestCycleNodeHandling]] - `uses` [INFERRED]
- [[TestDurationEstimation]] - `uses` [INFERRED]
- [[TestEmptyInput_2]] - `uses` [INFERRED]
- [[TestHearingOrderInput]] - `uses` [INFERRED]
- [[TestHearingOrderResult]] - `uses` [INFERRED]
- [[TestHearingPhase]] - `uses` [INFERRED]
- [[TestIssueTimeEstimate]] - `uses` [INFERRED]
- [[TestOutputMetadata_1]] - `uses` [INFERRED]
- [[TestPartyPosition]] - `uses` [INFERRED]
- [[TestPhaseClassification]] - `uses` [INFERRED]
- [[TestPlaintiffPriority]] - `uses` [INFERRED]
- [[TestTopologicalOrdering]] - `uses` [INFERRED]
- [[high impact 争点预估 30 分钟。]] - `uses` [INFERRED]
- [[issue_dependency_graph schemas 单元测试。 Unit tests for issue_dependency_graph sche]] - `uses` [INFERRED]
- [[low impact 争点预估 10 分钟。]] - `uses` [INFERRED]
- [[medium impact 争点预估 20 分钟。]] - `uses` [INFERRED]
- [[schemas.py]] - `contains` [EXTRACTED]
- [[total_estimated_duration_minutes == sum of all phases。]] - `uses` [INFERRED]
- [[单个事实争点出现在 factual 阶段。]] - `uses` [INFERRED]
- [[含损害赔偿关键词的争点分到 damages 阶段。]] - `uses` [INFERRED]
- [[场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.]] - `uses` [INFERRED]
- [[将争点分配到庭审阶段。 规则（优先级降序）： 1. procedural 类型 → procedural]] - `uses` [INFERRED]
- [[庭审时长按 outcome_impact 分级估算。]] - `uses` [INFERRED]
- [[庭审顺序建议产物。 合约保证： - issue_presentation_order 包含所有输入争点（无遗漏） - phas]] - `rationale_for` [EXTRACTED]
- [[庭审顺序建议生成器。 纯规则层，不持有外部状态，可安全复用同一实例。 使用方式 Usage generato]] - `uses` [INFERRED]
- [[所有输入争点均出现在 issue_presentation_order 中（无遗漏）。]] - `uses` [INFERRED]
- [[所有输入争点均出现在 issue_presentation_order（无遗漏）。]] - `uses` [INFERRED]
- [[环路节点被追加到对应阶段（不从拓扑排序中丢弃）。]] - `uses` [INFERRED]
- [[环路节点被追加到对应阶段（不从输出中丢弃）。]] - `uses` [INFERRED]
- [[生成庭审顺序建议。 Args inp 包含依赖图、争点列表和当事方立场的输入 Retu]] - `uses` [INFERRED]
- [[程序性 → 事实 → 法律 → 损害赔偿 的完整四阶段顺序。]] - `uses` [INFERRED]
- [[程序性争点在 factual 争点之前（阶段顺序）。]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users