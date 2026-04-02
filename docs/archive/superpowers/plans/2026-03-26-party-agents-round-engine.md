> Historical document.
> Archived during the April 2026 documentation reorganization.
> Kept for context only. Do not treat this file as the current source of truth.
# PartyAgents + RoundEngine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补全 v1 对抗引擎的关键缺口：citation 幻觉防护、访问控制强制验证、WorkspaceManager/JobManager 集成，使对抗系统满足 v1 acceptance 标准。

**Architecture:** 三个改动点：① `base_agent` 增加 citation validation + retry（删除垃圾 fallback）；② `RoundEngine` 集成 WorkspaceManager + JobManager（可选参数，向后兼容）；③ 新增覆盖以上两点的测试。`EvidenceManagerAgent` 同步修复垃圾 fallback。

**Tech Stack:** Python 3.12, Pydantic v2, pytest-asyncio, existing `AccessController` / `JobManager` / `WorkspaceManager`

---

## 现有代码状态（2026-03-26）

已实现且 23/23 测试通过：
- `engines/adversarial/schemas.py` — `RoundConfig`, `Argument`, `RoundState`, `AdversarialResult`
- `engines/adversarial/agents/base_agent.py` — `BasePartyAgent` 含 LLM 调用/解析/retry
- `engines/adversarial/agents/plaintiff.py` — `PlaintiffAgent`
- `engines/adversarial/agents/defendant.py` — `DefendantAgent`
- `engines/adversarial/agents/evidence_mgr.py` — `EvidenceManagerAgent`
- `engines/adversarial/round_engine.py` — `RoundEngine` 三轮编排
- `engines/adversarial/tests/test_agents.py` — 8 个 agent 单元测试
- `engines/adversarial/tests/test_round_engine.py` — 15 个集成测试

**已知问题（本 plan 修复）：**
1. `RoundConfig.temperature = 0.3`（应为 0.0，影响可复现性）
2. `_parse_agent_output` 用 `["unknown-issue"]`/`["unknown-evidence"]` 作垃圾 fallback（违反 citation 合约）
3. `EvidenceManagerAgent._build_agent_output` 同上
4. `RoundEngine` 不集成 `WorkspaceManager` / `JobManager`（v1 持久化 Must Have 缺失）
5. 缺少 citation hallucination 防护测试和持久化测试

---

## File Map

| 文件 | 动作 | 改动描述 |
|------|------|---------|
| `engines/adversarial/schemas.py` | Modify | `temperature` default 0.3→0.0 |
| `engines/adversarial/agents/base_agent.py` | Modify | 删 fallback，加 `AgentOutputValidationError`，`_validate_citations`，`_call_and_parse` 加 `visible_evidence` 参数并 retry on validation failure |
| `engines/adversarial/agents/plaintiff.py` | Modify | `generate_claim` / `generate_rebuttal` → 传 `visible_evidence` 给 `_call_and_parse` |
| `engines/adversarial/agents/defendant.py` | Modify | 同 plaintiff |
| `engines/adversarial/agents/evidence_mgr.py` | Modify | 删 fallback，加 validation，加 retry 循环 |
| `engines/adversarial/round_engine.py` | Modify | `__init__` 加可选 `workspace_manager` / `job_manager`；`run` 加持久化和 Job 生命周期 |
| `engines/adversarial/tests/test_agents.py` | Modify | 新增 citation validation 测试 |
| `engines/adversarial/tests/test_round_engine.py` | Modify | 新增 workspace/job 集成测试；修复 `test_round_config_defaults`（temperature） |

---

## Task 1: 修复 RoundConfig.temperature 默认值

**Files:** Modify `engines/adversarial/schemas.py:37`

- [ ] **Step 1: 修改 temperature 默认值**

```python
# engines/adversarial/schemas.py line 37 — 改为:
temperature: float = Field(default=0.0, ge=0.0, le=1.0)
```

