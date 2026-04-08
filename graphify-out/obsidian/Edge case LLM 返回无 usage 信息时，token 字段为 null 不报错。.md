---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\shared\tests\test_logging_config.py"
type: "rationale"
community: "C: Users"
location: "L55"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# Edge case LLM 返回无 usage 信息时，token 字段为 null 不报错。

## Connections
- [[.test_create_with_null_tokens()]] - `rationale_for` [EXTRACTED]
- [[ClaudeCLIClient]] - `uses` [INFERRED]
- [[CodexCLIClient]] - `uses` [INFERRED]
- [[JsonFormatter]] - `uses` [INFERRED]
- [[LLMCallRecord]] - `uses` [INFERRED]
- [[TokenTracker]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users