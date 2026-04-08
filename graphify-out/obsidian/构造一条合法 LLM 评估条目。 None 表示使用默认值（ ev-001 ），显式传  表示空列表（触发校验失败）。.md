---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\issue_impact_ranker\tests\test_ranker.py"
type: "rationale"
community: "C: Users"
location: "L178"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 构造一条合法 LLM 评估条目。 None 表示使用默认值（[ ev-001 ]），显式传 [] 表示空列表（触发校验失败）。

## Connections
- [[IssueImpactRanker]] - `uses` [INFERRED]
- [[IssueImpactRankerInput]] - `uses` [INFERRED]
- [[IssueImpactRankingResult]] - `uses` [INFERRED]
- [[_eval_entry()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users