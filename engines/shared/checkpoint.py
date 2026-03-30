"""Checkpoint manager for pipeline resume support.

Saves/loads checkpoint state so that a pipeline run can be resumed
from the last completed step after an interruption.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Bump this when the checkpoint format changes in a breaking way.
CHECKPOINT_SCHEMA_VERSION = 1
CHECKPOINT_FILENAME = "checkpoint.json"


@dataclass
class CheckpointState:
    """Deserialized checkpoint data."""

    run_id: str
    last_completed_step: str
    artifact_paths: dict[str, str]
    timestamp: str
    schema_version: int = CHECKPOINT_SCHEMA_VERSION


class CheckpointManager:
    """Manages checkpoint persistence for a single pipeline run.

    Usage::

        mgr = CheckpointManager(output_dir)
        mgr.save("step_1", {"evidence_index": "outputs/run/evidence_index.json"})
        state = mgr.load()   # returns CheckpointState or None
        mgr.clear()
    """

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = Path(output_dir)
        self._checkpoint_path = self._output_dir / CHECKPOINT_FILENAME

    @property
    def checkpoint_path(self) -> Path:
        return self._checkpoint_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(
        self,
        step_name: str,
        artifact_paths: dict[str, str],
        *,
        run_id: str = "",
    ) -> Path:
        """Persist checkpoint after a step completes.

        Args:
            step_name: Identifier of the completed step (e.g. "step_1").
            artifact_paths: Mapping of artifact name -> file path (relative
                or absolute).  Paths are stored as-is.
            run_id: Optional run identifier to embed in the checkpoint.

        Returns:
            Path to the written checkpoint file.
        """
        # Merge with existing checkpoint (accumulate artifact paths)
        existing = self.load()
        merged_artifacts: dict[str, str] = {}
        if existing is not None:
            merged_artifacts.update(existing.artifact_paths)
            if not run_id and existing.run_id:
                run_id = existing.run_id
        merged_artifacts.update(artifact_paths)

        payload: dict[str, Any] = {
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "run_id": run_id,
            "last_completed_step": step_name,
            "artifact_paths": merged_artifacts,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoint_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Checkpoint saved: step=%s  artifacts=%s", step_name, list(merged_artifacts))
        return self._checkpoint_path

    def load(self) -> CheckpointState | None:
        """Load checkpoint from disk.

        Returns:
            CheckpointState if a valid checkpoint exists, else None.

        Raises:
            ValueError: If the checkpoint file exists but is corrupt or
                has an incompatible schema version.
        """
        if not self._checkpoint_path.exists():
            return None

        raw = self._checkpoint_path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Checkpoint file is corrupt ({self._checkpoint_path}): {exc}"
            ) from exc

        version = data.get("schema_version")
        if version != CHECKPOINT_SCHEMA_VERSION:
            raise ValueError(
                f"Incompatible checkpoint schema version {version} "
                f"(expected {CHECKPOINT_SCHEMA_VERSION}). "
                f"Please delete the checkpoint and re-run from scratch."
            )

        return CheckpointState(
            run_id=data.get("run_id", ""),
            last_completed_step=data["last_completed_step"],
            artifact_paths=data.get("artifact_paths", {}),
            timestamp=data.get("timestamp", ""),
            schema_version=version,
        )

    def clear(self) -> None:
        """Remove the checkpoint file if it exists."""
        if self._checkpoint_path.exists():
            self._checkpoint_path.unlink()
            logger.info("Checkpoint cleared: %s", self._checkpoint_path)

    def validate_artifacts(self) -> list[str]:
        """Check that all artifact files referenced by the checkpoint exist.

        Returns:
            List of missing artifact paths (empty if all present).

        Raises:
            ValueError: If no checkpoint is loaded.
        """
        state = self.load()
        if state is None:
            raise ValueError("No checkpoint to validate")

        missing: list[str] = []
        for name, path_str in state.artifact_paths.items():
            p = Path(path_str)
            if not p.is_absolute():
                p = self._output_dir / p
            if not p.exists():
                missing.append(f"{name}: {path_str}")
        return missing
