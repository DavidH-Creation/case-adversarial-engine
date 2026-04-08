---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\shared\tests\test_logging_config.py"
type: "rationale"
community: "C: Users"
location: "L236"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 日志包含 llm_call 字段（input_tokens output_tokens latency_ms）。

## Connections
- [[.test_format_with_llm_call()]] - `rationale_for` [EXTRACTED]
- [[ClaudeCLIClient]] - `uses` [INFERRED]
- [[CodexCLIClient]] - `uses` [INFERRED]
- [[JsonFormatter]] - `uses` [INFERRED]
- [[LLMCallRecord]] - `uses` [INFERRED]
- [[TokenTracker]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users