> Historical document.
> Archived during the April 2026 documentation reorganization.
> Kept for context only. Do not treat this file as the current source of truth.
# v1 Gap Analysis — v0.5 → v1

**分析日期**：2026-03-26
**基准版本**：v0.5（已完成，39/39 验收，280 测试零回归）
**目标版本**：v1（单案种双边对抗引擎）

---

## A. v1 目标概述

v1 的核心转变是：从**静态分析**升级为**受限攻防**。

v0.5 做的是"一个读者视角的案件结构化"——把材料变成争点、证据、举证责任，然后生成诊断报告。v1 要做的是"两个对立视角的程序化博弈"——引入原告代理和被告代理，在固定回合约束下各自提出最强论证，并暴露对抗后仍未闭合的争点和证据缺口。

v1 Must Have 清单（来自 `docs/01_product_roadmap.md`）：

1. `CaseManager`
2. `JobManager`
3. 案件上下文持久化
4. 长任务状态机
5. `private/shared` 目录隔离
6. 固定回合：首轮主张、证据提交、针对性反驳
7. 输出：原告最强论证、被告最强抗辩、关键争点未闭合列表、缺证报告
8. 所有论点强制引用具体 `evidence_id`

v1 Acceptance 标准：

- 同一案件重复运行 5 次，争点树一致性 >= 75%
- 对抗后新增发现的关键缺证点比例显著高于 v0.5
- 所有论点必须引用具体证据编号
- 原被告无法读取对方 `owner_private` 材料
- 案件和任务状态可恢复、可回放

---

## B. 逐项 Must Have Gap 分析

### MH-1：`CaseManager`

| 维度 | 现状 |
|------|------|
| **已有** | `WorkspaceManager`（`engines/shared/workspace_manager.py`）：管理单个案件的持久化，支持原子写、产物读写、阶段推进、Run 注册 |
| **缺失** | 多案件入口层——没有"创建/列出/删除案件"的管理接口；`WorkspaceManager` 只能管理一个已知 `case_id` 的工作区 |
| **新建内容** | `engines/shared/case_manager.py`：薄包装，提供 `create_case()` / `list_cases()` / `get_workspace(case_id)` / `delete_case()` 接口；内部委托给 `WorkspaceManager` |
| **工作量** | **小**（WorkspaceManager 已做了所有实质工作，CaseManager 只是多案件目录索引） |
| **依赖** | 无上游依赖；WorkspaceManager 已可复用 |

> **注意**：Roadmap 没有明确说明 CaseManager 是"多案件管理"还是"单案件协调器"。从架构文档（`engines` 模块边界）的表述看，`case_manager` 的职责是"案件级上下文持久化和产物索引"——这更像是对 WorkspaceManager 的语义命名而非新能力。建议在实施前确认范围（见 G 节）。

---

### MH-2：`JobManager`

| 维度 | 现状 |
|------|------|
| **已有** | `schemas/procedure/job.schema.json`（完整 JSON Schema）；`docs/03_case_object_model.md` 定义了 `Job` 的 9 个 required 字段和状态迁移矩阵；`docs/02_architecture.md` 有 Job Lifecycle Contract 全文；`JobStatus` 枚举已在 `engines/shared/models.py` 中定义 |
| **缺失** | `Job` 的 Pydantic 模型（`models.py` 中只有 `JobStatus` 枚举，没有 `Job` 类）；`JobManager` 实现类（CRUD、状态迁移、进度更新、result_ref 绑定）；与 `WorkspaceManager` 的集成（`result_ref` → `artifact_index`） |
| **新建内容** | 1. `Job` Pydantic 模型加入 `engines/shared/models.py`（对照 docs/03 定义）；2. `engines/shared/job_manager.py`：JobManager 类，实现 `create_job()` / `update_progress()` / `complete_job()` / `fail_job()` / `cancel_job()` / `load_job()` |
| **工作量** | **中**（Schema 和 contract 完备，但需要与 WorkspaceManager 的持久化路径对齐，并做完整的状态迁移测试） |
| **依赖** | 依赖 `Job` Pydantic 模型；依赖 `WorkspaceManager`（用于写 `jobs/job_{id}.json`） |

---

### MH-3：案件上下文持久化

