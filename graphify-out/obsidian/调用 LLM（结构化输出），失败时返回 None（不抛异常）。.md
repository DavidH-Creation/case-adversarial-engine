---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\attack_chain_optimizer\optimizer.py"
type: "rationale"
community: "C: Users"
location: "L150"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 调用 LLM（结构化输出），失败时返回 None（不抛异常）。

## Connections
- [[._call_llm()_4]] - `rationale_for` [EXTRACTED]
- [[AttackChainOptimizerInput]] - `uses` [INFERRED]
- [[EvidenceStateMachine]] - `uses` [INFERRED]
- [[LLMAttackChainOutput]] - `uses` [INFERRED]
- [[LLMAttackNodeItem]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users