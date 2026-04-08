---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\amount_calculator\tests\test_calculator.py"
type: "rationale"
community: "C: Users"
location: "L618"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# contract_validity=invalid but no lpr_rate → skip + conflict warning。

## Connections
- [[.test_no_recalculation_without_lpr_rate()]] - `rationale_for` [EXTRACTED]
- [[AmountCalculator]] - `uses` [INFERRED]
- [[AmountCalculatorInput]] - `uses` [INFERRED]
- [[AmountClaimDescriptor]] - `uses` [INFERRED]
- [[RuleThresholds]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users