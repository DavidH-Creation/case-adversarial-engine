# Current Plan

## 当前目标

当前目标：`v0.5`

本阶段只做单案种、离线可跑通的案件分析器，默认案型固定为民事 `民间借贷`。本阶段仍然不落 `ui`，但所有输出格式必须兼容未来五阶段工作流：

1. `case_structuring`
2. `procedure_setup`
3. `simulation_run`
4. `report_generation`
5. `interactive_followup`

当前职责不是堆更多 agent，而是先把案件工作区、任务状态、对象模型和评测口径固定住。

## 本轮只做什么

- 保持 `v0.5` 的单案种离线边界不变
- 让输出兼容未来 `CaseWorkspace`
- 让后续任务顺序变成基础设施优先
- 固定工作流对象、任务状态与报告追问的契约

## 本轮明确不做什么

- 不做 `judge agent`
- 不做多轮对抗
- 不做刑事/行政
- 不做 `ui`
- 不做检索
- 不做在线协作
- 不做社交平台 action space
- 不做高自由人格模拟
- 不新增 `tasks/` 文件

## 依赖文件

- `docs/00_north_star.md`
- `docs/01_product_roadmap.md`
- `docs/02_architecture.md`
- `docs/03_case_object_model.md`
- `docs/04_eval_and_acceptance.md`

## 任务顺序

1. `case workspace design`
2. `job manager design`
3. `schema refinement`
4. `evidence indexer`
5. `issue extractor`
6. `report engine`
7. `interactive followup contract`
8. `scenario engine design`

约束：

- 每个任务都要先读取 `docs/03_case_object_model.md`
- 每个任务都要先声明将修改的文件清单
- 每个任务都要带测试与验收结果
- 不允许顺手扩到 `ui` 或社交仿真能力
- 不新增 `tasks/` 文件，但任务名称和依赖顺序在此写死

## 验收脚本

本阶段使用人工检查 + 命令检查，不额外创建脚本文件。

建议检查项：

```powershell
git diff --name-only --cached
rg "^## v" docs/01_product_roadmap.md
rg "Party|Claim|Defense|Issue|Evidence|Burden|ProcedureState|AgentOutput" docs/03_case_object_model.md
rg "private|submitted|challenged|admitted_for_discussion" docs/02_architecture.md docs/03_case_object_model.md
rg "private 证据泄漏|Hard Fail|evidence_id" docs/04_eval_and_acceptance.md
```

通过条件：

- 6 个核心文档全部存在
- `current_plan.md` 当前目标为 `v0.5`
- `03_case_object_model.md` 定义完整的核心对象
- `04_eval_and_acceptance.md` 明确 hard fail
- 工作流对象与任务状态契约已经写入文档

## 风险点

- 抽取不稳定
- `schema` 漂移
- benchmark 金标标注成本高
- LLM 在没有任务单约束时扩 scope
- 文档术语不统一导致后续实现跑偏
- 工作流状态机与法律程序状态机被混用
- `Job` / `Run` / `CaseWorkspace` 定义不闭合

## 输出物

- 系统文档基线
- `v0.5` 范围冻结结果
- 统一对象模型
- 统一评测口径
- 基础设施优先的任务顺序
- 兼容未来五阶段工作流的输出合同
