---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\amount_calculator\tests\test_calculator.py"
type: "rationale"
community: "C: Users"
location: "L456"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# rule #6 total_claimed total_principal_loans threshold → 预警。

## Connections
- [[AmountCalculator]] - `uses` [INFERRED]
- [[AmountCalculatorInput]] - `uses` [INFERRED]
- [[AmountClaimDescriptor]] - `uses` [INFERRED]
- [[RuleThresholds]] - `uses` [INFERRED]
- [[TestRule6ClaimDeliveryRatio]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users