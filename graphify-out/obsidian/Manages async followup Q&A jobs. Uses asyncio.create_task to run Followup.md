---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\service.py"
type: "rationale"
community: "C: Users"
location: "L1149"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# Manages async followup Q&A jobs. Uses asyncio.create_task to run Followup

## Connections
- [[AccessController]] - `uses` [INFERRED]
- [[AdversarialResult]] - `uses` [INFERRED]
- [[AdversarialSummarizer]] - `uses` [INFERRED]
- [[CaseEvent]] - `uses` [INFERRED]
- [[CaseIndex]] - `uses` [INFERRED]
- [[CaseIndexEntry]] - `uses` [INFERRED]
- [[CaseStatus]] - `uses` [INFERRED]
- [[ClaudeCLIClient]] - `uses` [INFERRED]
- [[DefendantAgent]] - `uses` [INFERRED]
- [[EventType]] - `uses` [INFERRED]
- [[EvidenceIndexer]] - `uses` [INFERRED]
- [[EvidenceManagerAgent]] - `uses` [INFERRED]
- [[EvidenceStateMachine]] - `uses` [INFERRED]
- [[FollowupJobManager]] - `rationale_for` [EXTRACTED]
- [[FollowupResponder]] - `uses` [INFERRED]
- [[FollowupStatus]] - `uses` [INFERRED]
- [[IssueExtractor]] - `uses` [INFERRED]
- [[PlaintiffAgent]] - `uses` [INFERRED]
- [[ReviewStatus]] - `uses` [INFERRED]
- [[RoundConfig]] - `uses` [INFERRED]
- [[RoundEngine]] - `uses` [INFERRED]
- [[RoundPhase]] - `uses` [INFERRED]
- [[RoundState]] - `uses` [INFERRED]
- [[ScenarioInput]] - `uses` [INFERRED]
- [[ScenarioSimulator]] - `uses` [INFERRED]
- [[ScenarioStatus]] - `uses` [INFERRED]
- [[SessionManager]] - `uses` [INFERRED]
- [[WorkspaceManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users