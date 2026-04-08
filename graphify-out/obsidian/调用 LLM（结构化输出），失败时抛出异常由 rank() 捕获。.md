---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\issue_impact_ranker\ranker.py"
type: "rationale"
community: "C: Users"
location: "L896"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 调用 LLM（结构化输出），失败时抛出异常由 rank() 捕获。

## Connections
- [[._call_llm_structured()_6]] - `rationale_for` [EXTRACTED]
- [[IssueImpactRankerInput]] - `uses` [INFERRED]
- [[IssueImpactRankingResult]] - `uses` [INFERRED]
- [[LLMIssueEvaluationOutput]] - `uses` [INFERRED]
- [[LLMSingleIssueEvaluation]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users