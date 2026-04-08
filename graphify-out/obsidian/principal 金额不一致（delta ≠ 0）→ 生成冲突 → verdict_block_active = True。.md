---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\amount_calculator\tests\test_calculator.py"
type: "rationale"
community: "C: Users"
location: "L350"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# principal 金额不一致（delta ≠ 0）→ 生成冲突 → verdict_block_active = True。

## Connections
- [[.test_verdict_block_when_principal_mismatch()]] - `rationale_for` [EXTRACTED]
- [[AmountCalculator]] - `uses` [INFERRED]
- [[AmountCalculatorInput]] - `uses` [INFERRED]
- [[AmountClaimDescriptor]] - `uses` [INFERRED]
- [[RuleThresholds]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users