| 维度 | 现状 |
|------|------|
| **已有** | `WorkspaceManager` 已完整实现：原子写、checkpoint resume、`material_index` / `artifact_index` 双索引、Run 注册、阶段推进 |
| **缺失** | v1 新增对抗产物（`AgentOutput` 的持久化路径）；`private/{party_id}/` 子目录下的私有材料持久化 |
| **新建内容** | 1. `WorkspaceManager.save_agent_output(output: AgentOutput)` 方法；2. `private/` 子目录写入逻辑（带 owner 隔离） |
| **工作量** | **小**（模式与现有 save_* 方法完全一致，只是增加新产物类型和新目录） |
| **依赖** | 依赖 `AgentOutput` Pydantic 模型 |

> v1 roadmap 把"案件上下文持久化"列为独立 Must Have，但 v0.5 的 WorkspaceManager 已覆盖了大部分需求。v1 只需在此基础上**增量扩展**，不需要重写。

---

### MH-4：长任务状态机

| 维度 | 现状 |
|------|------|
| **已有** | 完整的状态定义（Job Lifecycle Contract in `docs/02_architecture.md`）；6 个状态、10 条合法迁移路径全部文档化；架构设计文档明确不预设 queue/broker/云依赖 |
| **缺失** | 状态机实现代码本身（JobManager 中的迁移逻辑）；与 round_engine 的集成（每个对抗回合作为 Job） |
| **工作量** | **中**（与 MH-2 JobManager 合并实现，状态迁移逻辑在 JobManager 内，无需单独模块） |
| **依赖** | 与 MH-2 完全重叠，合并实现 |

---

### MH-5：`private/shared` 目录隔离

| 维度 | 现状 |
|------|------|
| **已有** | `AccessDomain` 枚举（`owner_private`, `shared_common`, `admitted_record`）已在 `models.py` 中定义；`Evidence.access_domain` 字段已存在；架构文档完整定义了访问域与角色层级的关系 |
| **缺失** | 文件系统层隔离：目前 `artifacts/` 目录没有按 owner 分区；没有 `access_control` 实现代码；没有防止 LLM 上下文跨越 owner_private 边界的 filtering 层 |
| **新建内容** | 1. 扩展 workspace 目录结构：`artifacts/private/{party_id}/` 和 `artifacts/shared/`；2. `engines/shared/access_control.py`：`AccessController` 类，提供 `filter_materials_for_role(role_code, materials)` 接口；3. `WorkspaceManager` 扩展支持按 access_domain 路由写入 |
| **工作量** | **中**（文件系统结构变化会影响现有的 `save_evidence_index` 等方法；access_control 本身逻辑不复杂，但测试验收要严格） |
| **依赖** | 依赖 `Party.role_code` 和 `Party.access_domain_scope` 的持久化；需要在 pipeline/round_engine 中实际调用 |

---

### MH-6：固定回合（首轮主张、证据提交、针对性反驳）

| 维度 | 现状 |
|------|------|
| **已有** | `ProcedurePhase` 枚举包含 `opening`, `evidence_submission`, `rebuttal`（恰好对应三个固定回合）；`ProcedureState` 对象模型完整定义了 `allowed_role_codes`, `readable_access_domains`, `writable_object_types`；`procedure_setup` 引擎已经能生成 `ProcedureState[]` 序列（v0.5 pipeline 中跳过但代码完整） |
| **缺失** | `round_engine`：程序化推进回合，消费 `ProcedureState` 约束，调度对应 party_agent；`party_agents`（原告代理、被告代理）：在 access_control 约束下生成 `AgentOutput`；回合间的状态迁移与 Job 进度更新 |
| **新建内容** | 1. `engines/round_engine/`：`RoundEngine` 类，接收 `ProcedureState[]` 和 party_agents，推进回合，每轮输出 `AgentOutput`；2. `agents/party_agents/`：`PlaintiffAgent` / `DefendantAgent`，输入受 `access_control` 过滤的材料，输出符合 `AgentOutput` contract 的结构化结论；3. 在 pipeline 中插入 `procedure_setup → round_engine` 阶段 |
| **工作量** | **大**（这是 v1 最核心的新能力，需要 round_engine、party_agents、access_control 三者协同，且需要精心设计 prompt 防止输出退化） |
| **依赖** | MH-5（access_control）；`AgentOutput` Pydantic 模型；`procedure_setup` 引擎（已有，需要激活到 pipeline 中） |

