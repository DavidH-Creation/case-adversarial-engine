---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\shared\tests\test_logging_config.py"
type: "rationale"
community: "C: Users"
location: "L352"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 验证 cli_adapter 客户端暴露 _last_usage 属性。

## Connections
- [[ClaudeCLIClient]] - `uses` [INFERRED]
- [[CodexCLIClient]] - `uses` [INFERRED]
- [[JsonFormatter]] - `uses` [INFERRED]
- [[LLMCallRecord]] - `uses` [INFERRED]
- [[TestCliAdapterLastUsage]] - `rationale_for` [EXTRACTED]
- [[TokenTracker]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users