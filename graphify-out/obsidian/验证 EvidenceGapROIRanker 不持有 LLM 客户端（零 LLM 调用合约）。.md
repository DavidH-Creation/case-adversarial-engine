---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\evidence_gap_roi_ranker\tests\test_ranker.py"
type: "rationale"
community: "C: Users"
location: "L553"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 验证 EvidenceGapROIRanker 不持有 LLM 客户端（零 LLM 调用合约）。

## Connections
- [[.test_no_llm_call_verifiable()]] - `rationale_for` [EXTRACTED]
- [[EvidenceGapDescriptor]] - `uses` [INFERRED]
- [[EvidenceGapROIRanker]] - `uses` [INFERRED]
- [[EvidenceGapRankerInput]] - `uses` [INFERRED]
- [[EvidenceGapRankingResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users