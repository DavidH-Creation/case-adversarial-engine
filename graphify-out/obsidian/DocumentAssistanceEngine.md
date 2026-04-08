---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\document_assistance\engine.py"
type: "code"
community: "C: Users"
location: "L68"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# DocumentAssistanceEngine

## Connections
- [[.__init__()_29]] - `method` [EXTRACTED]
- [[.generate()]] - `method` [EXTRACTED]
- [[Add case_id and owner_party_id to claim dicts.]] - `uses` [INFERRED]
- [[Add case_id and owner_party_id to defense dicts.]] - `uses` [INFERRED]
- [[Build EvidenceGapDescriptor list for P1.7 from two sources 1. Rule-based]] - `uses` [INFERRED]
- [[Convert YAML financials section to AmountCalculatorInput. Returns None if no fin]] - `uses` [INFERRED]
- [[Convert YAML material dicts to RawMaterial objects.]] - `uses` [INFERRED]
- [[CrossExaminationOpinion]] - `uses` [INFERRED]
- [[CrossExaminationOpinionItem]] - `uses` [INFERRED]
- [[DefenseStatement]] - `uses` [INFERRED]
- [[Derive evidence gap indicators from pretrial cross-examination results. U]] - `uses` [INFERRED]
- [[DocumentAssistanceInput]] - `uses` [INFERRED]
- [[DocumentDraft]] - `uses` [INFERRED]
- [[DocumentGenerationError]] - `uses` [INFERRED]
- [[EvidenceIndex 为空 → CrossExaminationOpinion items=, 不抛错, 不调 LLM。]] - `uses` [INFERRED]
- [[LLM 在 evidence_ids_cited 中引用但 items 里缺少 → engine 补充占位条目。]] - `uses` [INFERRED]
- [[LLM 所有重试均失败 → DocumentGenerationError，含 doc_type 和 case_type。]] - `uses` [INFERRED]
- [[LLM 返回 evidence_ids_cited= → DocumentGenerationError。]] - `uses` [INFERRED]
- [[LLM 返回无法解析为 schema 的 JSON → DocumentGenerationError，含 doc_type 和 case_type。]] - `uses` [INFERRED]
- [[Load and validate a YAML case file.]] - `uses` [INFERRED]
- [[Load pipeline section from config.yaml at project root. Returns {} if missing.]] - `uses` [INFERRED]
- [[MockLLMClient_5]] - `uses` [INFERRED]
- [[OptimalAttackChain 产物缺失 → attack_chain_basis= unavailable 。]] - `uses` [INFERRED]
- [[PROMPT_REGISTRY 覆盖全部 9 个 (doc_type, case_type) 组合。]] - `uses` [INFERRED]
- [[PleadingDraft]] - `uses` [INFERRED]
- [[Return True if step was already completed according to checkpoint.]] - `uses` [INFERRED]
- [[Run 3-round adversarial debate.]] - `uses` [INFERRED]
- [[Run post-debate analysis pipeline. Returns dict of all artifacts.]] - `uses` [INFERRED]
- [[TestCrossExaminationOpinionHappyPath]] - `uses` [INFERRED]
- [[TestDefenseStatementHappyPath]] - `uses` [INFERRED]
- [[TestEdgeCases_1]] - `uses` [INFERRED]
- [[TestErrorPaths]] - `uses` [INFERRED]
- [[TestPleadingDraftHappyPath]] - `uses` [INFERRED]
- [[TestPromptRegistryCoverage]] - `uses` [INFERRED]
- [[engine.py]] - `contains` [EXTRACTED]
- [[labor_dispute DefenseStatement defense_claim_items 包含 ≥1 条回应原告主张的条目。]] - `uses` [INFERRED]
- [[real_estate CrossExaminationOpinion 针对每个 evidence_id 生成恰好 1 条意见。]] - `uses` [INFERRED]
- [[所有 DocumentGenerationError 的消息都包含 doc_type 和 case_type。]] - `uses` [INFERRED]
- [[所有 build_user_prompt 函数返回非空字符串。]] - `uses` [INFERRED]
- [[文书辅助引擎。 Args llm_client 符合 LLMClient 协议的客户端实例 model]] - `rationale_for` [EXTRACTED]
- [[文书辅助引擎单元测试。 Unit tests for DocumentAssistanceEngine. 使用 mock LLM 客户端验证 Tes]] - `uses` [INFERRED]
- [[未注册的 (doc_type, case_type) → DocumentGenerationError。]] - `uses` [INFERRED]
- [[返回预定义 JSON 响应的 mock LLM 客户端。_3]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users