# AgentOutput + Job + JobManager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 v1 基础设施的前三个核心数据单元：`AgentOutput` Pydantic 模型、`Job` Pydantic 模型（含状态机验证）、以及 `JobManager` 长任务管理器。

**Architecture:**
- `JobStatus` / `JobError` / `Job` / `AgentOutput` 均加入 `engines/shared/models.py`，与现有模型并列。
- `Job` 使用 `@model_validator(mode='after')` 在模型层强制 status/progress/result_ref/error 四字段的一致性约束（invariants），`JobManager` 在其上追加状态迁移合法性约束（transition matrix）。
- `JobManager` 新建独立文件 `engines/shared/job_manager.py`，持久化到 `{workspace_dir}/jobs/job_{id}.json`，与 `WorkspaceManager` 完全解耦（不互相持有引用）。

**Tech Stack:** Python 3.11+, Pydantic v2, pytest

---

## 文件结构

| 操作 | 文件 | 职责 |
|------|------|------|
| 修改 | `engines/shared/models.py` | 追加 `JobStatus` / `JobError` / `Job` / `AgentOutput` |
| 新建 | `engines/shared/job_manager.py` | `JobManager` 类 — Job CRUD + 状态机 |
| 新建 | `engines/shared/tests/test_job_model.py` | Job 模型单元测试（含 `AgentOutput`、`JobError`、`JobStatus`） |
| 新建 | `engines/shared/tests/test_job_manager.py` | JobManager 单元测试 |

---

## 关键设计决策（已 approved）

- **验证层级**：Job 模型用 `@model_validator` 强制 invariants；JobManager 验证 transition legality
- **`risk_flags`**：`list[str]`，不定义枚举
- **`AgentOutput.issue_ids` / `evidence_citations`**：`Field(..., min_length=1)` 强制非空
- **JobManager 解耦**：只接受 `workspace_dir: Path`，不知道 `artifact_index` 细节
- **`result_ref` 类型**：复用已有 `ArtifactRef`（`index_name="artifact_index"`）

---

## 状态迁移矩阵（Job Lifecycle Contract）

```
created  → pending / running / cancelled / failed
pending  → running / cancelled / failed
running  → pending / completed / failed / cancelled
completed → (terminal)
failed    → (terminal)
cancelled → (terminal)
```

---

## Task 1: Job 基础设施模型（JobStatus + JobError + Job）

**Files:**
- Modify: `engines/shared/models.py`
- Create: `engines/shared/tests/test_job_model.py`

### Step 1.1: 写失败测试

创建 `engines/shared/tests/test_job_model.py`，内容如下：