- [ ] **Step 2: 跑受影响的 schema 测试**

```
pytest engines/adversarial/tests/test_round_engine.py::TestSchemas::test_round_config_defaults -v
```

Expected: FAIL（因为测试没断言 temperature，应该 PASS — 确认后继续）

---

## Task 2: base_agent citation 验证 + retry

**Files:** Modify `engines/adversarial/agents/base_agent.py`

- [ ] **Step 1: 先写失败测试**

在 `engines/adversarial/tests/test_agents.py` 末尾 `TestPlaintiffAgent` 类中添加：

```python
@pytest.mark.asyncio
async def test_rejects_hallucinated_evidence_id(
    self, config, issue_tree, plaintiff_evidence
):
    """LLM 引用了不在可见证据列表中的 ev-999，应触发重试并最终 raise。"""
    from engines.adversarial.agents.base_agent import AgentOutputValidationError

    # 始终返回包含幻觉 ev-999 的响应
    bad_response = json.dumps({
        "title": "幻觉引用",
        "body": "引用了不存在的证据",
        "case_id": CASE_ID,
        "issue_ids": ["issue-001"],
        "evidence_citations": ["ev-999"],  # 不在 plaintiff_evidence 中
        "risk_flags": [],
        "arguments": [
            {
                "issue_id": "issue-001",
                "position": "幻觉",
                "supporting_evidence_ids": ["ev-999"],
            }
        ],
    }, ensure_ascii=False)

    mock_llm = MockLLMClient(response=bad_response)
    agent = PlaintiffAgent(mock_llm, PLAINTIFF_ID, config)

    with pytest.raises(AgentOutputValidationError):
        await agent.generate_claim(
            issue_tree=issue_tree,
            visible_evidence=plaintiff_evidence,
            context_outputs=[],
            run_id="run-001",
            state_id="state-001",
            round_index=1,
        )


@pytest.mark.asyncio
async def test_retry_on_bad_citations_succeeds(
    self, config, issue_tree, plaintiff_evidence
):
    """第一次返回幻觉 citation，第二次返回有效 citation，应成功。"""
    from engines.adversarial.agents.base_agent import AgentOutputValidationError

    calls = []
    bad = json.dumps({
        "title": "幻觉",
        "body": "test",
        "case_id": CASE_ID,
        "issue_ids": ["issue-001"],
        "evidence_citations": ["ev-FAKE"],
        "risk_flags": [],
        "arguments": [{"issue_id": "issue-001", "position": "x", "supporting_evidence_ids": ["ev-FAKE"]}],
    })
    good = json.dumps({
        "title": "正确引用",
        "body": "test",
        "case_id": CASE_ID,
        "issue_ids": ["issue-001"],
        "evidence_citations": ["ev-001"],
        "risk_flags": [],
        "arguments": [{"issue_id": "issue-001", "position": "x", "supporting_evidence_ids": ["ev-001"]}],
    })

    class FlakyLLM:
        async def create_message(self, **kwargs) -> str:
            calls.append(1)
            return bad if len(calls) == 1 else good

    agent = PlaintiffAgent(FlakyLLM(), PLAINTIFF_ID, config)
    output = await agent.generate_claim(
        issue_tree=issue_tree,
        visible_evidence=plaintiff_evidence,
        context_outputs=[],
        run_id="run-001",
        state_id="state-001",
        round_index=1,
    )
    assert output.evidence_citations == ["ev-001"]
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_rejects_empty_issue_ids_after_aggregation(
    self, config, issue_tree, plaintiff_evidence
):
    """LLM 返回空 issue_ids 且 arguments 也为空，应 raise AgentOutputValidationError。"""
    from engines.adversarial.agents.base_agent import AgentOutputValidationError

    empty_response = json.dumps({
        "title": "空争点",
        "body": "test",
        "case_id": CASE_ID,
        "issue_ids": [],
        "evidence_citations": [],
        "risk_flags": [],
        "arguments": [],
    })
    mock_llm = MockLLMClient(response=empty_response)
    agent = PlaintiffAgent(mock_llm, PLAINTIFF_ID, config)

    with pytest.raises(AgentOutputValidationError):
        await agent.generate_claim(
            issue_tree=issue_tree,
            visible_evidence=plaintiff_evidence,
            context_outputs=[],
            run_id="run-001",
            state_id="state-001",
            round_index=1,
        )
```

