"""
ProgressReporter — 管道步骤进度上报抽象与实现。
Pipeline step progress reporter: abstract interface + CLI + SSE implementations.
"""
from __future__ import annotations

import abc
import asyncio
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
