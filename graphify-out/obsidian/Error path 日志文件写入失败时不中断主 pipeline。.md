---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\shared\tests\test_logging_config.py"
type: "rationale"
community: "C: Users"
location: "L310"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# Error path 日志文件写入失败时不中断主 pipeline。

## Connections
- [[.test_log_file_write_failure_does_not_crash()]] - `rationale_for` [EXTRACTED]
- [[ClaudeCLIClient]] - `uses` [INFERRED]
- [[CodexCLIClient]] - `uses` [INFERRED]
- [[JsonFormatter]] - `uses` [INFERRED]
- [[LLMCallRecord]] - `uses` [INFERRED]
- [[TokenTracker]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users