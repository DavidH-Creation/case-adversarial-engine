---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\adversarial\schemas.py"
type: "code"
community: "C: Users"
location: "L140"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# AdversarialSummary

## Connections
- [[5个 AgentOutput 应通过 WorkspaceManager 持久化到 artifact_index。]] - `uses` [INFERRED]
- [[6 条响应：原告主张、被告主张、证据整理、原告反驳、被告反驳、总结。]] - `uses` [INFERRED]
- [[6次 LLM 调用：R1原告 + R1被告 + R2证据管理 + R3原告 + R3被告 + Summarizer。]] - `uses` [INFERRED]
- [[AccessController 隔离：原告代理看不到被告 owner_private 证据。]] - `uses` [INFERRED]
- [[AccessController 隔离：被告代理看不到原告 owner_private 证据。]] - `uses` [INFERRED]
- [[AdversarialSummarizer]] - `uses` [INFERRED]
- [[AdversarialSummarizer 路径始终提供非空 overall_assessment（fallback 保证）。 Adversa]] - `uses` [INFERRED]
- [[AdversarialSummary 必须包含所有 5 个必要字段且非空。]] - `uses` [INFERRED]
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[ExecutiveSummarizer — 一页式执行摘要生成引擎（P2.12）。 Executive Summarizer — rule-based exe]] - `uses` [INFERRED]
- [[FailingMockLLM]] - `uses` [INFERRED]
- [[MockLLM]] - `uses` [INFERRED]
- [[RoundEngine 必须产出恰好 3 个 RoundState（claim, evidence, rebuttal）。]] - `uses` [INFERRED]
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
- [[_SingleResponseMock]] - `uses` [INFERRED]
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
- [[三轮对抗 LLM 语义分析总结产物。 LLM semantic summary of three-round adversarial debate.]] - `rationale_for` [EXTRACTED]
- [[三轮对抗 LLM 语义分析总结器。 LLM-powered semantic summarizer for three-round adversari]] - `uses` [INFERRED]
- [[不传 config 时使用默认 RoundConfig。]] - `uses` [INFERRED]
- [[不传 workspace_manager 和 job_manager 时仍正常运行（向后兼容）。]] - `uses` [INFERRED]
- [[全链路：EvidenceIndexer → IssueExtractor → RoundEngine，验证 AccessController 隔离。]] - `uses` [INFERRED]
- [[分析三轮对抗结果，输出结构化总结。 Analyze three-round adversarial result and produce st]] - `uses` [INFERRED]
- [[合法的 AdversarialSummary 可以正常创建。]] - `uses` [INFERRED]
- [[场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.]] - `uses` [INFERRED]
- [[完整对抗流程 happy path：EvidenceIndex → RoundEngine → AdversarialResult（含 summary）。]] - `uses` [INFERRED]
- [[将 LLM JSON 输出解析为 AdversarialSummary。 Parse LLM JSON output dict to Adve]] - `uses` [INFERRED]
- [[所有 StrongestArgument.evidence_ids 非空。]] - `uses` [INFERRED]
- [[按顺序返回不同响应的 mock LLM（模拟真实对话轮次）。 6 次调用： 1. 原告首轮主张 2. 被告首轮抗辩]] - `uses` [INFERRED]
- [[最小化 AdversarialResult，包含所有三轮输出。]] - `uses` [INFERRED]
- [[构建用户提示词，包含辩论全貌上下文。 Build user prompt containing full debate context.]] - `uses` [INFERRED]
- [[构造 AdversarialSummarizer 的 LLM mock 响应。]] - `uses` [INFERRED]
- [[构造 EvidenceManagerAgent 的 LLM mock 响应。]] - `uses` [INFERRED]
- [[构造 party agent 的 LLM mock 响应。]] - `uses` [INFERRED]
- [[构造含三类访问域证据的 EvidenceIndex：shared、原告私有、被告私有。]] - `uses` [INFERRED]
- [[每条 UnresolvedIssueDetail 含非空 why_unresolved。]] - `uses` [INFERRED]
- [[生成核心策略摘要（strategic_summary 字段）。 仅当 ActionRecommendation 包含 strategic_]] - `uses` [INFERRED]
- [[端到端对抗流程集成测试 — mock LLM 驱动完整三轮对抗。 End-to-end adversarial pipeline integration te]] - `uses` [INFERRED]
- [[被告私有证据 ev-002 不应出现在原告视角的 LLM 调用中。]] - `uses` [INFERRED]
- [[超重试次数后抛出 RuntimeError。]] - `uses` [INFERRED]
- [[返回类型为 AdversarialSummary。]] - `uses` [INFERRED]
- [[验证 Round 3 原被告 rebuttal 使用 asyncio.gather 并行执行。]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users