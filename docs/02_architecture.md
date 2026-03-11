# System Architecture

## 定位

本仓库是多角色案件对抗推演系统的系统仓库。当前版本只提交文档，不创建代码目录；但这里冻结的是未来工程实现必须遵守的模块边界、状态流转方式和访问控制原则。

系统的设计原则不是“多角色自由对话”，而是“对象模型 + 程序驱动 + 证据约束 + 权限隔离 + 可审计输出”。

## Product Workflow State Machine

这是产品体验层的状态机，用来组织律师使用系统的步骤，不替代法律程序状态。

统一工作流：

1. `case_structuring`
2. `procedure_setup`
3. `simulation_run`
4. `report_generation`
5. `interactive_followup`

约束：

- 工作流状态只描述产品阶段，不描述法律程序正当性
- 每个工作流阶段都要消费前一阶段的结构化产物
- 所有工作流产物都要落回统一案件上下文

## Legal Procedure State Machine

法律程序状态机继续保留原有回合语义，不被 UI 或产品流程替代。

## System Modules

### schemas

职责：定义所有核心对象和枚举，作为系统唯一数据契约来源。

至少覆盖：

- `Party`
- `Claim`
- `Defense`
- `Issue`
- `Evidence`
- `Burden`
- `ProcedureState`
- `AgentOutput`

约束：

- 字段命名只能来自 `docs/03_case_object_model.md`
- 新案型不得另造同义对象
- `schemas` 的变化必须同步更新评测基线

### engines

职责：承载系统行为，而不是承载业务话术。

核心子模块：

- `access_control`
- `case_manager`
- `job_manager`
- `round_engine`
- `evidence_state_machine`
- `citation_trace`
- `report_engine`
- `interaction_engine`
- `scenario_engine`
- `evaluator`

职责边界：

- `access_control` 只负责“谁能看什么、谁能在当前阶段写什么”
- `case_manager` 只负责案件级上下文持久化和产物索引
- `job_manager` 只负责长任务状态、进度与恢复
- `round_engine` 只负责程序化回合推进，不负责生成具体法律立场
- `evidence_state_machine` 只负责证据生命周期与合法迁移
- `citation_trace` 只负责结论与证据、规则、回合的追溯链
- `report_engine` 只负责把推演结果整理成律师可消费产物
- `interaction_engine` 只负责报告后的深度追问和 drill-down
- `scenario_engine` 只负责 `what-if` 变量注入与差异比较
- `evaluator` 只负责版本评测与回归比较

### templates

职责：承载案种、程序和角色的模板化差异。

未来至少拆分为：

- `civil`
- `criminal`
- `admin`

模板只定义：

- 案种要件模板
- 常见抗辩模板
- 程序回合模板
- 文书框架模板

模板不定义：

- 核心对象结构
- 权限底层逻辑
- 评测指标口径

### agents

职责：在受限输入与固定输出合同下生成角色化推演结果。

未来至少拆分为：

- `party_agents`
- `judge_agents`
- `review_agents`
- `safety_agents`

设计要求：

- 每个 `agent` 都必须带角色边界
- 每个 `agent` 输出都必须落入 `AgentOutput`
- 不允许输出无引用结论
- 不允许读取超出 `access_control` 的材料

### benchmarks

职责：提供版本回放、验收和回归比较的标准案件集。

未来至少按案型组织：

- `civil_loans`
- `civil_contracts`
- `criminal_drunk_driving`
- `admin_penalty`

每个 benchmark 用例都要能回放到：

- 输入材料
- 标准争点
- 关键证据
- 预期输出或人工评分记录

### ui

职责：面向律师的工作台和审计视图。

未来可能包含：

- `process`
- `run`
- `report`
- `interaction`
- `history`
- `issue_board`
- `evidence_board`
- `audit_log`

当前约束：

- `ui` 不是 `v0.5` 范围
- 任何 UI 设计都不能倒逼对象模型重命名

## Service / API Surfaces

为了避免把所有行为塞进单一接口，后续服务/API 至少按以下切面组织：

- `case`：案件、材料、工作区与产物索引
- `workflow`：产品工作流状态与阶段切换
- `simulation`：对抗回合、程序推进、场景运行
- `report`：报告生成、报告读取、报告后追问
- `audit`：审计日志、引用链、权限拦截记录

## Access Control

### 访问域

系统统一使用以下访问域：

- `owner_private`：材料仅对拥有方和授权审计角色可见
- `shared_common`：已交换或约定共享的材料，对相关当事方与中立角色可见
- `admitted_record`：已正式进入当前程序记录的材料，对裁判层与审计层可见

### 角色层级

- `orchestrator`
- `party_agent`
- `evidence_manager`
- `judge_agent`
- `review_agent`
- `audit_agent`

### 访问原则

- 原被告/控辩各自 `party_agent` 只能读取自己的 `owner_private` 与可见的 `shared_common`
- `judge_agent` 只能读取 `admitted_record` 与当前程序允许进入本轮的材料
- `review_agent` 可以读取 `shared_common` 与 `admitted_record`，但不能读取对方未披露的 `owner_private`
- `orchestrator` 只读取案件元数据与流程状态，不读取案件核心材料
- `audit_agent` 可读取审计必需信息，但必须留下访问日志

### 违规定义

以下情况直接视为系统违规：

- 任何 `judge_agent` 读取对方 `owner_private`
- 任何 `party_agent` 读取对方未共享材料
- 未进入程序的证据被当作裁判依据引用
- 输出中存在无法还原来源的“黑箱结论”

## Evidence State Machine

统一证据状态生命周期：

1. `private`
2. `submitted`
3. `challenged`
4. `admitted_for_discussion`

### 允许迁移

- `private -> submitted`
- `submitted -> challenged`
- `challenged -> admitted_for_discussion`

### 不允许迁移

- `private -> admitted_for_discussion`
- `submitted -> private`
- `admitted_for_discussion -> private`

### 状态含义

- `private`：材料只存在于拥有方可见域，尚未正式提交
- `submitted`：材料已被一方提交进入共同程序空间
- `challenged`：材料已被对方或中立角色提出质疑
- `admitted_for_discussion`：材料已获准进入本轮讨论和裁判参考范围

### 状态与访问关系

- `private` 默认落在 `owner_private`
- `submitted` 默认落在 `shared_common`
- `challenged` 仍处于 `shared_common`，但需附带争议记录
- `admitted_for_discussion` 才可进入 `admitted_record`

## Procedure-Driven Round Model

系统回合必须围绕程序推进，不允许“自由辩论”。

统一回合骨架：

1. `case_intake`
2. `element_mapping`
3. `opening`
4. `evidence_submission`
5. `evidence_challenge`
6. `judge_questions`
7. `rebuttal`
8. `output_branching`

约束：

- 每轮输出必须绑定 `issue_id`
- 每轮只能使用当前状态可读材料
- 只有 `output_branching` 才允许形成路径结论

## Design Priorities

1. `schema stability`
2. `reproducibility`
3. `citation traceability`
4. `access isolation`
5. `versioned evaluation`

## Explicitly Not Adopted

以下能力只作为参考对象，不作为本系统核心方案：

- 社交媒体式 action space
- 高自由 persona 生成
- 把外部图谱/记忆平台设为不可替代底座
- 用“平行世界仿真”替代法律程序与证据约束

## 当前实现边界

- 本次初始化不创建 `schemas/`、`engines/`、`templates/`、`agents/`、`benchmarks/`、`ui/` 实体目录
- 本次初始化只冻结系统架构，不落代码
- 后续任何代码任务都必须把本文件作为模块边界约束
