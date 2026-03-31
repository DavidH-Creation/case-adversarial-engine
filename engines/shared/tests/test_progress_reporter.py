"""
Tests for engines/shared/progress_reporter.py

Covers:
  - CLIProgressReporter: output format for start / complete / error
  - SSEProgressReporter: queue event schema for start / complete / error / close
  - Edge cases: error on step 3, multiple runs with separate queues
"""
from __future__ import annotations

import pytest

from engines.shared.progress_reporter import (
    CLIProgressReporter,
    SSEProgressReporter,
    get_progress_queue,
    remove_progress_queue,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_RUN_A = "test-run-progress-A"
_TEST_RUN_B = "test-run-progress-B"


def _drain(run_id: str) -> list:
    """Drain all events from a progress queue synchronously."""
    q = get_progress_queue(run_id)
    events = []
    while q is not None and not q.empty():
        events.append(q.get_nowait())
    return events


# ---------------------------------------------------------------------------
# CLIProgressReporter
# ---------------------------------------------------------------------------

class TestCLIProgressReporter:
    def test_step_complete_format(self, capsys):
        reporter = CLIProgressReporter(total_steps=5)
        for n, name in enumerate(["Alpha", "Beta", "Gamma", "Delta", "Epsilon"], 1):
            reporter.on_step_complete(n, name)

        lines = [ln for ln in capsys.readouterr().out.strip().split("\n") if ln]
        assert len(lines) == 5
        for i, name in enumerate(["Alpha", "Beta", "Gamma", "Delta", "Epsilon"], 1):
            assert lines[i - 1] == f"[Step {i}/5] {name}: completed"

    def test_step_start_format(self, capsys):
        reporter = CLIProgressReporter(total_steps=5)
        reporter.on_step_start(1, "Index Evidence")

        out = capsys.readouterr().out
        assert "[Step 1/5] Index Evidence: started" in out

    def test_error_format_contains_step_and_error(self, capsys):
        reporter = CLIProgressReporter(total_steps=5)
        reporter.on_step_start(3, "Adversarial Debate")
        reporter.on_error(3, "LLM timeout")

        lines = [ln for ln in capsys.readouterr().out.strip().split("\n") if ln]
        error_line = next(ln for ln in lines if "failed" in ln)
        assert "[Step 3/5]" in error_line
        assert "failed" in error_line
        assert "LLM timeout" in error_line

    def test_error_without_prior_start_uses_unknown(self, capsys):
        reporter = CLIProgressReporter(total_steps=5)
        reporter.on_error(2, "boom")

        out = capsys.readouterr().out
        assert "[Step 2/5]" in out
        assert "failed boom" in out

    def test_full_pipeline_happy_path(self, capsys):
        """Happy path: 5-step pipeline → 5 'completed' lines in order."""
        step_names = [
            "Index Evidence",
            "Extract Issues",
            "Adversarial Debate",
            "Write Outputs",
            "Generate DOCX",
        ]
        reporter = CLIProgressReporter(total_steps=5)
        for n, name in enumerate(step_names, 1):
            reporter.on_step_start(n, name)
            reporter.on_step_complete(n, name)

        lines = [ln for ln in capsys.readouterr().out.strip().split("\n") if ln]
        completed = [ln for ln in lines if "completed" in ln]
        assert len(completed) == 5
        for i, name in enumerate(step_names, 1):
            assert f"[Step {i}/5] {name}: completed" in completed[i - 1]


# ---------------------------------------------------------------------------
# SSEProgressReporter
# ---------------------------------------------------------------------------

class TestSSEProgressReporter:
    def setup_method(self):
        remove_progress_queue(_TEST_RUN_A)
        remove_progress_queue(_TEST_RUN_B)

    def teardown_method(self):
        remove_progress_queue(_TEST_RUN_A)
        remove_progress_queue(_TEST_RUN_B)

    def test_creates_queue_on_init(self):
        assert get_progress_queue(_TEST_RUN_A) is None
        SSEProgressReporter(_TEST_RUN_A)
        assert get_progress_queue(_TEST_RUN_A) is not None

    def test_step_start_event_schema(self):
        reporter = SSEProgressReporter(_TEST_RUN_A)
        reporter.on_step_start(1, "Index Evidence")

        events = _drain(_TEST_RUN_A)
        assert events == [{"step": 1, "status": "started", "name": "Index Evidence"}]

    def test_step_complete_event_schema(self):
        reporter = SSEProgressReporter(_TEST_RUN_A)
        reporter.on_step_complete(2, "Extract Issues")

        events = _drain(_TEST_RUN_A)
        assert events == [{"step": 2, "status": "completed", "name": "Extract Issues"}]

    def test_error_event_schema(self):
        reporter = SSEProgressReporter(_TEST_RUN_A)
        reporter.on_step_start(3, "Adversarial Debate")
        reporter.on_error(3, "LLM connection failed")

        events = _drain(_TEST_RUN_A)
        assert events[0] == {"step": 3, "status": "started", "name": "Adversarial Debate"}
        assert events[1]["step"] == 3
        assert events[1]["status"] == "failed"
        assert "LLM connection failed" in events[1]["error"]

    def test_close_pushes_none_sentinel(self):
        reporter = SSEProgressReporter(_TEST_RUN_A)
        reporter.on_step_complete(5, "Generate DOCX")
        reporter.close()

        events = _drain(_TEST_RUN_A)
        assert events[-1] is None

    def test_full_pipeline_happy_path_5_steps(self):
        """SSE: 5-step pipeline pushes 5 completed + 1 done sentinel."""
        step_names = [
            "Index Evidence",
            "Extract Issues",
            "Adversarial Debate",
            "Write Outputs",
            "Generate DOCX",
        ]
        reporter = SSEProgressReporter(_TEST_RUN_A)
        for n, name in enumerate(step_names, 1):
            reporter.on_step_complete(n, name)
        reporter.close()

        events = _drain(_TEST_RUN_A)
        assert len(events) == 6  # 5 step events + None sentinel
        for i, name in enumerate(step_names, 1):
            assert events[i - 1] == {"step": i, "status": "completed", "name": name}
        assert events[5] is None

    def test_pipeline_failure_at_step_3(self):
        """Edge case: pipeline fails at step 3 → error event then close."""
        reporter = SSEProgressReporter(_TEST_RUN_A)
        reporter.on_step_complete(1, "Index Evidence")
        reporter.on_step_complete(2, "Extract Issues")
        reporter.on_step_start(3, "Adversarial Debate")
        reporter.on_error(3, "Step 3 error")
        reporter.close()

        events = _drain(_TEST_RUN_A)
        assert events[0]["status"] == "completed"   # step 1
        assert events[1]["status"] == "completed"   # step 2
        assert events[2]["status"] == "started"     # step 3 started
        assert events[3]["step"] == 3
        assert events[3]["status"] == "failed"      # step 3 failed
        assert events[4] is None                    # sentinel

    def test_separate_run_ids_have_independent_queues(self):
        r1 = SSEProgressReporter(_TEST_RUN_A)
        r2 = SSEProgressReporter(_TEST_RUN_B)

        r1.on_step_complete(1, "Step One")
        r2.on_step_complete(2, "Step Two")

        events_a = _drain(_TEST_RUN_A)
        events_b = _drain(_TEST_RUN_B)

        assert events_a == [{"step": 1, "status": "completed", "name": "Step One"}]
        assert events_b == [{"step": 2, "status": "completed", "name": "Step Two"}]

    def test_remove_progress_queue_cleans_up(self):
        SSEProgressReporter(_TEST_RUN_A)
        assert get_progress_queue(_TEST_RUN_A) is not None
        remove_progress_queue(_TEST_RUN_A)
        assert get_progress_queue(_TEST_RUN_A) is None
