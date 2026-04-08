---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\shared\tests\test_progress_reporter.py"
type: "rationale"
community: "C: Users"
location: "L87"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# Happy path 5-step pipeline → 5 'completed' lines in order.

## Connections
- [[.test_full_pipeline_happy_path()]] - `rationale_for` [EXTRACTED]
- [[CLIProgressReporter]] - `uses` [INFERRED]
- [[JSONProgressReporter]] - `uses` [INFERRED]
- [[SSEProgressReporter]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users