> Historical document.
> Archived during the April 2026 documentation reorganization.
> Kept for context only. Do not treat this file as the current source of truth.
# Current Plan

## 当前目标

当前目标：`v1.5.0`（进行中）

v1.2 在 v1 双边对抗引擎基础上完成分析质量与决策能力升级。新增 12 个分析模块（P0.1–P0.4、P1.5–P1.8、P2.9–P2.12），覆盖争点影响排序、金额一致性校验、裁判路径树、最强攻击链、证据权重评分、争点分类、证据缺口 ROI、行动建议、可信度评分、替代主张生成和执行摘要。930 个测试全部通过。

**下一目标**：`v1.5` — 程序化庭前会议 / 质证版（`evidence_state_machine`、法官发问机制）。

## 当前基线

当前仓库已经补上最小工程骨架：

```text
schemas/
  case/
  procedure/
  reporting/
engines/
  case_structuring/
  procedure_setup/
  simulation_run/
  report_generation/
  interactive_followup/
benchmarks/
  fixtures/
  acceptance/
tests/
  contracts/
  smoke/
.bulwark/
  policies/
  tasks/
```

这一步只解决后续任务的稳定落点，不代表已经开始实现业务逻辑。

## 本轮只做什么

- 保持 `v0.5` 的单案种离线边界不变
- 让输出兼容未来 `CaseWorkspace`
- 让后续任务顺序变成基础设施优先
- 固定工作流对象、任务状态与报告追问的契约
- 使用 `.bulwark/tasks/` 承载可自动执行的 task contracts

## 本轮明确不做什么

- 不做 `judge agent`
- 不做多轮对抗
- 不做刑事/行政
- 不做 `ui`
- 不做检索
- 不做在线协作
- 不做社交平台 action space
- 不做高自由人格模拟
- 不在这一轮选择具体后端框架

## 依赖文件

- `docs/00_north_star.md`
- `docs/01_product_roadmap.md`
- `docs/02_architecture.md`
- `docs/03_case_object_model.md`
- `docs/04_eval_and_acceptance.md`

## 任务顺序

1. ✅ `repo layout bootstrap`
2. ✅ `case workspace design`
3. ✅ `job manager design`
4. ✅ `schema refinement`
5. ✅ `benchmark contract`
6. ✅ `evidence indexer`
7. ✅ `issue extractor`
8. ✅ `report engine`
9. ✅ `interactive followup contract`
10. ✅ `scenario engine design`

约束：

- 每个任务都要先读取 `docs/03_case_object_model.md`
- 每个任务都要先声明将修改的文件清单
- 每个任务都要带测试与验收结果
- 不允许顺手扩到 `ui` 或社交仿真能力
- `Bulwark` 任务一次只推进一个合同，不跨版本串行扩写

## 验收脚本

```bash
python scripts/verify_v05.py
```

自动化脚本：`scripts/verify_v05.py`（39 项全部通过）。

通过条件：

- 6 个核心文档全部存在
- `current_plan.md` 当前目标为 `v0.5`
- `03_case_object_model.md` 定义完整的核心对象
- `04_eval_and_acceptance.md` 明确 hard fail
- 工作流对象与任务状态契约已经写入文档
- 最小工程骨架与 `.bulwark/tasks/` 已经存在

## 风险点

- 抽取不稳定
- `schema` 漂移
- benchmark 金标标注成本高
- LLM 在没有任务单约束时扩 scope
- 文档术语不统一导致后续实现跑偏
- 工作流状态机与法律程序状态机被混用
- `Job` / `Run` / `CaseWorkspace` 定义不闭合
- task contract 的 stop condition 过紧导致自动执行中断

## 输出物

- 系统文档基线
- `v0.5` 范围冻结结果
- 统一对象模型
- 统一评测口径
- 基础设施优先的任务顺序
- 兼容未来五阶段工作流的输出合同
- 可供 `Bulwark` 执行的 task contracts

## 最近完成

- `v1.2-收尾（2026-03-28）`
- 交付物：
  `engines/simulation_run/issue_impact_ranker/` — P0.1 争点影响排序
  `engines/case_structuring/amount_calculator/` — P0.2 金额一致性硬校验
  `engines/simulation_run/decision_path_tree/` — P0.3 裁判路径树
  `engines/simulation_run/attack_chain_optimizer/` — P0.4 最强攻击链
  `engines/case_structuring/evidence_weight_scorer/` — P1.5 证据权重评分
  `engines/simulation_run/issue_category_classifier/` — P1.6 争点分类
  `engines/simulation_run/evidence_gap_roi_ranker/` — P1.7 证据缺口 ROI
  `engines/simulation_run/action_recommender/` — P1.8 行动建议
  `engines/simulation_run/credibility_scorer/` — P2.9 可信度评分
  `engines/shared/models.py` — P2.10 RiskFlag.impact_objects 迁移
  `engines/simulation_run/alternative_claim_generator/` — P2.11 替代主张生成
  `engines/report_generation/executive_summarizer/` — P2.12 执行摘要
  `pyproject.toml` — version 升至 1.2.0，testpaths 加入全部 v1.2 子引擎
