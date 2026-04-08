---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\procedure_setup\schemas.py"
type: "code"
community: "C: Users"
location: "L113"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# ProcedureSetupResult

## Connections
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[LLM 前两次失败后第三次成功应正常返回结果。 Should succeed after two LLM failures if third atte]] - `uses` [INFERRED]
- [[LLM 应收到包含 case_id 的 prompt。 LLM should receive prompts containing case_id.]] - `uses` [INFERRED]
- [[LLM 所有重试均失败应返回 status='failed' 的结果，不抛出异常。 Exhausted retries should return a]] - `uses` [INFERRED]
- [[LLM 缺少某阶段时应使用默认配置补全。 Missing phase in LLM response should be filled with de]] - `uses` [INFERRED]
- [[LLM 返回无法解析的响应时应返回 status='failed' 的结果。 Unparseable LLM response should retu]] - `uses` [INFERRED]
- [[MockLLMClient_7]] - `uses` [INFERRED]
- [[ProcedureConfig 应正确反映 LLM 输出和引擎常量。 ProcedureConfig should correctly reflect]] - `uses` [INFERRED]
- [[ProcedurePlanner]] - `uses` [INFERRED]
- [[ProcedurePlanner 单元测试。 Unit tests for ProcedurePlanner. 使用 mock LLM 客户端验证：]] - `uses` [INFERRED]
- [[ProcedureValidationError]] - `uses` [INFERRED]
- [[Run.input_snapshot 应包含争点的 material_refs。 Run.input_snapshot should have mat]] - `uses` [INFERRED]
- [[Run.scenario_id 应为 None（非场景执行）。 Run.scenario_id should be None (not a scena]] - `uses` [INFERRED]
- [[Run.trigger_type 必须固定为 'procedure_setup'。 Run.trigger_type must be 'procedu]] - `uses` [INFERRED]
- [[Run.workspace_id 应与 ProcedureSetupInput.workspace_id 一致。 Run.workspace_id s]] - `uses` [INFERRED]
- [[ValidationReport]] - `uses` [INFERRED]
- [[ValidationResult]] - `uses` [INFERRED]
- [[_make_state_id 应生成正确格式的 state_id。 _make_state_id should generate correctly]] - `uses` [INFERRED]
- [[issues 为空时应抛出 ValueError。 Empty issues should raise ValueError.]] - `uses` [INFERRED]
- [[judge_questions 阶段不得包含 owner_private 读取域。 judge_questions phase must not in]] - `uses` [INFERRED]
- [[judge_questions 阶段应清除 owner_private。 owner_private should be removed from j]] - `uses` [INFERRED]
- [[next_state_ids 应按 PHASE_ORDER 顺序引用下一状态。 next_state_ids should reference the]] - `uses` [INFERRED]
- [[output_branching 状态的 next_state_ids 必须为空。 output_branching.next_state_ids m]] - `uses` [INFERRED]
- [[output_branching 阶段 admissible_evidence_statuses 必须仅含 admitted_for_discussion。_1]] - `uses` [INFERRED]
- [[output_branching 阶段应仅保留 admitted_for_discussion。 output_branching phase sho]] - `uses` [INFERRED]
- [[plan() 应返回 ProcedureSetupResult 且字段齐全。 plan() should return a ProcedureSetu]] - `uses` [INFERRED]
- [[procedure_states 必须覆盖全部八个阶段。 procedure_states must cover all eight phases.]] - `uses` [INFERRED]
- [[schemas.py]] - `contains` [EXTRACTED]
- [[setup_input 与 issue_tree 的 case_id 不匹配时应抛出 ValueError。 Mismatched case_ids]] - `uses` [INFERRED]
- [[state_id 应按 pstate-{case_id}-{phase}-001 格式生成。 state_id should be generated]] - `uses` [INFERRED]
- [[不支持的案由类型应抛出 ValueError。 Unsupported case type should raise ValueError.]] - `uses` [INFERRED]
- [[严格模式校验：有 error 时抛出 ProcedureValidationError。 Strict validation raises Proc]] - `uses` [INFERRED]
- [[加载案由对应的 prompt 模板模块。 Load prompt template module for the given case typ_1]] - `uses` [INFERRED]
- [[单条校验错误 A single validation error entry._3]] - `uses` [INFERRED]
- [[场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.]] - `uses` [INFERRED]
- [[场景校验器 — 对 Scenario ScenarioResult 进行合约合规性验证。 Scenario validator — validates S]] - `uses` [INFERRED]
- [[失败结果应保留 run_id、case_id、workspace_id 等关键字段。 Failed result should preserve ru]] - `uses` [INFERRED]
- [[将 LLM 输出规范化为 ProcedureSetupResult。 Normalize LLM output into a Procedur]] - `uses` [INFERRED]
- [[应能从 LLM 的 markdown 代码块响应中解析 JSON。 Should parse JSON from LLM markdown code]] - `uses` [INFERRED]
- [[执行程序设置规划。 Execute procedure setup planning. Args]] - `uses` [INFERRED]
- [[时间线事件应至少包含举证期限事件。 Timeline events should include at least the evidence subm]] - `uses` [INFERRED]
- [[有效 ProcedureSetupResult 应通过校验。 A valid ProcedureSetupResult should pass val]] - `uses` [INFERRED]
- [[未知阶段应返回空列表。 Unknown phase should return empty list.]] - `uses` [INFERRED]
- [[构建可追溯的输入快照。 Build a traceable input snapshot from the issue tree.]] - `uses` [INFERRED]
- [[构建失败时的 ProcedureSetupResult（使用默认配置）。 Build a failed ProcedureSetupResul]] - `uses` [INFERRED]
- [[校验 ProcedureSetupResult 的合约合规性。 Validate ProcedureSetupResult contract comp]] - `uses` [INFERRED]
- [[校验单个 ProcedureState 是否符合合约约束。 Validate a single ProcedureState against cont]] - `uses` [INFERRED]
- [[根据阶段顺序生成 next_state_ids（终止阶段返回空列表）。 Build next_state_ids based on phase ord]] - `uses` [INFERRED]
- [[每个 ProcedureState.case_id 必须与 setup_input.case_id 一致。 Every ProcedureState.]] - `uses` [INFERRED]
- [[清理访问域列表，强制执行 judge_questions 约束。 Sanitize access domain list, enforcing jud]] - `uses` [INFERRED]
- [[清理证据状态列表，强制执行 output_branching 约束。 Sanitize evidence status list, enforcing]] - `uses` [INFERRED]
- [[生成确定性 state_id。 Generate a deterministic state_id from case_id and phase.]] - `uses` [INFERRED]
- [[程序设置引擎核心模块 Procedure setup engine core module. 根据案件类型（case_type）、当事人信息（parti]] - `uses` [INFERRED]
- [[程序设置校验失败异常，包含详细错误列表。 Procedure setup validation failed exception with detai]] - `uses` [INFERRED]
- [[程序设置校验结果汇总 Aggregated procedure setup validation result.]] - `uses` [INFERRED]
- [[程序设置规划器 Procedure Planner. 输入 ProcedureSetupInput + IssueTree，输出 Pro]] - `uses` [INFERRED]
- [[终止阶段 output_branching 应返回空列表。 Terminal phase output_branching should return]] - `uses` [INFERRED]
- [[规范化时间线事件列表。 Normalize timeline events list. - 过滤非法 phase 值]] - `uses` [INFERRED]
- [[计算引用完整性得分（0.0–1.0）。 Compute citation completeness score (0.0–1.0)._1]] - `uses` [INFERRED]
- [[调用 LLM（结构化输出），失败时抛出异常由 plan() 捕获。 Call LLM with structured output; exce]] - `uses` [INFERRED]
- [[返回人类可读的校验摘要 Return human-readable validation summary._4]] - `uses` [INFERRED]
- [[返回预定义 JSON 响应的 mock LLM 客户端。 Mock LLM client that returns predefined JSON r_2]] - `uses` [INFERRED]
- [[非 judge_questions 阶段不应修改访问域。 Non-judge_questions phases should not modify a]] - `uses` [INFERRED]
- [[非 output_branching 阶段不应修改证据状态。 Non-output_branching phases should not modif]] - `uses` [INFERRED]
- [[非终止阶段应返回下一阶段的 state_id。 Non-terminal phase should return next phase's state]] - `uses` [INFERRED]
- [[验证输入数据合法性。 Validate input data validity. Raises_2]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users