```python
"""
Job 模型单元测试 — JobStatus / JobError / Job invariant validation。
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from engines.shared.models import (
    ArtifactRef,
    Job,
    JobError,
    JobStatus,
)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _base_job(**overrides) -> dict:
    defaults = dict(
        job_id="job-001",
        case_id="case-001",
        workspace_id="ws-case-001",
        job_type="simulation_run",
        job_status=JobStatus.created,
        progress=0.0,
        message=None,
        result_ref=None,
        error=None,
        created_at=_now(),
        updated_at=_now(),
    )
    defaults.update(overrides)
    return defaults


def _artifact_ref() -> ArtifactRef:
    return ArtifactRef(
        index_name="artifact_index",
        object_type="ReportArtifact",
        object_id="report-001",
        storage_ref="artifacts/report.json",
    )


def _job_error() -> JobError:
    return JobError(code="ERR_LLM", message="LLM call failed")


# ---------------------------------------------------------------------------
# JobStatus
# ---------------------------------------------------------------------------

class TestJobStatus:
    def test_all_six_values_exist(self):
        values = {s.value for s in JobStatus}
        assert values == {"created", "pending", "running", "completed", "failed", "cancelled"}

    def test_is_str_enum(self):
        assert isinstance(JobStatus.created, str)
        assert JobStatus.running == "running"


# ---------------------------------------------------------------------------
# JobError
# ---------------------------------------------------------------------------

class TestJobError:
    def test_valid_minimal(self):
        e = JobError(code="E001", message="something went wrong")
        assert e.code == "E001"
        assert e.message == "something went wrong"
        assert e.details is None

    def test_valid_with_details(self):
        e = JobError(code="E001", message="failed", details={"retries": 3})
        assert e.details == {"retries": 3}

    def test_details_can_be_none(self):
        e = JobError(code="E001", message="err", details=None)
        assert e.details is None

    def test_empty_code_rejected(self):
        with pytest.raises(ValidationError):
            JobError(code="", message="err")

    def test_empty_message_rejected(self):
        with pytest.raises(ValidationError):
            JobError(code="E001", message="")


# ---------------------------------------------------------------------------
# Job — 合法构造
# ---------------------------------------------------------------------------

class TestJobValidConstruction:
    def test_created_state(self):
        job = Job(**_base_job(job_status=JobStatus.created, progress=0.0))
        assert job.job_status == JobStatus.created
        assert job.progress == 0.0
        assert job.result_ref is None
        assert job.error is None

    def test_pending_state(self):
        job = Job(**_base_job(job_status=JobStatus.pending, progress=0.3))
        assert job.job_status == JobStatus.pending

    def test_running_state(self):
        job = Job(**_base_job(job_status=JobStatus.running, progress=0.5, message="halfway"))
        assert job.job_status == JobStatus.running
        assert job.message == "halfway"

    def test_completed_state(self):
        job = Job(**_base_job(
            job_status=JobStatus.completed,
            progress=1.0,
            result_ref=_artifact_ref(),
        ))
        assert job.job_status == JobStatus.completed
        assert job.progress == 1.0
        assert job.result_ref is not None

    def test_failed_state(self):
        job = Job(**_base_job(
            job_status=JobStatus.failed,
            progress=0.4,
            error=_job_error(),
        ))
        assert job.job_status == JobStatus.failed
        assert job.error.code == "ERR_LLM"

    def test_cancelled_state(self):
        job = Job(**_base_job(job_status=JobStatus.cancelled, progress=0.2))
        assert job.job_status == JobStatus.cancelled


# ---------------------------------------------------------------------------
# Job — 非法构造（invariant violations）
# ---------------------------------------------------------------------------

class TestJobInvariantViolations:
    # created constraints
    def test_created_nonzero_progress_rejected(self):
        with pytest.raises(ValidationError, match="created"):
            Job(**_base_job(job_status=JobStatus.created, progress=0.5))

    def test_created_with_result_ref_rejected(self):
        with pytest.raises(ValidationError, match="created"):
            Job(**_base_job(job_status=JobStatus.created, progress=0.0, result_ref=_artifact_ref()))

    def test_created_with_error_rejected(self):
        with pytest.raises(ValidationError, match="created"):
            Job(**_base_job(job_status=JobStatus.created, progress=0.0, error=_job_error()))

    # pending / running constraints
    def test_pending_progress_one_rejected(self):
        with pytest.raises(ValidationError):
            Job(**_base_job(job_status=JobStatus.pending, progress=1.0))

    def test_running_progress_one_rejected(self):
        with pytest.raises(ValidationError):
            Job(**_base_job(job_status=JobStatus.running, progress=1.0))

    def test_running_with_result_ref_rejected(self):
        with pytest.raises(ValidationError):
            Job(**_base_job(job_status=JobStatus.running, progress=0.5, result_ref=_artifact_ref()))

    def test_running_with_error_rejected(self):
        with pytest.raises(ValidationError):
            Job(**_base_job(job_status=JobStatus.running, progress=0.5, error=_job_error()))

    # completed constraints
    def test_completed_progress_not_one_rejected(self):
        with pytest.raises(ValidationError, match="completed"):
            Job(**_base_job(job_status=JobStatus.completed, progress=0.9, result_ref=_artifact_ref()))

    def test_completed_no_result_ref_rejected(self):
        with pytest.raises(ValidationError, match="completed"):
            Job(**_base_job(job_status=JobStatus.completed, progress=1.0, result_ref=None))

    def test_completed_with_error_rejected(self):
        with pytest.raises(ValidationError, match="completed"):
            Job(**_base_job(
                job_status=JobStatus.completed,
                progress=1.0,
                result_ref=_artifact_ref(),
                error=_job_error(),
            ))

    # failed constraints
    def test_failed_progress_one_rejected(self):
        with pytest.raises(ValidationError):
            Job(**_base_job(job_status=JobStatus.failed, progress=1.0, error=_job_error()))

    def test_failed_no_error_rejected(self):
        with pytest.raises(ValidationError, match="failed"):
            Job(**_base_job(job_status=JobStatus.failed, progress=0.5, error=None))

    def test_failed_with_result_ref_rejected(self):
        with pytest.raises(ValidationError)):
            Job(**_base_job(
                job_status=JobStatus.failed,
                progress=0.5,
                error=_job_error(),
                result_ref=_artifact_ref(),
            ))

    # cancelled constraints
    def test_cancelled_progress_one_rejected(self):
        with pytest.raises(ValidationError):
            Job(**_base_job(job_status=JobStatus.cancelled, progress=1.0))

    def test_cancelled_with_result_ref_rejected(self):
        with pytest.raises(ValidationError):
            Job(**_base_job(job_status=JobStatus.cancelled, progress=0.2, result_ref=_artifact_ref()))

    def test_cancelled_with_error_rejected(self):
        with pytest.raises(ValidationError):
            Job(**_base_job(job_status=JobStatus.cancelled, progress=0.2, error=_job_error()))


# ---------------------------------------------------------------------------
# Job — 序列化往返
# ---------------------------------------------------------------------------

class TestJobRoundtrip:
    def test_created_roundtrip(self):
        job = Job(**_base_job())
        restored = Job.model_validate(job.model_dump())
        assert restored == job

    def test_completed_roundtrip(self):
        job = Job(**_base_job(
            job_status=JobStatus.completed,
            progress=1.0,
            result_ref=_artifact_ref(),
        ))
        restored = Job.model_validate(job.model_dump())
        assert restored.result_ref.object_id == "report-001"

    def test_failed_roundtrip(self):
        job = Job(**_base_job(
            job_status=JobStatus.failed,
            progress=0.3,
            error=_job_error(),
        ))
        restored = Job.model_validate(job.model_dump())
        assert restored.error.code == "ERR_LLM"
```

