---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\shared\tests\test_progress_reporter.py"
type: "rationale"
community: "C: Users"
location: "L36"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# Drain all events from a progress queue synchronously.

## Connections
- [[CLIProgressReporter]] - `uses` [INFERRED]
- [[JSONProgressReporter]] - `uses` [INFERRED]
- [[SSEProgressReporter]] - `uses` [INFERRED]
- [[_drain()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users