---

### MH-7：输出层（四类产物）

v1 要求输出：**原告最强论证**、**被告最强抗辩**、**关键争点未闭合列表**、**缺证报告**。

| 维度 | 现状 |
|------|------|
| **已有** | `ReportGenerator` 已能生成章节化报告，且每章有 `linked_issue_ids` 和 `linked_evidence_ids`；`IssueTree` 中有 `IssueStatus.open` 可以直接过滤未闭合争点 |
| **缺失** | 对抗视角的报告模板：现有报告是"中立诊断视角"，缺乏"原告最强论证"/"被告最强抗辩"的 prompt 和输出格式；缺证报告（gap analysis output）需要新的引擎或报告章节类型；`AgentOutput` 的聚合层（把多轮 AgentOutput 汇总为最强论证） |
| **新建内容** | 1. `report_generation` 引擎增加 `adversarial_summary` 模式：新 prompt profile 输入对抗双方的 `AgentOutput[]`，输出四类产物；2. 或者新建 `engines/adversarial_summary/`（更干净，v1 后容易扩展） |
| **工作量** | **中**（ReportGenerator 的 pattern 可以直接复用，关键是新 prompt 的设计和验证） |
| **依赖** | MH-6（round_engine 产出的 AgentOutput[]）；`AgentOutput` Pydantic 模型 |

---

### MH-8：所有论点强制引用具体 `evidence_id`

| 维度 | 现状 |
|------|------|
| **已有** | v0.5 的 report_generation 已有 `validate_report_strict` 验证所有关键结论必须有 `linked_evidence_ids`；`InteractionTurn` 有 `evidence_ids` 必填字段 |
| **缺失** | `AgentOutput.evidence_citations` 的验证器（docs/03 已定义该字段，但没有对应的 Pydantic 模型和验证逻辑）；在 round_engine 层对每轮 agent 输出进行 citation 完整性校验 |
| **新建内容** | 1. `AgentOutput` Pydantic 模型（加入 `models.py`）；2. `validate_agent_output_citations()` 验证函数；3. round_engine 在接受 AgentOutput 前强制校验 citation |
| **工作量** | **小**（验证模式已有样板，只需新增 AgentOutput 验证器） |
| **依赖** | `AgentOutput` Pydantic 模型 |

---

## C. v0.5 可复用资产清单

以下是 v0.5 中已经完整实现、v1 可以直接继承或小改复用的能力：

| 资产 | 位置 | 可复用程度 | v1 用途 |
|------|------|-----------|---------|
| `WorkspaceManager` | `engines/shared/workspace_manager.py` | **直接复用 + 增量扩展** | CaseManager 的基础；增加 AgentOutput / private 目录支持 |
| 共享 Pydantic 模型 | `engines/shared/models.py` | **直接复用 + 新增模型** | 补充 `Job` / `AgentOutput` Pydantic 类 |
| `LLMClient` Protocol | `engines/shared/models.py` | **直接复用** | party_agents 的 LLM 接口 |
| `ProcedurePhase` 枚举 | `engines/shared/models.py` | **直接复用** | round_engine 的回合类型 |
| `ProcedureState` 对象模型 | `engines/shared/models.py`（Tier 2 前瞻字段，目前为 Optional） | **激活已有字段** | round_engine 的约束输入 |
| `AccessDomain` 枚举 | `engines/shared/models.py` | **直接复用** | access_control 的域定义 |
| `EvidenceStatus` 状态机 | `engines/shared/models.py` | **直接复用** | 对抗中证据从 private → submitted → challenged 的迁移 |
| `procedure_setup` 引擎 | `engines/procedure_setup/` | **激活并插入 pipeline** | 生成 v1 的 `ProcedureState[]` 序列 |
| `ReportGenerator` | `engines/report_generation/` | **复用 + 新增 prompt profile** | 生成对抗总结报告 |
| `IssueTree` / `EvidenceIndex` | `engines/shared/models.py` | **直接复用** | party_agents 和 round_engine 的输入 |
| `validate_*_strict()` 模式 | 各引擎 `validator.py` | **直接复用（作为模板）** | `validate_agent_output_strict()` 的样板 |
| `pipeline.py` checkpoint 模式 | `engines/pipeline.py` | **复用模式** | v1 pipeline 增加对抗阶段的 checkpoint |
| JSON Schemas | `schemas/case/`, `schemas/procedure/` | **直接复用** | 新 schema 对齐已有 |
| benchmark 框架 | `benchmarks/civil_loans/` | **直接复用** | v1 一致性测试（5 次重复 >= 75%）的基础 |

