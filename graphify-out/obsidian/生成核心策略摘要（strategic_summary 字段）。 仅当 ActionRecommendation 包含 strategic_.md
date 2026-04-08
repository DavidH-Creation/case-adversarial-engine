---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\report_generation\executive_summarizer\summarizer.py"
type: "rationale"
community: "C: Users"
location: "L196"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 生成核心策略摘要（strategic_summary 字段）。 仅当 ActionRecommendation 包含 strategic_

## Connections
- [[._call_llm_with_retry()]] - `rationale_for` [EXTRACTED]
- [[._compute_strategic_summary()]] - `rationale_for` [EXTRACTED]
- [[AdversarialResult]] - `uses` [INFERRED]
- [[AdversarialSummary]] - `uses` [INFERRED]
- [[DefenseChainResult]] - `uses` [INFERRED]
- [[ExecutiveSummarizerInput]] - `uses` [INFERRED]
- [[MissingEvidenceSummary]] - `uses` [INFERRED]
- [[RoundConfig]] - `uses` [INFERRED]
- [[StrongestArgument]] - `uses` [INFERRED]
- [[UnresolvedIssueDetail]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users