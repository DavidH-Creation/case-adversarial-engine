---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\pretrial_conference\schemas.py"
type: "code"
community: "C: Users"
location: "L123"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# JudgeQuestionSet

## Connections
- [[ActionRecommenderInput accepts decision_path_tree.]] - `uses` [INFERRED]
- [[ActionRecommenderInput accepts non-empty evidence_gap_list.]] - `uses` [INFERRED]
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[Build a minimal PretrialConferenceResult with optional focus items.]] - `uses` [INFERRED]
- [[Empty focus list → empty gaps, no crash.]] - `uses` [INFERRED]
- [[ExecutiveSummarizerInput accepts decision_path_tree.]] - `uses` [INFERRED]
- [[ExecutiveSummarizerInput accepts defense_chain_result.]] - `uses` [INFERRED]
- [[ExecutiveSummarizerInput accepts evidence_gap_items from conference.]] - `uses` [INFERRED]
- [[ExecutiveSummaryArtifact includes defense_chain_id when defense chain provided.]] - `uses` [INFERRED]
- [[JudgeAgent]] - `uses` [INFERRED]
- [[JudgeAgent 单元测试 — TDD.]] - `uses` [INFERRED]
- [[LLM 返回 12 个问题，截断到 10。]] - `uses` [INFERRED]
- [[MinutesGenerator 单元测试。]] - `uses` [INFERRED]
- [[No conference result → empty gap list.]] - `uses` [INFERRED]
- [[PretrialConferenceEngine]] - `uses` [INFERRED]
- [[Resolved focus items are excluded from evidence gaps.]] - `uses` [INFERRED]
- [[Risk assessment does not mention defense when chain is None.]] - `uses` [INFERRED]
- [[Risk assessment text includes defense chain info when available.]] - `uses` [INFERRED]
- [[Test evidence gap derivation from pretrial cross-examination results.]] - `uses` [INFERRED]
- [[TestAccessControl]] - `uses` [INFERRED]
- [[TestActionRecommenderDataFlow]] - `uses` [INFERRED]
- [[TestBasicGeneration]] - `uses` [INFERRED]
- [[TestCrossExaminationFocusItem]] - `uses` [INFERRED]
- [[TestCrossExaminationOpinion]] - `uses` [INFERRED]
- [[TestCrossExaminationRecord]] - `uses` [INFERRED]
- [[TestCrossExaminationResult]] - `uses` [INFERRED]
- [[TestDeriveEvidenceGaps]] - `uses` [INFERRED]
- [[TestEnrichment]] - `uses` [INFERRED]
- [[TestEnumCoverage]] - `uses` [INFERRED]
- [[TestExecutiveSummarizerDataFlow]] - `uses` [INFERRED]
- [[TestIssueFiltering]] - `uses` [INFERRED]
- [[TestJudgeQuestion]] - `uses` [INFERRED]
- [[TestJudgeQuestionSet]] - `uses` [INFERRED]
- [[TestLLMFailure_1]] - `uses` [INFERRED]
- [[TestMinutesGenerator]] - `uses` [INFERRED]
- [[TestPipelineWiring]] - `uses` [INFERRED]
- [[TestPretrialConferenceResult]] - `uses` [INFERRED]
- [[TestRuleLayer_1]] - `uses` [INFERRED]
- [[Unresolved focus items become evidence gap items.]] - `uses` [INFERRED]
- [[Verify _run_post_debate accepts conference_result parameter.]] - `uses` [INFERRED]
- [[Verify defense chain, decision tree, and evidence gaps flow to ExecutiveSummariz]] - `uses` [INFERRED]
- [[Verify evidence gaps and decision tree flow to ActionRecommenderInput.]] - `uses` [INFERRED]
- [[Verify evidence_gap_items=None is no longer hardcoded in run_case.py source.]] - `uses` [INFERRED]
- [[Verify evidence_gap_list= is no longer hardcoded in run_case.py source.]] - `uses` [INFERRED]
- [[_run_post_debate has conference_result parameter.]] - `uses` [INFERRED]
- [[conference_result defaults to None for backward compatibility.]] - `uses` [INFERRED]
- [[defense_chain_id is None when no defense chain provided.]] - `uses` [INFERRED]
- [[issue_dependency_graph schemas 单元测试。 Unit tests for issue_dependency_graph sche]] - `uses` [INFERRED]
- [[object dict 不再被接受为 final_evidence_index。]] - `uses` [INFERRED]
- [[priority 超范围时被截断到 1, 10。]] - `uses` [INFERRED]
- [[schemas.py]] - `contains` [EXTRACTED]
- [[传入非 admitted 证据应抛 ValueError。]] - `uses` [INFERRED]
- [[已解决的争点不传入 LLM（仅 open 争点被发送）。]] - `uses` [INFERRED]
- [[庭前会议编排器 — v1.5 顶层组件。 Pretrial conference engine — v1.5 top-level orchestrator.]] - `uses` [INFERRED]
- [[庭前会议编排器。 Args llm_client 符合 LLMClient 协议的客户端实例 model]] - `uses` [INFERRED]
- [[引用不存在的 issue_id 的问题被丢弃。]] - `uses` [INFERRED]
- [[执行庭前会议全流程。 Args issue_tree 争点树]] - `uses` [INFERRED]
- [[提供 blocking_conditions 时，prompt 中包含阻断条件。]] - `uses` [INFERRED]
- [[提供 evidence_gaps 时，prompt 中包含缺口信息。]] - `uses` [INFERRED]
- [[构建包含完整内容的 PretrialConferenceResult。]] - `uses` [INFERRED]
- [[每个 section 的 linked_output_ids 不为空（满足 ReportArtifact 契约）。]] - `uses` [INFERRED]
- [[生成法官追问。 Args issue_tree 争点树 admi]] - `uses` [INFERRED]
- [[生成的纪要应通过现有 ReportArtifact validator 的 output 回链检查。]] - `uses` [INFERRED]
- [[程序法官代理 — v1.5 核心组件。 Judge agent — v1.5 core component. 职责 Responsibilities]] - `uses` [INFERRED]
- [[程序法官代理。 Args llm_client 符合 LLMClient 协议的客户端实例 model]] - `uses` [INFERRED]
- [[集成测试 — 模块间数据流断点修复验证 (Unit 7)。 Integration tests — inter-module data flow breakp]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users