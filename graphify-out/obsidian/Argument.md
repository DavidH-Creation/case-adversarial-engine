---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\adversarial\schemas.py"
type: "code"
community: "C: Users"
location: "L49"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# Argument

## Connections
- [[5个 AgentOutput 应通过 WorkspaceManager 持久化到 artifact_index。]] - `uses` [INFERRED]
- [[6次 LLM 调用：R1原告 + R1被告 + R2证据管理 + R3原告 + R3被告 + Summarizer。]] - `uses` [INFERRED]
- [[AdversarialSummarizer 路径始终提供非空 overall_assessment（fallback 保证）。 Adversa]] - `uses` [INFERRED]
- [[AgentOutputValidationError]] - `uses` [INFERRED]
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[BasePartyAgent]] - `uses` [INFERRED]
- [[BasePartyAgent — 共享 LLM 调用逻辑的基类。 BasePartyAgent — base class with shared LLM ca]] - `uses` [INFERRED]
- [[FailingMockLLM]] - `uses` [INFERRED]
- [[MockLLM]] - `uses` [INFERRED]
- [[RoundEngine]] - `uses` [INFERRED]
- [[RoundEngine — 三轮对抗辩论编排器。 RoundEngine — three-round adversarial debate orchestra]] - `uses` [INFERRED]
- [[RoundEngine 集成测试 — 使用 mock LLMClient 验证三轮编排逻辑。 RoundEngine integration tests —]] - `uses` [INFERRED]
- [[RoundEngine.run() 后 result.summary 类型为 AdversarialSummary（非 None）。]] - `uses` [INFERRED]
- [[SequentialMockLLM]] - `uses` [INFERRED]
- [[Summarizer 只调用一次 LLM。]] - `uses` [INFERRED]
- [[TestAdversarialSummarizer]] - `uses` [INFERRED]
- [[TestAdversarialSummarySchema]] - `uses` [INFERRED]
- [[TestRound3Parallelism]] - `uses` [INFERRED]
- [[TestRoundEngine]] - `uses` [INFERRED]
- [[TestRoundEngineWithInfrastructure]] - `uses` [INFERRED]
- [[TestSchemas]] - `uses` [INFERRED]
- [[citation 或争点验证失败，触发 _call_and_parse 重试。 Raised when LLM output fails citati]] - `uses` [INFERRED]
- [[defendant_strongest_defenses 非空。]] - `uses` [INFERRED]
- [[engines report_generation executive_summarizer tests test_summarizer.py Execu]] - `uses` [INFERRED]
- [[evidence_ids 为必填非空列表。]] - `uses` [INFERRED]
- [[job_manager 提供时，job 应完成 created→running→completed 生命周期。]] - `uses` [INFERRED]
- [[missing_evidence_report 非空。]] - `uses` [INFERRED]
- [[overall_assessment 传入字符串仍然有效（向后兼容）。]] - `uses` [INFERRED]
- [[overall_assessment 在 v1.2 改为 Optional，可以为 None（DecisionPathTree 存在时）。]] - `uses` [INFERRED]
- [[p_rebuttal 和 d_rebuttal 的开始时间差应 单次调用耗时（并行标志）。]] - `uses` [INFERRED]
- [[plaintiff_strongest_arguments 非空。]] - `uses` [INFERRED]
- [[result.summary.overall_assessment 非空。]] - `uses` [INFERRED]
- [[schemas.py]] - `contains` [EXTRACTED]
- [[三轮对抗辩论编排器。Three-round adversarial debate orchestrator. Args llm]] - `uses` [INFERRED]
- [[不传 config 时使用默认 RoundConfig。]] - `uses` [INFERRED]
- [[不传 workspace_manager 和 job_manager 时仍正常运行（向后兼容）。]] - `uses` [INFERRED]
- [[从 AgentOutput 中提取为 Argument 列表（取引用证据最多的输出）。 Extract best arguments from]] - `uses` [INFERRED]
- [[分析各争点上哪方缺乏证据支撑。 Analyze which party lacks evidence for each issue.]] - `uses` [INFERRED]
- [[单条法律论点，必须绑定争点和证据。 Single legal argument, must bind to an issue and cite evi]] - `rationale_for` [EXTRACTED]
- [[合法的 AdversarialSummary 可以正常创建。]] - `uses` [INFERRED]
- [[将 IssueTree 格式化为 prompt 可读摘要。 Format IssueTree as a prompt-readable sum]] - `uses` [INFERRED]
- [[将 LLM JSON 输出解析为 AgentOutput。 Parse LLM JSON output dict to AgentOutput]] - `uses` [INFERRED]
- [[将历史 AgentOutput 格式化为 prompt 上下文。 Format prior AgentOutputs as prompt co]] - `uses` [INFERRED]
- [[将证据列表格式化为 prompt 可读摘要。 Format evidence list as prompt-readable summary.]] - `uses` [INFERRED]
- [[所有 StrongestArgument.evidence_ids 非空。]] - `uses` [INFERRED]
- [[所有当事方代理的基类，封装 LLM 调用和重试逻辑。 Base class for all party agents, encapsulating L]] - `uses` [INFERRED]
- [[执行完整的三轮对抗模拟。 Execute the complete three-round adversarial simulation.]] - `uses` [INFERRED]
- [[按顺序返回不同响应的 mock LLM（模拟真实对话轮次）。 6 次调用： 1. 原告首轮主张 2. 被告首轮抗辩]] - `uses` [INFERRED]
- [[最小化 AdversarialResult，包含所有三轮输出。]] - `uses` [INFERRED]
- [[每条 UnresolvedIssueDetail 含非空 why_unresolved。]] - `uses` [INFERRED]
- [[生成反驳轮输出。Generate rebuttal round output.]] - `uses` [INFERRED]
- [[生成首轮主张。Generate round-1 claim.]] - `uses` [INFERRED]
- [[被告私有证据 ev-002 不应出现在原告视角的 LLM 调用中。]] - `uses` [INFERRED]
- [[计算仍未解决的争点（有冲突的争点视为未解决）。 Compute unresolved issues (issues with conflict]] - `uses` [INFERRED]
- [[调用 LLM（带重试）并验证输出为合法 AgentOutput。 Call LLM with unified retry loop and v]] - `uses` [INFERRED]
- [[超重试次数后抛出 RuntimeError。]] - `uses` [INFERRED]
- [[返回 LLM 输出的 JSON schema 说明（防退化用）。 Return JSON schema description for LLM]] - `uses` [INFERRED]
- [[返回类型为 AdversarialSummary。]] - `uses` [INFERRED]
- [[验证 Round 3 原被告 rebuttal 使用 asyncio.gather 并行执行。]] - `uses` [INFERRED]
- [[验证所有引用的证据 ID 必须存在于可见证据中（防幻觉）。 Validate all cited evidence IDs exist in]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users