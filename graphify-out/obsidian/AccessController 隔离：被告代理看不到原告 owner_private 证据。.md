---
source_file: "C:\Users\david\dev\case-adversarial-engine\tests\integration\test_adversarial_pipeline.py"
type: "rationale"
community: "C: Users"
location: "L329"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# AccessController 隔离：被告代理看不到原告 owner_private 证据。

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
- [[test_access_controller_defendant_cannot_see_plaintiff_private()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users