---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\evidence_weight_scorer\scorer.py"
type: "rationale"
community: "C: Users"
location: "L151"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 调用 LLM（结构化输出优先，fallback 到 json_utils），失败时返回 None（不抛异常）。 Call LLM (struc

## Connections
- [[._call_llm()_2]] - `rationale_for` [EXTRACTED]
- [[EvidenceWeightScorerInput]] - `uses` [INFERRED]
- [[LLMEvidenceWeightItem]] - `uses` [INFERRED]
- [[LLMEvidenceWeightOutput]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users