---

## D. v1 新增能力清单（按依赖顺序）

以下按实施的依赖顺序排列。每一项都依赖它上方已完成的项。

### 阶段 0：基础模型补全（无依赖，可最先做）

**D0-1**：`Job` Pydantic 模型加入 `engines/shared/models.py`
- 对照 `docs/03_case_object_model.md` 和 `schemas/procedure/job.schema.json`
- 9 个 required 字段 + `job_status` 使用已有 `JobStatus` 枚举

**D0-2**：`AgentOutput` Pydantic 模型加入 `engines/shared/models.py`
- 对照 `docs/03_case_object_model.md`
- 关键字段：`issue_ids`（required, non-empty）、`evidence_citations`（required）、`statement_class`、`risk_flags`

**D0-3**：`ProcedureState` 从 Tier 2 Optional 升级为 Tier 1 required
- 目前 `ProcedureState` 相关字段在各引擎中分散，需要在 `models.py` 中定义完整的 `ProcedureState` Pydantic 类

### 阶段 1：基础设施层（依赖 D0）

**D1-1**：`JobManager` — `engines/shared/job_manager.py`
- CRUD + 状态迁移 + result_ref 绑定
- 持久化路径：`{workspace_dir}/{case_id}/jobs/job_{id}.json`
- 与 `WorkspaceManager` 解耦：JobManager 只管 Job 文件，不知道 artifact_index 细节

**D1-2**：`CaseManager` — `engines/shared/case_manager.py`
- 多案件目录索引（`cases.json` at base_dir 级别）
- 委托给 `WorkspaceManager` 完成单案件操作
- 提供 `create_case()` / `list_cases()` / `get_workspace_manager(case_id)` 接口

**D1-3**：`WorkspaceManager` 扩展
- `save_agent_output(output: AgentOutput, owner_party_id: str)` — 写 `artifacts/private/{party_id}/agent_outputs/{output_id}.json` 或 `artifacts/shared/agent_outputs/`
- `artifact_index` 增加 `AgentOutput` 键
- `save_job(job: Job)` / `load_job(job_id: str)` 方法

### 阶段 2：访问控制层（依赖 D0, D1）

**D2-1**：`AccessController` — `engines/shared/access_control.py`
- `filter_materials_for_role(role_code, all_materials, all_evidence)` → 只返回该角色可见的材料
- 实现 `docs/02_architecture.md` 中的访问原则（party_agent 不能读对方 owner_private 等）
- 严格模式：违规时抛异常，不静默过滤

**D2-2**：workspace 目录结构扩展
- `artifacts/private/{party_id}/` — owner_private 产物
- `artifacts/shared/` — shared_common 产物
- `artifacts/admitted/` — admitted_record 产物
- 现有 `artifacts/` 根目录下的产物（evidence_index.json 等）维持现状（中立分析产物）

### 阶段 3：对抗引擎层（依赖 D0, D1, D2）

**D3-1**：`procedure_setup` 激活并插入 pipeline
- 在 `pipeline.py` 的 `# v1: procedure_setup goes here` 注释处补实现
- 输出 `ProcedureState[]` 序列，持久化到 workspace

**D3-2**：`party_agents` — `agents/party_agents/`
- `PlaintiffAgent` / `DefendantAgent`：各接收经 access_control 过滤的材料，输出 `AgentOutput`
- 输出 contract：`issue_ids` 非空、`evidence_citations` 非空、`statement_class` 明确
- Prompt 设计关键：强制"最强论证"视角，而非中立分析

**D3-3**：`RoundEngine` — `engines/round_engine/`
- 接收 `ProcedureState[]` 和两个 party_agents
- 按顺序推进三个固定回合：`opening` → `evidence_submission` → `rebuttal`
- 每轮前调用 `AccessController` 过滤材料，每轮后验证 `AgentOutput` citation 完整性
- 通过 `JobManager` 更新 Job 进度

### 阶段 4：输出层（依赖 D3）

