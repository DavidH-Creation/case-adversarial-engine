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
- 终止态 Job（completed/failed/cancelled）不能重新打开；重试必须创建新 job_id
- 中断恢复通过已持久化的 Job 文件重新装载，不依赖内存中间结果
- 状态一致性由两层保证：Job model_validator（invariants）+ _transition（transition legality）
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_JOB_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")

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
    JobStatus.created: frozenset(
        {JobStatus.pending, JobStatus.running, JobStatus.cancelled, JobStatus.failed}
    ),
    JobStatus.pending: frozenset({JobStatus.running, JobStatus.cancelled, JobStatus.failed}),
    JobStatus.running: frozenset(
        {JobStatus.pending, JobStatus.completed, JobStatus.failed, JobStatus.cancelled}
    ),
    JobStatus.completed: frozenset(),
    JobStatus.failed: frozenset(),
    JobStatus.cancelled: frozenset(),
}


class JobManager:
    """案件工作区内的长任务生命周期管理器。

    使用方式 / Usage:
        mgr = JobManager(workspace_dir=Path("cases/case-001"))
        job = mgr.create_job("case-001", "ws-case-001", "simulation_run")
        mgr.start_job(job.job_id)
        mgr.update_progress(job.job_id, 0.5, "halfway")
        mgr.complete_job(job.job_id, result_ref)

    Job 文件路径 / Job file path:
        {workspace_dir}/jobs/job_{job_id}.json
    """

    def __init__(self, workspace_dir: Path) -> None:
        self.workspace_dir = workspace_dir

    # ------------------------------------------------------------------
    # 内部辅助 / Internal helpers
    # ------------------------------------------------------------------

    def _jobs_dir(self) -> Path:
        return self.workspace_dir / "jobs"

    def _job_path(self, job_id: str) -> Path:
        if not _JOB_ID_RE.match(job_id):
            raise ValueError(
                f"Invalid job_id format: {job_id!r}. "
                "Only alphanumeric characters, hyphens, and underscores are allowed."
            )
        return self._jobs_dir() / f"job_{job_id}.json"

    def _atomic_write(self, path: Path, data: dict) -> None:
        """原子写：先写 .tmp，再 os.replace。
        Atomic write: write .tmp then os.replace.
        On POSIX this is atomic; on Windows it is best-effort (os.replace).
        """
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
        """内部状态迁移：验证合法性，更新字段，持久化，返回新 Job。

        field_overrides 中的值会覆盖 model_dump() 中对应的键。
        ArtifactRef / JobError 等嵌套对象需先 .model_dump() 再传入。
        """
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
        """创建并持久化新 Job（初始状态：created，progress=0.0）。
        Create and persist a new Job (initial state: created, progress=0.0).
        """
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
        """从磁盘加载 Job。若文件不存在，返回 None。
        Load Job from disk. Returns None if the file does not exist.
        """
        path = self._job_path(job_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return Job.model_validate(data)

    def list_jobs(self) -> list[Job]:
        """返回当前 {workspace_dir}/jobs/ 下所有 Job（按文件名排序）。
        Return all Jobs under {workspace_dir}/jobs/ sorted by filename.
        """
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
        """running → pending（中断 checkpoint）。
        Running → pending (interrupt checkpoint).
        可选地覆盖 message；不传则保留原有 message。
        """
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
        Update progress and optional message on running/pending job (no status change).

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
            raise ValueError("Use complete_job() to set progress=1.0 and record result_ref")
        data = job.model_dump()
        data["progress"] = progress
        data["updated_at"] = self._now()
        if message is not None:
            data["message"] = message
        updated = Job.model_validate(data)
        self._atomic_write(self._job_path(job_id), updated.model_dump())
        return updated

    def complete_job(self, job_id: str, result_ref: ArtifactRef) -> Job:
        """running → completed。result_ref 必须指向已在 artifact_index 登记的产物。
        Running → completed. result_ref must point to an artifact registered in artifact_index.
        """
        return self._transition(
            job_id,
            JobStatus.completed,
            progress=1.0,
            result_ref=result_ref.model_dump(),
            error=None,
        )

    def fail_job(self, job_id: str, error: JobError) -> Job:
        """created / pending / running → failed。
        Created / pending / running → failed.
        """
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