- [ ] **Step 1.1: 写失败测试** — 创建上述文件

- [ ] **Step 1.2: 运行测试，确认 FAIL（ImportError）**

```bash
cd /c/Users/david/dev/case-adversarial-engine
python -m pytest engines/shared/tests/test_job_model.py -v 2>&1 | head -20
```

期望：`ImportError: cannot import name 'Job' from 'engines.shared.models'`

- [ ] **Step 1.3: 实现 JobStatus + JobError + Job**

在 `engines/shared/models.py` 的枚举段末尾（`ScenarioStatus` 之后，第 151 行后）插入 `JobStatus`，在文件末尾追加 `JobError` 和 `Job`。

**在 `ScenarioStatus` 类之后插入（枚举段）：**

```python
class JobStatus(str, Enum):
    """长任务生命周期状态。"""
    created = "created"
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
```

**在文件末尾追加（`Run` 类之后）：**

```python
# ---------------------------------------------------------------------------
# 长任务层 / Long-running job layer
# ---------------------------------------------------------------------------


class JobError(BaseModel):
    """长任务结构化错误对象。对应 schemas/indexing.schema.json#/$defs/job_error。"""
    code: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    details: Optional[dict[str, Any]] = None


# 合法状态迁移表（在 Job 类之前定义，供 model_validator 引用）
_JOB_VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    "created":   frozenset({"pending", "running", "cancelled", "failed"}),
    "pending":   frozenset({"running", "cancelled", "failed"}),
    "running":   frozenset({"pending", "completed", "failed", "cancelled"}),
    "completed": frozenset(),
    "failed":    frozenset(),
    "cancelled": frozenset(),
}


class Job(BaseModel):
    """长任务状态与进度追踪。对应 schemas/procedure/job.schema.json。

    invariants（由 model_validator 强制）：
    - created:   progress=0, result_ref=null, error=null
    - pending:   0 <= progress < 1, result_ref=null, error=null
    - running:   0 <= progress < 1, result_ref=null, error=null
    - completed: progress=1, result_ref≠null, error=null
    - failed:    progress < 1, result_ref=null, error≠null
    - cancelled: progress < 1, result_ref=null, error=null
    """
    job_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    workspace_id: str = Field(..., min_length=1)
    job_type: str = Field(..., min_length=1)
    job_status: JobStatus
    progress: float = Field(..., ge=0.0, le=1.0)
    message: Optional[str] = None
    result_ref: Optional[ArtifactRef] = None
    error: Optional[JobError] = None
    created_at: str
    updated_at: str

    @model_validator(mode="after")
    def _validate_status_invariants(self) -> "Job":
        s = self.job_status
        p = self.progress
        r = self.result_ref
        e = self.error

        if s == JobStatus.created:
            if p != 0.0:
                raise ValueError("created job must have progress=0.0")
            if r is not None:
                raise ValueError("created job must have result_ref=null")
            if e is not None:
                raise ValueError("created job must have error=null")

        elif s in (JobStatus.pending, JobStatus.running):
            if p >= 1.0:
                raise ValueError(f"{s.value} job progress must be < 1.0")
            if r is not None:
                raise ValueError(f"{s.value} job must have result_ref=null")
            if e is not None:
                raise ValueError(f"{s.value} job must have error=null")

        elif s == JobStatus.completed:
            if p != 1.0:
                raise ValueError("completed job must have progress=1.0")
            if r is None:
                raise ValueError("completed job must have a valid result_ref")
            if e is not None:
                raise ValueError("completed job must have error=null")

        elif s == JobStatus.failed:
            if p >= 1.0:
                raise ValueError("failed job progress must be < 1.0")
            if r is not None:
                raise ValueError("failed job must have result_ref=null")
            if e is None:
                raise ValueError("failed job must have a structured error")

        elif s == JobStatus.cancelled:
            if p >= 1.0:
                raise ValueError("cancelled job progress must be < 1.0")
            if r is not None:
                raise ValueError("cancelled job must have result_ref=null")
            if e is not None:
                raise ValueError("cancelled job must have error=null")

        return self
```

> **注意**：还需在文件顶部的 `from pydantic import BaseModel, Field` 行追加 `model_validator`：
> `from pydantic import BaseModel, Field, model_validator`

- [ ] **Step 1.4: 运行测试，确认全部通过**

```bash
python -m pytest engines/shared/tests/test_job_model.py -v
```

期望：所有 test 通过，0 failures。

- [ ] **Step 1.5: 运行现有全量测试，确认零回归**

```bash
python -m pytest --tb=short -q
```

期望：全部原有测试继续通过。

- [ ] **Step 1.6: Commit**

```bash
git add engines/shared/models.py engines/shared/tests/test_job_model.py
git commit -m "feat(models): add JobStatus, JobError, Job Pydantic models with invariant validators"
```

---

## Task 2: AgentOutput 模型