**D4-1**：对抗总结引擎
- 输入：三轮 `AgentOutput[]`（原告 + 被告各三轮）、`IssueTree`、`EvidenceIndex`
- 输出：原告最强论证（1份）、被告最强抗辩（1份）、未闭合争点列表、缺证报告
- 实现路径：在 `report_generation` 中新增 `adversarial` prompt profile，**或**新建 `engines/adversarial_summary/`

**D4-2**：v1 pipeline 集成
- 在现有 `pipeline.py` 中插入对抗阶段
- 新增 checkpoint：`agent_outputs_exist()` → 跳过
- 保持 v0.5 的静态分析能力（v1 在其上叠加，不替代）

### 阶段 5：一致性保障（依赖 D4）

**D5-1**：重复性测试
- 编写 5 次重复运行脚本，计算争点树一致性（>= 75%）
- 核心手段：temperature=0.0（已有），prompt 约束（D3-2 中强制格式）

**D5-2**：v1 验收脚本
- 类似 `scripts/verify_v05.py` 的自动化验收（建议 `scripts/verify_v1.py`）

---

## E. 风险和需要提前做的设计决策

### E1. 最高风险：回合退化（Roadmap 已标注）

**风险**：party_agent prompt 不够约束，输出退化为空泛长文，失去证据引用。
**缓解**：
- Prompt 必须硬编码输出格式（JSON schema mode 或 XML tag 约束）
- `RoundEngine` 在接受 AgentOutput 前调用 `validate_agent_output_strict()`，拒绝无 citation 输出并重试（最多 3 次）
- 基准测试：在 v1 开发前，先用手工 prompt 验证民间借贷案件能否产出格式正确的 AgentOutput，再进入工程化

**需要提前决策**：party_agent 的输出格式——是与现有 `ReportSection` 类似的 JSON 结构，还是新的 `AgentOutput` 专用格式（docs/03 定义）？建议严格使用 docs/03 的 `AgentOutput`，不另立格式。

### E2. 高风险：private 材料泄漏

**风险**：即使文件系统做了隔离，LLM 的 context window 中仍可能因为 bug 混入对方材料。
**缓解**：
- `AccessController.filter_materials_for_role()` 是唯一入口，严格 allowlist 而非 denylist
- 集成测试：验证 PlaintiffAgent 的 LLM 调用中不包含 defendant_private materials（可通过 mock LLM 验证 system prompt 内容）
- Acceptance: "原被告无法读取对方 owner_private 材料" 对应的测试必须在 v1 验收脚本中有覆盖

### E3. 中风险：CaseManager / JobManager / WorkspaceManager 三者关系混乱

**风险**：三个管理器职责边界不清，导致重复逻辑或循环依赖。
**设计决策（建议提前固化）**：
- `WorkspaceManager`：单案件、文件系统操作、产物读写（已有，保持不变）
- `JobManager`：长任务生命周期（Job CRUD + 状态机），持久化到 `{workspace_dir}/jobs/`，与 WorkspaceManager 解耦
- `CaseManager`：多案件目录入口，`create/list/get_workspace_manager(case_id)`，不知道 Job 细节
- 三者不互相持有引用；pipeline/orchestrator 层负责组合调用

### E4. 中风险：procedure_setup 激活对现有 pipeline 的影响

**风险**：`procedure_setup` 在 v0.5 中被跳过，schema 和 prompt 可能没有经过真实运行验证。
**缓解**：在 D3-1 之前，先对 `procedure_setup` 做一次独立的 happy path 测试（用 v0.5 的 IssueTree 作为输入），确认它能稳定输出 `ProcedureState[]`。

### E5. 低风险（但容易被忽略）：`AgentOutput` 缺少 Pydantic 模型

`docs/03` 中完整定义了 `AgentOutput`（11个 required 字段），但 `engines/shared/models.py` 目前没有这个类。所有 v1 的 agent 相关代码都依赖它。**这是 v1 开始前最先要做的事**（D0-2）。

### E6. schema 对齐欠债

v0.5 使用了 Tier 2 前瞻字段（Optional，待对齐）。v1 使用这些字段前（如 `Issue.description`、`Issue.priority`、`Burden.burden_type` 等），需要先做一轮 JSON Schema 对齐，避免持久化格式漂移。

