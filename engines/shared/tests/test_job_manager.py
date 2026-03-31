"""
JobManager 单元测试。
JobManager unit tests.

覆盖路径 / Coverage:
1. create_job: 创建并持久化，生成唯一 job_id，初始状态正确
2. load_job: 加载已有 / 不存在返回 None
3. list_jobs: 空目录 / 多 job
4. start_job: created → running / pending → running
5. pend_job: running → pending（可带 message）
6. update_progress: running/pending 中更新 progress + message
7. complete_job: running → completed，写入 result_ref
8. fail_job: running/created → failed，写入 error
9. cancel_job: created/pending/running → cancelled
10. 非法迁移: 终止态 → 任意状态，抛 ValueError("Invalid transition")
11. update_progress >= 1.0: 抛 ValueError
12. update_progress on created: 抛 ValueError
13. 恢复语义: 重建 JobManager 后可继续已有任务
14. 终止 Job 作为审计记录保留
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engines.shared.job_manager import JobManager
from engines.shared.models import (
    ArtifactRef,
    JobError,
    JobStatus,
)


# ---------------------------------------------------------------------------
# 工具函数 / Utilities
# ---------------------------------------------------------------------------


def _mgr(tmp_path: Path) -> JobManager:
    return JobManager(workspace_dir=tmp_path / "case-test-001")


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
        assert job.message is None

    def test_create_stores_correct_metadata(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-case-001", "simulation_run")
        assert job.case_id == "case-001"
        assert job.workspace_id == "ws-case-001"
        assert job.job_type == "simulation_run"

    def test_create_generates_unique_ids(self, tmp_path):
        mgr = _mgr(tmp_path)
        j1 = mgr.create_job("case-001", "ws-001", "sim")
        j2 = mgr.create_job("case-001", "ws-001", "sim")
        assert j1.job_id != j2.job_id

    def test_create_persists_to_disk(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-case-001", "simulation_run")
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
        assert loaded.created_at == job.created_at


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
        assert len(jobs) == 2


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

    def test_start_unknown_job_raises(self, tmp_path):
        mgr = _mgr(tmp_path)
        with pytest.raises(ValueError, match="not found"):
            mgr.start_job("nonexistent-job-id")


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

    def test_pend_without_message_keeps_existing(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        mgr.update_progress(job.job_id, 0.3, message="step 1 done")
        pending = mgr.pend_job(job.job_id)
        # no message override → preserves prior message
        assert pending.message == "step 1 done"

    def test_pend_persists(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        mgr.pend_job(job.job_id, message="halted")
        loaded = mgr.load_job(job.job_id)
        assert loaded.job_status == JobStatus.pending
        assert loaded.message == "halted"


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
        assert updated.progress == 0.3

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

    def test_update_progress_persists(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        mgr.update_progress(job.job_id, 0.6, message="two thirds done")
        loaded = mgr.load_job(job.job_id)
        assert loaded.progress == 0.6
        assert loaded.message == "two thirds done"


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
        assert loaded.progress == 1.0

    def test_complete_result_ref_preserves_all_fields(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        ref = ArtifactRef(
            index_name="artifact_index",
            object_type="AgentOutput",
            object_id="out-001",
            storage_ref="artifacts/private/plaintiff/agent_outputs/out-001.json",
        )
        completed = mgr.complete_job(job.job_id, ref)
        assert completed.result_ref.object_type == "AgentOutput"
        assert (
            completed.result_ref.storage_ref
            == "artifacts/private/plaintiff/agent_outputs/out-001.json"
        )


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

    def test_fail_with_details(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        err = JobError(code="ERR_TIMEOUT", message="timed out", details={"timeout_s": 60})
        failed = mgr.fail_job(job.job_id, err)
        assert failed.error.details == {"timeout_s": 60}


# ---------------------------------------------------------------------------
# cancel_job
# ---------------------------------------------------------------------------


class TestCancelJob:
    def test_created_to_cancelled(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        cancelled = mgr.cancel_job(job.job_id)
        assert cancelled.job_status == JobStatus.cancelled
        assert cancelled.result_ref is None
        assert cancelled.error is None

    def test_pending_to_cancelled(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        mgr.pend_job(job.job_id)
        cancelled = mgr.cancel_job(job.job_id)
        assert cancelled.job_status == JobStatus.cancelled

    def test_running_to_cancelled(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        cancelled = mgr.cancel_job(job.job_id)
        assert cancelled.job_status == JobStatus.cancelled

    def test_cancel_persists(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.cancel_job(job.job_id)
        loaded = mgr.load_job(job.job_id)
        assert loaded.job_status == JobStatus.cancelled


# ---------------------------------------------------------------------------
# 非法迁移 / Invalid transitions
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
        """created → completed は合法迁移外，必须先 start。"""
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        with pytest.raises(ValueError, match="Invalid transition"):
            mgr.complete_job(job.job_id, _artifact_ref())

    def test_completed_cannot_be_pending(self, tmp_path):
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        mgr.complete_job(job.job_id, _artifact_ref())
        with pytest.raises(ValueError, match="Invalid transition"):
            mgr.pend_job(job.job_id)


# ---------------------------------------------------------------------------
# 恢复语义 / Recovery semantics
# ---------------------------------------------------------------------------


class TestRecovery:
    def test_fresh_manager_can_resume_pending_job(self, tmp_path):
        """进程重启后重建 JobManager 可继续 pending 任务。"""
        ws_dir = tmp_path / "case-test-001"
        mgr1 = JobManager(workspace_dir=ws_dir)
        job = mgr1.create_job("case-001", "ws-001", "sim")
        mgr1.start_job(job.job_id)
        mgr1.pend_job(job.job_id, message="interrupted at round 1")

        # 模拟进程重启：重建 JobManager
        mgr2 = JobManager(workspace_dir=ws_dir)
        loaded = mgr2.load_job(job.job_id)
        assert loaded is not None
        assert loaded.job_status == JobStatus.pending
        assert loaded.message == "interrupted at round 1"

        resumed = mgr2.start_job(loaded.job_id)
        assert resumed.job_status == JobStatus.running

    def test_terminal_job_preserved_as_audit_record(self, tmp_path):
        """完成后的 Job 作为审计记录保留，不能重新打开；重试需创建新 job。"""
        mgr = _mgr(tmp_path)
        job = mgr.create_job("case-001", "ws-001", "sim")
        mgr.start_job(job.job_id)
        mgr.complete_job(job.job_id, _artifact_ref())

        # 新任务创建新 job_id
        new_job = mgr.create_job("case-001", "ws-001", "sim")
        assert new_job.job_id != job.job_id

        # 原 job 仍可加载（审计记录）
        original = mgr.load_job(job.job_id)
        assert original.job_status == JobStatus.completed

    def test_progress_only_reflects_persisted_milestones(self, tmp_path):
        """progress 只反映已持久化的里程碑，not in-memory state。"""
        ws_dir = tmp_path / "case-test-001"
        mgr1 = JobManager(workspace_dir=ws_dir)
        job = mgr1.create_job("case-001", "ws-001", "sim")
        mgr1.start_job(job.job_id)
        mgr1.update_progress(job.job_id, 0.33, message="round 1 done")

        # 重建 mgr，progress 仍是 0.33
        mgr2 = JobManager(workspace_dir=ws_dir)
        loaded = mgr2.load_job(job.job_id)
        assert loaded.progress == 0.33
        assert loaded.message == "round 1 done"
