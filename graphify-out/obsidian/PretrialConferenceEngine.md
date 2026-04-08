---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\pretrial_conference\conference_engine.py"
type: "code"
community: "C: Users"
location: "L41"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# PretrialConferenceEngine

## Connections
- [[.__init__()_36]] - `method` [EXTRACTED]
- [[.run()_2]] - `method` [EXTRACTED]
- [[Add case_id and owner_party_id to claim dicts.]] - `uses` [INFERRED]
- [[Add case_id and owner_party_id to defense dicts.]] - `uses` [INFERRED]
- [[Build EvidenceGapDescriptor list for P1.7 from two sources 1. Rule-based]] - `uses` [INFERRED]
- [[Convert YAML financials section to AmountCalculatorInput. Returns None if no fin]] - `uses` [INFERRED]
- [[Convert YAML material dicts to RawMaterial objects.]] - `uses` [INFERRED]
- [[Create a minimal Evidence object for testing.]] - `uses` [INFERRED]
- [[CrossExaminationEngine]] - `uses` [INFERRED]
- [[CrossExaminationResult]] - `uses` [INFERRED]
- [[DecisionPathTreeGenerator would reject evidence_index with private evidence]] - `uses` [INFERRED]
- [[Derive evidence gap indicators from pretrial cross-examination results. U]] - `uses` [INFERRED]
- [[EvidenceStateMachine]] - `uses` [INFERRED]
- [[JudgeAgent]] - `uses` [INFERRED]
- [[JudgeQuestionSet]] - `uses` [INFERRED]
- [[LLM 全部失败仍返回 PretrialConferenceResult（空内容）。]] - `uses` [INFERRED]
- [[Legacy promote directly set private → admitted_for_discussion (bypass state mac]] - `uses` [INFERRED]
- [[Load and validate a YAML case file.]] - `uses` [INFERRED]
- [[Load pipeline section from config.yaml at project root. Returns {} if missing.]] - `uses` [INFERRED]
- [[Pretrial LLM failure → conference returns partial results without raising.]] - `uses` [INFERRED]
- [[Pretrial conference executes → evidence progresses through state machine.]] - `uses` [INFERRED]
- [[Pretrial with no evidence IDs submitted → conference returns empty results grace]] - `uses` [INFERRED]
- [[PretrialConferenceEngine 集成测试。]] - `uses` [INFERRED]
- [[PretrialConferenceResult]] - `uses` [INFERRED]
- [[Return True if step was already completed according to checkpoint.]] - `uses` [INFERRED]
- [[Run 3-round adversarial debate.]] - `uses` [INFERRED]
- [[Run post-debate analysis pipeline. Returns dict of all artifacts.]] - `uses` [INFERRED]
- [[Stage 1 指定的 private 证据 → submitted。]] - `uses` [INFERRED]
- [[Status ordering private submitted challenged admitted_for_discussion.]] - `uses` [INFERRED]
- [[TestEvidenceSubmission]] - `uses` [INFERRED]
- [[TestFullPipeline]] - `uses` [INFERRED]
- [[TestLLMFailureGraceful]] - `uses` [INFERRED]
- [[TestNoEvidenceToSubmit]] - `uses` [INFERRED]
- [[conference_engine.py]] - `contains` [EXTRACTED]
- [[enforce_minimum_status only checks specified evidence_ids.]] - `uses` [INFERRED]
- [[enforce_minimum_status passes when all evidence meets threshold.]] - `uses` [INFERRED]
- [[enforce_minimum_status raises EvidenceStatusViolation for evidence below thresho]] - `uses` [INFERRED]
- [[全链路：private → submitted → admitted → judge questions。]] - `uses` [INFERRED]
- [[创建 engine + mock LLM。 LLM side_effect - 1st call cross-exam for pl]] - `uses` [INFERRED]
- [[庭前会议编排器。 Args llm_client 符合 LLMClient 协议的客户端实例 model]] - `rationale_for` [EXTRACTED]
- [[构建全部 accepted 的质证 LLM 响应。]] - `uses` [INFERRED]
- [[证据经历 private → submitted → admitted_for_discussion。]] - `uses` [INFERRED]
- [[集成测试 — pretrial conference 接入主 pipeline + evidence_state_machine 全链路 enforce。 I]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users