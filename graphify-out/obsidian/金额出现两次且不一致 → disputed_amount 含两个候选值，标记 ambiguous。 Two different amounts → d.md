---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\case_extraction\tests\test_extractor.py"
type: "rationale"
community: "C: Users"
location: "L172"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 金额出现两次且不一致 → disputed_amount 含两个候选值，标记 ambiguous。 Two different amounts → d

## Connections
- [[CaseExtractionResult]] - `uses` [INFERRED]
- [[CaseExtractor]] - `uses` [INFERRED]
- [[test_extract_ambiguous_amounts()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users