**Files:**
- Modify: `engines/shared/models.py`（追加 `AgentOutput`）
- Modify: `engines/shared/tests/test_job_model.py`（追加 AgentOutput 测试）

### Step 2.1: 写失败测试

在 `test_job_model.py` 文件末尾追加：

```python
# ---------------------------------------------------------------------------
# AgentOutput
# ---------------------------------------------------------------------------

from engines.shared.models import (
    AgentOutput,
    ProcedurePhase,
    StatementClass,
)


def _base_agent_output(**overrides) -> dict:
    defaults = dict(
        output_id="out-001",
        case_id="case-001",
        run_id="run-001",
        state_id="state-opening-001",
        phase=ProcedurePhase.opening,
        round_index=0,
        agent_role_code="plaintiff_agent",
        owner_party_id="party-plaintiff-001",
        issue_ids=["issue-001"],
        title="原告首轮主张",
        body="原告主张：借贷关系成立，金额为 10 万元。",
        evidence_citations=["ev-001"],
        statement_class=StatementClass.fact,
        risk_flags=[],
        created_at=_now(),
    )
    defaults.update(overrides)
    return defaults


class TestAgentOutputValidConstruction:
    def test_minimal_valid(self):
        out = AgentOutput(**_base_agent_output())
        assert out.output_id == "out-001"
        assert out.phase == ProcedurePhase.opening
        assert out.statement_class == StatementClass.fact

    def test_multiple_issues_and_citations(self):
        out = AgentOutput(**_base_agent_output(
            issue_ids=["issue-001", "issue-002"],
            evidence_citations=["ev-001", "ev-002", "ev-003"],
        ))
        assert len(out.issue_ids) == 2
        assert len(out.evidence_citations) == 3

    def test_inference_class(self):
        out = AgentOutput(**_base_agent_output(statement_class=StatementClass.inference))
        assert out.statement_class == StatementClass.inference

    def test_assumption_class_with_risk_flags(self):
        out = AgentOutput(**_base_agent_output(
            statement_class=StatementClass.assumption,
            risk_flags=["引用不足", "越权风险"],
        ))
        assert "引用不足" in out.risk_flags

    def test_risk_flags_can_be_empty(self):
        out = AgentOutput(**_base_agent_output(risk_flags=[]))
        assert out.risk_flags == []

    def test_round_index_zero(self):
        out = AgentOutput(**_base_agent_output(round_index=0))
        assert out.round_index == 0


class TestAgentOutputInvariantViolations:
    def test_empty_issue_ids_rejected(self):
        with pytest.raises(ValidationError):
            AgentOutput(**_base_agent_output(issue_ids=[]))

    def test_missing_issue_ids_rejected(self):
        data = _base_agent_output()
        del data["issue_ids"]
        with pytest.raises(ValidationError):
            AgentOutput(**data)

    def test_empty_evidence_citations_rejected(self):
        with pytest.raises(ValidationError):
            AgentOutput(**_base_agent_output(evidence_citations=[]))

    def test_missing_evidence_citations_rejected(self):
        data = _base_agent_output()
        del data["evidence_citations"]
        with pytest.raises(ValidationError):
            AgentOutput(**data)

    def test_negative_round_index_rejected(self):
        with pytest.raises(ValidationError):
            AgentOutput(**_base_agent_output(round_index=-1))

    def test_invalid_phase_rejected(self):
        with pytest.raises(ValidationError):
            AgentOutput(**_base_agent_output(phase="invalid_phase"))


class TestAgentOutputRoundtrip:
    def test_serialization_roundtrip(self):
        out = AgentOutput(**_base_agent_output())
        restored = AgentOutput.model_validate(out.model_dump())
        assert restored == out

    def test_phase_serializes_as_string(self):
        out = AgentOutput(**_base_agent_output())
        data = out.model_dump()
        assert data["phase"] == "opening"

    def test_statement_class_serializes_as_string(self):
        out = AgentOutput(**_base_agent_output())
        data = out.model_dump()
        assert data["statement_class"] == "fact"
```

- [ ] **Step 2.1: 追加测试代码**

- [ ] **Step 2.2: 运行测试，确认 FAIL（ImportError: AgentOutput）**

```bash
python -m pytest engines/shared/tests/test_job_model.py::TestAgentOutputValidConstruction -v 2>&1 | head -10
```

- [ ] **Step 2.3: 实现 AgentOutput**

在 `engines/shared/models.py` 的 `Job` 类之后追加：

```python
# ---------------------------------------------------------------------------
# 对抗层 / Adversarial layer
# ---------------------------------------------------------------------------


class AgentOutput(BaseModel):
    """角色在某一程序回合的规范化输出。对应 docs/03_case_object_model.md AgentOutput。

    constraints:
    - issue_ids:         非空（至少绑定一个争点）
    - evidence_citations: 非空（所有关键结论必须有证据引用）
    - statement_class:   明确分类；assumption 不得伪装为 fact（语义层面约束）
    """
    output_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    state_id: str = Field(..., min_length=1)
    phase: ProcedurePhase
    round_index: int = Field(..., ge=0)
    agent_role_code: str = Field(..., min_length=1)
    owner_party_id: str = Field(..., min_length=1)
    issue_ids: list[str] = Field(..., min_length=1, description="必须非空；每条输出都必须绑定争点")
    title: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    evidence_citations: list[str] = Field(
        ..., min_length=1, description="必须非空；所有关键结论必须引用具体证据 ID"
    )
    statement_class: StatementClass
    risk_flags: list[str] = Field(
        default_factory=list,
        description="风险标记列表（自由字符串，如'越权风险'/'引用不足'）",
    )
    created_at: str
```

