---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\report_generation\tests\test_matrix.py"
type: "rationale"
community: "C: Users"
location: "L173"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# defense_chain=None → all rows have empty defense_ids, matrix still built.

## Connections
- [[.test_no_defense_chain_all_rows_empty_defense()]] - `rationale_for` [EXTRACTED]
- [[IssueEvidenceDefenseMatrix]] - `uses` [INFERRED]
- [[MatrixRow]] - `uses` [INFERRED]
- [[ReportGenerator]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users