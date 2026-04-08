---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\amount_calculator\tests\test_calculator.py"
type: "rationale"
community: "C: Users"
location: "L218"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 放款 5 万 - 还款 1 万 = 4 万，但 claimed 3.5 万 → inconsistent。

## Connections
- [[.test_inconsistent_when_principal_mismatches()]] - `rationale_for` [EXTRACTED]
- [[AmountCalculator]] - `uses` [INFERRED]
- [[AmountCalculatorInput]] - `uses` [INFERRED]
- [[AmountClaimDescriptor]] - `uses` [INFERRED]
- [[RuleThresholds]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users