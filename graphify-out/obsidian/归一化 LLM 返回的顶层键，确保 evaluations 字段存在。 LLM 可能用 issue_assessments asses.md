---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\issue_impact_ranker\ranker.py"
type: "rationale"
community: "C: Users"
location: "L318"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 归一化 LLM 返回的顶层键，确保 evaluations 字段存在。 LLM 可能用 issue_assessments asses

## Connections
- [[IssueImpactRankerInput]] - `uses` [INFERRED]
- [[IssueImpactRankingResult]] - `uses` [INFERRED]
- [[LLMIssueEvaluationOutput]] - `uses` [INFERRED]
- [[LLMSingleIssueEvaluation]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users