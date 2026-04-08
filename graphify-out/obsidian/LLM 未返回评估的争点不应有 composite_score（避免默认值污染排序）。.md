---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\issue_impact_ranker\tests\test_ranker.py"
type: "rationale"
community: "C: Users"
location: "L742"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# LLM 未返回评估的争点不应有 composite_score（避免默认值污染排序）。

## Connections
- [[IssueImpactRanker]] - `uses` [INFERRED]
- [[IssueImpactRankerInput]] - `uses` [INFERRED]
- [[IssueImpactRankingResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users