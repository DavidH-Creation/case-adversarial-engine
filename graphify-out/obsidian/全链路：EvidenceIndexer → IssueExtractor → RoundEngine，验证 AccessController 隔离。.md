---
source_file: "C:\Users\david\dev\case-adversarial-engine\tests\integration\test_adversarial_pipeline.py"
type: "rationale"
community: "C: Users"
location: "L513"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 全链路：EvidenceIndexer → IssueExtractor → RoundEngine，验证 AccessController 隔离。

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
- [[test_full_pipeline_evidence_indexer_to_round_engine()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users