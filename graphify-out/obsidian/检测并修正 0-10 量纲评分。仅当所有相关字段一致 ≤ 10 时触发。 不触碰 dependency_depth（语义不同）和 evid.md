---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\issue_impact_ranker\ranker.py"
type: "rationale"
community: "C: Users"
location: "L517"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 检测并修正 0-10 量纲评分。仅当所有相关字段一致 ≤ 10 时触发。 不触碰 dependency_depth（语义不同）和 evid

## Connections
- [[IssueImpactRankerInput]] - `uses` [INFERRED]
- [[IssueImpactRankingResult]] - `uses` [INFERRED]
- [[LLMIssueEvaluationOutput]] - `uses` [INFERRED]
- [[LLMSingleIssueEvaluation]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users