"""
ProgressReporter — 管道步骤进度上报抽象与实现。
Pipeline step progress reporter: abstract interface + CLI + SSE + JSON implementations.
"""

from __future__ import annotations

import abc
import asyncio
import json
import sys
import time
from typing import Any, Optional


class ProgressReporter(abc.ABC):
    """Abstract progress reporter for pipeline steps."""

    @abc.abstractmethod
    def on_step_start(self, step_n: int, step_name: str) -> None:
        """Called when a pipeline step begins execution."""

    @abc.abstractmethod
    def on_step_complete(self, step_n: int, step_name: str) -> None:
        """Called when a pipeline step finishes successfully."""

    @abc.abstractmethod
    def on_error(self, step_n: int, error: str) -> None:
        """Called when a pipeline step fails."""


class CLIProgressReporter(ProgressReporter):
    """Prints formatted step progress to stdout.

    Output format:
        [Step N/total] <name>: started
        [Step N/total] <name>: completed
        [Step N/total] <name>: failed <error>
    """

    def __init__(self, total_steps: int = 5) -> None:
        self.total_steps = total_steps
        self._current_step_name: str = ""

    def on_step_start(self, step_n: int, step_name: str) -> None:
        self._current_step_name = step_name
        print(f"[Step {step_n}/{self.total_steps}] {step_name}: started")

    def on_step_complete(self, step_n: int, step_name: str) -> None:
        print(f"[Step {step_n}/{self.total_steps}] {step_name}: completed")

    def on_error(self, step_n: int, error: str) -> None:
        name = self._current_step_name or "unknown"
        print(f"[Step {step_n}/{self.total_steps}] {name}: failed {error}")


# ---------------------------------------------------------------------------
# SSE progress store — run_id → asyncio.Queue[Optional[dict[str, Any]]]
# ---------------------------------------------------------------------------

_QUEUES: dict[str, asyncio.Queue] = {}


def get_progress_queue(run_id: str) -> Optional[asyncio.Queue]:
    """Return the progress queue for *run_id*, or None if not registered."""
    return _QUEUES.get(run_id)


def remove_progress_queue(run_id: str) -> None:
    """Remove and discard the progress queue for *run_id*."""
    _QUEUES.pop(run_id, None)


class SSEProgressReporter(ProgressReporter):
    """Pushes structured JSON step events to a per-run asyncio.Queue for SSE streaming.

    Event schema:
        {"step": N, "status": "started"|"completed"|"failed", "name": "..."}
        {"step": N, "status": "failed", "error": "..."}  # on_error
        None  # pipeline complete sentinel (via close())
    """

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        queue: asyncio.Queue = asyncio.Queue()
        _QUEUES[run_id] = queue
        self._queue = queue

    def on_step_start(self, step_n: int, step_name: str) -> None:
        self._queue.put_nowait({"step": step_n, "status": "started", "name": step_name})

    def on_step_complete(self, step_n: int, step_name: str) -> None:
        self._queue.put_nowait({"step": step_n, "status": "completed", "name": step_name})

    def on_error(self, step_n: int, error: str) -> None:
        self._queue.put_nowait({"step": step_n, "status": "failed", "error": str(error)})

    def close(self) -> None:
        """Signal pipeline completion by pushing None sentinel."""
        self._queue.put_nowait(None)


class JSONProgressReporter(ProgressReporter):
    """Writes JSON-line progress events to stderr for CLI pipeline consumers.

    Each event is a single JSON object written to stderr (one per line),
    making it easy for wrapper scripts to parse progress while stdout
    carries the normal human-readable output.

    Event schema::

        {"ts": <unix_epoch>, "step": N, "total": T, "name": "...", "status": "started"|"completed"|"failed", "pct": 0-100}
        {"ts": <unix_epoch>, "step": N, "total": T, "name": "...", "status": "failed", "error": "..."}

    The ``pct`` field is an approximate percentage based on step_n / total_steps.
    """

    def __init__(self, total_steps: int = 5, *, stream: Any = None) -> None:
        self.total_steps = total_steps
        self._stream = stream if stream is not None else sys.stderr
        self._current_step_name: str = ""

    def _emit(self, event: dict[str, Any]) -> None:
        """Write a single JSON line to the output stream."""
        line = json.dumps(event, ensure_ascii=False)
        self._stream.write(line + "\n")
        self._stream.flush()

    def on_step_start(self, step_n: int, step_name: str) -> None:
        self._current_step_name = step_name
        self._emit({
            "ts": time.time(),
            "step": step_n,
            "total": self.total_steps,
            "name": step_name,
            "status": "started",
            "pct": int((step_n - 1) / self.total_steps * 100),
        })

    def on_step_complete(self, step_n: int, step_name: str) -> None:
        self._emit({
            "ts": time.time(),
            "step": step_n,
            "total": self.total_steps,
            "name": step_name,
            "status": "completed",
            "pct": int(step_n / self.total_steps * 100),
        })

    def on_error(self, step_n: int, error: str) -> None:
        name = self._current_step_name or "unknown"
        self._emit({
            "ts": time.time(),
            "step": step_n,
            "total": self.total_steps,
            "name": name,
            "status": "failed",
            "error": str(error),
            "pct": int((step_n - 1) / self.total_steps * 100),
        })