- [ ] **Step 2: 跑新测试，确认 FAIL**

```
pytest engines/adversarial/tests/test_agents.py::TestPlaintiffAgent::test_rejects_hallucinated_evidence_id -v
pytest engines/adversarial/tests/test_agents.py::TestPlaintiffAgent::test_retry_on_bad_citations_succeeds -v
pytest engines/adversarial/tests/test_agents.py::TestPlaintiffAgent::test_rejects_empty_issue_ids_after_aggregation -v
```

Expected: 3 FAIL（`AgentOutputValidationError` 未定义）

- [ ] **Step 3: 实现 AgentOutputValidationError + _validate_citations**

在 `engines/adversarial/agents/base_agent.py` 开头（import 之后，类定义之前）添加：

```python
class AgentOutputValidationError(ValueError):
    """AgentOutput citation 验证失败（引用幻觉或空 issue_ids）。
    Raised when AgentOutput fails citation validation (hallucinated IDs or empty issue_ids).
    """
```

在 `BasePartyAgent` 类末尾添加：

```python
def _validate_citations(
    self,
    output: AgentOutput,
    known_evidence_ids: set[str],
) -> None:
    """验证 AgentOutput 的 issue_ids 和 evidence_citations 合法性。
    Validate AgentOutput issue_ids and evidence_citations.

    Raises:
        AgentOutputValidationError: issue_ids 为空、evidence_citations 为空或包含幻觉 ID。
    """
    if not output.issue_ids:
        raise AgentOutputValidationError(
            "issue_ids 为空，LLM 未绑定任何争点。"
        )
    if not output.evidence_citations:
        raise AgentOutputValidationError(
            "evidence_citations 为空，不允许无引用结论。"
        )
    invalid_ids = [
        eid for eid in output.evidence_citations
        if eid not in known_evidence_ids
    ]
    if invalid_ids:
        raise AgentOutputValidationError(
            f"引用了可见证据列表中不存在的 ID（幻觉引用）: {invalid_ids}。"
            f"可见证据 ID 集合: {sorted(known_evidence_ids)}"
        )
```

- [ ] **Step 4: 修改 `_parse_agent_output` — 删除垃圾 fallback**

将：
```python
# 最终保底：避免空列表导致 AgentOutput 校验失败
if not issue_ids:
    issue_ids = ["unknown-issue"]
if not evidence_citations:
    evidence_citations = ["unknown-evidence"]
```

替换为：
```python
# 不再做垃圾 fallback：空列表由 _validate_citations 捕获并触发重试
if not issue_ids:
    raise AgentOutputValidationError(
        "issue_ids 聚合后仍为空：LLM 未在顶层或 arguments 中提供争点 ID。"
    )
if not evidence_citations:
    raise AgentOutputValidationError(
        "evidence_citations 聚合后仍为空：LLM 未提供任何证据引用。"
    )
```

- [ ] **Step 5: 修改 `_call_and_parse` — 加 visible_evidence 参数 + validation retry**

将现有 `_call_and_parse` 替换为：

