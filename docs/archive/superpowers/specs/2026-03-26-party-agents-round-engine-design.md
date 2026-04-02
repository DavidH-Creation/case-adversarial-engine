> Historical document.
> Archived during the April 2026 documentation reorganization.
> Kept for context only. Do not treat this file as the current source of truth.
# PartyAgents + RoundEngine 设计规格
**日期**：2026-03-26
**版本**：v1
**作者**：Claude Code（设计） / David（审阅）
**状态**：APPROVED（self-review）

---

## 1. 背景与目标

v1 的核心目标是把 v0.5 的"静态分析"升级为"受限攻防"。本文规定 v1 对抗引擎中最核心的两个子系统：

- **PartyAgents**：原告代理（PlaintiffAgent）、被告代理（DefendantAgent）、证据管理员（EvidenceManager）
- **RoundEngine**：三回合编排器，驱动 agents 按固定程序推进并产出 AgentOutput

---

## 2. 范围边界

### v1 包含
- 三个固定回合：`opening` → `evidence_submission` → `rebuttal`
- 原告和被告各轮各产出一个 AgentOutput
- EvidenceManager 在 evidence_submission 回合产出一个 AgentOutput
- 访问控制：每方 agent 只能看到自己的 owner_private + shared_common + admitted_record
- 强制 citation 验证（代码层，非 prompt 层）
- JobManager 生命周期跟踪
- WorkspaceManager 持久化

### v1 不包含
- `EvidenceStatus` 状态机迁移（`private→submitted→challenged→admitted`）——v1.5
- `ProcedureState` 来自真实 procedure_setup 引擎——v1.5
- AdversarialSummary 四类产物——D4-1 单独实现
- 证据 admissibility 强制门禁——v1.5
- 程序法官与质证状态机——v1.5

---

## 3. 架构选择：轻量 ProcedureState（方案 C）

RoundEngine 在内部为每个 phase 构建最小化 `ProcedureState` 对象（不依赖 procedure_setup 引擎），从而：
1. AgentOutput.state_id 有合法来源（满足 docs/03 contract）
2. 不依赖未经完整验证的 procedure_setup 引擎
3. v1.5 升级路径清晰：改为消费真实 ProcedureState[] 即可

---

## 4. 文件结构

```
engines/adversarial/
  __init__.py
  schemas.py            ← RoundConfig, AdversarialRoundResult
  round_engine.py       ← RoundEngine（核心编排）
  agents/
    __init__.py
    base_agent.py       ← BasePartyAgent（共享逻辑：LLM调用、验证、重试）
    plaintiff.py        ← PlaintiffAgent
    defendant.py        ← DefendantAgent
    evidence_mgr.py     ← EvidenceManager
  prompts/
    __init__.py         ← PROMPT_REGISTRY
    civil_loan.py       ← 三阶段 × 三角色 prompt 函数
  tests/
    __init__.py
    test_agents.py      ← mock LLM 单元测试（~18 cases）
    test_round_engine.py ← mock LLM 集成测试（~12 cases）
```

---

## 5. 数据模型

### 5.1 RoundConfig（schemas.py）
```python
class RoundConfig(BaseModel):
    phase_sequence: list[ProcedurePhase] = [
        ProcedurePhase.opening,
        ProcedurePhase.evidence_submission,
        ProcedurePhase.rebuttal,
    ]
    max_retries: int = 3
    model: str = "claude-sonnet-4-20250514"
    temperature: float = 0.0
    max_tokens: int = 4096
```

### 5.2 AdversarialRoundResult（schemas.py）
```python
class AdversarialRoundResult(BaseModel):
    case_id: str
    run_id: str
    job_id: str
    plaintiff_outputs: list[AgentOutput]    # 每回合一个
    defendant_outputs: list[AgentOutput]    # 每回合一个
    evidence_manager_outputs: list[AgentOutput]  # 仅 evidence_submission 一个
    open_issue_ids: list[str]               # 三轮后仍未闭合的争点 ID
    created_at: str
```

`open_issue_ids` 计算逻辑：从 IssueTree 中取所有 `status=open` 的 issue，排除掉被任何 `plaintiff_outputs` 或 `defendant_outputs` 的 `issue_ids` 引用到的争点。未覆盖者视为未闭合。

---

## 6. BasePartyAgent 设计

