---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\issue_impact_ranker\ranker.py"
type: "rationale"
community: "C: Users"
location: "L626"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 将 LLM 评估结果校验后富化到 Issue 对象。 校验失败规则（任一失败 → 清空对应字段，记入 unevaluated_issue_

## Connections
- [[._apply_evaluations()]] - `rationale_for` [EXTRACTED]
- [[IssueImpactRankerInput]] - `uses` [INFERRED]
- [[IssueImpactRankingResult]] - `uses` [INFERRED]
- [[LLMIssueEvaluationOutput]] - `uses` [INFERRED]
- [[LLMSingleIssueEvaluation]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users