---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\amount_calculator\tests\test_calculator.py"
type: "rationale"
community: "C: Users"
location: "L193"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 无还款时，all_repayments_attributed 为 True（空集合满足全称命题）。

## Connections
- [[.test_all_attributed_when_no_repayments()]] - `rationale_for` [EXTRACTED]
- [[AmountCalculator]] - `uses` [INFERRED]
- [[AmountCalculatorInput]] - `uses` [INFERRED]
- [[AmountClaimDescriptor]] - `uses` [INFERRED]
- [[RuleThresholds]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users