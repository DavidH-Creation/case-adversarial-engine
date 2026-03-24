# 报告引擎合同 (Report Engine Contract)

## 概述
报告引擎负责将争点树（IssueTree）和推演输出（AgentOutput）转化为律师可直接使用的诊断报告（ReportArtifact），确保每个关键结论都可追溯到具体证据和推演输出。

## 输入
| 字段 | 类型 | 说明 |
|------|------|------|
| issue_tree | IssueTree | 争点树，须符合 issue_tree.schema.json |
| agent_outputs | AgentOutput[] | 推演输出列表，须符合 agent_output.schema.json |
| evidence | Evidence[] | 已索引证据列表，须符合 evidence.schema.json |

## 输出
产物为 ReportArtifact 对象，须符合 `report_artifact.schema.json`，包含：
- **sections**: 结构化章节列表，每章节包含正文、关联争点、引用证据、关键结论
- **key_conclusions**: 每个关键结论绑定 `supporting_evidence_ids` 和 `statement_class`
- **summary**: 律师可在 5 分钟内读懂的报告摘要

## 约束规则
1. **引用完整性 (citation_completeness = 100%)**：每个关键结论必须有至少一个 `supporting_evidence_ids`
2. **推演回连**：每个章节必须有 `linked_output_ids` 回连推演输出
3. **陈述分类**：每个结论必须标注 `statement_class`（fact / inference / assumption）
4. **争点覆盖**：报告必须覆盖 IssueTree 中的所有顶层 Issue
5. **可读性**：报告摘要（summary）须在 500 字以内，律师可在 5 分钟内理解核心结论

## 不含
- 交互追问（留给 Task 101 InteractionTurn）
- 场景比较（留给 Task 102 Scenario）
- 报告渲染/格式化（v0.5 报告产物为 JSON 结构，UI 渲染留给后续版本）

## 运行方式
- 通过 Job + Run 管理
- 一个 Run 产生一份主 ReportArtifact
- Job.result_ref 指向产出的 ReportArtifact

## 验收标准
- `citation_completeness = 100%`（关键结论 → 证据引用无遗漏）
- 报告覆盖 IssueTree 中 100% 的顶层争点
- 零悬空引用（所有 evidence_id、output_id、issue_id 可解析）
- 报告摘要长度 ≤ 500 字