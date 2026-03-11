# System Architecture

## 定位

本仓库是多角色案件对抗推演系统的系统仓库。当前版本只提交文档，不创建代码目录；但这里冻结的是未来工程实现必须遵守的模块边界、状态流转方式和访问控制原则。

系统的设计原则不是“多角色自由对话”，而是“对象模型 + 程序驱动 + 证据约束 + 权限隔离 + 可审计输出”。

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
- `round_engine`
- `evidence_state_machine`
- `citation_trace`
- `evaluator`

职责边界：

- `access_control` 只负责“谁能看什么、谁能在当前阶段写什么”
- `round_engine` 只负责程序化回合推进，不负责生成具体法律立场
- `evidence_state_machine` 只负责证据生命周期与合法迁移
- `citation_trace` 只负责结论与证据、规则、回合的追溯链
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

- `workspace`
- `issue_board`
- `evidence_board`
- `audit_log`

当前约束：

- `ui` 不是 `v0.5` 范围
- 任何 UI 设计都不能倒逼对象模型重命名

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

## 当前实现边界

- 本次初始化不创建 `schemas/`、`engines/`、`templates/`、`agents/`、`benchmarks/`、`ui/` 实体目录
- 本次初始化只冻结系统架构，不落代码
- 后续任何代码任务都必须把本文件作为模块边界约束
