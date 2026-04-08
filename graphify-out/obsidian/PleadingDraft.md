---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\document_assistance\schemas.py"
type: "code"
community: "C: Users"
location: "L60"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# PleadingDraft

## Connections
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[DocumentAssistanceEngine]] - `uses` [INFERRED]
- [[DocumentDraft 可序列化为 JSON 再还原。]] - `uses` [INFERRED]
- [[EvidenceIndex 为空 → CrossExaminationOpinion items=, 不抛错, 不调 LLM。]] - `uses` [INFERRED]
- [[LLM 在 evidence_ids_cited 中引用但 items 里缺少 → engine 补充占位条目。]] - `uses` [INFERRED]
- [[LLM 所有重试均失败 → DocumentGenerationError，含 doc_type 和 case_type。]] - `uses` [INFERRED]
- [[LLM 返回 evidence_ids_cited= → DocumentGenerationError。]] - `uses` [INFERRED]
- [[LLM 返回无法解析为 schema 的 JSON → DocumentGenerationError，含 doc_type 和 case_type。]] - `uses` [INFERRED]
- [[MockLLMClient_5]] - `uses` [INFERRED]
- [[OptimalAttackChain 产物缺失 → attack_chain_basis= unavailable 。]] - `uses` [INFERRED]
- [[PROMPT_REGISTRY 覆盖全部 9 个 (doc_type, case_type) 组合。]] - `uses` [INFERRED]
- [[TestCrossExaminationOpinion]] - `uses` [INFERRED]
- [[TestCrossExaminationOpinionHappyPath]] - `uses` [INFERRED]
- [[TestDefenseStatement]] - `uses` [INFERRED]
- [[TestDefenseStatementHappyPath]] - `uses` [INFERRED]
- [[TestDocumentAssistanceInput]] - `uses` [INFERRED]
- [[TestDocumentDraft]] - `uses` [INFERRED]
- [[TestDocumentGenerationError]] - `uses` [INFERRED]
- [[TestEdgeCases_1]] - `uses` [INFERRED]
- [[TestErrorPaths]] - `uses` [INFERRED]
- [[TestPleadingDraft]] - `uses` [INFERRED]
- [[TestPleadingDraftHappyPath]] - `uses` [INFERRED]
- [[TestPromptRegistryCoverage]] - `uses` [INFERRED]
- [[evidence_ids_cited 字段是必填字段，缺失时 ValidationError。]] - `uses` [INFERRED]
- [[issue_dependency_graph schemas 单元测试。 Unit tests for issue_dependency_graph sche]] - `uses` [INFERRED]
- [[items 默认为空列表（EvidenceIndex 为空时的边界情况）。]] - `uses` [INFERRED]
- [[labor_dispute DefenseStatement defense_claim_items 包含 ≥1 条回应原告主张的条目。]] - `uses` [INFERRED]
- [[real_estate CrossExaminationOpinion 针对每个 evidence_id 生成恰好 1 条意见。]] - `uses` [INFERRED]
- [[schemas.py]] - `contains` [EXTRACTED]
- [[将 LLM 返回的 dict 解析为对应的文书骨架模型。 Parse LLM-returned dict into the corresponding]] - `uses` [INFERRED]
- [[所有 DocumentGenerationError 的消息都包含 doc_type 和 case_type。]] - `uses` [INFERRED]
- [[所有 build_user_prompt 函数返回非空字符串。]] - `uses` [INFERRED]
- [[文书辅助引擎。 Args llm_client 符合 LLMClient 协议的客户端实例 model]] - `uses` [INFERRED]
- [[文书辅助引擎主类。 Document assistance engine main class. 职责 Responsibilities 1.]] - `uses` [INFERRED]
- [[文书辅助引擎单元测试。 Unit tests for DocumentAssistanceEngine. 使用 mock LLM 客户端验证 Tes]] - `uses` [INFERRED]
- [[未注册的 (doc_type, case_type) → DocumentGenerationError。]] - `uses` [INFERRED]
- [[每个 evidence_id 对应恰好 1 条意见。]] - `uses` [INFERRED]
- [[生成一份结构化文书草稿。 Generate a structured document draft. Args]] - `uses` [INFERRED]
- [[起诉状骨架 — 原告方使用。 Pleading draft skeleton — used by plaintiff.]] - `rationale_for` [EXTRACTED]
- [[返回预定义 JSON 响应的 mock LLM 客户端。_3]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users