---
source_file: "C:\Users\david\dev\case-adversarial-engine\tests\integration\conftest.py"
type: "code"
community: "C: Users"
location: "L69"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# SequentialMockLLMClient

## Connections
- [[.__init__()_81]] - `method` [EXTRACTED]
- [[.create_message()_24]] - `method` [EXTRACTED]
- [[6 条响应：原告主张、被告主张、证据整理、原告反驳、被告反驳、总结。]] - `uses` [INFERRED]
- [[AccessController 隔离：原告代理看不到被告 owner_private 证据。]] - `uses` [INFERRED]
- [[AccessController 隔离：被告代理看不到原告 owner_private 证据。]] - `uses` [INFERRED]
- [[AdversarialSummary 必须包含所有 5 个必要字段且非空。]] - `uses` [INFERRED]
- [[Create a minimal Evidence object for testing.]] - `uses` [INFERRED]
- [[DecisionPathTreeGenerator would reject evidence_index with private evidence]] - `uses` [INFERRED]
- [[Legacy promote directly set private → admitted_for_discussion (bypass state mac]] - `uses` [INFERRED]
- [[Pretrial LLM failure → conference returns partial results without raising.]] - `uses` [INFERRED]
- [[Pretrial conference executes → evidence progresses through state machine.]] - `uses` [INFERRED]
- [[Pretrial with no evidence IDs submitted → conference returns empty results grace]] - `uses` [INFERRED]
- [[RoundEngine 必须产出恰好 3 个 RoundState（claim, evidence, rebuttal）。]] - `uses` [INFERRED]
- [[Status ordering private submitted challenged admitted_for_discussion.]] - `uses` [INFERRED]
- [[_SingleResponseMock]] - `uses` [INFERRED]
- [[conftest.py]] - `contains` [EXTRACTED]
- [[enforce_minimum_status only checks specified evidence_ids.]] - `uses` [INFERRED]
- [[enforce_minimum_status passes when all evidence meets threshold.]] - `uses` [INFERRED]
- [[enforce_minimum_status raises EvidenceStatusViolation for evidence below thresho]] - `uses` [INFERRED]
- [[全链路：EvidenceIndexer → IssueExtractor → RoundEngine，验证 AccessController 隔离。]] - `uses` [INFERRED]
- [[完整六引擎串联：每步输出能正确作为下一步输入，且各合约不变量均成立。 Full six-engine chain each output feeds]] - `uses` [INFERRED]
- [[完整对抗流程 happy path：EvidenceIndex → RoundEngine → AdversarialResult（含 summary）。]] - `uses` [INFERRED]
- [[按顺序返回不同响应的 mock LLM 客户端（用于多轮追问测试）。 Mock LLM client returning responses sequ]] - `rationale_for` [EXTRACTED]
- [[构造 AdversarialSummarizer 的 LLM mock 响应。]] - `uses` [INFERRED]
- [[构造 EvidenceManagerAgent 的 LLM mock 响应。]] - `uses` [INFERRED]
- [[构造 party agent 的 LLM mock 响应。]] - `uses` [INFERRED]
- [[构造含三类访问域证据的 EvidenceIndex：shared、原告私有、被告私有。]] - `uses` [INFERRED]
- [[端到端对抗流程集成测试 — mock LLM 驱动完整三轮对抗。 End-to-end adversarial pipeline integration te]] - `uses` [INFERRED]
- [[端到端集成测试 — 全链路六引擎串联。 End-to-end integration tests — full six-engine pipeline.]] - `uses` [INFERRED]
- [[运行 EvidenceIndexer，返回 listEvidence。]] - `uses` [INFERRED]
- [[运行 IssueExtractor，返回 IssueTree。]] - `uses` [INFERRED]
- [[运行 ReportGenerator，返回 ReportArtifact。]] - `uses` [INFERRED]
- [[集成测试 — pretrial conference 接入主 pipeline + evidence_state_machine 全链路 enforce。 I]] - `uses` [INFERRED]
- [[验证 Evidence.model_dump() 格式被 IssueExtractor 正确消费，且 evidence_id 字段名保留。 Verif]] - `uses` [INFERRED]
- [[验证 ProcedurePlanner LLM 持续失败时： - 不抛出异常（plan() 内部捕获） - 返回 run.status =]] - `uses` [INFERRED]
- [[验证 ScenarioSimulator.affected_issue_ids ⊆ IssueTree.issues .issue_id。 Ver]] - `uses` [INFERRED]
- [[验证两轮追问： - 第二轮 previous_turns 正确传入（体现在 LLM user prompt 中） - issue_ids 始]] - `uses` [INFERRED]
- [[验证从 listEvidence 手动构建 EvidenceIndex 后，ReportGenerator 零悬空引用。 Verifies zer]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users