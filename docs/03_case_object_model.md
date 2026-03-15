# Case Object Model

## 目的

本文件是多角色案件对抗推演系统的 canonical object model。后续任何 `schemas/`、`engines/`、`agents/`、评测脚本、任务单和接口设计，都必须严格使用这里定义的对象名、字段名和状态名。

如果实现中出现与本文件不一致的新对象名，视为越界实现。

## Common Enums

### `case_type`

- `civil`
- `criminal`
- `admin`

### `access_domain`

- `owner_private`
- `shared_common`
- `admitted_record`

### `evidence_status`

- `private`
- `submitted`
- `challenged`
- `admitted_for_discussion`

### `phase`

- `case_intake`
- `element_mapping`
- `opening`
- `evidence_submission`
- `evidence_challenge`
- `judge_questions`
- `rebuttal`
- `output_branching`

### `statement_class`

- `fact`
- `inference`
- `assumption`

### `workflow_stage`

- `case_structuring`
- `procedure_setup`
- `simulation_run`
- `report_generation`
- `interactive_followup`

### `job_status`

- `created`
- `pending`
- `running`
- `completed`
- `failed`
- `cancelled`

## `Party`

### 作用

表示案件中的参与主体，包括当事人、代理人、裁判角色、中立角色和审计角色。

### Required Fields

- `party_id`
- `case_id`
- `name`
- `party_type`
- `role_code`
- `side`
- `case_type`
- `access_domain_scope`
- `active`

### 字段说明

- `party_type`：自然人、法人、机关、律所角色或系统角色
- `role_code`：如 `plaintiff_agent`、`defendant_agent`、`judge_agent`、`evidence_manager`
- `side`：如 `plaintiff`、`defendant`、`prosecution`、`defense`、`neutral`
- `access_domain_scope`：该主体默认可访问的域集合

### Constraints

- `role_code` 必须可映射到明确权限，不允许模糊角色
- `neutral` 角色不能自动继承任一当事方的 `owner_private`

## `Claim`

### 作用

表示一方提出的请求、主张、指控或程序请求。

### Required Fields

- `claim_id`
- `case_id`
- `owner_party_id`
- `case_type`
- `title`
- `claim_text`
- `claim_category`
- `target_issue_ids`
- `supporting_fact_ids`
- `supporting_evidence_ids`
- `status`

### 字段说明

- `claim_category`：实体请求、程序请求、指控、量刑主张等
- `target_issue_ids`：该主张对应的争点
- `supporting_fact_ids`：支持主张的事实命题
- `supporting_evidence_ids`：当前已绑定的证据

### Constraints

- `Claim` 必须至少对应一个 `Issue`
- 不允许存在没有提出方的匿名主张

## `Defense`

### 作用

表示对 `Claim` 或指控的反驳、抗辩、异议或程序性回应。

### Required Fields

- `defense_id`
- `case_id`
- `owner_party_id`
- `against_claim_id`
- `defense_text`
- `defense_category`
- `target_issue_ids`
- `supporting_fact_ids`
- `supporting_evidence_ids`
- `status`

### 字段说明

- `defense_category`：实体抗辩、程序异议、证据异议、量刑抗辩等
- `against_claim_id`：被回应的 `Claim`

### Constraints

- `Defense` 必须明确指向至少一个 `Claim`
- 程序性 `Defense` 也必须进入 `Issue` 体系，不可漂浮在外

## `Issue`

### 作用

表示争点，是主张、抗辩、事实、证据和举证责任的汇合点。

### Required Fields

- `issue_id`
- `case_id`
- `title`
- `issue_type`
- `description`
- `parent_issue_id`
- `related_claim_ids`
- `related_defense_ids`
- `fact_propositions`
- `burden_ids`
- `evidence_ids`
- `status`
- `priority`

### 字段说明

- `issue_type`：实体争点、程序争点、证据争点、量刑争点
- `fact_propositions`：围绕该争点需要判断的事实命题
- `status`：如 `open`、`narrowed`、`closed`

