---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\tests\test_simulator.py"
type: "rationale"
community: "C: Users"
location: "L552"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# LLM 所有重试均失败应返回 status='failed' 的 ScenarioResult，不抛出异常。 Exhausted retries sh

## Connections
- [[ScenarioInput]] - `uses` [INFERRED]
- [[ScenarioResult]] - `uses` [INFERRED]
- [[ScenarioSimulator]] - `uses` [INFERRED]
- [[ScenarioStatus]] - `uses` [INFERRED]
- [[test_llm_retry_exhausted_returns_failed_result()_1]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users