### 接口
```python
class BasePartyAgent:
    def __init__(
        self,
        llm_client: LLMClient,
        role_code: str,
        case_type: str = "civil_loan",
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        max_retries: int = 3,
    )

    async def generate(
        self,
        phase: ProcedurePhase,
        round_index: int,
        state_id: str,
        case_id: str,
        run_id: str,
        owner_party_id: str,
        visible_evidence: list[Evidence],
        issue_tree: IssueTree,
        prior_outputs: list[AgentOutput],
    ) -> AgentOutput
```

### 生成流程
1. 构建 system prompt（角色身份、任务约束、JSON 格式要求）
2. 构建 user prompt（当前阶段、可见证据列表、争点树、已有的 prior_outputs）
3. `_call_llm_with_retry`（最多 max_retries 次）
4. `_parse_and_validate_output`：JSON 解析 + citation 验证
5. 自动注入 `risk_flags`（代码层）
6. 构建并返回 AgentOutput

### citation 验证规则
- `issue_ids` 非空（`min_length=1`）
- `evidence_citations` 非空（`min_length=1`）
- 所有 `evidence_citations` 中的 ID 必须存在于 `visible_evidence`（防止 LLM 幻觉）
- `statement_class` 必须是合法枚举值
- 验证失败 → 重试，带错误反馈给 LLM（第二次 attempt 时告知上一次失败原因）

### risk_flags 自动注入
```python
flags = []
if len(output.evidence_citations) < 2:
    flags.append("citation_count_low")
if not any(iid in open_issue_ids for iid in output.issue_ids):
    flags.append("issue_coverage_incomplete")
output.risk_flags = flags
```

---

## 7. PlaintiffAgent / DefendantAgent

两者仅在 `role_code` 和系统 prompt 立场上有差异，其余完全继承 BasePartyAgent。

- `PlaintiffAgent.role_code = "plaintiff_agent"`
- `DefendantAgent.role_code = "defendant_agent"`

---

## 8. EvidenceManager

- `role_code = "evidence_manager"`
- **仅在 `evidence_submission` 阶段被 RoundEngine 调用**
- 访问域：`shared_common + admitted_record`（AccessController 已约束，不需额外逻辑）
- 任务：对双方已提交的证据（体现在 prior_outputs 中）逐条审查，输出书面意见
- 输出：`AgentOutput`，`statement_class = "inference"`，`evidence_citations` 必须引用其审查的证据

---

## 9. RoundEngine 设计

### 接口
```python
class RoundEngine:
    def __init__(
        self,
        llm_client: LLMClient,
        access_controller: AccessController,
        job_manager: JobManager,
        workspace_manager: WorkspaceManager,
        config: RoundConfig = RoundConfig(),
    )

    async def run(
        self,
        case_id: str,
        run_id: str,
        issue_tree: IssueTree,
        evidence_index: EvidenceIndex,
        plaintiff_party: Party,
        defendant_party: Party,
        job_id: Optional[str] = None,
    ) -> AdversarialRoundResult
```

### 编排流程
```
1. job = create_job(或 load 已有 job)
2. job_mgr.start_job(job.job_id)
3. plaintiff_agent = PlaintiffAgent(llm_client, ...)
   defendant_agent = DefendantAgent(llm_client, ...)
   evidence_manager = EvidenceManager(llm_client, ...)
4. prior_outputs: list[AgentOutput] = []

5. for round_index, phase in enumerate(config.phase_sequence):
   state_id = f"state-{case_id}-r{round_index}"  # 内部轻量 ProcedureState

   # 原告
   p_evidence = access_ctrl.filter_evidence_for_agent(
       "plaintiff_agent", plaintiff_party.party_id, all_ev
   )
   p_out = await plaintiff_agent.generate(phase, round_index, state_id, ...)
   workspace.save_agent_output(p_out, AccessDomain.owner_private)
   prior_outputs.append(p_out)

   # 被告（symmetric）
   d_evidence = access_ctrl.filter_evidence_for_agent(
       "defendant_agent", defendant_party.party_id, all_ev
   )
   d_out = await defendant_agent.generate(phase, round_index, state_id, ...)
   workspace.save_agent_output(d_out, AccessDomain.owner_private)
   prior_outputs.append(d_out)

   # 证据管理员（仅 evidence_submission）
   if phase == ProcedurePhase.evidence_submission:
       em_evidence = access_ctrl.filter_evidence_for_agent(
           "evidence_manager", "", all_ev
       )
       em_out = await evidence_manager.generate(phase, round_index, state_id, ...)
       workspace.save_agent_output(em_out, AccessDomain.shared_common)
       prior_outputs.append(em_out)

   job_mgr.update_progress(job_id, (round_index+1)/3, f"完成 {phase.value}")

6. 构建 AdversarialRoundResult（计算 open_issue_ids）
7. result_ref = ArtifactRef(object_type="AgentOutput", object_id=last_output_id, ...)
8. job_mgr.complete_job(job_id, result_ref)
9. return result
```

