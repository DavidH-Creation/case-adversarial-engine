# Eval And Acceptance

## 目标

本文件定义这个仓库怎么判断“跑通了”、怎么判断“退化了”、以及什么问题一票否决。

现在评估也按双轨走：

- `Core Track = v2`
- `Output Track = v3.x`

## Benchmark Dataset Organization

### 当前 civil gold set

- 当前最成熟的金标集在 `benchmarks/civil_loans/`
- 已有 20 个民间借贷 benchmark case
- 每案至少包含：
  - `case_manifest`
  - `source_materials`
  - `gold_issue_tree`
  - `gold_evidence_index`
  - `gold_burden_map`
  - `lawyer_notes`

### Stable fixtures

`benchmarks/fixtures/` 用于保存稳定 JSON 示例和 replay fixtures，不用于展示式 demo。

## Metric Definitions

### Core Track metrics

- `issue_extraction_accuracy`
- `citation_completeness`
- `evidence_gap_discovery_rate`
- `run_to_run_consistency`
- `access_isolation_violations`
- `state_machine_violations`
- `job_recoverability`
- `report_followup_traceability`
- `scenario_diff_validity`
- `run_replayability`

### Output Track metrics

- `markdown_docx_semantic_parity`
- `probability_free_output`
- `mainline_export_recoverability`
- `report_resume_regeneration`

## Core Track Acceptance

### `v0.5`

- `issue_extraction_accuracy >= 80%`
- 每份证据都能绑定至少一个待证事实
- 关键结论 `citation_completeness = 100%`
- 报告可被律师快速读懂并判断是否有用

### `v1`

- 同一案件重复运行 5 次，争点树一致性 `>= 75%`
- 对抗后新增关键缺证点比例显著高于 `v0.5`
- 关键论点全部带 `evidence_id`
- `access_isolation_violations = 0`
- `job_recoverability` 基础可用

### `v1.2`

- `outcome_impact = high` 的争点全部出现在输出列表前 50%
- `amount_calculator` 零 LLM 调用
- `verdict_block_active = true` 时 `DecisionPathTree` 不输出置信区间
- 原被告各有一份 `OptimalAttackChain`，Top3 节点全部绑定 `issue_id` 和 `evidence_ids`

### `v1.5`

- 法官追问中，70% 以上被律师评价为“确实会问”
- 证据状态机无非法迁移
- `private` 证据泄漏为零
- 报告追问答案继续具备证据追溯

### `v2`

- 多案型 civil kernel 不破坏统一对象模型
- `CaseWorkspace` / `Run` / `Job` 语义在 CLI、API、scenario 间保持一致
- `scenario_diff_validity` 达标
- 服务重启或清空内存后，关键 API 产物仍可恢复

### `v2.5`

- 能支撑更完整的律师工作流
- 审计链完整
- 用户级权限和脱敏边界可验证

## Output Track Acceptance

### `v3.x`

- 用户可见输出不再出现概率、置信区间、`prob=`、`可能性：` 这类措辞
- 主线输出不再出现 mediation / settlement-range 段落
- Markdown 和 DOCX 的核心结论、路径顺序和措辞保持一致
- `--resume` 能从持久化的 post-debate artifacts 重新生成 `report.md` 和 `report.docx`
- API 的 Markdown report、DOCX report 和 artifacts 在恢复后仍可读取

## Hard Fail

以下问题一票否决：

- `private` 证据泄漏
- 无证据引用的关键结论
- 证据状态机非法迁移
- 裁判层引用未进入 `admitted_record` 的证据
- 输出无法区分 `fact` / `inference` / `assumption`
- `Job` 状态与实际持久化产物不一致
- `Scenario` 差异结果不可解释
- Markdown 和 DOCX 在主线语义上发生明显分叉

## Unacceptable Regression

以下 regression 不可接受，即使加了新功能也不能合并：

- `issue_extraction_accuracy` 显著下降
- `citation_completeness` 下降
- `run_to_run_consistency` 显著下降
- 新版本引入访问隔离漏洞
- 新版本引入证据状态错乱
- 旧 artifact 因字段漂移而无法恢复
- 用户可见报告重新引入 probability / confidence / mediation 语义

## 当前评测重点

当前仓库的评测重点不是再证明“有没有 scaffold”，而是守住三件事：

1. `Core Track` 的对象模型、持久化和恢复语义不能乱。
2. `Output Track` 的 Markdown / DOCX parity 不能裂开。
3. CLI、API 和 scenario 对同一案件的结构化理解不能彼此打架。
