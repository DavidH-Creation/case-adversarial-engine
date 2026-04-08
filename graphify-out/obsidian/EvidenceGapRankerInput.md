---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\evidence_gap_roi_ranker\schemas.py"
type: "code"
community: "C: Users"
location: "L52"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# EvidenceGapRankerInput

## Connections
- [[10 个输入项，roi_rank 应为 1-10。]] - `uses` [INFERRED]
- [[Add case_id and owner_party_id to claim dicts.]] - `uses` [INFERRED]
- [[Add case_id and owner_party_id to defense dicts.]] - `uses` [INFERRED]
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[Build EvidenceGapDescriptor list for P1.7 from two sources 1. Rule-based]] - `uses` [INFERRED]
- [[Convert YAML financials section to AmountCalculatorInput. Returns None if no fin]] - `uses` [INFERRED]
- [[Convert YAML material dicts to RawMaterial objects.]] - `uses` [INFERRED]
- [[Derive evidence gap indicators from pretrial cross-examination results. U]] - `uses` [INFERRED]
- [[EvidenceGapItem 的 related_issue_id 为空字符串时应报 ValidationError。]] - `uses` [INFERRED]
- [[EvidenceGapItem.roi_rank 最小值为 1，0 应报 ValidationError。]] - `uses` [INFERRED]
- [[EvidenceGapROIRanker]] - `uses` [INFERRED]
- [[EvidenceGapROIRanker 输入 wrapper。 Args case_id 案件 ID]] - `rationale_for` [EXTRACTED]
- [[IssueImpactRanker — 争点影响排序模块主类。 Issue Impact Ranker — main class for P0.1 issue]] - `uses` [INFERRED]
- [[IssueImpactRanker 单元测试。 Unit tests for IssueImpactRanker. 测试策略： - 不依赖真实 LLM]] - `uses` [INFERRED]
- [[Load and validate a YAML case file.]] - `uses` [INFERRED]
- [[Load pipeline section from config.yaml at project root. Returns {} if missing.]] - `uses` [INFERRED]
- [[OutcomeImpactSize 必须包含三个合法值。]] - `uses` [INFERRED]
- [[PracticallyObtainable 必须包含三个合法值。]] - `uses` [INFERRED]
- [[Return True if step was already completed according to checkpoint.]] - `uses` [INFERRED]
- [[Run 3-round adversarial debate.]] - `uses` [INFERRED]
- [[Run post-debate analysis pipeline. Returns dict of all artifacts.]] - `uses` [INFERRED]
- [[SupplementCost 必须包含三个合法值。]] - `uses` [INFERRED]
- [[TestDescriptorSchemaValidation]] - `uses` [INFERRED]
- [[TestEmptyInput_1]] - `uses` [INFERRED]
- [[TestEnums]] - `uses` [INFERRED]
- [[TestFullMixedScenario]] - `uses` [INFERRED]
- [[TestGroup1]] - `uses` [INFERRED]
- [[TestGroup2]] - `uses` [INFERRED]
- [[TestGroup3]] - `uses` [INFERRED]
- [[TestGroup4]] - `uses` [INFERRED]
- [[TestSingleItem]] - `uses` [INFERRED]
- [[gap_description 为空字符串时应触发 ValidationError。]] - `uses` [INFERRED]
- [[gap_id 为空字符串时应触发 ValidationError。]] - `uses` [INFERRED]
- [[obtainable=no 的任何 impact 均属于组 4，且按 impact DESC 排序。]] - `uses` [INFERRED]
- [[ranked_items 中每个元素都是 EvidenceGapItem 实例。]] - `uses` [INFERRED]
- [[ranked_items 内每个 EvidenceGapItem 的 case_id run_id 来自输入。]] - `uses` [INFERRED]
- [[related_issue_id 为空字符串时应触发 ValidationError。]] - `uses` [INFERRED]
- [[roi_rank 必须从 1 开始，连续无空缺。]] - `uses` [INFERRED]
- [[schemas.py]] - `contains` [EXTRACTED]
- [[uncertain+moderate 属于组 4（不满足组 3 条件 uncertain+significant）。]] - `uses` [INFERRED]
- [[uncertain+significant 排在 yes+moderate 之后。]] - `uses` [INFERRED]
- [[uncertain+significant 排在所有组 4 项目之前。]] - `uses` [INFERRED]
- [[yes+marginal 属于组 4（不在前三组中）。]] - `uses` [INFERRED]
- [[yes+marginal 属于组 4，组内按 cost ASC 排序。]] - `uses` [INFERRED]
- [[yes+moderate 排在 yes+significant 之后。]] - `uses` [INFERRED]
- [[yes+significant 应排在所有其他组之前。]] - `uses` [INFERRED]
- [[创建测试用 EvidenceGapDescriptor。]] - `uses` [INFERRED]
- [[创建测试用 EvidenceGapRankerInput。]] - `uses` [INFERRED]
- [[单条缺证项的所有字段被正确复制到 EvidenceGapItem。]] - `uses` [INFERRED]
- [[单条缺证项，roi_rank 必须为 1。]] - `uses` [INFERRED]
- [[同为组 1 的项按原始顺序排列（稳定排序）。]] - `uses` [INFERRED]
- [[四个优先组混合输入，最终顺序必须严格符合规则。]] - `uses` [INFERRED]
- [[场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.]] - `uses` [INFERRED]
- [[将 EvidenceGapDescriptor 转换为带 roi_rank 的 EvidenceGapItem。]] - `uses` [INFERRED]
- [[执行缺证 ROI 排序，返回完整结果。 Args inp 排序器输入（含 case_id、run_id、ga]] - `uses` [INFERRED]
- [[空 gap_items 列表返回空 ranked_items。]] - `uses` [INFERRED]
- [[空输入结果仍包含正确的 case_id 和 run_id。]] - `uses` [INFERRED]
- [[组 4 内同 impact + 同 cost 时，原始顺序保持不变（稳定排序）。]] - `uses` [INFERRED]
- [[组 4 内同 impact 时按 supplement_cost 升序排列（low medium high）。]] - `uses` [INFERRED]
- [[组 4 内按 outcome_impact_size 降序排列（significant moderate marginal）。]] - `uses` [INFERRED]
- [[结果中 case_id 和 run_id 来自输入。]] - `uses` [INFERRED]
- [[缺证 ROI 排序器（P1.7）。 纯规则层，不持有外部状态，可安全复用同一实例。 使用方式 Usage r]] - `uses` [INFERRED]
- [[计算排序键（tuple 越小越靠前）。 优先组 1-3：固定 tuple 保证组间顺序正确；组内 tie-breaking 全为 0 以保]] - `uses` [INFERRED]
- [[返回值必须是 EvidenceGapRankingResult 实例。]] - `uses` [INFERRED]
- [[验证 EvidenceGapROIRanker 不持有 LLM 客户端（零 LLM 调用合约）。]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users