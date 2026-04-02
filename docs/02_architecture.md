# System Architecture

## Overview

这个仓库现在不是 bootstrap scaffold 了。它已经有真实的 CLI、API、workspace persistence、scenario flow 和报告导出链路。

系统的骨架可以概括成一句话：

**同一套对象模型，驱动两种入口，产出同一批可回放、可恢复、可比较的案件产物。**

两个主要入口：

- CLI：`scripts/run_case.py`
- API：`api/app.py`

共享的运行时底座：

- `engines/shared/`
- `schemas/`
- `engines/*`
- `benchmarks/`
- `tests/`

## Runtime Surfaces

### CLI

CLI 负责离线和半离线运行：

1. 读取 `cases/*.yaml`
2. 进入五阶段工作流
3. 写出 `outputs/<timestamp>/`
4. 支持 `--resume` 基于已持久化产物继续后半程

CLI 主线产物目前包括：

- `result.json`
- `report.md`
- `report.docx`
- `decision_tree.json`
- `executive_summary.json`
- `attack_chain.json`
- `amount_report.json`

### API

API 负责案件式、可恢复、可重连的服务化运行：

1. `POST /api/cases/` 创建案件
2. `POST /api/cases/{case_id}/materials` 上传材料
3. `POST /api/cases/{case_id}/extract` 启动提取
4. `POST /api/cases/{case_id}/confirm` 确认提取结果
5. `POST /api/cases/{case_id}/analyze` 启动分析
6. `GET /api/cases/{case_id}/analysis` 通过 SSE 看进度
7. `GET /api/cases/{case_id}/artifacts` / `report` / `report/markdown` 读取产物
8. `POST /api/scenarios/run` 基于 baseline `run_id` 运行情景比较

API 层的状态与产物持久化在 `workspaces/api/<case_id>/`。

## Five-Stage Workflow

仓库当前按五阶段工作流组织代码：

1. `case_structuring`
2. `procedure_setup`
3. `simulation_run`
4. `report_generation`
5. `interactive_followup`

这五阶段是产品工作流，不等于法律程序状态机。

法律程序层的状态和证据准入规则，仍由共享对象模型、证据状态机和程序模板约束。

## Persistence Model

### Case-level persistence

核心持久化容器是 `CaseWorkspace` 这套概念模型。

在代码里主要落为：

- `engines/shared/models.py`
- `engines/shared/workspace_manager.py`
- API workspace 目录
- CLI output 目录

### Two persistence surfaces

当前仓库有两种持久化表面：

- `outputs/<timestamp>/`
  主要给 CLI / baseline run / export 使用
- `workspaces/api/<case_id>/`
  主要给 API 的案件恢复、artifact 恢复和 report 恢复使用

设计要求是这两种表面最终都能回到同一批结构化产物，而不是各写一套互不相认的状态。

## Scenario Flow

`simulation_run` 不只负责对抗，还负责 baseline 到 scenario 的差异运行。

当前 scenario 链路的核心约束是：

- scenario 必须绑定 baseline `run_id`
- baseline output 目录写出 `baseline_meta.json`
- scenario 运行时从 baseline metadata 恢复真实 `case_type`
- 差异输出必须可解释，不能只给一段模糊文本

API 场景入口是：

- `POST /api/scenarios/run`
- `GET /api/scenarios/{scenario_id}`

## Reporting Architecture

报告层现在已经是 active runtime，不是占位目录。

主线 report stack 位于 `engines/report_generation/`，负责：

- Markdown report
- DOCX export
- executive summary
- outcome / path rendering
- parity 和语义一致性

当前 `Output Track = v3.2` 的主线规则：

- 主线输出 probability-free
- 主线输出 mediation-free
- Markdown 与 DOCX 保持同一套报告语义
- `--resume` 后仍能重新生成 `report.md` 和 `report.docx`

## Access and Evidence Rules

系统的硬边界仍然是：

- `owner_private`
- `shared_common`
- `admitted_record`

证据状态机仍然是：

- `private`
- `submitted`
- `challenged`
- `admitted_for_discussion`

任何角色化输出都不能绕过这套边界。

## Evaluation Stack

评测与回归能力由三层构成：

- `schemas/`：契约边界
- `benchmarks/`：金标和 fixtures
- `tests/`：单元、集成、API、smoke

当前默认 `pytest` 覆盖大量单元与集成测试，`tests/smoke/` 中的 CLI smoke 则作为显式单独运行的补充。

## Design Priorities

1. `schema stability`
2. `workspace-backed recovery`
3. `citation traceability`
4. `access isolation`
5. `replayability`
6. `report parity`
