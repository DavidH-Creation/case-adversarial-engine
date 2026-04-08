---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\issue_impact_ranker\schemas.py"
type: "code"
community: "C: Users"
location: "L64"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# LLMIssueEvaluationOutput

## Connections
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[Filter LLM-emitted impact_targets against the per-case-type vocabulary.]] - `uses` [INFERRED]
- [[IssueImpactRanker]] - `uses` [INFERRED]
- [[IssueImpactRanker — 争点影响排序模块主类。 Issue Impact Ranker — main class for P0.1 issue]] - `uses` [INFERRED]
- [[LLM 批量评估输出（中间模型）。LLM batch evaluation output (intermediate model).]] - `rationale_for` [EXTRACTED]
- [[schemas.py]] - `contains` [EXTRACTED]
- [[争点影响排序器。 Args llm_client 符合 LLMClient 协议的客户端实例 case_]] - `uses` [INFERRED]
- [[将 LLM 评估结果校验后富化到 Issue 对象。 校验失败规则（任一失败 → 清空对应字段，记入 unevaluated_issue_]] - `uses` [INFERRED]
- [[归一化 LLM 返回的顶层键，确保 evaluations 字段存在。 LLM 可能用 issue_assessments asses]] - `uses` [INFERRED]
- [[归一化单条评估项的字段名，展平 dimensions 嵌套结构。]] - `uses` [INFERRED]
- [[执行争点影响排序。 Args inp 排序器输入（含争点树、证据索引、金额报告、主张方 ID）]] - `uses` [INFERRED]
- [[按 composite_score DESC 排序，多级 fallback 确保不因 ID 顺序产生错误排名。 排序优先级（降序重要性）：]] - `uses` [INFERRED]
- [[检测并修正 0-10 量纲评分。仅当所有相关字段一致 ≤ 10 时触发。 不触碰 dependency_depth（语义不同）和 evid]] - `uses` [INFERRED]
- [[计算加权综合分。越高 = 争点越关键。 - importance_score, swing_score, credibility_impa]] - `uses` [INFERRED]
- [[调用 LLM（结构化输出），失败时抛出异常由 rank() 捕获。]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users