---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\action_recommender\schemas.py"
type: "code"
community: "C: Users"
location: "L28"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# ActionRecommenderInput

## Connections
- [[ActionRecommender]] - `uses` [INFERRED]
- [[ActionRecommender — 行动建议引擎主类（P1.8）。 Action Recommender — hybrid (rule-based + o]] - `uses` [INFERRED]
- [[ActionRecommender 单元测试（P1.8）。 测试策略： - 使用 Pydantic 模型构建测试数据（不用 Mock） - 验证每个规]] - `uses` [INFERRED]
- [[ActionRecommender 输入 wrapper。 Args case_id]] - `rationale_for` [EXTRACTED]
- [[ActionRecommenderInput accepts decision_path_tree.]] - `uses` [INFERRED]
- [[ActionRecommenderInput accepts non-empty evidence_gap_list.]] - `uses` [INFERRED]
- [[Add case_id and owner_party_id to claim dicts.]] - `uses` [INFERRED]
- [[Add case_id and owner_party_id to defense dicts.]] - `uses` [INFERRED]
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[Build EvidenceGapDescriptor list for P1.7 from two sources 1. Rule-based]] - `uses` [INFERRED]
- [[Build a minimal PretrialConferenceResult with optional focus items.]] - `uses` [INFERRED]
- [[Convert YAML financials section to AmountCalculatorInput. Returns None if no fin]] - `uses` [INFERRED]
- [[Convert YAML material dicts to RawMaterial objects.]] - `uses` [INFERRED]
- [[Derive evidence gap indicators from pretrial cross-examination results. U]] - `uses` [INFERRED]
- [[Empty focus list → empty gaps, no crash.]] - `uses` [INFERRED]
- [[ExecutiveSummarizerInput accepts decision_path_tree.]] - `uses` [INFERRED]
- [[ExecutiveSummarizerInput accepts defense_chain_result.]] - `uses` [INFERRED]
- [[ExecutiveSummarizerInput accepts evidence_gap_items from conference.]] - `uses` [INFERRED]
- [[ExecutiveSummaryArtifact includes defense_chain_id when defense chain provided.]] - `uses` [INFERRED]
- [[Load and validate a YAML case file.]] - `uses` [INFERRED]
- [[Load pipeline section from config.yaml at project root. Returns {} if missing.]] - `uses` [INFERRED]
- [[No conference result → empty gap list.]] - `uses` [INFERRED]
- [[Resolved focus items are excluded from evidence gaps.]] - `uses` [INFERRED]
- [[Return True if step was already completed according to checkpoint.]] - `uses` [INFERRED]
- [[Risk assessment does not mention defense when chain is None.]] - `uses` [INFERRED]
- [[Risk assessment text includes defense chain info when available.]] - `uses` [INFERRED]
- [[Run 3-round adversarial debate.]] - `uses` [INFERRED]
- [[Run post-debate analysis pipeline. Returns dict of all artifacts.]] - `uses` [INFERRED]
- [[Test evidence gap derivation from pretrial cross-examination results.]] - `uses` [INFERRED]
- [[TestActionRecommenderDataFlow]] - `uses` [INFERRED]
- [[TestBasicBehavior]] - `uses` [INFERRED]
- [[TestClaimsToAbandon]] - `uses` [INFERRED]
- [[TestDeriveEvidenceGaps]] - `uses` [INFERRED]
- [[TestDisputeCategoryDetection]] - `uses` [INFERRED]
- [[TestEvidenceSupplementPriorities]] - `uses` [INFERRED]
- [[TestExecutiveSummarizerDataFlow]] - `uses` [INFERRED]
- [[TestMixedScenario]] - `uses` [INFERRED]
- [[TestPipelineWiring]] - `uses` [INFERRED]
- [[TestRecommendedClaimAmendments]] - `uses` [INFERRED]
- [[TestTrialExplanationPriorities]] - `uses` [INFERRED]
- [[Unresolved focus items become evidence gap items.]] - `uses` [INFERRED]
- [[Verify _run_post_debate accepts conference_result parameter.]] - `uses` [INFERRED]
- [[Verify defense chain, decision tree, and evidence gaps flow to ExecutiveSummariz]] - `uses` [INFERRED]
- [[Verify evidence gaps and decision tree flow to ActionRecommenderInput.]] - `uses` [INFERRED]
- [[Verify evidence_gap_items=None is no longer hardcoded in run_case.py source.]] - `uses` [INFERRED]
- [[Verify evidence_gap_list= is no longer hardcoded in run_case.py source.]] - `uses` [INFERRED]
- [[_run_post_debate has conference_result parameter.]] - `uses` [INFERRED]
- [[conference_result defaults to None for backward compatibility.]] - `uses` [INFERRED]
- [[defense_chain_id is None when no defense chain provided.]] - `uses` [INFERRED]
- [[schemas.py]] - `contains` [EXTRACTED]
- [[supplement_evidence 争点不会出现在 amendments 或 claims_to_abandon 中。]] - `uses` [INFERRED]
- [[为每条行动建议标注受影响的裁判路径 ID。 逻辑：若行动绑定的 issue_id 出现在某条路径的 trigger_issue_ids 中]] - `uses` [INFERRED]
- [[争点有 amend_claim 但 related_claim_ids 为空时，不生成建议。]] - `uses` [INFERRED]
- [[从 evidence_gap_list 按 roi_rank 升序排序，返回 gap_id 列表。]] - `uses` [INFERRED]
- [[从 recommended_action=abandon 的争点派生放弃建议。]] - `uses` [INFERRED]
- [[从 recommended_action=amend_claim 的争点派生修改建议。]] - `uses` [INFERRED]
- [[从 recommended_action=explain_in_trial 的争点派生庭审解释优先事项。]] - `uses` [INFERRED]
- [[当规则层 trial_explanations 不足时，按案型注入补充建议。 保守策略： - 仅当 existing 数]] - `uses` [INFERRED]
- [[所有四种 recommended_action 同时存在时，正确分发。]] - `uses` [INFERRED]
- [[手动编排三轮对抗，允许为每个代理分配不同的 LLM 客户端。]] - `uses` [INFERRED]
- [[执行行动建议聚合，返回 ActionRecommendation。 Args inp 引擎输入（含 case]] - `uses` [INFERRED]
- [[最小合法 AmountCalculationReport（无流水记录，仅满足 Pydantic 约束）。]] - `uses` [INFERRED]
- [[根据路径树整体态势调整策略建议。 修订清单一-3 一-6： - 若最可能路径对被告有利，原告建议自动下调（去除攻击性表述]] - `uses` [INFERRED]
- [[行动建议引擎（P1.8）。 支持两种模式： - 纯规则层（llm_client=None）：等价于 v1，零 LLM 调用 -]] - `uses` [INFERRED]
- [[解析 LLM 策略层输出，校验后返回结构化结果。]] - `uses` [INFERRED]
- [[调用 LLM 生成 party-specific 策略建议。失败返回 None。]] - `uses` [INFERRED]
- [[集成测试 — 模块间数据流断点修复验证 (Unit 7)。 Integration tests — inter-module data flow breakp]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users