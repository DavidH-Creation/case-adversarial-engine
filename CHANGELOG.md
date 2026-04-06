# Changelog

## [2.5.0] — 2026-04-06

律师工作台 v2.5 — 五阶段交付，658 个测试全部通过。

### Phase 1: Case List & Query
- `GET /api/cases` — 案件列表端点，支持分页、排序、多字段过滤
- `CaseIndex` 内存索引 + 启动时磁盘扫描重建

### Phase 2: Replay & Audit
- `engines/shared/event_log.py` — 追加式 JSONL 事件日志
- `GET /api/cases/{case_id}/events` — 审计追踪端点
- Artifact 版本化：WorkspaceManager 保存产物快照

### Phase 3: Human Review
- `api/review_service.py` — ReviewStore 原子持久化（`{workspace}/reviews/rev-*.json`）
- `POST /api/cases/{case_id}/reviews` — 复核提交（状态机：none→pending_review→approved/rejected/revision_requested）
- `GET /api/cases/{case_id}/reviews` — 复核历史查询
- Section-level flags（section_key + flag + comment）
- EventLog 集成：`review_submitted` 事件

### Phase 4: Users & Permissions
- `api/auth.py` — JWT 认证（python-jose, HS256），三模式（dev/static/JWT）
- `api/users.py` — UserStore + 5 角色（admin/senior_lawyer/junior_lawyer/reviewer/readonly）
- `api/permissions.py` — `require_permission()` 工厂依赖，10 种操作的 RBAC 矩阵
- 所有端点迁移至 per-route `Depends(require_permission(Action.xxx))`
- `actor_id` 写入所有审计事件

### Phase 5: Export Enhancement
- `api/export_service.py` — CaseExporter：结构化 JSON 快照 + 批量 ZIP 打包
- `GET /api/cases/{case_id}/export?format=json|markdown|docx` — 单案件导出
- `POST /api/cases/export/bulk` — 批量导出（最多 50 件，ZIP 格式）
- `CaseSnapshot` 模型：含 events、reviews、evidence、analysis_data 等完整快照
- EventLog 集成：`exported` 事件

---

## [2.0.0-dev] — Unreleased

### In Progress

- v2 多案型内核（civil_loan / labor_dispute / real_estate）
- 文书辅助引擎
- 统一对象模型：Party、Claim、Defense、Issue、Evidence、Burden、ProcedureState
- 结构化输出路径 OutcomePath（胜诉路径、败诉路径、调解路径、补证路径）

---

## [1.5.0] — 2026-03-31

程序化庭前会议 / 质证版，v1.5 `evidence_state_machine` 与法官发问机制合并到 main。

### Added

- `engines/pretrial_conference/` — 庭前会议引擎（法官发问、质证状态机）
- `evidence_state_machine` — 证据状态迁移（submitted → challenged → admitted）
- 质证维度：真实性、关联性、合法性、证明力
- 输出：《模拟庭前会议纪要》《质证焦点清单》《法官可能追问 Top10》

---

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