```python
async def _call_and_parse(
    self,
    user_prompt: str,
    visible_evidence: list[Evidence],
    run_id: str,
    state_id: str,
    round_index: int,
    phase: ProcedurePhase,
) -> AgentOutput:
    """调用 LLM（带重试）、解析并验证 citation 合法性。
    Call LLM with retry, parse and validate citation correctness.

    重试条件 / Retry conditions:
    - LLM 调用异常（网络等）
    - AgentOutputValidationError（空 issue_ids / 空 citations / 幻觉 ID）
    """
    known_ids = {e.evidence_id for e in visible_evidence}
    system = self._build_system_prompt()
    current_prompt = user_prompt
    last_error: Exception | None = None

    for attempt in range(1, self._config.max_retries + 1):
        try:
            raw = await self._llm.create_message(
                system=system,
                user=current_prompt,
                model=self._config.model,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens_per_output,
            )
            data = _extract_json_object(raw)
            output = self._parse_agent_output(data, run_id, state_id, round_index, phase)
            self._validate_citations(output, known_ids)
            return output
        except AgentOutputValidationError as e:
            last_error = e
            if attempt < self._config.max_retries:
                current_prompt = (
                    user_prompt
                    + f"\n\n[重试反馈 第{attempt}次] 上次输出格式错误：{e}"
                    "\n请严格按照 JSON 格式重新输出，issue_ids 和 evidence_citations 必须非空，"
                    "且 evidence_citations 中的每个 ID 必须来自上方证据列表。"
                )
        except Exception as e:
            last_error = e
            if attempt < self._config.max_retries:
                continue
            break

    raise AgentOutputValidationError(
        f"连续 {self._config.max_retries} 次输出验证失败。最后错误: {last_error}"
    )
```

- [ ] **Step 6: 更新 `generate_claim` 和 `generate_rebuttal` — 传 visible_evidence**

```python
async def generate_claim(
    self,
    issue_tree: IssueTree,
    visible_evidence: list[Evidence],
    context_outputs: list[AgentOutput],
    run_id: str,
    state_id: str,
    round_index: int,
) -> AgentOutput:
    user_prompt = self._build_claim_prompt(issue_tree, visible_evidence, context_outputs)
    return await self._call_and_parse(
        user_prompt=user_prompt,
        visible_evidence=visible_evidence,   # ← 新增
        run_id=run_id,
        state_id=state_id,
        round_index=round_index,
        phase=ProcedurePhase.opening,
    )

async def generate_rebuttal(
    self,
    issue_tree: IssueTree,
    visible_evidence: list[Evidence],
    context_outputs: list[AgentOutput],
    opponent_outputs: list[AgentOutput],
    run_id: str,
    state_id: str,
    round_index: int,
) -> AgentOutput:
    user_prompt = self._build_rebuttal_prompt(
        issue_tree, visible_evidence, context_outputs, opponent_outputs
    )
    return await self._call_and_parse(
        user_prompt=user_prompt,
        visible_evidence=visible_evidence,   # ← 新增
        run_id=run_id,
        state_id=state_id,
        round_index=round_index,
        phase=ProcedurePhase.rebuttal,
    )
```

- [ ] **Step 7: 跑所有 agent 测试**

```
pytest engines/adversarial/tests/test_agents.py -v
```

Expected: 所有测试（包含新增的 3 个）全部通过

---

## Task 3: EvidenceManager citation 验证

**Files:** Modify `engines/adversarial/agents/evidence_mgr.py`

- [ ] **Step 1: 先写失败测试**

在 `test_agents.py` `TestEvidenceManagerAgent` 类中添加：

```python
@pytest.mark.asyncio
async def test_evidence_manager_rejects_empty_citations(
    self, config, issue_tree, plaintiff_evidence, defendant_evidence
):
    """EvidenceManager 返回空 evidence_citations 时应 raise。"""
    from engines.adversarial.agents.base_agent import AgentOutputValidationError

    bad_response = json.dumps({
        "title": "空引用",
        "body": "test",
        "issue_ids": [],
        "evidence_citations": [],
        "risk_flags": [],
        "conflicts": [],
    })
    evidence_index = EvidenceIndex(
        case_id=CASE_ID,
        evidence=plaintiff_evidence + defendant_evidence,
    )
    mock_llm = MockLLMClient(response=bad_response)
    agent = EvidenceManagerAgent(mock_llm, config)

    with pytest.raises(AgentOutputValidationError):
        await agent.analyze(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_outputs=[],
            defendant_outputs=[],
            run_id="run-001",
            state_id="state-002",
            round_index=2,
        )
```

