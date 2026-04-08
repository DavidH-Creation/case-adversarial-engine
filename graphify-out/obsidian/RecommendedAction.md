---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\shared\models\core.py"
type: "code"
community: "C: Users"
location: "L238"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# RecommendedAction

## Connections
- [[ActionRecommendation]] - `uses` [INFERRED]
- [[AgentOutput]] - `uses` [INFERRED]
- [[AlternativeClaimSuggestion]] - `uses` [INFERRED]
- [[Burden]] - `uses` [INFERRED]
- [[Claim]] - `uses` [INFERRED]
- [[ClaimAbandonSuggestion]] - `uses` [INFERRED]
- [[ClaimAmendmentSuggestion]] - `uses` [INFERRED]
- [[ClaimDecomposition]] - `uses` [INFERRED]
- [[ClaimIssueMapping]] - `uses` [INFERRED]
- [[ConfidenceMetrics]] - `uses` [INFERRED]
- [[ConsistencyCheckResult]] - `uses` [INFERRED]
- [[CredibilityDeduction]] - `uses` [INFERRED]
- [[CredibilityScorecard]] - `uses` [INFERRED]
- [[Defense]] - `uses` [INFERRED]
- [[DefenseIssueMapping]] - `uses` [INFERRED]
- [[Enum]] - `inherits` [EXTRACTED]
- [[Evidence]] - `uses` [INFERRED]
- [[EvidenceGapItem]] - `uses` [INFERRED]
- [[EvidenceIndex]] - `uses` [INFERRED]
- [[ExecutiveSummaryArtifact]] - `uses` [INFERRED]
- [[ExecutiveSummaryStructuredOutput]] - `uses` [INFERRED]
- [[FactProposition]] - `uses` [INFERRED]
- [[InteractionTurn]] - `uses` [INFERRED]
- [[InternalDecisionSummary]] - `uses` [INFERRED]
- [[Issue]] - `uses` [INFERRED]
- [[IssueTree]] - `uses` [INFERRED]
- [[KeyConclusion]] - `uses` [INFERRED]
- [[Party]] - `uses` [INFERRED]
- [[PartyActionPlan]] - `uses` [INFERRED]
- [[ReportArtifact]] - `uses` [INFERRED]
- [[ReportSection]] - `uses` [INFERRED]
- [[RiskFlag]] - `uses` [INFERRED]
- [[StrategicRecommendation]] - `uses` [INFERRED]
- [[TrialExplanationPriority]] - `uses` [INFERRED]
- [[core.py]] - `contains` [EXTRACTED]
- [[str]] - `inherits` [EXTRACTED]
- [[一页式执行摘要（P2.12）。附加产物，不替代长报告 ReportArtifact。 聚合 P0.1-P1.8 全量产物中的关键决策信息。P1.7]] - `uses` [INFERRED]
- [[举证责任对象。canonical 字段名使用 burden_party_id（docs 03）。]] - `uses` [INFERRED]
- [[争点对象。Tier 1 对应 issue.schema.json；Tier 2 为 docs 03 前瞻字段（Optional）。]] - `uses` [INFERRED]
- [[争点树产物，对应 schemas case issue_tree.schema.json。]] - `uses` [INFERRED]
- [[内部决策版本摘要（v7）。不对外展示，仅供律师 内部团队决策使用。 包含：最可能输赢方向、最现实可回收金额、最先该补哪条证据。]] - `uses` [INFERRED]
- [[分析层模型 Analysis layer models. 包含核心案件对象、报告产物、对抗层和所有分析结果模型。]] - `uses` [INFERRED]
- [[单方行动计划（P1.8 v2）。聚合规则层结构行动和 LLM 策略建议。]] - `uses` [INFERRED]
- [[单条可信度扣分项。由规则层生成，不允许 LLM 修改。]] - `uses` [INFERRED]
- [[场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.]] - `uses` [INFERRED]
- [[庭审中优先解释事项（P1.8）。每条必须绑定 issue_id——零容忍。 Args priority_id 条目]] - `uses` [INFERRED]
- [[建议修改诉请条目（P1.8）。P2.11 实装后，同一 original_claim_id 的详细替代方案由 AlternativeClaimSugg]] - `uses` [INFERRED]
- [[建议放弃诉请条目（P1.8）。每条必须绑定 issue_id 和放弃理由——零容忍。 Args suggestion_id]] - `uses` [INFERRED]
- [[执行摘要结构化 JSON 输出（P2 双层输出）。 与现有叙述性输出并存，提供机器可读的结构化摘要。 Args]] - `uses` [INFERRED]
- [[执行摘要置信度指标（P2 结构化输出）。 Args overall_confidence 整体置信度（0.0-1.0]] - `uses` [INFERRED]
- [[报告章节。v7 起每个 section 必须标注视角、置信度和依赖。]] - `uses` [INFERRED]
- [[拆分后的诉请结构（v7）。替代原 current_most_stable_claim 单一 str 字段。 三个字段对应修订清单一-2 的要求：]] - `uses` [INFERRED]
- [[替代主张建议（P2.11）。当原主张不稳定时自动生成更稳固的替代版本。 触发条件（规则层，不调用 LLM）： 1. Issue.reco]] - `uses` [INFERRED]
- [[案件整体可信度折损评分卡。P2.9 产物，纳入 CaseWorkspace.artifact_index。 base_score 固定为 100，]] - `uses` [INFERRED]
- [[案型适配的策略性建议（P1.8 v2）。由 LLM 策略层生成。]] - `uses` [INFERRED]
- [[硬规则：final_score 必须等于 base_score + sum(deduction_points)。]] - `uses` [INFERRED]
- [[硬规则：list 字段长度约束 + traceability。 1. top3_immediate_actions 为列表时：长度 ≤ 3]] - `uses` [INFERRED]
- [[结构化证据对象。Tier 1 字段对应 evidence.schema.json。]] - `uses` [INFERRED]
- [[缺证项及其补证价值评估。P1.7 产物，纳入 CaseWorkspace.artifact_index。 roi_rank 由规则层（Eviden]] - `uses` [INFERRED]
- [[行动建议产物（P1.8）。纳入 CaseWorkspace.artifact_index。 在 report_generation 阶段由 Act]] - `uses` [INFERRED]
- [[角色在某一程序回合的规范化输出。对应 docs 03_case_object_model.md AgentOutput。 constraints（]] - `uses` [INFERRED]
- [[证据索引工作格式（非磁盘 artifact envelope）。]] - `uses` [INFERRED]
- [[输出前一致性校验结果（v7）。附加在最终输出末尾。 校验维度（修订清单四）： 1. perspective_consistent]] - `uses` [INFERRED]
- [[风险标记结构体。对应 docs 03_case_object_model.md RiskFlag。 constraints - fla]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users