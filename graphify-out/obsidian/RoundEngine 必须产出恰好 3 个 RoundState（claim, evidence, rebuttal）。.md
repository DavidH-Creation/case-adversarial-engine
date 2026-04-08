---
source_file: "C:\Users\david\dev\case-adversarial-engine\tests\integration\test_adversarial_pipeline.py"
type: "rationale"
community: "C: Users"
location: "L256"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# RoundEngine 必须产出恰好 3 个 RoundState（claim, evidence, rebuttal）。

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
- [[test_round_engine_produces_three_rounds()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users