### Constraints

- 所有回合输出都必须绑定 `issue_id`
- `Issue` 是系统的最小攻防单元，禁止跳过争点直接生成长文结论

## `Evidence`

### 作用

表示案件材料中的证据对象，是系统所有结论的主要引用来源。

### Required Fields

- `evidence_id`
- `case_id`
- `owner_party_id`
- `title`
- `source`
- `summary`
- `evidence_type`
- `target_fact_ids`
- `target_issue_ids`
- `access_domain`
- `status`
- `submitted_by_party_id`
- `challenged_by_party_ids`
- `admissibility_notes`

### 字段说明

- `source`：材料来源或生成来源
- `summary`：证据摘要
- `evidence_type`：书证、物证、证人证言、电子数据等
- `target_fact_ids`：该证据欲证明的事实命题
- `target_issue_ids`：该证据关联的争点
- `access_domain`：`owner_private`、`shared_common`、`admitted_record`
- `status`：`private`、`submitted`、`challenged`、`admitted_for_discussion`
- `admissibility_notes`：关于真实性、关联性、合法性、证明力的备注

### Constraints

- 每个 `Evidence` 必须有 `source` 与 `summary`
- `Evidence.status` 只能按合法状态机迁移
- `status = admitted_for_discussion` 时，`access_domain` 必须为 `admitted_record`
- 未进入 `admitted_record` 的证据不得被裁判层作为依据引用

## `Burden`

### 作用

表示争点或事实命题上的举证责任配置。

### Required Fields

- `burden_id`
- `case_id`
- `issue_id`
- `burden_party_id`
- `burden_type`
- `proof_standard`
- `fact_proposition`
- `legal_basis`
- `shift_condition`
- `status`

### 字段说明

- `burden_type`：初始举证责任、转移后的举证责任、说明责任等
- `proof_standard`：按案型定义所需证明强度
- `shift_condition`：举证责任转移条件

### Constraints

- 每个核心 `Issue` 至少应绑定一个 `Burden`
- 举证责任不能只写主体，不写证明命题

## `ProcedureState`

### 作用

表示系统在某一程序阶段的可执行状态，用来约束谁能读什么、写什么、推进什么。

### Required Fields

- `state_id`
- `case_id`
- `phase`
- `round_index`
- `allowed_role_codes`
- `readable_access_domains`
- `writable_object_types`
- `admissible_evidence_statuses`
- `open_issue_ids`
- `entry_conditions`
- `exit_conditions`
- `next_state_ids`

### 字段说明

- `phase`：必须来自统一 `phase` 枚举
- `allowed_role_codes`：当前状态允许参与的角色
- `readable_access_domains`：当前状态可读访问域
- `writable_object_types`：当前状态允许更新的对象类型
- `admissible_evidence_statuses`：当前状态允许进入本轮讨论的证据状态
- `open_issue_ids`：当前尚未闭合的争点

### Constraints

- `judge_questions` 不能读取 `owner_private`
- `output_branching` 只能基于允许的 `admissible_evidence_statuses`
- 没有 `next_state_ids` 的状态必须显式标记为终止状态

## `AgentOutput`

### 作用

表示任一角色在某一轮或某一阶段生成的规范化输出，是审计和回放的最小单位。

### Required Fields

- `output_id`
- `case_id`
- `run_id`
- `state_id`
- `phase`
- `round_index`
- `agent_role_code`
- `owner_party_id`
- `issue_ids`
- `title`
- `body`
- `evidence_citations`
- `statement_class`
- `risk_flags`
- `created_at`

### 字段说明

- `run_id`：该输出属于哪次运行快照
- `agent_role_code`：输出来源角色
- `issue_ids`：该输出覆盖的争点
- `body`：规范化输出正文
- `evidence_citations`：引用的 `evidence_id` 列表
- `statement_class`：`fact`、`inference`、`assumption`
- `risk_flags`：如越权风险、引用不足、程序冲突、状态冲突

