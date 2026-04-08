---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\report_generation\schemas.py"
type: "code"
community: "C: Users"
location: "L50"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# MatrixRow

## Connections
- [[3 issues, each with 2 evidence and 1 defense → 3 rows, correct counts.]] - `uses` [INFERRED]
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[Each matrix row appears as a markdown table row with correct values.]] - `uses` [INFERRED]
- [[Empty issue_impact renders as '-'.]] - `uses` [INFERRED]
- [[Empty issues list → None.]] - `uses` [INFERRED]
- [[Evidence with multiple target_issue_ids appears in all target rows.]] - `uses` [INFERRED]
- [[Extract .value from enum or return str; default to empty string.]] - `uses` [INFERRED]
- [[Full generate() call with defense_chain → report has matrix section.]] - `uses` [INFERRED]
- [[Issue with both evidence and defense → has_unrebutted_evidence=False.]] - `uses` [INFERRED]
- [[Issue with evidence but no defense → has_unrebutted_evidence=True.]] - `uses` [INFERRED]
- [[Issue with no associated evidence → evidence_ids=, count=0, has_unrebutted=Fal]] - `uses` [INFERRED]
- [[Issues without outcome_impact → impact='', sorted to end.]] - `uses` [INFERRED]
- [[Markdown includes correct table column headers.]] - `uses` [INFERRED]
- [[Mock Evidence-like object._1]] - `uses` [INFERRED]
- [[Mock Issue-like object.]] - `uses` [INFERRED]
- [[None issue_tree → None.]] - `uses` [INFERRED]
- [[Number of data rows in markdown equals len(matrix.rows).]] - `uses` [INFERRED]
- [[Rendered markdown includes the section header.]] - `uses` [INFERRED]
- [[Rows must be sorted high → medium → low.]] - `uses` [INFERRED]
- [[TestBuildMatrix]] - `uses` [INFERRED]
- [[TestMatrixIntegrationWithGenerator]] - `uses` [INFERRED]
- [[TestRenderMatrixMarkdown]] - `uses` [INFERRED]
- [[TestSafeEnumValue]] - `uses` [INFERRED]
- [[When EvidenceIndex has no match, fall back to Issue.evidence_ids.]] - `uses` [INFERRED]
- [[defense_chain=None → all rows have empty defense_ids, matrix still built.]] - `uses` [INFERRED]
- [[generate() without defense_chain also produces matrix section.]] - `uses` [INFERRED]
- [[has_unrebutted_evidence=True renders as '是'.]] - `uses` [INFERRED]
- [[issue_evidence_defense_matrix 单元测试。 Tests for engines.report_generation.issue_e]] - `uses` [INFERRED]
- [[issues_with_evidence counts only issues that have ≥1 evidence.]] - `uses` [INFERRED]
- [[schemas.py]] - `contains` [EXTRACTED]
- [[争点-证据-抗辩矩阵聚合模块。 Issue-Evidence-Defense Matrix aggregation module. 从 IssueTre]] - `uses` [INFERRED]
- [[从 IssueTree × EvidenceIndex × DefenseChain 构建三维关联矩阵。 Build a three-dimens]] - `uses` [INFERRED]
- [[渲染矩阵为 Markdown 表格。 Render matrix as a Markdown table. Returns]] - `uses` [INFERRED]
- [[矩阵单行：一个争点及其关联证据和抗辩点。 Matrix row one issue with associated evidence IDs and]] - `rationale_for` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/C:_Users