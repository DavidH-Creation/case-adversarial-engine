---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\amount_calculator\tests\test_calculator.py"
type: "rationale"
community: "C: Users"
location: "L523"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# No principal_base_contribution=True loans + claimed=0 → skip (both zero)。

## Connections
- [[.test_no_principal_loans_claimed_zero_skips()]] - `rationale_for` [EXTRACTED]
- [[AmountCalculator]] - `uses` [INFERRED]
- [[AmountCalculatorInput]] - `uses` [INFERRED]
- [[AmountClaimDescriptor]] - `uses` [INFERRED]
- [[RuleThresholds]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users