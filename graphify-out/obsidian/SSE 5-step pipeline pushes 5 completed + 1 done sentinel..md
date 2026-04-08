---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\shared\tests\test_progress_reporter.py"
type: "rationale"
community: "C: Users"
location: "L160"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# SSE 5-step pipeline pushes 5 completed + 1 done sentinel.

## Connections
- [[.test_full_pipeline_happy_path_5_steps()]] - `rationale_for` [EXTRACTED]
- [[CLIProgressReporter]] - `uses` [INFERRED]
- [[JSONProgressReporter]] - `uses` [INFERRED]
- [[SSEProgressReporter]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users