# Repository Map

这是当前仓库结构的权威总览。顶层 `README.md` 只链接这里，不再内嵌一份容易过时的目录树。

## Top Level

| Path | Purpose |
|------|------|
| `README.md` | 仓库入口和当前状态 |
| `CLAUDE.md` | 项目级代理协作规则 |
| `docs/` | 当前有效文档 |
| `docs/archive/` | 历史计划、评审和旧规格 |
| `scripts/` | CLI 和辅助脚本 |
| `api/` | FastAPI 服务入口和 API orchestration |
| `engines/` | 五阶段工作流引擎和共享运行时 |
| `schemas/` | JSON Schema 契约 |
| `benchmarks/` | 金标集、fixtures、acceptance 参考 |
| `tests/` | 单元、集成、API、smoke 测试 |
| `cases/` | CLI 示例 / 案件 YAML |
| `scenarios/` | scenario 相关样例和配置 |
| `outputs/` | CLI / local run 输出目录 |
| `workspaces/` | API 和其他持久化工作区 |

## `engines/`

| Path | Purpose |
|------|------|
| `engines/shared/` | 共享模型、workspace manager、access control、CLI adapter、progress/report helpers |
| `engines/case_structuring/` | 材料结构化、证据索引、争点提取、金额/证据规则层 |
| `engines/procedure_setup/` | 程序配置、庭前准备、hearing order 等 |
| `engines/simulation_run/` | 对抗推演、路径树、攻击链、可信度、scenario |
| `engines/report_generation/` | Markdown / DOCX / executive summary / report parity |
| `engines/interactive_followup/` | 报告后追问和 drill-down |
| `engines/adversarial/` | 原有双边对抗主引擎 |
| `engines/pretrial_conference/` | 程序化庭前会议能力 |
| `engines/case_extraction/` | API 驱动的提取相关能力 |
| `engines/document_assistance/` | 文书辅助能力 |
| `engines/similar_case_search/` | 相似案例搜索能力 |

## `schemas/`

| Path | Purpose |
|------|------|
| `schemas/case/` | `CaseWorkspace`、`Issue`、`Evidence`、`Scenario` 等案件对象契约 |
| `schemas/procedure/` | `Run`、`Job` 等程序和长任务契约 |
| `schemas/reporting/` | `ReportArtifact`、`InteractionTurn` 等报告层契约 |
| `schemas/indexing.schema.json` | 通用索引结构 |

## `benchmarks/`

| Path | Purpose |
|------|------|
| `benchmarks/civil_loans/` | 当前最成熟的 civil benchmark 金标集 |
| `benchmarks/fixtures/` | 稳定 JSON fixtures 和 replay 示例 |
| `benchmarks/acceptance/` | 机器可读的 acceptance 参考 |

## `tests/`

| Path | Purpose |
|------|------|
| `engines/**/tests` | 绝大多数单元测试 |
| `tests/integration/` | 跨模块集成测试 |
| `api/tests/` | API 层测试 |
| `tests/contracts/` | schema / interface contract 相关检查 |
| `tests/smoke/` | 显式运行的 CLI smoke 和 fixture-based parity 检查 |

## `docs/archive/`

| Path | Purpose |
|------|------|
| `docs/archive/plans/` | 历史计划文档 |
| `docs/archive/reviews/` | 历史 review 文档 |
| `docs/archive/superpowers/` | 旧 superpowers 设计与计划资料 |
| `docs/archive/specs/` | 旧版本规格文档 |
| `docs/archive/root-plans/` | 原根目录 `plans/*.md` 归档 |