- [ ] **Step 2: 跑新测试，确认 FAIL**

```
pytest engines/adversarial/tests/test_agents.py::TestEvidenceManagerAgent::test_evidence_manager_rejects_empty_citations -v
```

- [ ] **Step 3: 修改 `EvidenceManagerAgent._build_agent_output`**

从 `from engines.adversarial.agents.base_agent import AgentOutputValidationError` 导入，然后：

将：
```python
issue_ids = data.get("issue_ids", []) or ["unknown-issue"]
evidence_citations = data.get("evidence_citations", []) or ["unknown-evidence"]
```

替换为：
```python
issue_ids = data.get("issue_ids", [])
evidence_citations = data.get("evidence_citations", [])
if not issue_ids:
    raise AgentOutputValidationError(
        "EvidenceManager: issue_ids 为空，LLM 未绑定争点。"
    )
if not evidence_citations:
    raise AgentOutputValidationError(
        "EvidenceManager: evidence_citations 为空，不允许无引用输出。"
    )
```

- [ ] **Step 4: 在 `analyze` 方法中添加 retry 循环**

将现有的：
```python
raw = await self._call_llm_with_retry(system_prompt, user_prompt)
data = _extract_json_object(raw)
conflicts = self._parse_conflicts(data)
output = self._build_agent_output(data, run_id, state_id, round_index, evidence_index.case_id)
return output, conflicts
```

替换为：
```python
from engines.adversarial.agents.base_agent import AgentOutputValidationError

last_error: Exception | None = None
current_prompt = user_prompt
for attempt in range(1, self._config.max_retries + 1):
    try:
        raw = await self._call_llm_with_retry(system_prompt, current_prompt)
        data = _extract_json_object(raw)
        conflicts = self._parse_conflicts(data)
        output = self._build_agent_output(data, run_id, state_id, round_index, evidence_index.case_id)
        return output, conflicts
    except AgentOutputValidationError as e:
        last_error = e
        if attempt < self._config.max_retries:
            current_prompt = (
                user_prompt
                + f"\n\n[重试反馈 第{attempt}次] 上次输出格式错误：{e}"
                "\n请重新输出，issue_ids 和 evidence_citations 必须非空。"
            )
        else:
            raise AgentOutputValidationError(
                f"EvidenceManager 连续 {self._config.max_retries} 次输出验证失败。"
                f"最后错误: {last_error}"
            ) from e
raise AgentOutputValidationError(f"EvidenceManager 验证失败: {last_error}")
```

Note: `_call_llm_with_retry` 需要接受 user_prompt 参数，改为：`self._call_llm_with_retry(system_prompt, current_prompt)`（现有接口已符合）

- [ ] **Step 5: 跑所有 agent 测试，确认全通过**

```
pytest engines/adversarial/tests/test_agents.py -v
```

---

## Task 4: RoundEngine 集成 WorkspaceManager + JobManager

**Files:** Modify `engines/adversarial/round_engine.py`

- [ ] **Step 1: 先写失败测试**

在 `test_round_engine.py` 末尾添加新测试类：

