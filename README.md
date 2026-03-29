# case-adversarial-engine

多角色案件对抗推演系统 / Multi-role adversarial case simulation engine

## What This Is

这是一个面向中国诉讼场景的案件备战系统仓库。它的目标不是替律师“判输赢”，而是把案件材料结构化为可推演对象，在程序约束、证据规则、权限隔离和审计链下，提前暴露：

- 争点
- 证据缺口
- 程序风险
- 对方最强攻击路径
- 法官可能追问
- 多路径结论与补证方向

当前仓库首先承担 `source of truth` 的职责：先冻结产品边界、路线图、架构、对象模型和评测口径，再驱动后续实现。

## What This Is Not

- 不是 AI 法官
- 不是自由聊天 demo
- 不是面向普通用户的法律咨询产品
- 不是自动对法院提交材料的工具
- 不是绕过律师复核直接生成正式法律意见的系统

## Current Status

引擎版本：`v1.5`（2026-03-29）

单案种（民事 `民间借贷`）、离线可跑通的双边对抗案件分析引擎。

### Version Dimensions

本仓库有三个独立版本维度：

| 维度 | 当前值 | 含义 | Source of Truth |
|------|--------|------|-----------------|
| Engine version | `1.5.0` | 产品路线图里程碑（整体能力边界） | `pyproject.toml` |
| civil_loan pipeline | `v4` | 民间借贷分析链语义演进 | commit message / scripts |
| Case fixture schema | `fixture-schema-1` | 测试夹具与案件包数据结构版本 | `benchmarks/` manifest |

Engine version 跟踪产品路线图；pipeline version 跟踪单个案型分析链的语义升级（v1=静态 → v2=对抗 → v3=全链路 post-debate → v4=加权排序+策略层）；fixture schema 跟踪测试数据结构的兼容性。三者独立演进。

### Milestones

| 版本 | 内容 | 测试数 |
|------|------|--------|
| v0.5 | 静态分析：案件结构化、争点提取、证据索引、报告生成 | 280 |
| v1 | 双边对抗：原告/被告代理、证据管理员、三轮对抗、访问隔离 | 482 |
| v1.2 | 分析质量升级：12 个分析模块（争点排序、金额校验、裁判路径树、攻击链、证据权重、行动建议等） | 930 |
| v1.5 | 加权排序、可执行路径树、案型适配行动建议、LLM 策略层、庭前会议 | TBD |

**下一目标**：`v2.0` — 多案种核心（3-5 个案型）。

当前明确不做：

- 刑事/行政
- `ui`
- 在线协作

## Product Workflow

未来统一按五阶段工作流组织：

1. `case_structuring`
2. `procedure_setup`
3. `simulation_run`
4. `report_generation`
5. `interactive_followup`

这套工作流是产品层骨架，不替代法律程序状态机。

## Repository Map

```text
docs/
  00_north_star.md
  01_product_roadmap.md
  02_architecture.md
  03_case_object_model.md
  04_eval_and_acceptance.md
plans/
  current_plan.md
.bulwark/
  policies/
  tasks/
schemas/
  README.md
  case/
  procedure/
  reporting/
engines/
  README.md
  shared/                  # 共享模型、JobManager、AccessController、CLI adapter
  case_structuring/        # 证据索引、争点提取、金额计算、证据权重评分
  procedure_setup/
  simulation_run/          # 模拟推演 + 9 个 v1.2 分析子引擎
  report_generation/       # 报告生成 + 执行摘要
  adversarial/             # 双边对抗引擎（原告/被告/证据管理员）
  interactive_followup/
benchmarks/
  README.md
  fixtures/
  acceptance/
tests/
  README.md
  contracts/
  smoke/
```

推荐阅读顺序：

1. [docs/00_north_star.md](docs/00_north_star.md)
2. [docs/03_case_object_model.md](docs/03_case_object_model.md)
3. [docs/02_architecture.md](docs/02_architecture.md)
4. [docs/01_product_roadmap.md](docs/01_product_roadmap.md)
5. [docs/04_eval_and_acceptance.md](docs/04_eval_and_acceptance.md)
6. [plans/current_plan.md](plans/current_plan.md)

## Design Principles

- `schema stability`
- `reproducibility`
- `citation traceability`
- `access isolation`
- `versioned evaluation`

同时明确不采用：

- 社交媒体式 action space
- 高自由 persona 生成
- 把外部图谱/记忆平台设为不可替代底座

## Repository Bootstrap

仓库保持 pre-framework，不绑定具体运行时或部署方案：

- `schemas/`：版本化数据契约和交换边界（12 个 JSON Schema）
- `engines/`：7 个引擎目录，含 20 个子模块，与五阶段工作流对齐
- `benchmarks/`：回归评测输入与验收参考
- `tests/`：契约测试、smoke 测试、集成测试（930 个测试）
- `.bulwark/`：面向 Codex / Claude 的任务合同与策略控制平面

## Near-Term Direction

v1.5 已完成加权排序、可执行路径树和 LLM 策略层。下一步方向（v2.0）：

1. 多案种核心（3-5 个案型）
2. 案型 prompt profile 插件化
3. 跨案型共享规则层抽取

## License / Reference Note

本仓库当前以自有文档与规划为主。外部项目只借鉴产品链路、状态管理和报告互动思路，不直接复用受许可证约束的实现代码。
