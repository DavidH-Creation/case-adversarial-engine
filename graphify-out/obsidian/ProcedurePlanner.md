---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\procedure_setup\planner.py"
type: "code"
community: "C: Users"
location: "L184"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# ProcedurePlanner

## Connections
- [[.__init__()_39]] - `method` [EXTRACTED]
- [[._build_failed_result()]] - `method` [EXTRACTED]
- [[._build_input_snapshot()]] - `method` [EXTRACTED]
- [[._build_result()_1]] - `method` [EXTRACTED]
- [[._build_timeline_events()]] - `method` [EXTRACTED]
- [[._call_llm_structured()_3]] - `method` [EXTRACTED]
- [[._validate_input()_3]] - `method` [EXTRACTED]
- [[.plan()]] - `method` [EXTRACTED]
- [[LLM 前两次失败后第三次成功应正常返回结果。 Should succeed after two LLM failures if third atte]] - `uses` [INFERRED]
- [[LLM 应收到包含 case_id 的 prompt。 LLM should receive prompts containing case_id.]] - `uses` [INFERRED]
- [[LLM 所有重试均失败应返回 status='failed' 的结果，不抛出异常。 Exhausted retries should return a]] - `uses` [INFERRED]
- [[LLM 缺少某阶段时应使用默认配置补全。 Missing phase in LLM response should be filled with de]] - `uses` [INFERRED]
- [[LLM 返回无法解析的响应时应返回 status='failed' 的结果。 Unparseable LLM response should retu]] - `uses` [INFERRED]
- [[LLMProcedureConfig]] - `uses` [INFERRED]
- [[LLMProcedureOutput]] - `uses` [INFERRED]
- [[LLMProcedureState]] - `uses` [INFERRED]
- [[MockLLMClient_7]] - `uses` [INFERRED]
- [[ProcedureConfig]] - `uses` [INFERRED]
- [[ProcedureConfig 应正确反映 LLM 输出和引擎常量。 ProcedureConfig should correctly reflect]] - `uses` [INFERRED]
- [[ProcedurePlanner 单元测试。 Unit tests for ProcedurePlanner. 使用 mock LLM 客户端验证：]] - `uses` [INFERRED]
- [[ProcedureSetupInput]] - `uses` [INFERRED]
- [[ProcedureSetupResult]] - `uses` [INFERRED]
- [[ProcedureState]] - `uses` [INFERRED]
- [[Run.input_snapshot 应包含争点的 material_refs。 Run.input_snapshot should have mat]] - `uses` [INFERRED]
- [[Run.scenario_id 应为 None（非场景执行）。 Run.scenario_id should be None (not a scena]] - `uses` [INFERRED]
- [[Run.trigger_type 必须固定为 'procedure_setup'。 Run.trigger_type must be 'procedu]] - `uses` [INFERRED]
- [[Run.workspace_id 应与 ProcedureSetupInput.workspace_id 一致。 Run.workspace_id s]] - `uses` [INFERRED]
- [[TimelineEvent]] - `uses` [INFERRED]
- [[_make_state_id 应生成正确格式的 state_id。 _make_state_id should generate correctly]] - `uses` [INFERRED]
- [[issues 为空时应抛出 ValueError。 Empty issues should raise ValueError.]] - `uses` [INFERRED]
- [[judge_questions 阶段不得包含 owner_private 读取域。 judge_questions phase must not in]] - `uses` [INFERRED]
- [[judge_questions 阶段应清除 owner_private。 owner_private should be removed from j]] - `uses` [INFERRED]
- [[next_state_ids 应按 PHASE_ORDER 顺序引用下一状态。 next_state_ids should reference the]] - `uses` [INFERRED]
- [[output_branching 状态的 next_state_ids 必须为空。 output_branching.next_state_ids m]] - `uses` [INFERRED]
- [[output_branching 阶段 admissible_evidence_statuses 必须仅含 admitted_for_discussion。_1]] - `uses` [INFERRED]
- [[output_branching 阶段应仅保留 admitted_for_discussion。 output_branching phase sho]] - `uses` [INFERRED]
- [[plan() 应返回 ProcedureSetupResult 且字段齐全。 plan() should return a ProcedureSetu]] - `uses` [INFERRED]
- [[planner.py]] - `contains` [EXTRACTED]
- [[procedure_states 必须覆盖全部八个阶段。 procedure_states must cover all eight phases.]] - `uses` [INFERRED]
- [[setup_input 与 issue_tree 的 case_id 不匹配时应抛出 ValueError。 Mismatched case_ids]] - `uses` [INFERRED]
- [[state_id 应按 pstate-{case_id}-{phase}-001 格式生成。 state_id should be generated]] - `uses` [INFERRED]
- [[不支持的案由类型应抛出 ValueError。 Unsupported case type should raise ValueError.]] - `uses` [INFERRED]
- [[场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.]] - `uses` [INFERRED]
- [[失败结果应保留 run_id、case_id、workspace_id 等关键字段。 Failed result should preserve ru]] - `uses` [INFERRED]
- [[完整六引擎串联：每步输出能正确作为下一步输入，且各合约不变量均成立。 Full six-engine chain each output feeds]] - `uses` [INFERRED]
- [[应能从 LLM 的 markdown 代码块响应中解析 JSON。 Should parse JSON from LLM markdown code]] - `uses` [INFERRED]
- [[时间线事件应至少包含举证期限事件。 Timeline events should include at least the evidence subm]] - `uses` [INFERRED]
- [[有效 ProcedureSetupResult 应通过校验。 A valid ProcedureSetupResult should pass val]] - `uses` [INFERRED]
- [[未知阶段应返回空列表。 Unknown phase should return empty list.]] - `uses` [INFERRED]
- [[每个 ProcedureState.case_id 必须与 setup_input.case_id 一致。 Every ProcedureState.]] - `uses` [INFERRED]
- [[程序设置规划器 Procedure Planner. 输入 ProcedureSetupInput + IssueTree，输出 Pro]] - `rationale_for` [EXTRACTED]
- [[端到端集成测试 — 全链路六引擎串联。 End-to-end integration tests — full six-engine pipeline.]] - `uses` [INFERRED]
- [[终止阶段 output_branching 应返回空列表。 Terminal phase output_branching should return]] - `uses` [INFERRED]
- [[运行 EvidenceIndexer，返回 listEvidence。]] - `uses` [INFERRED]
- [[运行 IssueExtractor，返回 IssueTree。]] - `uses` [INFERRED]
- [[运行 ReportGenerator，返回 ReportArtifact。]] - `uses` [INFERRED]
- [[返回预定义 JSON 响应的 mock LLM 客户端。 Mock LLM client that returns predefined JSON r_2]] - `uses` [INFERRED]
- [[非 judge_questions 阶段不应修改访问域。 Non-judge_questions phases should not modify a]] - `uses` [INFERRED]
- [[非 output_branching 阶段不应修改证据状态。 Non-output_branching phases should not modif]] - `uses` [INFERRED]
- [[非终止阶段应返回下一阶段的 state_id。 Non-terminal phase should return next phase's state]] - `uses` [INFERRED]
- [[验证 Evidence.model_dump() 格式被 IssueExtractor 正确消费，且 evidence_id 字段名保留。 Verif]] - `uses` [INFERRED]
- [[验证 ProcedurePlanner LLM 持续失败时： - 不抛出异常（plan() 内部捕获） - 返回 run.status =]] - `uses` [INFERRED]
- [[验证 ScenarioSimulator.affected_issue_ids ⊆ IssueTree.issues .issue_id。 Ver]] - `uses` [INFERRED]
- [[验证两轮追问： - 第二轮 previous_turns 正确传入（体现在 LLM user prompt 中） - issue_ids 始]] - `uses` [INFERRED]
- [[验证从 listEvidence 手动构建 EvidenceIndex 后，ReportGenerator 零悬空引用。 Verifies zer]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users