---

## F. 建议的 v1 实施路线图（任务顺序）

以下是建议的任务分解，每个任务对应一个 Bulwark task contract：

```
T0-1  补全 AgentOutput Pydantic 模型           [小] 无依赖
T0-2  补全 Job Pydantic 模型                   [小] 无依赖
T0-3  激活 ProcedureState Pydantic 模型        [小] 无依赖

T1-1  实现 JobManager                          [中] 依赖 T0-2
T1-2  实现 CaseManager                         [小] 依赖 WorkspaceManager（已有）
T1-3  扩展 WorkspaceManager（AgentOutput 支持）[小] 依赖 T0-1

T2-1  实现 AccessController                    [中] 依赖 T0-1
T2-2  扩展 workspace 目录结构（private/shared）[小] 依赖 T2-1

T3-1  验证并激活 procedure_setup 引擎          [中] 依赖 T0-3
T3-2  实现 party_agents（Plaintiff + Defendant）[大] 依赖 T0-1, T2-1
T3-3  实现 RoundEngine                         [大] 依赖 T3-1, T3-2, T1-1

T4-1  实现对抗总结引擎（adversarial summary）  [中] 依赖 T3-3
T4-2  v1 pipeline 集成                         [中] 依赖 T4-1

T5-1  v1 一致性测试（5次重复 >= 75%）          [中] 依赖 T4-2
T5-2  v1 验收脚本 verify_v1.py                 [小] 依赖 T5-1
```

关键路径：`T0-1 → T2-1 → T3-2 → T3-3 → T4-1 → T4-2`

并行机会：
- T0-1 / T0-2 / T0-3 可以并行
- T1-1 / T1-2 可以并行
- T3-1 可以与 T2-1 并行

估算：
- 阶段 0-1（T0+T1）：基础设施补全，相对确定
- 阶段 2（T2）：访问控制，中等复杂度，测试要严格
- 阶段 3（T3）：最核心的对抗引擎，**T3-2 和 T3-3 是最大不确定项**，建议在 T3-2 之前先做手工 prompt 探索
- 阶段 4-5（T4+T5）：集成与验收，风险较低

---

## G. 对 Roadmap 文档本身的修改建议

### G1. `CaseManager` 定义需要澄清范围

**现状**：Roadmap 只说"CaseManager"，没说是多案件管理器还是单案件协调器。
**建议**：在 v1 的 Must Have 中补充一句说明：

> `CaseManager`：多案件入口层，提供案件的创建、列表和工作区访问。单案件内的持久化操作由 `WorkspaceManager` 承担，`CaseManager` 委托给它。

### G2. "长任务状态机" 和 "JobManager" 是同一能力的两种表述

**现状**：Must Have 列表中两者分开列（MH-2 和 MH-4），容易让人以为是两件事。
**建议**：合并为一条：

> `JobManager`：实现长任务生命周期状态机（created / pending / running / completed / failed / cancelled），支持中断恢复和进度追踪。

### G3. "案件上下文持久化" 标注继承关系

**现状**：v1 roadmap 把"案件上下文持久化"列为 Must Have，但 v0.5 已经实现了大部分。
**建议**：改为：

> 案件上下文持久化（v0.5 基础上扩展）：增加 `AgentOutput` 产物路径和 `private/shared` 目录隔离。

### G4. 输出格式名称固化

**现状**："原告最强论证、被告最强抗辩、关键争点未闭合列表、缺证报告" 是产品语言，没有映射到具体的对象模型名称。
**建议**：在 v1 Must Have 中明确：

> 输出产物类型：`AdversarialSummary`（聚合最强论证、最强抗辩、未闭合争点、缺证报告的顶层产物），所有子项均为 `AgentOutput` 的派生聚合，必须可通过 `artifact_index` 找回。

### G5. 明确 v1 不做什么（补充一条）

**现状**：v1 Not In Scope 缺少对 `evidence_state_machine` 的明确排除（那是 v1.5 的内容）。
**建议**：在 v1 Not In Scope 中补充：

> - `evidence_state_machine`（完整质证状态机，delayed to v1.5）

这能防止实现时把 v1.5 的能力悄悄拉进来。

---

*本文档由 Claude Code 自动生成。分析基于 2026-03-26 主干快照。如代码有变化请重新运行分析。*

