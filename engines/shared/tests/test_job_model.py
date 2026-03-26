"""
Job 模型单元测试 — JobStatus / JobError / Job / AgentOutput。
Job model unit tests — JobStatus / JobError / Job / AgentOutput.

覆盖路径 / Coverage:
1. JobStatus: 枚举值完整性
2. JobError: 合法/非法构造
3. Job: 合法构造（每种终态和中间态）
4. Job: invariant 违反（model_validator 拒绝不一致状态）
5. Job: 序列化往返（含 ArtifactRef 嵌套）
6. AgentOutput: 合法构造
7. AgentOutput: 非法构造（issue_ids/evidence_citations 不能为空）
8. AgentOutput: 序列化往返
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from engines.shared.models import (
    AgentOutput,
    ArtifactRef,
    Job,
    JobError,
    JobStatus,
    ProcedurePhase,
    StatementClass,
)


# ---------------------------------------------------------------------------
# 工具函数 / Utilities
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _base_job(**overrides) -> dict:
    defaults: dict = dict(
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


def _base_agent_output(**overrides) -> dict:
    defaults: dict = dict(
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
        assert job.progress == 0.3

    def test_running_state_with_message(self):
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
        assert job.error is None

    def test_failed_state(self):
        job = Job(**_base_job(
            job_status=JobStatus.failed,
            progress=0.4,
            error=_job_error(),
        ))
        assert job.job_status == JobStatus.failed
        assert job.error.code == "ERR_LLM"
        assert job.result_ref is None

    def test_cancelled_state(self):
        job = Job(**_base_job(job_status=JobStatus.cancelled, progress=0.2))
        assert job.job_status == JobStatus.cancelled
        assert job.result_ref is None
        assert job.error is None

    def test_running_zero_progress_valid(self):
        job = Job(**_base_job(job_status=JobStatus.running, progress=0.0))
        assert job.progress == 0.0


# ---------------------------------------------------------------------------
# Job — invariant 违反（model_validator 拒绝）
# ---------------------------------------------------------------------------


class TestJobInvariantViolations:
    # created constraints
    def test_created_nonzero_progress_rejected(self):
        with pytest.raises(ValidationError, match="created"):
            Job(**_base_job(job_status=JobStatus.created, progress=0.5))

    def test_created_with_result_ref_rejected(self):
        with pytest.raises(ValidationError, match="created"):
            Job(**_base_job(
                job_status=JobStatus.created,
                progress=0.0,
                result_ref=_artifact_ref(),
            ))

    def test_created_with_error_rejected(self):
        with pytest.raises(ValidationError, match="created"):
            Job(**_base_job(
                job_status=JobStatus.created,
                progress=0.0,
                error=_job_error(),
            ))

    # pending / running constraints
    def test_pending_progress_one_rejected(self):
        with pytest.raises(ValidationError):
            Job(**_base_job(job_status=JobStatus.pending, progress=1.0))

    def test_running_progress_one_rejected(self):
        with pytest.raises(ValidationError):
            Job(**_base_job(job_status=JobStatus.running, progress=1.0))

    def test_running_with_result_ref_rejected(self):
        with pytest.raises(ValidationError):
            Job(**_base_job(
                job_status=JobStatus.running,
                progress=0.5,
                result_ref=_artifact_ref(),
            ))

    def test_running_with_error_rejected(self):
        with pytest.raises(ValidationError):
            Job(**_base_job(
                job_status=JobStatus.running,
                progress=0.5,
                error=_job_error(),
            ))

    # completed constraints
    def test_completed_progress_not_one_rejected(self):
        with pytest.raises(ValidationError, match="completed"):
            Job(**_base_job(
                job_status=JobStatus.completed,
                progress=0.9,
                result_ref=_artifact_ref(),
            ))

    def test_completed_no_result_ref_rejected(self):
        with pytest.raises(ValidationError, match="completed"):
            Job(**_base_job(
                job_status=JobStatus.completed,
                progress=1.0,
                result_ref=None,
            ))

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
            Job(**_base_job(
                job_status=JobStatus.failed,
                progress=1.0,
                error=_job_error(),
            ))

    def test_failed_no_error_rejected(self):
        with pytest.raises(ValidationError, match="failed"):
            Job(**_base_job(job_status=JobStatus.failed, progress=0.5, error=None))

    def test_failed_with_result_ref_rejected(self):
        with pytest.raises(ValidationError):
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
            Job(**_base_job(
                job_status=JobStatus.cancelled,
                progress=0.2,
                result_ref=_artifact_ref(),
            ))

    def test_cancelled_with_error_rejected(self):
        with pytest.raises(ValidationError):
            Job(**_base_job(
                job_status=JobStatus.cancelled,
                progress=0.2,
                error=_job_error(),
            ))


# ---------------------------------------------------------------------------
# Job — 序列化往返 / Serialization roundtrip
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
        assert restored.result_ref.index_name == "artifact_index"

    def test_failed_roundtrip(self):
        job = Job(**_base_job(
            job_status=JobStatus.failed,
            progress=0.3,
            error=_job_error(),
        ))
        restored = Job.model_validate(job.model_dump())
        assert restored.error.code == "ERR_LLM"
        assert restored.error.message == "LLM call failed"

    def test_job_status_serializes_as_string(self):
        job = Job(**_base_job())
        data = job.model_dump()
        assert data["job_status"] == "created"


# ---------------------------------------------------------------------------
# AgentOutput — 合法构造
# ---------------------------------------------------------------------------


class TestAgentOutputValidConstruction:
    def test_minimal_valid(self):
        out = AgentOutput(**_base_agent_output())
        assert out.output_id == "out-001"
        assert out.phase == ProcedurePhase.opening
        assert out.statement_class == StatementClass.fact
        assert out.round_index == 0

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
        assert len(out.risk_flags) == 2

    def test_risk_flags_can_be_empty(self):
        out = AgentOutput(**_base_agent_output(risk_flags=[]))
        assert out.risk_flags == []

    def test_risk_flags_default_to_empty(self):
        data = _base_agent_output()
        del data["risk_flags"]
        out = AgentOutput(**data)
        assert out.risk_flags == []

    def test_all_procedure_phases(self):
        for phase in ProcedurePhase:
            out = AgentOutput(**_base_agent_output(phase=phase))
            assert out.phase == phase

    def test_rebuttal_phase_round_index_two(self):
        out = AgentOutput(**_base_agent_output(
            phase=ProcedurePhase.rebuttal,
            round_index=2,
        ))
        assert out.round_index == 2


# ---------------------------------------------------------------------------
# AgentOutput — invariant 违反
# ---------------------------------------------------------------------------


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

    def test_invalid_statement_class_rejected(self):
        with pytest.raises(ValidationError):
            AgentOutput(**_base_agent_output(statement_class="opinion"))


# ---------------------------------------------------------------------------
# AgentOutput — 序列化往返 / Serialization roundtrip
# ---------------------------------------------------------------------------


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

    def test_roundtrip_with_risk_flags(self):
        out = AgentOutput(**_base_agent_output(risk_flags=["越权风险", "程序冲突"]))
        restored = AgentOutput.model_validate(out.model_dump())
        assert restored.risk_flags == ["越权风险", "程序冲突"]
