---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\shared\job_manager.py"
type: "code"
community: "C: Users"
location: "L55"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# JobManager

## Connections
- [[.__init__()_53]] - `method` [EXTRACTED]
- [[._atomic_write()]] - `method` [EXTRACTED]
- [[._job_path()]] - `method` [EXTRACTED]
- [[._jobs_dir()]] - `method` [EXTRACTED]
- [[._now()]] - `method` [EXTRACTED]
- [[._transition()]] - `method` [EXTRACTED]
- [[.cancel_job()]] - `method` [EXTRACTED]
- [[.complete_job()]] - `method` [EXTRACTED]
- [[.create_job()]] - `method` [EXTRACTED]
- [[.fail_job()]] - `method` [EXTRACTED]
- [[.list_jobs()]] - `method` [EXTRACTED]
- [[.load_job()]] - `method` [EXTRACTED]
- [[.pend_job()]] - `method` [EXTRACTED]
- [[.start_job()]] - `method` [EXTRACTED]
- [[.update_progress()]] - `method` [EXTRACTED]
- [[5个 AgentOutput 应通过 WorkspaceManager 持久化到 artifact_index。]] - `uses` [INFERRED]
- [[6次 LLM 调用：R1原告 + R1被告 + R2证据管理 + R3原告 + R3被告 + Summarizer。]] - `uses` [INFERRED]
- [[JobManager 单元测试。 JobManager unit tests. 覆盖路径 Coverage 1. create_job 创建并]] - `uses` [INFERRED]
- [[RoundEngine]] - `uses` [INFERRED]
- [[RoundEngine — 三轮对抗辩论编排器。 RoundEngine — three-round adversarial debate orchestra]] - `uses` [INFERRED]
- [[RoundEngine 集成测试 — 使用 mock LLMClient 验证三轮编排逻辑。 RoundEngine integration tests —]] - `uses` [INFERRED]
- [[RoundEngine.run() 后 result.summary 类型为 AdversarialSummary（非 None）。]] - `uses` [INFERRED]
- [[SequentialMockLLM]] - `uses` [INFERRED]
- [[TestCancelJob]] - `uses` [INFERRED]
- [[TestCompleteJob]] - `uses` [INFERRED]
- [[TestCreateAndLoad]] - `uses` [INFERRED]
- [[TestFailJob]] - `uses` [INFERRED]
- [[TestInvalidTransitions]] - `uses` [INFERRED]
- [[TestListJobs]] - `uses` [INFERRED]
- [[TestPendJob]] - `uses` [INFERRED]
- [[TestRecovery]] - `uses` [INFERRED]
- [[TestRound3Parallelism]] - `uses` [INFERRED]
- [[TestRoundEngine]] - `uses` [INFERRED]
- [[TestRoundEngineWithInfrastructure]] - `uses` [INFERRED]
- [[TestSchemas]] - `uses` [INFERRED]
- [[TestStartJob]] - `uses` [INFERRED]
- [[TestUpdateProgress]] - `uses` [INFERRED]
- [[created → completed は合法迁移外，必须先 start。]] - `uses` [INFERRED]
- [[job_manager 提供时，job 应完成 created→running→completed 生命周期。]] - `uses` [INFERRED]
- [[job_manager.py]] - `contains` [EXTRACTED]
- [[p_rebuttal 和 d_rebuttal 的开始时间差应 单次调用耗时（并行标志）。]] - `uses` [INFERRED]
- [[progress 只反映已持久化的里程碑，not in-memory state。]] - `uses` [INFERRED]
- [[result.summary.overall_assessment 非空。]] - `uses` [INFERRED]
- [[三轮对抗辩论编排器。Three-round adversarial debate orchestrator. Args llm]] - `uses` [INFERRED]
- [[不传 config 时使用默认 RoundConfig。]] - `uses` [INFERRED]
- [[不传 workspace_manager 和 job_manager 时仍正常运行（向后兼容）。]] - `uses` [INFERRED]
- [[从 AgentOutput 中提取为 Argument 列表（取引用证据最多的输出）。 Extract best arguments from]] - `uses` [INFERRED]
- [[分析各争点上哪方缺乏证据支撑。 Analyze which party lacks evidence for each issue.]] - `uses` [INFERRED]
- [[场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.]] - `uses` [INFERRED]
- [[完成后的 Job 作为审计记录保留，不能重新打开；重试需创建新 job。]] - `uses` [INFERRED]
- [[执行完整的三轮对抗模拟。 Execute the complete three-round adversarial simulation.]] - `uses` [INFERRED]
- [[按顺序返回不同响应的 mock LLM（模拟真实对话轮次）。 6 次调用： 1. 原告首轮主张 2. 被告首轮抗辩]] - `uses` [INFERRED]
- [[案件工作区内的长任务生命周期管理器。 使用方式 Usage mgr = JobManager(workspace_dir=]] - `rationale_for` [EXTRACTED]
- [[被告私有证据 ev-002 不应出现在原告视角的 LLM 调用中。]] - `uses` [INFERRED]
- [[计算仍未解决的争点（有冲突的争点视为未解决）。 Compute unresolved issues (issues with conflict]] - `uses` [INFERRED]
- [[进程重启后重建 JobManager 可继续 pending 任务。]] - `uses` [INFERRED]
- [[验证 Round 3 原被告 rebuttal 使用 asyncio.gather 并行执行。]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users