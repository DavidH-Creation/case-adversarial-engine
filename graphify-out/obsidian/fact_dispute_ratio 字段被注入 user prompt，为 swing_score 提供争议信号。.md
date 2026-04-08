---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\issue_impact_ranker\tests\test_ranker.py"
type: "rationale"
community: "C: Users"
location: "L514"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# fact_dispute_ratio 字段被注入 user prompt，为 swing_score 提供争议信号。

## Connections
- [[IssueImpactRanker]] - `uses` [INFERRED]
- [[IssueImpactRankerInput]] - `uses` [INFERRED]
- [[IssueImpactRankingResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users