### Constraints

- `AgentOutput` 不允许无 `issue_ids`
- `AgentOutput` 不允许无 `evidence_citations` 的关键结论
- `statement_class = assumption` 时必须显式标识为假设，不得伪装成事实

## `CaseWorkspace`

### 作用

表示案件级持久化上下文，是工作流五阶段共享的容器。

### Required Fields

- `workspace_id`
- `case_id`
- `case_type`
- `current_workflow_stage`
- `material_index`
- `artifact_index`
- `run_ids`
- `active_scenario_id`
- `status`

### 字段说明

- `current_workflow_stage`：必须来自统一 `workflow_stage` 枚举，表示当前案件工作流推进到的产品阶段
- `material_index`：案件输入材料与程序化基础对象的持久化索引，必须按 canonical object name 分组，并且每个索引项都要能通过对象类型 + 对象标识回到持久化记录
- `artifact_index`：工作流输出产物的持久化索引，至少要稳定承载 `AgentOutput`、`ReportArtifact`、`InteractionTurn`、`Scenario` 的按类型分组索引，并且每个索引项都要能通过对象类型 + 对象标识回到持久化记录；`Run.output_refs` 与 `Job.result_ref` 都只能解析到这里登记的 canonical artifact
- `run_ids`：当前 `CaseWorkspace` 已登记的 `Run` 标识列表，所有可回放执行都必须先在这里登记
- `active_scenario_id`：当前激活的 `Scenario` 标识；若尚未进入场景分支，可显式为空值，但字段本身不能缺失
- `status`：案件工作区的状态字段，字段名冻结为 `status`

### Constraints

- 所有案件产物都必须可从 `CaseWorkspace` 找回
- 工作流切换不能绕开 `CaseWorkspace`
- `material_index` 与 `artifact_index` 不得退化为自由文本描述，必须能稳定支持按对象类型和对象标识回查

## `Run`

### 作用

表示一次推演、报告生成或场景重跑的执行快照。

### Required Fields

- `run_id`
- `case_id`
- `workspace_id`
- `scenario_id`
- `trigger_type`
- `input_snapshot`
- `output_refs`
- `started_at`
- `finished_at`
- `status`

### 字段说明

- `scenario_id`：该次执行绑定的 `Scenario` 标识；若为 baseline 执行，可显式为空值，但字段本身不能缺失
- `trigger_type`：触发该次执行快照的工作流动作或系统动作
- `input_snapshot`：该次执行使用的输入快照，必须由可追溯引用组成，并能回到 `CaseWorkspace.material_index` 或 `CaseWorkspace.artifact_index`
- `output_refs`：该次执行产出的输出引用，必须由可追溯引用组成，并能回到 `CaseWorkspace.artifact_index`
- `started_at` / `finished_at`：执行开始与结束时间戳；未结束执行可显式保留空值，但字段本身不能缺失
- `status`：执行快照的状态字段，字段名冻结为 `status`

### Constraints

- `Run` 必须能回放
- `Run` 的输入快照和输出引用必须可追溯
- `Run.output_refs` 不得写成自由文本列表，必须能解析到 `CaseWorkspace` 中已登记的持久化产物
- `Run` 仍然是可回放执行的 canonical 执行快照；`Job` 只负责长任务生命周期，不替代 `Run`

## `Job`

### 作用

表示系统中的长任务状态与进度。

### Required Fields

- `job_id`
- `case_id`
- `workspace_id`
- `job_type`
- `job_status`
- `progress`
- `message`
- `result_ref`
- `error`
- `created_at`
- `updated_at`

### 字段说明

