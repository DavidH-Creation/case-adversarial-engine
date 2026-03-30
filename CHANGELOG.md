# Changelog

## [1.2.0] — 2026-03-28

分析质量升级：新增 12 个分析子模块（P0.1–P2.12），930 个测试全部通过。

### Added
- `engines/simulation_run/issue_impact_ranker/` — P0.1 争点影响排序
- `engines/case_structuring/amount_calculator/` — P0.2 金额一致性硬校验
- `engines/simulation_run/decision_path_tree/` — P0.3 裁判路径树
- `engines/simulation_run/attack_chain_optimizer/` — P0.4 最强攻击链
- `engines/case_structuring/evidence_weight_scorer/` — P1.5 证据权重评分
- `engines/simulation_run/issue_category_classifier/` — P1.6 争点分类
- `engines/simulation_run/evidence_gap_roi_ranker/` — P1.7 证据缺口 ROI
- `engines/simulation_run/action_recommender/` — P1.8 行动建议
- `engines/simulation_run/credibility_scorer/` — P2.9 可信度评分
- `engines/shared/models.py` — P2.10 RiskFlag.impact_objects 字段迁移
- `engines/simulation_run/alternative_claim_generator/` — P2.11 替代主张生成
- `engines/report_generation/executive_summarizer/` — P2.12 执行摘要

### Changed
- `pyproject.toml` version 升至 1.2.0；testpaths 加入全部 v1.2 子引擎

---

## [1.0.0] — 2026-03-26

双边对抗引擎正式版，461 个测试全部通过。

### Added
- `engines/adversarial/` — RoundEngine、PlaintiffAgent、DefendantAgent、EvidenceManagerAgent、AdversarialSummarizer
- `engines/shared/job_manager.py` — 长任务状态机（6 状态 10 条迁移）
- `engines/shared/access_control.py` — AccessController（allowlist 模式）
- `tests/integration/test_adversarial_pipeline.py` — 端到端对抗流程集成测试
- `plans/v1_completion_report.md` — v1 完成报告

### Changed
- `pyproject.toml` version 升至 1.0.0；testpaths 加入 `engines/adversarial/tests`

### Notes
- 三轮对抗编排（claim → evidence → rebuttal）完整实现
- AccessController 隔离：原告/被告无法读取对方 owner_private 证据
- AdversarialSummarizer 含 5 个必要语义字段（最强论点、未闭合争点、缺证报告）

---

## [1.2.0-pre / v1.2 spec] — 2026-03-27 _(pre-release spec)_

v1.2 规格文档冻结（`docs/06_v1.2_spec.md`），定义 P0–P2 共 12 个分析模块的接口与验收口径。

---

## [0.5.0] — 2026-03-26

静态分析基线，280 个测试全部通过。

### Added
- `schemas/` — 12 个 JSON Schema（case、procedure、reporting 三个命名空间）
- `engines/case_structuring/evidence_indexer/` — 证据索引
- `engines/case_structuring/issue_extractor/` — 争点提取
- `engines/procedure_setup/` — 程序规划
- `engines/report_generation/` — 报告生成
- `engines/interactive_followup/` — 追问交互
- `engines/shared/workspace_manager.py` — WorkspaceManager 原子持久化
- `engines/shared/models.py` — 共享对象模型（与 JSON Schema 对齐）
- `scripts/verify_v05.py` — 39 项自动化验收脚本（全部通过）
- `tests/integration/test_pipeline_with_persistence.py` — Pipeline + WorkspaceManager 集成测试
- `benchmarks/` — 回归评测输入与验收参考

### Notes
- 单案种（民事 `民间借贷`）、离线可跑通的静态分析引擎
- `CaseWorkspace` + `Run` + `Job` 契约已冻结为 machine-readable schema
