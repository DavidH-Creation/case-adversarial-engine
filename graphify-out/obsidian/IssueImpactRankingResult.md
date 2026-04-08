---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\issue_impact_ranker\schemas.py"
type: "code"
community: "C: Users"
location: "L99"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# IssueImpactRankingResult

## Connections
- [[AmountConsistencyCheck 内容被注入到 user prompt。]] - `uses` [INFERRED]
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[D01_xxx → stripped to xxx → mapped to field]] - `uses` [INFERRED]
- [[Filter LLM-emitted impact_targets against the per-case-type vocabulary.]] - `uses` [INFERRED]
- [[Full rank() flow with Opus-style output produces non-zero composite scores.]] - `uses` [INFERRED]
- [[Issue where all propositions are 'supported' → 0 disputed shown in prompt.]] - `uses` [INFERRED]
- [[IssueImpactRanker]] - `uses` [INFERRED]
- [[IssueImpactRanker — 争点影响排序模块主类。 Issue Impact Ranker — main class for P0.1 issue]] - `uses` [INFERRED]
- [[IssueImpactRanker 单元测试。 Unit tests for IssueImpactRanker. 测试策略： - 不依赖真实 LLM]] - `uses` [INFERRED]
- [[Issues with equal composite_score are NOT sorted by issue_id insertion order w]] - `uses` [INFERRED]
- [[LLM 前 N 次失败后成功，触发重试机制。_1]] - `uses` [INFERRED]
- [[LLM 整体失败：返回原始 issue_tree，所有争点进 unevaluated_issue_ids。]] - `uses` [INFERRED]
- [[LLM 未返回评估的争点不应有 composite_score（避免默认值污染排序）。]] - `uses` [INFERRED]
- [[LLM 返回未知 issue_id → 对应评估条目被忽略，不影响结果。]] - `uses` [INFERRED]
- [[MockLLMClient_13]] - `uses` [INFERRED]
- [[TestImpactTargetsVocabularyFilter]] - `uses` [INFERRED]
- [[TestOpusStyleNormalization_2]] - `uses` [INFERRED]
- [[TestRankFullFlow]] - `uses` [INFERRED]
- [[TestSortIssues]] - `uses` [INFERRED]
- [[TestValidationRules_1]] - `uses` [INFERRED]
- [[Unit 22 Phase C.5a C.5b 回归测试。 Issue.impact_targets 是 liststr，没有 enum 校验]] - `uses` [INFERRED]
- [[When composite_score and outcome_impact are equal, swing_score DESC breaks the t]] - `uses` [INFERRED]
- [[When composite_score and swing_score are equal, abs(evidence_strength_gap) DESC]] - `uses` [INFERRED]
- [[civil_loan ranker 必须丢弃 labor_dispute real_estate 完全未知值。]] - `uses` [INFERRED]
- [[dimensions dict → flat scoring fields]] - `uses` [INFERRED]
- [[fact_dispute_ratio 字段被注入 user prompt，为 swing_score 提供争议信号。]] - `uses` [INFERRED]
- [[issue_assessments → evaluations]] - `uses` [INFERRED]
- [[labor_dispute ranker 必须丢弃 civil_loan real_estate 未知值。]] - `uses` [INFERRED]
- [[opponent_attack_evidence_ids 含未知证据 ID → opponent_attack_strength 被清空。]] - `uses` [INFERRED]
- [[outcome_impact inside dimensions → extracted to top level]] - `uses` [INFERRED]
- [[proponent_evidence_ids 为空时，proponent_evidence_strength 被清空。]] - `uses` [INFERRED]
- [[rank() 只调用一次 LLM（批量模式）。]] - `uses` [INFERRED]
- [[real_estate ranker 必须丢弃 civil_loan labor_dispute 未知值。]] - `uses` [INFERRED]
- [[recommended_action_basis 为空 → recommended_action 被清空。]] - `uses` [INFERRED]
- [[schemas.py]] - `contains` [EXTRACTED]
- [[争点影响排序器。 Args llm_client 符合 LLMClient 协议的客户端实例 case_]] - `uses` [INFERRED]
- [[争点影响排序结果产物。纳入 CaseWorkspace.artifact_index。 Issue impact ranking result art]] - `rationale_for` [EXTRACTED]
- [[合法评估结果正确富化到 Issue 对象。]] - `uses` [INFERRED]
- [[同权重争点维持原始顺序（Python sorted 稳定保证）。]] - `uses` [INFERRED]
- [[将 LLM 评估结果校验后富化到 Issue 对象。 校验失败规则（任一失败 → 清空对应字段，记入 unevaluated_issue_]] - `uses` [INFERRED]
- [[归一化 LLM 返回的顶层键，确保 evaluations 字段存在。 LLM 可能用 issue_assessments asses]] - `uses` [INFERRED]
- [[归一化单条评估项的字段名，展平 dimensions 嵌套结构。]] - `uses` [INFERRED]
- [[执行争点影响排序。 Args inp 排序器输入（含争点树、证据索引、金额报告、主张方 ID）]] - `uses` [INFERRED]
- [[按 composite_score DESC 排序，多级 fallback 确保不因 ID 顺序产生错误排名。 排序优先级（降序重要性）：]] - `uses` [INFERRED]
- [[排序规则测试——不调用 LLM，直接测试 _sort_issues。]] - `uses` [INFERRED]
- [[构造一条合法 LLM 评估条目。 None 表示使用默认值（ ev-001 ），显式传  表示空列表（触发校验失败）。]] - `uses` [INFERRED]
- [[检测并修正 0-10 量纲评分。仅当所有相关字段一致 ≤ 10 时触发。 不触碰 dependency_depth（语义不同）和 evid]] - `uses` [INFERRED]
- [[测试 Opus 风格 LLM 输出归一化（dimensions 嵌套 + D0X_ 前缀）。]] - `uses` [INFERRED]
- [[端到端：LLM 返回混合词汇，rank() 后 Issue.impact_targets 仅含案由合法值。 这是覆盖 ranker.py]] - `uses` [INFERRED]
- [[规则层校验——通过 rank() + MockLLMClient 触发各种失败场景。]] - `uses` [INFERRED]
- [[计算加权综合分。越高 = 争点越关键。 - importance_score, swing_score, credibility_impa]] - `uses` [INFERRED]
- [[调用 LLM（结构化输出），失败时抛出异常由 rank() 捕获。]] - `uses` [INFERRED]
- [[输出争点按 outcome_impact 降序排列。]] - `uses` [INFERRED]
- [[过滤前先做 strip + lower（保留 Phase C 之前的合约）。]] - `uses` [INFERRED]
- [[返回预定义 JSON 响应的 mock LLM 客户端。 Mock LLM client that returns predefined JSON r_4]] - `uses` [INFERRED]
- [[非法 outcome_impact 枚举值 → 该字段清空，争点进 unevaluated。]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users