- 结果：
  v1.2 P0–P2 共 12 项全部完成，930 个测试零回归

- `v1-收尾（2026-03-26）`
- 交付物：
  `engines/adversarial/` — RoundEngine、PlaintiffAgent、DefendantAgent、EvidenceManagerAgent、AdversarialSummarizer
  `engines/shared/case_manager.py` — 多案件目录入口
  `engines/shared/job_manager.py` — 长任务状态机（6 状态 10 条迁移）
  `engines/shared/access_control.py` — AccessController（allowlist 模式）
  `tests/integration/test_adversarial_pipeline.py` — 端到端对抗流程集成测试
  `plans/v1_completion_report.md` — v1 完成报告
- 工作内容：
  三轮对抗编排（claim → evidence → rebuttal）完整实现
  AccessController 隔离验证（原被告无法读取对方 owner_private）
  AdversarialSummary 包含 5 个必要字段（LLM 语义分析层）
  pyproject.toml 补充 `engines/adversarial/tests` 到 testpaths
- 结果：
  v1 验收标准全部通过，461 个测试零回归

- `v0-5-job-manager-contract`
- 交付物：
  `schemas/indexing.schema.json`
  `schemas/procedure/job.schema.json`
  `docs/02_architecture.md`
  `docs/03_case_object_model.md`
  `plans/current_plan.md`
- 结果：
  `Job` 生命周期、恢复语义与进度 contract 已冻结为 machine-readable schema + 文档约束，并与 `Run` / `CaseWorkspace` 的 replayable artifact linkage 对齐
- scope guard：
  本里程碑只补 contract / documentation，不引入 queue、worker、broker 或云依赖

- `v0-5-case-workspace-contract`
- 交付物：
  `schemas/indexing.schema.json`
  `schemas/case/case_workspace.schema.json`
  `schemas/procedure/run.schema.json`
  `benchmarks/fixtures/case_workspace_run_replay.json`
- 结果：
  `CaseWorkspace` 与 `Run` 已有 machine-readable contract，且 fixture 证明了 `CaseWorkspace.run_ids -> Run.output_refs -> artifact_index` 的回放路径
- 后续留给 `v0.5` 之外：
  为 `Job`、`ReportArtifact`、`InteractionTurn`、`Scenario` 补独立 schema
  增加基于 schema 的自动 contract validation

- `v0-5-收尾（2026-03-26）`
- 交付物：
  `scripts/verify_v05.py` — 39 项自动化验收脚本，全部通过
  `tests/integration/test_pipeline_with_persistence.py` — Pipeline + WorkspaceManager 集成测试
  `schemas/case/issue.schema.json` — UTF-8 乱码修复
  `schemas/case/issue_tree.schema.json` — UTF-8 乱码修复
  `plans/current_plan.md` — 任务全部标记完成
- 工作内容：
  六引擎端到端 happy path 测试通过
  `WorkspaceManager` 原子持久化实现完成
  共享对象模型（`engines/shared/models.py`）与 JSON Schema 对齐
  `review` 修复：`EvidenceIndexer`/`IssueExtractor`/`ReportGenerator` 等六引擎 contract 测试全通过
- 结果：
  v0.5 验收标准 39/39 通过，280 个测试零回归

- `v1-收尾（2026-03-26）`
- 交付物：
  `engines/adversarial/` — PlaintiffAgent、DefendantAgent、EvidenceManagerAgent、RoundEngine、AdversarialSummarizer
  `engines/shared/access_control.py` — AccessController（private/shared 隔离）
  `engines/shared/job_manager.py` — JobManager（6 状态任务生命周期）
  `engines/shared/models.py` — AgentOutput、Job 模型
  `engines/adversarial/tests/` — 37 个对抗层单元测试
  `tests/integration/test_adversarial_pipeline.py` — 全链路对抗集成测试（含 AccessController 隔离验证）
  `plans/v1_completion_report.md` — v1 完成报告
  `pyproject.toml` — version 升至 1.0.0，testpaths 加入 engines/adversarial/tests
- 工作内容：
  三轮对抗编排（claim → evidence → rebuttal）实现完成
  AccessController allowlist 模式：原告/被告无法读取对方 owner_private 证据
  AdversarialSummarizer LLM 语义分析层（最强论点、未闭合争点、缺证报告）
  全链路集成测试：EvidenceIndexer → IssueExtractor → RoundEngine
- 结果：
  v1 Must Have 8/8 全部完成，adversarial 37 + shared 163 + v0.5 引擎 282 = 482 测试零回归
- 已知限制：无真实 LLM 测试、回合数固定 3 轮、只支持民间借贷、无程序法官
- v1.5 建议：引入程序法官、质证状态机（submitted→challenged→admitted）、证据状态迁移