- `job_type`：长任务类型，例如索引、模拟运行或报告生成；字段本身不绑定额外枚举，但必须稳定可判别
- `job_status`：必须来自统一 `job_status` 枚举
- `progress`：`[0, 1]` 的归一化数值进度；`created` 固定为 `0`，`completed` 固定为 `1`
- `message`：面向人的进度说明；可显式为空值，但不是权威状态来源
- `result_ref`：可显式为空值；一旦存在，必须是指向 `CaseWorkspace.artifact_index` 的 canonical artifact 引用；若长任务产出多份结果，该字段只指向主结果入口
- `error`：可显式为空值；仅 `failed` 终止状态使用的结构化错误对象
- `created_at` / `updated_at`：任务创建与最近一次持久化更新时间戳

### Constraints

- `job_status` 只能使用统一枚举
- `progress` 必须使用 `[0, 1]` 归一化数值区间；除 `completed` 外不得写成 `1`
- `message` 只用于人类可读说明，不能覆盖 `job_status`、`progress` 或持久化产物的真实语义
- `Job` 可在中断后从已持久化状态重新装载；恢复时不得依赖只存在于内存中的中间结果
- `Job` 绝不能在没有有效 `result_ref` 的情况下声称 `completed`
- 非 `completed` 状态的 `result_ref` 必须为空
- `failed` 是唯一必须带 `error` 的终止状态；非 `failed` 状态的 `error` 必须为空
- `Job.job_status`、`progress` 与产物可见性必须与真实已持久化输出一致

## `ReportArtifact`

### 作用

表示生成后的报告及其追溯结构。

### Required Fields

- `report_id`
- `case_id`
- `run_id`
- `title`
- `section_index`
- `summary`
- `linked_output_ids`
- `linked_evidence_ids`
- `created_at`

### Constraints

- `ReportArtifact` 必须能回连 `AgentOutput`
- 关键结论必须带 `linked_evidence_ids`

## `InteractionTurn`

### 作用

表示报告生成后的单次追问记录。

### Required Fields

- `turn_id`
- `case_id`
- `report_id`
- `run_id`
- `question`
- `answer`
- `issue_ids`
- `evidence_ids`
- `created_at`

### Constraints

- 报告后追问必须继续绑定 `issue_ids`
- 报告后追问必须继续绑定 `evidence_ids`

## `Scenario`

### 作用

表示一次 `what-if` 变量注入及其与 baseline 的差异结果。

### Required Fields

- `scenario_id`
- `case_id`
- `baseline_run_id`
- `change_set`
- `diff_summary`
- `affected_issue_ids`
- `affected_evidence_ids`
- `status`

### Constraints

- `Scenario` 必须记录相对 baseline 的变更项
- `Scenario` 差异结果必须可解释

## Relationship Rules

- `Claim` 与 `Defense` 必须通过 `Issue` 发生关系
- `Issue` 必须能回连到 `Evidence` 与 `Burden`
- `ProcedureState` 决定 `AgentOutput` 的合法输入范围
- `Evidence` 的访问域与状态共同决定其可见性
- 裁判相关输出只能引用 `admitted_record` 中的证据
- `AgentOutput` 必须回连 `Run`
- `Job` 只跟踪长任务生命周期；`Run` 仍然是可回放执行快照
- `Job.result_ref` 必须解析到 `CaseWorkspace.artifact_index` 中的 canonical artifact，不能写成临时 payload 或自由文本结果
- 同一长任务若生成多份输出，`Run.output_refs` 记录完整输出集合，`Job.result_ref` 只提供主结果入口
- `ReportArtifact` 必须回连引用的 `AgentOutput` 与 `Evidence`
- `InteractionTurn` 必须回连 `ReportArtifact`
- `Scenario` 必须明确 baseline 与差异输出

## Hard Rules

- 不允许新增同义对象替代这里的八类核心对象
- 不允许新增工作流对象时绕开这里定义的 `CaseWorkspace`、`Run`、`Job`、`ReportArtifact`、`InteractionTurn`、`Scenario`
- 不允许把程序控制写进 prompt 而绕开 `ProcedureState`
- 不允许把证据状态、访问域和争点绑定写成自由文本
- 不允许输出无引用、无争点绑定、无分类标记的结论
