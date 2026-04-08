---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\defense_chain\tests\test_optimizer.py"
type: "rationale"
community: "C: Users"
location: "L436"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# LLM 调用失败时返回降级结果，不抛异常。

## Connections
- [[DefenseChainInput]] - `uses` [INFERRED]
- [[DefenseChainOptimizer]] - `uses` [INFERRED]
- [[DefenseChainResult]] - `uses` [INFERRED]
- [[DefensePoint]] - `uses` [INFERRED]
- [[LLMDefenseChainOutput]] - `uses` [INFERRED]
- [[LLMDefensePointOutput]] - `uses` [INFERRED]
- [[PlaintiffDefenseChain]] - `uses` [INFERRED]
- [[TestLLMFailureHandling_2]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users