```python
# ---------------------------------------------------------------------------
# RoundEngine + WorkspaceManager + JobManager 集成测试
# ---------------------------------------------------------------------------


class TestRoundEngineWithInfrastructure:
    """验证 RoundEngine 与 WorkspaceManager / JobManager 的集成。"""

    def _make_workspace_manager(self, tmp_path, case_id):
        from engines.shared.workspace_manager import WorkspaceManager
        wm = WorkspaceManager(tmp_path, case_id)
        wm.init_workspace("civil")
        return wm

    def _make_job_manager(self, tmp_path):
        from engines.shared.job_manager import JobManager
        return JobManager(tmp_path / CASE_ID)

    @pytest.mark.asyncio
    async def test_outputs_saved_to_workspace(
        self, mock_llm, config, issue_tree, evidence_index, tmp_path
    ):
        """运行后，workspace.artifact_index.AgentOutput 应有 5 条记录。"""
        wm = self._make_workspace_manager(tmp_path, CASE_ID)
        jm = self._make_job_manager(tmp_path)

        engine = RoundEngine(mock_llm, config, workspace_manager=wm, job_manager=jm)
        result = await engine.run(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_party_id=PLAINTIFF_ID,
            defendant_party_id=DEFENDANT_ID,
        )

        ws = wm.load_workspace()
        assert len(ws["artifact_index"]["AgentOutput"]) == 5

    @pytest.mark.asyncio
    async def test_job_lifecycle_completed(
        self, mock_llm, config, issue_tree, evidence_index, tmp_path
    ):
        """Job 应从 created 推进到 completed，progress=1.0。"""
        from engines.shared.models import JobStatus

        wm = self._make_workspace_manager(tmp_path, CASE_ID)
        jm = self._make_job_manager(tmp_path)

        engine = RoundEngine(mock_llm, config, workspace_manager=wm, job_manager=jm)
        result = await engine.run(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_party_id=PLAINTIFF_ID,
            defendant_party_id=DEFENDANT_ID,
        )

        job = jm.load_job(result.job_id)
        assert job is not None
        assert job.job_status == JobStatus.completed
        assert job.progress == 1.0
        assert job.result_ref is not None

    @pytest.mark.asyncio
    async def test_no_workspace_still_works(
        self, mock_llm, config, issue_tree, evidence_index
    ):
        """不传 workspace_manager / job_manager 时行为与之前一致（向后兼容）。"""
        engine = RoundEngine(mock_llm, config)  # 无 infrastructure
        result = await engine.run(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_party_id=PLAINTIFF_ID,
            defendant_party_id=DEFENDANT_ID,
        )
        assert isinstance(result, AdversarialResult)
        assert result.job_id == ""  # 无 JobManager 时为空字符串
```

同时修改现有 `test_round_config_defaults`（检查 temperature）：
```python
def test_round_config_defaults(self):
    cfg = RoundConfig()
    assert cfg.num_rounds == 3
    assert cfg.max_tokens_per_output == 2000
    assert cfg.max_retries == 3
    assert cfg.temperature == 0.0  # ← 新增
```

- [ ] **Step 2: 跑新测试，确认 FAIL**

```
pytest engines/adversarial/tests/test_round_engine.py::TestRoundEngineWithInfrastructure -v
```

- [ ] **Step 3: 实现 RoundEngine 的 infrastructure 集成**

修改 `engines/adversarial/round_engine.py`：

**a. 新增 import：**
```python
from typing import Optional

from engines.shared.job_manager import JobManager
from engines.shared.models import (
    AccessDomain,
    AgentOutput,
    AgentRole,
    ArtifactRef,
    EvidenceIndex,
    IssueTree,
    JobError,
    LLMClient,
)
from engines.shared.workspace_manager import WorkspaceManager
```

**b. 修改 `__init__`：**
```python
def __init__(
    self,
    llm_client: LLMClient,
    config: RoundConfig | None = None,
    workspace_manager: Optional[WorkspaceManager] = None,
    job_manager: Optional[JobManager] = None,
) -> None:
    self._llm = llm_client
    self._config = config or RoundConfig()
    self._access_ctrl = AccessController()
    self._workspace = workspace_manager
    self._job_mgr = job_manager
```

**c. 修改 `run()` — 添加 job 生命周期和 workspace 持久化：**

