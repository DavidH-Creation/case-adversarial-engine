"""Tests for engines.shared.checkpoint — CheckpointManager."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engines.shared.checkpoint import (
    CHECKPOINT_FILENAME,
    CHECKPOINT_SCHEMA_VERSION,
    CheckpointManager,
    CheckpointState,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def run_dir(tmp_path: Path) -> Path:
    """Return a temporary output directory for a single run."""
    d = tmp_path / "outputs" / "test-run"
    d.mkdir(parents=True)
    return d


@pytest.fixture()
def mgr(run_dir: Path) -> CheckpointManager:
    return CheckpointManager(run_dir)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestSaveAndLoad:
    """save() persists state; load() recovers it."""

    def test_save_creates_checkpoint_file(self, mgr: CheckpointManager, run_dir: Path) -> None:
        mgr.save("step_1", {"evidence_index": "evidence_index.json"}, run_id="run-abc")
        assert (run_dir / CHECKPOINT_FILENAME).exists()

    def test_load_returns_correct_state(self, mgr: CheckpointManager) -> None:
        mgr.save("step_2", {"issue_tree": "issue_tree.json"}, run_id="run-xyz")
        state = mgr.load()

        assert state is not None
        assert state.run_id == "run-xyz"
        assert state.last_completed_step == "step_2"
        assert state.artifact_paths == {"issue_tree": "issue_tree.json"}
        assert state.schema_version == CHECKPOINT_SCHEMA_VERSION
        assert state.timestamp  # non-empty

    def test_save_merges_artifact_paths(self, mgr: CheckpointManager) -> None:
        """Successive saves accumulate artifact paths."""
        mgr.save("step_1", {"a": "a.json"}, run_id="run-1")
        mgr.save("step_2", {"b": "b.json"})

        state = mgr.load()
        assert state is not None
        assert state.last_completed_step == "step_2"
        assert state.artifact_paths == {"a": "a.json", "b": "b.json"}
        # run_id should be preserved from first save
        assert state.run_id == "run-1"

    def test_full_pipeline_checkpoint_last_step(self, mgr: CheckpointManager) -> None:
        """After a full run, last_completed_step is the final step."""
        mgr.save("step_1", {"ev": "ev.json"}, run_id="run-full")
        mgr.save("step_2", {"it": "it.json"})
        mgr.save("step_3", {"res": "res.json"})
        mgr.save("step_4", {"out": "out.json"})
        mgr.save("step_5", {"docx": "docx.json"})

        state = mgr.load()
        assert state is not None
        assert state.last_completed_step == "step_5"
        assert len(state.artifact_paths) == 5


class TestClear:
    def test_clear_removes_file(self, mgr: CheckpointManager, run_dir: Path) -> None:
        mgr.save("step_1", {"a": "a.json"})
        assert (run_dir / CHECKPOINT_FILENAME).exists()

        mgr.clear()
        assert not (run_dir / CHECKPOINT_FILENAME).exists()

    def test_clear_when_no_checkpoint(self, mgr: CheckpointManager) -> None:
        """clear() is a no-op when there's nothing to clear."""
        mgr.clear()  # should not raise


class TestLoadNone:
    def test_load_returns_none_when_no_file(self, mgr: CheckpointManager) -> None:
        assert mgr.load() is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestCorruptCheckpoint:
    def test_corrupt_json_raises_valueerror(self, mgr: CheckpointManager, run_dir: Path) -> None:
        (run_dir / CHECKPOINT_FILENAME).write_text("NOT VALID JSON {{", encoding="utf-8")
        with pytest.raises(ValueError, match="corrupt"):
            mgr.load()

    def test_incompatible_schema_version(self, mgr: CheckpointManager, run_dir: Path) -> None:
        payload = {
            "schema_version": 9999,
            "run_id": "old",
            "last_completed_step": "step_1",
            "artifact_paths": {},
            "timestamp": "2026-01-01T00:00:00Z",
        }
        (run_dir / CHECKPOINT_FILENAME).write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError, match="Incompatible checkpoint schema version"):
            mgr.load()


