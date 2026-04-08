---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\shared\models\pipeline.py"
type: "rationale"
community: "C: Users"
location: "L106"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 长任务结构化错误。对应 schemas indexing.schema.json# $defs job_error。

## Connections
- [[AmountCalculationReport]] - `uses` [INFERRED]
- [[AmountConflict]] - `uses` [INFERRED]
- [[AmountConsistencyCheck]] - `uses` [INFERRED]
- [[BlockingConditionType]] - `uses` [INFERRED]
- [[ClaimCalculationEntry]] - `uses` [INFERRED]
- [[DisputedAmountAttribution]] - `uses` [INFERRED]
- [[InterestRecalculation]] - `uses` [INFERRED]
- [[JobError]] - `rationale_for` [EXTRACTED]
- [[JobStatus]] - `uses` [INFERRED]
- [[LoanTransaction]] - `uses` [INFERRED]
- [[RepaymentTransaction]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users