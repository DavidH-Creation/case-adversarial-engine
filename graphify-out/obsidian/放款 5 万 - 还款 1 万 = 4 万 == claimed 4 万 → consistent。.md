---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\amount_calculator\tests\test_calculator.py"
type: "rationale"
community: "C: Users"
location: "L212"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 放款 5 万 - 还款 1 万 = 4 万 == claimed 4 万 → consistent。

## Connections
- [[.test_consistent_when_principal_matches()]] - `rationale_for` [EXTRACTED]
- [[AmountCalculator]] - `uses` [INFERRED]
- [[AmountCalculatorInput]] - `uses` [INFERRED]
- [[AmountClaimDescriptor]] - `uses` [INFERRED]
- [[RuleThresholds]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users