- [ ] **Step 2.4: 运行测试，确认全部通过**

```bash
python -m pytest engines/shared/tests/test_job_model.py -v
```

- [ ] **Step 2.5: 运行全量测试**

```bash
python -m pytest --tb=short -q
```

- [ ] **Step 2.6: Commit**

```bash
git add engines/shared/models.py engines/shared/tests/test_job_model.py
git commit -m "feat(models): add AgentOutput Pydantic model with issue/citation non-empty constraints"
```

---

## Task 3: JobManager

**Files:**
- Create: `engines/shared/job_manager.py`
- Create: `engines/shared/tests/test_job_manager.py`

### Step 3.1: 写失败测试

创建 `engines/shared/tests/test_job_manager.py`：

```python
"""
JobManager 单元测试。

覆盖路径：
1. create_job: 创建并持久化，生成唯一 job_id
2. load_job: 加载已有 / 缺失返回 None
3. list_jobs: 空列表 / 多 job
4. start_job: created → running / pending → running
5. pend_job: running → pending（可带 message）
6. update_progress: running/pending 中更新 progress + message
7. complete_job: running → completed，写入 result_ref
8. fail_job: running → failed，写入 error
9. cancel_job: created/pending/running → cancelled
10. 非法迁移: 终止态 → 任意状态，抛 ValueError
11. update_progress 越界（>=1）: 抛 ValueError
12. 恢复语义（recovery）: 重建 JobManager 后可继续已有任务
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from engines.shared.job_manager import JobManager
from engines.shared.models import (
    ArtifactRef,
    JobError,
    JobStatus,
)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mgr(tmp_path: Path) -> JobManager:
    ws_dir = tmp_path / "case-test-001"
    return JobManager(workspace_dir=ws_dir)


def _artifact_ref() -> ArtifactRef:
    return ArtifactRef(
        index_name="artifact_index",
        object_type="ReportArtifact",
        object_id="report-001",
        storage_ref="artifacts/report.json",
    )


def _job_error() -> JobError:
    return JobError(code="ERR_LLM", message="LLM call failed")


# ---------------------------------------------------------------------------
# create_job / load_job
# ---------------------------------------------------------------------------

class TestCreateAndLoad:
    def test_create_returns_created_status(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-case-001", "simulation_run")
        assert job.job_status == JobStatus.created
        assert job.progress == 0.0
        assert job.result_ref is None
        assert job.error is None

    def test_create_generates_unique_ids(self, tmp_path):
        mgr = _mgr(tmp_path)
        j1 = mgr.create_job("case-001", "ws-001", "sim")
        j2 = mgr.create_job("case-001", "ws-001", "sim")
        assert j1.job_id != j2.job_id

    def test_create_persists_to_disk(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-case-001", "simulation_run")
        # 直接检查文件存在
        jobs_dir = tmp_path / "case-test-001" / "jobs"
        assert (jobs_dir / f"job_{job.job_id}.json").exists()

    def test_load_existing_job(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-case-001", "simulation_run")
        loaded = mgr.load_job(job.job_id)
        assert loaded is not None
        assert loaded.job_id == job.job_id
        assert loaded.job_status == JobStatus.created

    def test_load_missing_returns_none(self, tmp_path):
        mgr = _mgr(tmp_path)
        assert mgr.load_job("nonexistent-id") is None

    def test_load_roundtrip_preserves_all_fields(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-case-001", "report_generation")
        loaded = mgr.load_job(job.job_id)
        assert loaded.case_id == "case-001"
        assert loaded.workspace_id == "ws-case-001"
        assert loaded.job_type == "report_generation"


# ---------------------------------------------------------------------------
# list_jobs
# ---------------------------------------------------------------------------

class TestListJobs:
    def test_empty_workspace_returns_empty_list(self, tmp_path):
        mgr = _mgr(tmp_path)
        assert mgr.list_jobs() == []

    def test_lists_all_created_jobs(self, tmp_path):
        mgr = _mgr(tmp_path)
        j1 = mgr.create_job("case-001", "ws-001", "sim")
        j2 = mgr.create_job("case-001", "ws-001", "report")
        jobs = mgr.list_jobs()
        ids = {j.job_id for j in jobs}
        assert j1.job_id in ids
        assert j2.job_id in ids


# ---------------------------------------------------------------------------
# start_job (created/pending → running)
# ---------------------------------------------------------------------------

class TestStartJob:
    def test_created_to_running(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        running = mgr.start_job(job.job_id)
        assert running.job_status == JobStatus.running
        assert running.progress == 0.0

    def test_pending_to_running(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        pending = mgr.pend_job(job.job_id)
        resumed = mgr.start_job(pending.job_id)
        assert resumed.job_status == JobStatus.running

    def test_start_persists(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        loaded = mgr.load_job(job.job_id)
        assert loaded.job_status == JobStatus.running


# ---------------------------------------------------------------------------
# pend_job (running → pending)
# ---------------------------------------------------------------------------

class TestPendJob:
    def test_running_to_pending(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        pending = mgr.pend_job(job.job_id)
        assert pending.job_status == JobStatus.pending

    def test_pend_with_message(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        pending = mgr.pend_job(job.job_id, message="checkpoint after round 1")
        assert pending.message == "checkpoint after round 1"


# ---------------------------------------------------------------------------
# update_progress
# ---------------------------------------------------------------------------

class TestUpdateProgress:
    def test_update_progress_on_running(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        updated = mgr.update_progress(job.job_id, 0.5)
        assert updated.progress == 0.5

    def test_update_progress_with_message(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        updated = mgr.update_progress(job.job_id, 0.3, message="opening round done")
        assert updated.message == "opening round done"

    def test_update_progress_on_pending(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        mgr.pend_job(job.job_id)
        updated = mgr.update_progress(job.job_id, 0.4)
        assert updated.progress == 0.4

    def test_update_progress_to_one_raises(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        with pytest.raises(ValueError, match="complete_job"):
            mgr.update_progress(job.job_id, 1.0)

    def test_update_progress_on_created_raises(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        with pytest.raises(ValueError):
            mgr.update_progress(job.job_id, 0.5)


# ---------------------------------------------------------------------------
# complete_job
# ---------------------------------------------------------------------------

class TestCompleteJob:
    def test_running_to_completed(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        completed = mgr.complete_job(job.job_id, _artifact_ref())
        assert completed.job_status == JobStatus.completed
        assert completed.progress == 1.0
        assert completed.result_ref is not None
        assert completed.result_ref.object_id == "report-001"
        assert completed.error is None

    def test_complete_persists(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        mgr.complete_job(job.job_id, _artifact_ref())
        loaded = mgr.load_job(job.job_id)
        assert loaded.job_status == JobStatus.completed
        assert loaded.result_ref.object_id == "report-001"


# ---------------------------------------------------------------------------
# fail_job
# ---------------------------------------------------------------------------

class TestFailJob:
    def test_running_to_failed(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        failed = mgr.fail_job(job.job_id, _job_error())
        assert failed.job_status == JobStatus.failed
        assert failed.error.code == "ERR_LLM"
        assert failed.result_ref is None

    def test_created_to_failed(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        failed = mgr.fail_job(job.job_id, _job_error())
        assert failed.job_status == JobStatus.failed

    def test_fail_persists(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        mgr.fail_job(job.job_id, _job_error())
        loaded = mgr.load_job(job.job_id)
        assert loaded.job_status == JobStatus.failed
        assert loaded.error.message == "LLM call failed"


# ---------------------------------------------------------------------------
# cancel_job
# ---------------------------------------------------------------------------

class TestCancelJob:
    def test_created_to_cancelled(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        cancelled = mgr.cancel_job(job.job_id)
        assert cancelled.job_status == JobStatus.cancelled

    def test_running_to_cancelled(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        cancelled = mgr.cancel_job(job.job_id)
        assert cancelled.job_status == JobStatus.cancelled
        assert cancelled.result_ref is None
        assert cancelled.error is None


# ---------------------------------------------------------------------------
# 非法迁移
# ---------------------------------------------------------------------------

class TestInvalidTransitions:
    def test_completed_cannot_be_cancelled(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        mgr.complete_job(job.job_id, _artifact_ref())
        with pytest.raises(ValueError, match="Invalid transition"):
            mgr.cancel_job(job.job_id)

    def test_completed_cannot_be_failed(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        mgr.complete_job(job.job_id, _artifact_ref())
        with pytest.raises(ValueError, match="Invalid transition"):
            mgr.fail_job(job.job_id, _job_error())

    def test_failed_cannot_be_restarted(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.fail_job(job.job_id, _job_error())
        with pytest.raises(ValueError, match="Invalid transition"):
            mgr.start_job(job.job_id)

    def test_cancelled_cannot_be_started(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.cancel_job(job.job_id)
        with pytest.raises(ValueError, match="Invalid transition"):
            mgr.start_job(job.job_id)

    def test_created_cannot_be_completed_directly(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        # created → pending/running/cancelled/failed only; not completed
        # 需要先 start 才能 complete
        with pytest.raises(ValueError, match="Invalid transition"):
            mgr.complete_job(job.job_id, _artifact_ref())

    def test_start_unknown_job_raises(self, tmp_path):
        mgr = _mgr(tmp_path)
        with pytest.raises(ValueError, match="not found"):
            mgr.start_job("nonexistent-job-id")


# ---------------------------------------------------------------------------
# 恢复语义 (recovery)
# ---------------------------------------------------------------------------

class TestRecovery:
    def test_fresh_manager_can_resume_pending_job(self, tmp_path):
        """模拟进程重启：重建 JobManager 后可继续 pending 任务。"""
        ws_dir = tmp_path / "case-test-001"
        mgr1 = JobManager(workspace_dir=ws_dir)
        job = mgr1.create_job("case-001", "ws-001", "sim")
        mgr1.start_job(job.job_id)
        mgr1.pend_job(job.job_id, message="interrupted at round 1")

        # 模拟进程重启：重建 mgr
        mgr2 = JobManager(workspace_dir=ws_dir)
        loaded = mgr2.load_job(job.job_id)
        assert loaded is not None
        assert loaded.job_status == JobStatus.pending
        assert loaded.message == "interrupted at round 1"

        # 可以继续
        resumed = mgr2.start_job(loaded.job_id)
        assert resumed.job_status == JobStatus.running

    def test_terminal_job_preserved_as_audit_record(self, tmp_path):
        """完成后的 Job 作为审计记录保留，不能重新打开。"""
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        mgr.complete_job(job.job_id, _artifact_ref())

        # 创建新 job 而不是重新打开旧 job
        new_job = mgr.create_job("case-001", "ws-001", "sim")
        assert new_job.job_id != job.job_id

        # 原 job 仍可加载（审计记录）
        original = mgr.load_job(job.job_id)
        assert original.job_status == JobStatus.completed
```

