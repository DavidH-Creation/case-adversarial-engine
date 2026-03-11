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

当前目标：`v0.5`

当前阶段聚焦单案种、离线可跑通的案件分析器，默认案型固定为民事 `民间借贷`。首版优先稳定以下产物：

- `case_manifest`
- `evidence_index`
- `issue_tree`
- `burden_map`
- `timeline`
- 结构化案件诊断报告

当前明确不做：

- `judge agent`
- 多轮对抗
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

## Near-Term Direction

后续实现优先级不是继续堆更多 agent，而是先补齐基础设施：

1. `case workspace design`
2. `job manager design`
3. `schema refinement`
4. `evidence indexer`
5. `issue extractor`
6. `report engine`
7. `interactive followup contract`
8. `scenario engine design`

## License / Reference Note

本仓库当前以自有文档与规划为主。外部项目只借鉴产品链路、状态管理和报告互动思路，不直接复用受许可证约束的实现代码。
