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

## Relationship Rules

- `Claim` 与 `Defense` 必须通过 `Issue` 发生关系
- `Issue` 必须能回连到 `Evidence` 与 `Burden`
- `ProcedureState` 决定 `AgentOutput` 的合法输入范围
- `Evidence` 的访问域与状态共同决定其可见性
- 裁判相关输出只能引用 `admitted_record` 中的证据

## Hard Rules

- 不允许新增同义对象替代这里的八类核心对象
- 不允许把程序控制写进 prompt 而绕开 `ProcedureState`
- 不允许把证据状态、访问域和争点绑定写成自由文本
- 不允许输出无引用、无争点绑定、无分类标记的结论
