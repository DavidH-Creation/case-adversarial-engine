---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\admissibility_evaluator\schemas.py"
type: "code"
community: "C: Users"
location: "L99"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# ChainImpact

## Connections
- [[AdmissibilityEvaluator 单元测试。 Unit tests for AdmissibilityEvaluator and simulate]] - `uses` [INFERRED]
- [[AdmissibilityEvaluatorInput 需要 case_id、run_id 和 evidence_index。]] - `uses` [INFERRED]
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[Evidence 新增 admissibility_challenges 字段，默认空列表。]] - `uses` [INFERRED]
- [[Evidence 新增 admissibility_score 字段，默认 1.0。]] - `uses` [INFERRED]
- [[Evidence 新增 exclusion_impact 字段，默认 None。]] - `uses` [INFERRED]
- [[ImpactReport 包含 excluded_evidence_id 和 case_id。]] - `uses` [INFERRED]
- [[ImpactReport 包含所有预期字段。]] - `uses` [INFERRED]
- [[LLM 失败时：返回原始 EvidenceIndex，不抛异常。]] - `uses` [INFERRED]
- [[LLM 抛出异常时返回原始 EvidenceIndex。]] - `uses` [INFERRED]
- [[LLM 输出了未知 evidence_id → 忽略，已知证据正常处理。]] - `uses` [INFERRED]
- [[LLM 返回非法 JSON 时返回原始 EvidenceIndex。]] - `uses` [INFERRED]
- [[LLMAdmissibilityItem 字段默认值正确。]] - `uses` [INFERRED]
- [[LLMAdmissibilityOutput 默认 evidence_assessments 为空列表。]] - `uses` [INFERRED]
- [[MockLLMClient_2]] - `uses` [INFERRED]
- [[PROMPT_REGISTRY 包含 civil_loan 键及所需函数。]] - `uses` [INFERRED]
- [[TestConstructorValidation]] - `uses` [INFERRED]
- [[TestLLMFailureHandling]] - `uses` [INFERRED]
- [[TestLowScoreEnforcement]] - `uses` [INFERRED]
- [[TestPromptContent]] - `uses` [INFERRED]
- [[TestScoreRangeValidation]] - `uses` [INFERRED]
- [[TestSimulateExclusion]] - `uses` [INFERRED]
- [[TestSuccessfulEvaluation]] - `uses` [INFERRED]
- [[admissibility_challenges 接受字符串列表。]] - `uses` [INFERRED]
- [[admissibility_score 0.5 且有 challenges → 正常更新。]] - `uses` [INFERRED]
- [[admissibility_score 0.5 但无 challenges → 跳过（保持默认值）。]] - `uses` [INFERRED]
- [[admissibility_score = 0.5（临界值，不触发强制）时无 challenges 也可接受。]] - `uses` [INFERRED]
- [[admissibility_score 接受 0.0, 1.0 之间的值。]] - `uses` [INFERRED]
- [[admissibility_score 被四舍五入到两位小数。]] - `uses` [INFERRED]
- [[admissibility_score 超出 0.0, 1.0 时 Pydantic 拒绝。]] - `uses` [INFERRED]
- [[admissibility_score=0 的证据为最弱，排除时为 primary evidence。]] - `uses` [INFERRED]
- [[challenges 全为空白字符串视为空，也被跳过。]] - `uses` [INFERRED]
- [[max_retries=2 时 LLM 连续失败后返回原始索引，call_count=3。]] - `uses` [INFERRED]
- [[prompt 内容测试——确认关键信息传入 LLM。]] - `uses` [INFERRED]
- [[schemas.py]] - `contains` [EXTRACTED]
- [[simulate_exclusion — 证据排除传播分析（规则层，不调用 LLM）。 Rules-based utility propagates evi]] - `uses` [INFERRED]
- [[simulate_exclusion 规则层测试。]] - `uses` [INFERRED]
- [[system prompt 提及可采性评分、质疑理由等关键概念。]] - `uses` [INFERRED]
- [[system prompt 特别提及录音 录屏证据的审查要点。]] - `uses` [INFERRED]
- [[system prompt 非空并传递给 LLM。]] - `uses` [INFERRED]
- [[user prompt 包含待评估的证据 ID。]] - `uses` [INFERRED]
- [[user prompt 包含待评估证据的 ID。]] - `uses` [INFERRED]
- [[user prompt 包含证据数量提示。]] - `uses` [INFERRED]
- [[user prompt 对录音 录屏证据有特殊标注。]] - `uses` [INFERRED]
- [[不支持的案件类型在构造时抛出 ValueError。]] - `uses` [INFERRED]
- [[两条或以上路径不可行时，overall_severity 升为 case_breaking。]] - `uses` [INFERRED]
- [[争点不依赖该证据时，不出现在 affected_issues 中。]] - `uses` [INFERRED]
- [[争点仅有该证据时，排除后 severity=case_breaking。]] - `uses` [INFERRED]
- [[争点有多份证据时，排除其中最强证据后 severity=significant。]] - `uses` [INFERRED]
- [[分析争点层影响：哪些争点依赖该证据，排除后剩余证据情况。]] - `uses` [INFERRED]
- [[分析攻击链层影响：哪些攻击节点依赖该证据。]] - `uses` [INFERRED]
- [[分析路径层影响：admissibility_gate 中包含该证据的路径变为不可行。]] - `uses` [INFERRED]
- [[判断 evidence_id 是否为该争点的主要证据（admissibility_score 最高者）。]] - `uses` [INFERRED]
- [[同时传入争点树、路径树、攻击链时，三层均分析。]] - `uses` [INFERRED]
- [[攻击节点依赖该证据时，节点出现在 broken_attack_node_ids 中。]] - `uses` [INFERRED]
- [[无争点树、路径树、攻击链时，整体影响为 negligible。]] - `uses` [INFERRED]
- [[模拟将指定证据排除后对全链路的影响。 Args evidence_id 被排除的证据 ID]] - `uses` [INFERRED]
- [[规则层强制：低分证据必须有 admissibility_challenges。]] - `uses` [INFERRED]
- [[证据仅在 key_evidence_ids 中时，路径不设为不可行。]] - `uses` [INFERRED]
- [[证据在 admissibility_gate 中时，路径变为不可行。]] - `uses` [INFERRED]
- [[评估后，admissibility_challenges 被更新。]] - `uses` [INFERRED]
- [[评估后，admissibility_score 被更新。]] - `uses` [INFERRED]
- [[评估后，exclusion_impact 被更新。]] - `uses` [INFERRED]
- [[评估后，原有字段（title, summary 等）不受影响。]] - `uses` [INFERRED]
- [[路径不依赖该证据时不出现在 affected_paths 中。]] - `uses` [INFERRED]
- [[输出 EvidenceIndex 的 case_id 与输入一致。]] - `uses` [INFERRED]
- [[返回预定义 JSON 响应的 mock LLM 客户端。]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users