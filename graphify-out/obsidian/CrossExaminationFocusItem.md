---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\pretrial_conference\schemas.py"
type: "code"
community: "C: Users"
location: "L87"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# CrossExaminationFocusItem

## Connections
- [[ActionRecommenderInput accepts decision_path_tree.]] - `uses` [INFERRED]
- [[ActionRecommenderInput accepts non-empty evidence_gap_list.]] - `uses` [INFERRED]
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[Build a minimal PretrialConferenceResult with optional focus items.]] - `uses` [INFERRED]
- [[CrossExaminationEngine]] - `uses` [INFERRED]
- [[Empty focus list → empty gaps, no crash.]] - `uses` [INFERRED]
- [[ExecutiveSummarizerInput accepts decision_path_tree.]] - `uses` [INFERRED]
- [[ExecutiveSummarizerInput accepts defense_chain_result.]] - `uses` [INFERRED]
- [[ExecutiveSummarizerInput accepts evidence_gap_items from conference.]] - `uses` [INFERRED]
- [[ExecutiveSummaryArtifact includes defense_chain_id when defense chain provided.]] - `uses` [INFERRED]
- [[MinutesGenerator 单元测试。]] - `uses` [INFERRED]
- [[No conference result → empty gap list.]] - `uses` [INFERRED]
- [[Resolved focus items are excluded from evidence gaps.]] - `uses` [INFERRED]
- [[Risk assessment does not mention defense when chain is None.]] - `uses` [INFERRED]
- [[Risk assessment text includes defense chain info when available.]] - `uses` [INFERRED]
- [[Test evidence gap derivation from pretrial cross-examination results.]] - `uses` [INFERRED]
- [[TestActionRecommenderDataFlow]] - `uses` [INFERRED]
- [[TestCrossExaminationFocusItem]] - `uses` [INFERRED]
- [[TestCrossExaminationOpinion]] - `uses` [INFERRED]
- [[TestCrossExaminationRecord]] - `uses` [INFERRED]
- [[TestCrossExaminationResult]] - `uses` [INFERRED]
- [[TestDeriveEvidenceGaps]] - `uses` [INFERRED]
- [[TestEnumCoverage]] - `uses` [INFERRED]
- [[TestExecutiveSummarizerDataFlow]] - `uses` [INFERRED]
- [[TestJudgeQuestion]] - `uses` [INFERRED]
- [[TestJudgeQuestionSet]] - `uses` [INFERRED]
- [[TestMinutesGenerator]] - `uses` [INFERRED]
- [[TestPipelineWiring]] - `uses` [INFERRED]
- [[TestPretrialConferenceResult]] - `uses` [INFERRED]
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
- [[schemas.py]] - `contains` [EXTRACTED]
- [[执行质证流程。 Returns (CrossExaminationResult, 更新后的 EvidenceI]] - `uses` [INFERRED]
- [[构建包含完整内容的 PretrialConferenceResult。]] - `uses` [INFERRED]
- [[构建质证记录、焦点清单，并执行证据状态迁移。]] - `uses` [INFERRED]
- [[每个 section 的 linked_output_ids 不为空（满足 ReportArtifact 契约）。]] - `uses` [INFERRED]
- [[生成的纪要应通过现有 ReportArtifact validator 的 output 回链检查。]] - `uses` [INFERRED]
- [[解析 LLM 输出并校验，返回合法意见列表。]] - `uses` [INFERRED]
- [[调用 LLM 对一批证据进行质证，返回校验后的意见列表。]] - `uses` [INFERRED]
- [[质证编排器 — v1.5 核心组件。 Cross-examination engine — v1.5 core component. 职责 Resp]] - `uses` [INFERRED]
- [[质证编排器。 Args llm_client 符合 LLMClient 协议的客户端实例 model]] - `uses` [INFERRED]
- [[集成测试 — 模块间数据流断点修复验证 (Unit 7)。 Integration tests — inter-module data flow breakp]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users