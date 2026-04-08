---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\shared\models\civil_loan.py"
type: "rationale"
community: "C: Users"
location: "L204"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 利息重算记录 — 合同无效时的利率切换结果。 注：interest_amount 字段为单期概念金额（principal × rate），用于对比

## Connections
- [[ContractValidity]] - `uses` [INFERRED]
- [[DisputeResolutionStatus]] - `uses` [INFERRED]
- [[InterestRecalculation]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users