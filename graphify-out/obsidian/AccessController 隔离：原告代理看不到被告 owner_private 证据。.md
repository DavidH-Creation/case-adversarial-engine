---
source_file: "C:\Users\david\dev\case-adversarial-engine\tests\integration\test_adversarial_pipeline.py"
type: "rationale"
community: "C: Users"
location: "L310"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# AccessController 隔离：原告代理看不到被告 owner_private 证据。

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
- [[test_access_controller_plaintiff_cannot_see_defendant_private()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users