---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\shared\models\pipeline.py"
type: "rationale"
community: "C: Users"
location: "L200"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 置信度区间。仅在 verdict_block_active=False 时允许填写。

## Connections
- [[AmountCalculationReport]] - `uses` [INFERRED]
- [[AmountConflict]] - `uses` [INFERRED]
- [[AmountConsistencyCheck]] - `uses` [INFERRED]
- [[BlockingConditionType]] - `uses` [INFERRED]
- [[ClaimCalculationEntry]] - `uses` [INFERRED]
- [[ConfidenceInterval]] - `rationale_for` [EXTRACTED]
- [[DisputedAmountAttribution]] - `uses` [INFERRED]
- [[InterestRecalculation]] - `uses` [INFERRED]
- [[JobStatus]] - `uses` [INFERRED]
- [[LoanTransaction]] - `uses` [INFERRED]
- [[RepaymentTransaction]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users