---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\adversarial\schemas.py"
type: "code"
community: "C: Users"
location: "L83"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# ConflictEntry

## Connections
- [[AdversarialSummarizer 路径始终提供非空 overall_assessment（fallback 保证）。 Adversa]] - `uses` [INFERRED]
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[EvidenceManagerAgent]] - `uses` [INFERRED]
- [[EvidenceManagerAgent — 整理双方证据清单，标记冲突。 EvidenceManagerAgent — organizes evidence]] - `uses` [INFERRED]
- [[FailingMockLLM]] - `uses` [INFERRED]
- [[MockLLM]] - `uses` [INFERRED]
- [[RoundEngine]] - `uses` [INFERRED]
- [[RoundEngine — 三轮对抗辩论编排器。 RoundEngine — three-round adversarial debate orchestra]] - `uses` [INFERRED]
- [[Summarizer 只调用一次 LLM。]] - `uses` [INFERRED]
- [[TestAdversarialSummarizer]] - `uses` [INFERRED]
- [[TestAdversarialSummarySchema]] - `uses` [INFERRED]
- [[defendant_strongest_defenses 非空。]] - `uses` [INFERRED]
- [[engines report_generation executive_summarizer tests test_summarizer.py Execu]] - `uses` [INFERRED]
- [[evidence_ids 为必填非空列表。]] - `uses` [INFERRED]
- [[missing_evidence_report 非空。]] - `uses` [INFERRED]
- [[overall_assessment 传入字符串仍然有效（向后兼容）。]] - `uses` [INFERRED]
- [[overall_assessment 在 v1.2 改为 Optional，可以为 None（DecisionPathTree 存在时）。]] - `uses` [INFERRED]
- [[plaintiff_strongest_arguments 非空。]] - `uses` [INFERRED]
- [[schemas.py]] - `contains` [EXTRACTED]
- [[三轮对抗辩论编排器。Three-round adversarial debate orchestrator. Args llm]] - `uses` [INFERRED]
- [[从 AgentOutput 中提取为 Argument 列表（取引用证据最多的输出）。 Extract best arguments from]] - `uses` [INFERRED]
- [[分析各争点上哪方缺乏证据支撑。 Analyze which party lacks evidence for each issue.]] - `uses` [INFERRED]
- [[双方证据冲突条目。Evidence conflict between parties.]] - `rationale_for` [EXTRACTED]
- [[合法的 AdversarialSummary 可以正常创建。]] - `uses` [INFERRED]
- [[所有 StrongestArgument.evidence_ids 非空。]] - `uses` [INFERRED]
- [[执行完整的三轮对抗模拟。 Execute the complete three-round adversarial simulation.]] - `uses` [INFERRED]
- [[执行证据分析，返回 (AgentOutput, 冲突列表)。 Execute evidence analysis, return (Agent]] - `uses` [INFERRED]
- [[最小化 AdversarialResult，包含所有三轮输出。]] - `uses` [INFERRED]
- [[每条 UnresolvedIssueDetail 含非空 why_unresolved。]] - `uses` [INFERRED]
- [[计算仍未解决的争点（有冲突的争点视为未解决）。 Compute unresolved issues (issues with conflict]] - `uses` [INFERRED]
- [[证据管理代理 — 整理双方证据，标记冲突项。 Evidence manager agent — organizes party evidence an]] - `uses` [INFERRED]
- [[超重试次数后抛出 RuntimeError。]] - `uses` [INFERRED]
- [[返回类型为 AdversarialSummary。]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users