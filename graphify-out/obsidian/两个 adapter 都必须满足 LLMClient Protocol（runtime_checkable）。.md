---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\shared\tests\test_cli_adapter.py"
type: "rationale"
community: "C: Users"
location: "L35"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 两个 adapter 都必须满足 LLMClient Protocol（runtime_checkable）。

## Connections
- [[CLICallError]] - `uses` [INFERRED]
- [[CLINotFoundError]] - `uses` [INFERRED]
- [[ClaudeCLIClient]] - `uses` [INFERRED]
- [[CodexCLIClient]] - `uses` [INFERRED]
- [[TestProtocolCompliance]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users