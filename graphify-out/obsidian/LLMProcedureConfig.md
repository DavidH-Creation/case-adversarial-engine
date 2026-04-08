---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\procedure_setup\schemas.py"
type: "code"
community: "C: Users"
location: "L139"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# LLMProcedureConfig

## Connections
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[ProcedurePlanner]] - `uses` [INFERRED]
- [[schemas.py]] - `contains` [EXTRACTED]
- [[加载案由对应的 prompt 模板模块。 Load prompt template module for the given case typ_1]] - `uses` [INFERRED]
- [[将 LLM 输出规范化为 ProcedureSetupResult。 Normalize LLM output into a Procedur]] - `uses` [INFERRED]
- [[执行程序设置规划。 Execute procedure setup planning. Args]] - `uses` [INFERRED]
- [[构建可追溯的输入快照。 Build a traceable input snapshot from the issue tree.]] - `uses` [INFERRED]
- [[构建失败时的 ProcedureSetupResult（使用默认配置）。 Build a failed ProcedureSetupResul]] - `uses` [INFERRED]
- [[根据阶段顺序生成 next_state_ids（终止阶段返回空列表）。 Build next_state_ids based on phase ord]] - `uses` [INFERRED]
- [[清理访问域列表，强制执行 judge_questions 约束。 Sanitize access domain list, enforcing jud]] - `uses` [INFERRED]
- [[清理证据状态列表，强制执行 output_branching 约束。 Sanitize evidence status list, enforcing]] - `uses` [INFERRED]
- [[生成确定性 state_id。 Generate a deterministic state_id from case_id and phase.]] - `uses` [INFERRED]
- [[程序设置引擎核心模块 Procedure setup engine core module. 根据案件类型（case_type）、当事人信息（parti]] - `uses` [INFERRED]
- [[程序设置规划器 Procedure Planner. 输入 ProcedureSetupInput + IssueTree，输出 Pro]] - `uses` [INFERRED]
- [[规范化时间线事件列表。 Normalize timeline events list. - 过滤非法 phase 值]] - `uses` [INFERRED]
- [[调用 LLM（结构化输出），失败时抛出异常由 plan() 捕获。 Call LLM with structured output; exce]] - `uses` [INFERRED]
- [[验证输入数据合法性。 Validate input data validity. Raises_2]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users