---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\hearing_order\schemas.py"
type: "rationale"
community: "C: Users"
location: "L88"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/C:_Users
---

# 庭审顺序建议产物。 合约保证： - issue_presentation_order 包含所有输入争点（无遗漏） - phas

## Connections
- [[ExtractionParty]] - `rationale_for` [EXTRACTED]
- [[HearingOrderResult]] - `rationale_for` [EXTRACTED]
- [[IssueDependencyGraph]] - `uses` [INFERRED]

#graphify/rationale #graphify/EXTRACTED #community/C:_Users