- [ ] **Step 3.1: 写测试文件**

- [ ] **Step 3.2: 运行测试，确认 FAIL（ImportError）**

```bash
python -m pytest engines/shared/tests/test_job_manager.py -v 2>&1 | head -10
```

期望：`ImportError: cannot import name 'JobManager' from 'engines.shared.job_manager'`（或 ModuleNotFoundError）

- [ ] **Step 3.3: 实现 JobManager**

创建 `engines/shared/job_manager.py`：

```python
"""
JobManager — 长任务生命周期管理器。
JobManager — long-running job lifecycle manager.

职责 / Responsibility:
- Job 的 CRUD + 状态迁移 + 进度更新
- 持久化到 {workspace_dir}/jobs/job_{id}.json
- 与 WorkspaceManager 完全解耦（不互相持有引用）
- 只知道 Job 文件，不知道 artifact_index 细节

设计原则 / Design:
- 不预设 queue / broker / 云依赖（单进程本地实现）
- 终止态 Job 不能重新打开；重试必须创建新 job_id
- 中断后通过已持久化的 Job 文件重新装载，不依赖内存中间结果
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from engines.shared.models import (
    ArtifactRef,
    Job,
    JobError,
    JobStatus,
)

# ---------------------------------------------------------------------------
# 状态迁移矩阵 / Transition matrix
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.created:   frozenset({JobStatus.pending, JobStatus.running, JobStatus.cancelled, JobStatus.failed}),
    JobStatus.pending:   frozenset({JobStatus.running, JobStatus.cancelled, JobStatus.failed}),
    JobStatus.running:   frozenset({JobStatus.pending, JobStatus.completed, JobStatus.failed, JobStatus.cancelled}),
    JobStatus.completed: frozenset(),
    JobStatus.failed:    frozenset(),
    JobStatus.cancelled: frozenset(),
}


class JobManager:
    """案件工作区内的长任务生命周期管理器。

    初始化时只需要 workspace_dir（= {base_dir}/{case_id}）；
    Job 文件存储在 {workspace_dir}/jobs/job_{id}.json。
    """

    def __init__(self, workspace_dir: Path) -> None:
        self.workspace_dir = workspace_dir

    # ------------------------------------------------------------------
    # 内部辅助 / Internal helpers
    # ------------------------------------------------------------------

    def _jobs_dir(self) -> Path:
        return self.workspace_dir / "jobs"

    def _job_path(self, job_id: str) -> Path:
        return self._jobs_dir() / f"job_{job_id}.json"

    def _atomic_write(self, path: Path, data: dict) -> None:
        """原子写：先写 .tmp，再 os.replace。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)

    def _now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _transition(
        self,
        job_id: str,
        new_status: JobStatus,
        **field_overrides,
    ) -> Job:
        """内部状态迁移辅助：验证合法性，更新字段，持久化并返回新 Job。"""
        job = self.load_job(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id!r}")
        if new_status not in _VALID_TRANSITIONS[job.job_status]:
            raise ValueError(
                f"Invalid transition {job.job_status.value!r} → {new_status.value!r} "
                f"for job {job_id!r}"
            )
        data = job.model_dump()
        data["job_status"] = new_status.value
        data["updated_at"] = self._now()
        for key, val in field_overrides.items():
            data[key] = val
        updated = Job.model_validate(data)
        self._atomic_write(self._job_path(job_id), updated.model_dump())
        return updated

    # ------------------------------------------------------------------
    # CRUD / Lifecycle
    # ------------------------------------------------------------------

    def create_job(self, case_id: str, workspace_id: str, job_type: str) -> Job:
        """创建并持久化新 Job（初始状态：created, progress=0）。"""
        job_id = str(uuid.uuid4())
        now = self._now()
        job = Job(
            job_id=job_id,
            case_id=case_id,
            workspace_id=workspace_id,
            job_type=job_type,
            job_status=JobStatus.created,
            progress=0.0,
            message=None,
            result_ref=None,
            error=None,
            created_at=now,
            updated_at=now,
        )
        self._atomic_write(self._job_path(job_id), job.model_dump())
        return job

    def load_job(self, job_id: str) -> Optional[Job]:
        """从磁盘加载 Job。若文件不存在，返回 None。"""
        path = self._job_path(job_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return Job.model_validate(data)

    def list_jobs(self) -> list[Job]:
        """返回当前 workspace_dir/jobs/ 下所有 Job（按文件名排序）。"""
        jobs_dir = self._jobs_dir()
        if not jobs_dir.exists():
            return []
        jobs = []
        for path in sorted(jobs_dir.glob("job_*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            jobs.append(Job.model_validate(data))
        return jobs

    # ------------------------------------------------------------------
    # 状态迁移 / State transitions
    # ------------------------------------------------------------------

    def start_job(self, job_id: str) -> Job:
        """created / pending → running。"""
        return self._transition(job_id, JobStatus.running)

    def pend_job(self, job_id: str, message: Optional[str] = None) -> Job:
        """running → pending（中断 checkpoint）。可选地设置 message。"""
        overrides: dict = {}
        if message is not None:
            overrides["message"] = message
        return self._transition(job_id, JobStatus.pending, **overrides)

    def update_progress(
        self,
        job_id: str,
        progress: float,
        message: Optional[str] = None,
    ) -> Job:
        """在 running / pending 状态下更新 progress 和可选 message（不改变 status）。

        progress 必须 < 1.0；完成任务请调用 complete_job()。
        """
        job = self.load_job(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id!r}")
        if job.job_status not in (JobStatus.running, JobStatus.pending):
            raise ValueError(
                f"update_progress only applies to running/pending jobs, "
                f"got {job.job_status.value!r}"
            )
        if progress >= 1.0:
            raise ValueError(
                "Use complete_job() to set progress=1.0 and record result_ref"
            )
        data = job.model_dump()
        data["progress"] = progress
        data["updated_at"] = self._now()
        if message is not None:
            data["message"] = message
        updated = Job.model_validate(data)
        self._atomic_write(self._job_path(job_id), updated.model_dump())
        return updated

    def complete_job(self, job_id: str, result_ref: ArtifactRef) -> Job:
        """running → completed。result_ref 必须指向已登记的 artifact。"""
        return self._transition(
            job_id,
            JobStatus.completed,
            progress=1.0,
            result_ref=result_ref.model_dump(),
            error=None,
        )

    def fail_job(self, job_id: str, error: JobError) -> Job:
        """created / pending / running → failed。"""
        return self._transition(
            job_id,
            JobStatus.failed,
            error=error.model_dump(),
            result_ref=None,
        )

    def cancel_job(self, job_id: str) -> Job:
        """created / pending / running → cancelled。"""
        return self._transition(
            job_id,
            JobStatus.cancelled,
            result_ref=None,
            error=None,
        )
```

