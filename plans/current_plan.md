# Current Plan

## 当前目标

当前目标：`v0.5`

本阶段只做单案种、离线可跑通的案件分析器，默认案型固定为民事 `民间借贷`。本阶段的职责不是写出“会吵架的 agent”，而是先冻结系统文档、对象模型和评测口径，让后续实现有稳定边界。

## 本轮只做什么

- 冻结 `docs/00_north_star.md`
- 冻结 `docs/01_product_roadmap.md`
- 冻结 `docs/02_architecture.md`
- 冻结 `docs/03_case_object_model.md`
- 冻结 `docs/04_eval_and_acceptance.md`
- 固定 `v0.5` 的任务顺序和验收口径

## 本轮明确不做什么

- 不做 `judge agent`
- 不做多轮对抗
- 不做刑事/行政
- 不做 `ui`
- 不做检索
- 不做在线协作
- 不做代码脚手架

## 依赖文件

- `docs/00_north_star.md`
- `docs/01_product_roadmap.md`
- `docs/02_architecture.md`
- `docs/03_case_object_model.md`
- `docs/04_eval_and_acceptance.md`

## 任务顺序

1. `repo bootstrap`
2. `schema design`
3. `evidence indexer`
4. `issue extractor`
5. `report generator`

约束：

- 每个任务都要先读取 `docs/03_case_object_model.md`
- 每个任务都要先声明将修改的文件清单
- 每个任务都要带测试与验收结果
- 不允许顺手扩到 `parser` 之外的功能层

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

## 风险点

- 抽取不稳定
- `schema` 漂移
- benchmark 金标标注成本高
- LLM 在没有任务单约束时扩 scope
- 文档术语不统一导致后续实现跑偏

## 输出物

- 系统文档基线
- `v0.5` 范围冻结结果
- 统一对象模型
- 统一评测口径
- `v0.5` 前 5 个任务的固定执行顺序
