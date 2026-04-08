---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\shared\models\civil_loan.py"
type: "code"
community: "C: Users"
location: "L137"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# ClaimCalculationEntry

## Connections
- [[ArtifactRef]] - `uses` [INFERRED]
- [[AttackNode]] - `uses` [INFERRED]
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[BlockingCondition]] - `uses` [INFERRED]
- [[ConfidenceInterval]] - `uses` [INFERRED]
- [[ContractValidity]] - `uses` [INFERRED]
- [[DecisionPath]] - `uses` [INFERRED]
- [[DecisionPathTree]] - `uses` [INFERRED]
- [[DisputeResolutionStatus]] - `uses` [INFERRED]
- [[ExtractionMetadata_1]] - `uses` [INFERRED]
- [[InputSnapshot]] - `uses` [INFERRED]
- [[Job]] - `uses` [INFERRED]
- [[JobError]] - `uses` [INFERRED]
- [[MaterialRef]] - `uses` [INFERRED]
- [[OptimalAttackChain]] - `uses` [INFERRED]
- [[PathRankingItem]] - `uses` [INFERRED]
- [[Run]] - `uses` [INFERRED]
- [[civil_loan.py]] - `contains` [EXTRACTED]
- [[单个攻击节点。OptimalAttackChain.top_attacks 列表元素（规则层保证恰好 3 个）。]] - `uses` [INFERRED]
- [[执行快照，对应 schemas procedure run.schema.json。 output_refs 接受 material_ref ar]] - `uses` [INFERRED]
- [[提取过程元信息，prompt_profile 持久化于此以支持重放。]] - `uses` [INFERRED]
- [[某一方的最优攻击顺序与反制准备。P0.4 产物，纳入 CaseWorkspace.artifact_index。 为原告和被告各生成一份。]] - `uses` [INFERRED]
- [[流水线与基础设施模型 Pipeline and infrastructure models. 包含运行快照、长任务、金额计算、裁判路径树和攻击链模型。]] - `uses` [INFERRED]
- [[置信度区间。仅在 verdict_block_active=False 时允许填写。]] - `uses` [INFERRED]
- [[裁判路径树。P0.3 产物，纳入 CaseWorkspace.artifact_index（由调用方负责注册，同 P0.1 P0.2）。 替代 Adv]] - `uses` [INFERRED]
- [[路径概率排序条目。DecisionPathTree.path_ranking 列表元素。]] - `uses` [INFERRED]
- [[长任务状态与进度追踪。对应 schemas procedure job.schema.json。 model_validator 强制以下 inv]] - `uses` [INFERRED]
- [[长任务结构化错误。对应 schemas indexing.schema.json $defs job_error。]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users