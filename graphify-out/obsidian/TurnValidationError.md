---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\interactive_followup\validator.py"
type: "code"
community: "C: Users"
location: "L90"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# TurnValidationError

## Connections
- [[.__init__()_34]] - `method` [EXTRACTED]
- [[Exception]] - `inherits` [EXTRACTED]
- [[FollowupResponder 单元测试。 Unit tests for FollowupResponder. 测试覆盖 Test covera]] - `uses` [INFERRED]
- [[LLM 前两次失败后第三次成功应正常返回。 Should succeed after two LLM failures if third attemp]] - `uses` [INFERRED]
- [[LLM 应收到包含报告摘要的 user prompt。 LLM user prompt should contain report summary c]] - `uses` [INFERRED]
- [[LLM 所有重试均失败应抛出 RuntimeError。 Exhausted retries should raise RuntimeError.]] - `uses` [INFERRED]
- [[LLM 返回未知 statement_class 时应默认为 inference。 Unknown statement_class from LLM]] - `uses` [INFERRED]
- [[LLM 返回空 issue_ids 时，引擎应从报告中推断出默认争点。 When LLM returns empty issue_ids, engin]] - `uses` [INFERRED]
- [[MockLLMClient_6]] - `uses` [INFERRED]
- [[TestSanitizeQuestion]] - `uses` [INFERRED]
- [[respond() 应返回 InteractionTurn 且字段齐全。 respond() should return an Interaction]] - `uses` [INFERRED]
- [[respond_safe() 在 LLM 正常时应返回正常 InteractionTurn。 respond_safe() should return]] - `uses` [INFERRED]
- [[respond_safe() 对无效输入（空问题）仍应抛出 ValueError。 respond_safe() should still raise]] - `uses` [INFERRED]
- [[sanitize_question() 测试 Tests for sanitize_question().]] - `uses` [INFERRED]
- [[validate_turn_strict 应在有 error 时抛出 TurnValidationError。 validate_turn_stric]] - `uses` [INFERRED]
- [[validate_turn_strict()]] - `calls` [INFERRED]
- [[validator.py]] - `contains` [EXTRACTED]
- [[不支持的案由类型应在初始化时抛出 ValueError。 Unsupported case type should raise ValueError]] - `uses` [INFERRED]
- [[仅含 HTML 标签的输入在标签移除后应抛出 ValueError。]] - `uses` [INFERRED]
- [[合约：evidence_ids 必须是报告已引用证据的子集。 Contract evidence_ids must be subset of rep]] - `uses` [INFERRED]
- [[合约：issue_ids 不能为空。 Contract issue_ids must be non-empty.]] - `uses` [INFERRED]
- [[合约：statement_class 必须是合法枚举值。 Contract statement_class must be a valid enum]] - `uses` [INFERRED]
- [[场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.]] - `uses` [INFERRED]
- [[多轮追问时，previous_turns 应传入 LLM 的 user prompt。 For multi-turn, previous_turns]] - `uses` [INFERRED]
- [[恰好 MAX_QUESTION_LENGTH 长度的输入不应被截断。]] - `uses` [INFERRED]
- [[有效追问轮次应通过校验。 A valid turn should pass validation.]] - `uses` [INFERRED]
- [[校验器应捕获悬空争点 ID 引用。 Validator should catch dangling issue ID references.]] - `uses` [INFERRED]
- [[校验器应捕获悬空证据 ID 引用。 Validator should catch dangling evidence ID references.]] - `uses` [INFERRED]
- [[校验器应捕获空 issue_ids 违规。 Validator should catch empty issue_ids violation.]] - `uses` [INFERRED]
- [[每次 respond() 应生成唯一的 turn_id。 Each respond() call should generate a unique t]] - `uses` [INFERRED]
- [[空 question 应抛出 ValueError。 Empty question should raise ValueError.]] - `uses` [INFERRED]
- [[超长输入应截断至 MAX_QUESTION_LENGTH。]] - `uses` [INFERRED]
- [[返回预定义 JSON 响应的 mock LLM 客户端。 Mock LLM client that returns predefined JSON r_1]] - `uses` [INFERRED]
- [[追问校验失败异常，包含详细错误列表。 Turn validation failed exception with detailed error lis]] - `rationale_for` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/C:_Users