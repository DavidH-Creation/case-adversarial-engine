---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\adversarial\tests\test_round_engine.py"
type: "rationale"
community: "C: Users"
location: "L101"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 按顺序返回不同响应的 mock LLM（模拟真实对话轮次）。 6 次调用： 1. 原告首轮主张 2. 被告首轮抗辩

## Connections
- [[AdversarialResult]] - `uses` [INFERRED]
- [[AdversarialSummary]] - `uses` [INFERRED]
- [[Argument]] - `uses` [INFERRED]
- [[JobManager]] - `uses` [INFERRED]
- [[RoundConfig]] - `uses` [INFERRED]
- [[RoundEngine]] - `uses` [INFERRED]
- [[RoundPhase]] - `uses` [INFERRED]
- [[SequentialMockLLM]] - `rationale_for` [EXTRACTED]
- [[WorkspaceManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users