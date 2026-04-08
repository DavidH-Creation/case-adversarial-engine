---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\issue_impact_ranker\ranker.py"
type: "rationale"
community: "C: Users"
location: "L551"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 按 composite_score DESC 排序，多级 fallback 确保不因 ID 顺序产生错误排名。 排序优先级（降序重要性）：

## Connections
- [[._sort_issues()]] - `rationale_for` [EXTRACTED]
- [[IssueImpactRankerInput]] - `uses` [INFERRED]
- [[IssueImpactRankingResult]] - `uses` [INFERRED]
- [[LLMIssueEvaluationOutput]] - `uses` [INFERRED]
- [[LLMSingleIssueEvaluation]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users