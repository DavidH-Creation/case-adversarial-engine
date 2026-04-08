---
source_file: "C:\Users\david\dev\case-adversarial-engine\tests\integration\test_adversarial_pipeline.py"
type: "rationale"
community: "C: Users"
location: "L232"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 完整对抗流程 happy path：EvidenceIndex → RoundEngine → AdversarialResult（含 summary）。

## Connections
- [[AccessController]] - `uses` [INFERRED]
- [[AdversarialResult]] - `uses` [INFERRED]
- [[AdversarialSummary]] - `uses` [INFERRED]
- [[EvidenceIndexer]] - `uses` [INFERRED]
- [[IssueExtractor]] - `uses` [INFERRED]
- [[RoundConfig]] - `uses` [INFERRED]
- [[RoundEngine]] - `uses` [INFERRED]
- [[RoundPhase]] - `uses` [INFERRED]
- [[SequentialMockLLMClient]] - `uses` [INFERRED]
- [[test_adversarial_pipeline_happy_path()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users