### 错误处理
- `AgentOutputValidationError`（agent 连续重试失败）→ `job_mgr.fail_job(JobError(...))`，re-raise
- 任何其他异常 → 同上包装为 `JobError`，fail_job，re-raise

---

## 10. Prompt 设计原则（prompts/civil_loan.py）

每个 prompt 包含四个部分：

1. **角色定义**：明确身份、立场、任务
2. **可见证据列表**：按 `evidence_id: summary` 格式逐条呈现（限制幻觉）
3. **争点清单**：列出所有 open issues（issue_id + title）
4. **历史论点上下文**：prior_outputs 中前一轮对方的论点（rebuttal 阶段最关键）
5. **输出格式严格约束**：JSON schema + 明确禁止额外文字

**输出格式模板（必须在 system prompt 中）**：
```json
{
  "issue_ids": ["issue-xxx-001"],
  "title": "...",
  "body": "每个论点后括注证据ID，例：借贷关系成立[ev-001]",
  "evidence_citations": ["ev-001"],
  "statement_class": "fact|inference|assumption",
  "risk_flags": []
}
```

---

## 11. 测试策略

### test_agents.py（单元）
| 测试 | 关注点 |
|------|--------|
| `test_plaintiff_output_contract` | output 有非空 issue_ids 和 evidence_citations |
| `test_defendant_output_contract` | 同上 |
| `test_evidence_manager_output_contract` | 同上 |
| `test_access_isolation` | 原告不能 cite 被告的 owner_private 证据 ID |
| `test_retry_on_invalid_json` | mock 首次返回非 JSON，验证重试成功 |
| `test_retry_on_empty_citations` | mock 首次返回空 citations，验证重试 |
| `test_raises_after_max_retries` | mock 始终失败 → `AgentOutputValidationError` |
| `test_risk_flags_injected_low_citations` | 单 citation 自动注入 risk_flag |
| `test_risk_flags_injected_no_issue_coverage` | issue 未覆盖注入 risk_flag |

### test_round_engine.py（集成）
| 测试 | 关注点 |
|------|--------|
| `test_produces_correct_output_count` | 3回合 → 7个 AgentOutput（2×3 + 1） |
| `test_job_lifecycle_complete` | job: created→running→completed |
| `test_job_fails_on_agent_error` | agent 失败 → job failed |
| `test_plaintiff_cannot_see_defendant_private` | 传给 plaintiff agent 的 evidence 不含 defendant private |
| `test_prior_outputs_passed_correctly` | 第 3 回合收到前 2 轮所有 outputs |
| `test_open_issue_ids_computed` | 未被任何 output 覆盖的 issue 出现在 open_issue_ids |
| `test_evidence_manager_gets_shared_evidence_only` | em_evidence 不含任何 owner_private |
| `test_output_saved_to_workspace` | workspace.artifact_index 有正确数量的 AgentOutput |

---

## 12. Self-Review 检查清单

- [x] `AgentOutput` 不允许无 `issue_ids`（`min_length=1` + 代码验证）
- [x] `AgentOutput` 不允许无 `evidence_citations`（`min_length=1` + 代码验证）
- [x] 原被告无法读取对方 `owner_private` 材料（AccessController + filter before generate）
- [x] `statement_class = assumption` 时不伪装成 fact（prompt 约束 + enum 验证）
- [x] Job 生命周期完整：created→running→completed（或 failed）
- [x] `Job.result_ref` 指向已在 `artifact_index` 登记的 `AgentOutput`
- [x] 所有 AgentOutput 通过 `WorkspaceManager.save_agent_output` 持久化
- [x] EvidenceManager 只在 `evidence_submission` 阶段运行
- [x] prior_outputs 传给所有后续 agent（信息流正确）
- [x] citation 幻觉防护：所有 cited evidence_id 必须在 visible_evidence 中存在

---

*本文档已通过 self-review，无需修改，可进入实现阶段。*

