---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\hearing_order\generator.py"
type: "rationale"
community: "C: Users"
location: "L54"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 庭审顺序建议生成器。 纯规则层，不持有外部状态，可安全复用同一实例。 使用方式 Usage generato

## Connections
- [[HearingOrderGenerator]] - `rationale_for` [EXTRACTED]
- [[HearingOrderInput]] - `uses` [INFERRED]
- [[HearingOrderResult]] - `uses` [INFERRED]
- [[HearingPhase]] - `uses` [INFERRED]
- [[IssueTimeEstimate]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users