- [ ] **Step 3.4: 运行 JobManager 测试，确认全部通过**

```bash
python -m pytest engines/shared/tests/test_job_manager.py -v
```

期望：所有测试通过。

- [ ] **Step 3.5: 运行全量测试，确认零回归**

```bash
python -m pytest --tb=short -q
```

- [ ] **Step 3.6: Commit**

```bash
git add engines/shared/job_manager.py engines/shared/tests/test_job_manager.py
git commit -m "feat(job_manager): implement JobManager with state machine and atomic persistence"
```

---

## Task 4: 最终验收 + Push

- [ ] **Step 4.1: 运行全量测试（含所有已有测试）**

```bash
python -m pytest --tb=short -q
```

期望：所有原有测试继续通过，新增测试全部通过。

- [ ] **Step 4.2: 确认新增测试数量**

```bash
python -m pytest engines/shared/tests/ -v --co -q
```

期望：test_job_model.py 和 test_job_manager.py 的测试用例全部列出。

- [ ] **Step 4.3: Push**

```bash
export PATH="/c/Program Files/GitHub CLI:$PATH"
git push
```

---

## 注意事项

1. **`model_validator` import**：在 `models.py` 顶部的 `from pydantic import ...` 行需要追加 `model_validator`。
2. **`_JOB_VALID_TRANSITIONS` 字典**：放在 `Job` 类定义之前，供 `model_validator` 引用（实际在 `Job` 的 validator 内部访问 `self.job_status` 做分支判断，不直接用字典，所以字典放在 `job_manager.py` 里即可）。
3. **`test_job_model.py` 的 import 顺序**：两个 import 块（Task 1 的和 Task 2 追加的）合并成一个 import 块放在文件顶部。
4. **`test_failed_with_result_ref_rejected` 中有语法错误**：`pytest.raises(ValidationError))` 有多余的 `)`, 写测试时需修正。
5. **`_base_agent_output` 的默认值**：`risk_flags=[]` 使用 `default_factory=list` 在 AgentOutput 中是安全的。
6. **Windows 路径**：代码中使用 `os.replace()` 而非 POSIX rename，已在 WorkspaceManager 中验证可用。
