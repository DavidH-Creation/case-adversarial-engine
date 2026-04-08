---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\document_assistance\tests\test_schemas.py"
type: "rationale"
community: "C: Users"
location: "L106"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# evidence_ids_cited 字段是必填字段，缺失时 ValidationError。

## Connections
- [[.test_evidence_ids_cited_required()]] - `rationale_for` [EXTRACTED]
- [[CrossExaminationOpinion]] - `uses` [INFERRED]
- [[CrossExaminationOpinionItem]] - `uses` [INFERRED]
- [[DefenseStatement]] - `uses` [INFERRED]
- [[DocumentAssistanceInput]] - `uses` [INFERRED]
- [[DocumentDraft]] - `uses` [INFERRED]
- [[DocumentGenerationError]] - `uses` [INFERRED]
- [[PleadingDraft]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users