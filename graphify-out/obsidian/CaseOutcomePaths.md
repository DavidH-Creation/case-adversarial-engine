---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\report_generation\schemas.py"
type: "code"
community: "C: Users"
location: "L163"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# CaseOutcomePaths

## Connections
- [[3 个来源产物均完整 → CaseOutcomePaths 4 条路径全部填充。]] - `uses` [INFERRED]
- [[Aggregate source artifacts into CaseOutcomePaths. Args decision]] - `uses` [INFERRED]
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[Build LOSE path from defendant-favored DecisionPath entries.]] - `uses` [INFERRED]
- [[Build MEDIATION path from MediationRange dataclass.]] - `uses` [INFERRED]
- [[Build SUPPLEMENT path from top-3 EvidenceGapItem entries.]] - `uses` [INFERRED]
- [[Build WIN path from plaintiff-favored DecisionPath entries.]] - `uses` [INFERRED]
- [[CaseOutcomePaths 可序列化为 JSON。]] - `uses` [INFERRED]
- [[Get attribute as string; returns empty string if missing or None.]] - `uses` [INFERRED]
- [[Get attribute or dict key; returns None if missing.]] - `uses` [INFERRED]
- [[IssueDependencyGraphGenerator — 争点依赖图构建器（P2）。 Issue Dependency Graph Generator]] - `uses` [INFERRED]
- [[LOSE path 的 trigger_conditions 包含 defendant-favored 路径的触发条件。]] - `uses` [INFERRED]
- [[MEDIATION path 包含调解区间 key_actions。]] - `uses` [INFERRED]
- [[MEDIATION path 的 trigger_conditions 来自 MediationRange.rationale。]] - `uses` [INFERRED]
- [[Render CaseOutcomePaths as Markdown lines for report output. Args]] - `uses` [INFERRED]
- [[ReportGenerator]] - `uses` [INFERRED]
- [[SUPPLEMENT path 包含 top3 gap 的 key_actions（按 roi_rank 排序）。]] - `uses` [INFERRED]
- [[SUPPLEMENT path 的 required_evidence_ids 包含 top3 gap_id。]] - `uses` [INFERRED]
- [[TestBuildCaseOutcomePathsHappy]] - `uses` [INFERRED]
- [[TestBuildCaseOutcomePathsMissingSources]] - `uses` [INFERRED]
- [[TestIntegrationJsonSerialization]] - `uses` [INFERRED]
- [[TestIntegrationMarkdownRendering]] - `uses` [INFERRED]
- [[TestInternalBuilders]] - `uses` [INFERRED]
- [[TestSupplementPathRanking]] - `uses` [INFERRED]
- [[TestVerdictBlockActive_1]] - `uses` [INFERRED]
- [[WIN path 的 required_evidence_ids 来自 plaintiff 路径的 key_evidence_ids。]] - `uses` [INFERRED]
- [[WIN path 的 trigger_conditions 包含 plaintiff-favored 路径的触发条件。]] - `uses` [INFERRED]
- [[decision_tree=None → LOSE trigger_conditions= insufficient_data 。]] - `uses` [INFERRED]
- [[decision_tree=None → MEDIATION 和 SUPPLEMENT 路径不受影响。]] - `uses` [INFERRED]
- [[decision_tree=None → WIN trigger_conditions= insufficient_data 。]] - `uses` [INFERRED]
- [[gap_result 有对象但 ranked_items 为空 → key_actions=，不抛错。]] - `uses` [INFERRED]
- [[gap_result=None → SUPPLEMENT trigger_conditions= insufficient_data 。]] - `uses` [INFERRED]
- [[mediation_range=None → MEDIATION trigger_conditions= insufficient_data 。]] - `uses` [INFERRED]
- [[mediation_range=None → WIN LOSE SUPPLEMENT 路径不受影响。]] - `uses` [INFERRED]
- [[model_dump() 返回包含 4 条路径的字典。]] - `uses` [INFERRED]
- [[outcome_paths 单元测试。 Tests for engines.report_generation.outcome_paths module.]] - `uses` [INFERRED]
- [[ranked_items 按 roi_rank 升序取前 3。]] - `uses` [INFERRED]
- [[render_outcome_paths_md_lines 包含 trigger_conditions 内容。]] - `uses` [INFERRED]
- [[render_outcome_paths_md_lines 输出包含 4 条路径标签。]] - `uses` [INFERRED]
- [[render_outcome_paths_md_lines 返回字符串列表。]] - `uses` [INFERRED]
- [[schemas.py]] - `contains` [EXTRACTED]
- [[source_artifact 字段均有值。]] - `uses` [INFERRED]
- [[verdict_block_active=False is now a compatibility no-op for risk_points.]] - `uses` [INFERRED]
- [[verdict_block_active=True → LOSE risk_points 为空。]] - `uses` [INFERRED]
- [[verdict_block_active=True → WIN risk_points 为空。]] - `uses` [INFERRED]
- [[加载案由对应的 prompt 模板模块。 Load prompt template module for the given case typ_2]] - `uses` [INFERRED]
- [[只有 1 条缺证项 → key_actions 只有 1 条。]] - `uses` [INFERRED]
- [[四路径结构化输出聚合。 Aggregated 4-path outcome structure for a case.]] - `rationale_for` [EXTRACTED]
- [[多条 plaintiff 路径共享 evidence_id 时去重。]] - `uses` [INFERRED]
- [[对 ReportArtifact 的所有面向用户的文本字段执行 PII 脱敏。 Redact PII from all user-facing t]] - `uses` [INFERRED]
- [[将 LLM 输出规范化为 ReportArtifact。 Normalize LLM output into a ReportArtifact]] - `uses` [INFERRED]
- [[将 LLM 返回的 statement_class 字符串解析为枚举值。 Resolve raw statement_class string to_1]] - `uses` [INFERRED]
- [[将文书草稿附加为 ReportArtifact 的额外章节。 Append document drafts as extra sections to]] - `uses` [INFERRED]
- [[当路径为 insufficient_data 时，渲染结果中可见该标记。]] - `uses` [INFERRED]
- [[所有来源均 None → 4 条路径均为 insufficient_data。]] - `uses` [INFERRED]
- [[执行报告生成。 Execute report generation. Args issue_]] - `uses` [INFERRED]
- [[报告生成器 Report Generator. 输入 IssueTree + EvidenceIndex，输出结构化 ReportArt]] - `uses` [INFERRED]
- [[无 defendant 路径 → LOSE trigger_conditions= insufficient_data 。]] - `uses` [INFERRED]
- [[无 plaintiff 路径 → WIN trigger_conditions= insufficient_data 。]] - `uses` [INFERRED]
- [[构建矩阵并作为额外章节附加到报告。 Build the matrix and attach it as an extra section to]] - `uses` [INFERRED]
- [[结构化输出路径聚合 — 从三个来源产物构建 CaseOutcomePaths。 Outcome path aggregator — builds CaseOu]] - `uses` [INFERRED]
- [[调用 LLM（结构化输出）。 Call LLM with structured output. Raises_1]] - `uses` [INFERRED]
- [[验证输入数据合法性。 Validate input data validity. Raises_3]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users