---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\amount_calculator\tests\test_calculator.py"
type: "rationale"
community: "C: Users"
location: "L399"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# interest 类诉请无法从流水确定性计算 → calculated_amount = None，delta = None。

## Connections
- [[.test_interest_claim_has_no_calculated_amount()]] - `rationale_for` [EXTRACTED]
- [[AmountCalculator]] - `uses` [INFERRED]
- [[AmountCalculatorInput]] - `uses` [INFERRED]
- [[AmountClaimDescriptor]] - `uses` [INFERRED]
- [[RuleThresholds]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users