class TestValidateArtifacts:
    def test_all_artifacts_present(self, mgr: CheckpointManager, run_dir: Path) -> None:
        # Create actual artifact files
        (run_dir / "a.json").write_text("{}", encoding="utf-8")
        (run_dir / "b.json").write_text("{}", encoding="utf-8")
        mgr.save("step_2", {
            "a": str(run_dir / "a.json"),
            "b": str(run_dir / "b.json"),
        })
        missing = mgr.validate_artifacts()
        assert missing == []

    def test_missing_artifact_detected(self, mgr: CheckpointManager, run_dir: Path) -> None:
        mgr.save("step_1", {"gone": str(run_dir / "nonexistent.json")})
        missing = mgr.validate_artifacts()
        assert len(missing) == 1
        assert "gone" in missing[0]

    def test_relative_path_resolved_against_output_dir(self, mgr: CheckpointManager, run_dir: Path) -> None:
        """Relative paths are resolved relative to the output directory."""
        (run_dir / "rel.json").write_text("{}", encoding="utf-8")
        mgr.save("step_1", {"rel": "rel.json"})
        missing = mgr.validate_artifacts()
        assert missing == []

    def test_validate_raises_when_no_checkpoint(self, mgr: CheckpointManager) -> None:
        with pytest.raises(ValueError, match="No checkpoint"):
            mgr.validate_artifacts()


# ---------------------------------------------------------------------------
# _should_skip helper (imported via run_case)
# ---------------------------------------------------------------------------

class TestShouldSkip:
    """Test the step-skip logic used during resume."""

    def test_no_checkpoint_skips_nothing(self) -> None:
        from scripts.run_case import _should_skip
        assert _should_skip("step_1_evidence", None) is False

    def test_completed_step_is_skipped(self) -> None:
        from scripts.run_case import _should_skip, STEP_EVIDENCE, STEP_DEBATE
        assert _should_skip(STEP_EVIDENCE, STEP_DEBATE) is True

    def test_same_step_is_skipped(self) -> None:
        from scripts.run_case import _should_skip, STEP_ISSUES
        assert _should_skip(STEP_ISSUES, STEP_ISSUES) is True

    def test_future_step_not_skipped(self) -> None:
        from scripts.run_case import _should_skip, STEP_EVIDENCE, STEP_DOCX
        assert _should_skip(STEP_DOCX, STEP_EVIDENCE) is False

    def test_unknown_step_not_skipped(self) -> None:
        from scripts.run_case import _should_skip
        assert _should_skip("unknown_step", "step_1_evidence") is False


# ---------------------------------------------------------------------------
# Resume integration (simulated — no LLM calls)
# ---------------------------------------------------------------------------

class TestResumeIntegration:
    """Simulate the checkpoint + resume flow without actual LLM calls."""

    def test_checkpoint_round_trip(self, tmp_path: Path) -> None:
        """Write checkpoint from one manager, read from another."""
        out = tmp_path / "run-rt"
        out.mkdir()

        mgr1 = CheckpointManager(out)
        mgr1.save("step_1_evidence", {"evidence_index": "evidence_index.json"}, run_id="case-001")
        mgr1.save("step_2_issues", {"issue_tree": "issue_tree.json"})

        mgr2 = CheckpointManager(out)
        state = mgr2.load()
        assert state is not None
        assert state.last_completed_step == "step_2_issues"
        assert "evidence_index" in state.artifact_paths
        assert "issue_tree" in state.artifact_paths

    def test_save_creates_output_dir_if_missing(self, tmp_path: Path) -> None:
        out = tmp_path / "brand" / "new" / "dir"
        mgr = CheckpointManager(out)
        mgr.save("step_1", {"a": "a.json"}, run_id="x")
        assert (out / CHECKPOINT_FILENAME).exists()


class TestCheckpointState:
    """CheckpointState dataclass behavior."""

    def test_default_schema_version(self) -> None:
        state = CheckpointState(
            run_id="r", last_completed_step="s", artifact_paths={}, timestamp="t",
        )
        assert state.schema_version == CHECKPOINT_SCHEMA_VERSION