在 `run_id = ...` 之后添加：
```python
case_id = issue_tree.case_id

# ── Job 生命周期开始 ─────────────────────────────────────────────────
job_id = ""
if self._job_mgr:
    ws_id = f"ws-{case_id}"
    if self._workspace:
        ws_meta = self._workspace.load_workspace()
        if ws_meta:
            ws_id = ws_meta.get("workspace_id", ws_id)
    job = self._job_mgr.create_job(case_id, ws_id, "adversarial_simulation")
    job = self._job_mgr.start_job(job.job_id)
    job_id = job.job_id
```

在每个 round 结束后（`rounds.append(...)` 之后）添加：
```python
# 进度更新
if self._job_mgr and job_id:
    progress = (round_num) / 3  # round_num = 1, 2, 3
    self._job_mgr.update_progress(job_id, progress, f"完成第{round_num}轮")
```

在每个 `model_copy` 之后（原告/被告/evidence_manager 输出确定后）添加 workspace 保存：
```python
if self._workspace:
    self._workspace.save_agent_output(p_claim, AccessDomain.owner_private)
    # ... 同理 d_claim, ev_output, p_rebuttal, d_rebuttal
```

在 `return AdversarialResult(...)` 之前添加 job 完成：
```python
if self._job_mgr and job_id:
    last_output = all_outputs[-1]
    last_ref = ArtifactRef(
        object_type="AgentOutput",
        object_id=last_output.output_id,
        storage_ref=f"artifacts/adversarial/{last_output.output_id}.json",
    )
    self._job_mgr.complete_job(job_id, last_ref)
```

修改 `AdversarialResult` 增加 `job_id` 字段（在 `schemas.py`）：
```python
class AdversarialResult(BaseModel):
    case_id: str = ...
    run_id: str = ...
    job_id: str = Field(default="")  # ← 新增，无 JobManager 时为空字符串
    ...
```

用 try/except 包裹整个 run 主体，on exception 调用 `fail_job`：
```python
except Exception as exc:
    if self._job_mgr and job_id:
        self._job_mgr.fail_job(
            job_id,
            JobError(code="adversarial_run_failed", message=str(exc))
        )
    raise
```

- [ ] **Step 4: 跑所有测试**

```
pytest engines/adversarial/tests/ -v
```

Expected: 全部通过（包含新增的 5 个 infrastructure 测试）

---

## Task 5: 全量测试 + 回归检查

- [ ] **Step 1: 全量测试**

```
pytest engines/adversarial/ -v --tb=short
```

Expected: 全部通过，0 FAIL

- [ ] **Step 2: 全项目测试确认无回归**

```
pytest --tb=short -q 2>&1 | tail -5
```

Expected: 原有全部测试 + 新增测试全通过

- [ ] **Step 3: Commit**

```bash
git add engines/adversarial/
git add docs/superpowers/
git commit -m "feat(adversarial): citation validation, workspace/job integration

- RoundConfig.temperature 0.3→0.0（可复现性）
- BasePartyAgent: 删除垃圾 fallback，加 AgentOutputValidationError + _validate_citations
- _call_and_parse: retry on validation failure（幻觉 citation 防护）
- EvidenceManagerAgent: 同步修复 fallback + retry
- RoundEngine: 集成 WorkspaceManager + JobManager（可选参数，向后兼容）
- 新增测试：citation hallucination、retry、workspace 持久化、job lifecycle"
```

- [ ] **Step 4: Push**

```bash
export PATH="/c/Program Files/GitHub CLI:$PATH"
gh auth status
git push
```

---

## Self-Review

- [x] citation 幻觉防护：cited evidence_ids 必须在 visible_evidence 中存在
- [x] 空 issue_ids / empty citations → retry（不再 silently 填 garbage）
- [x] 向后兼容：不传 workspace_manager / job_manager 时行为不变
- [x] Job lifecycle：created→running→(progress)→completed / failed on error
- [x] 所有 5 条 AgentOutput 都通过 workspace.save_agent_output 落盘
- [x] result_ref 指向 artifact_index 中已登记的 AgentOutput
- [x] temperature=0.0 确保可复现性

