"""
多轮追问会话管理器 — 持久化会话状态到 session.json。
Multi-turn followup session manager — persists session state to session.json.

职责 / Responsibilities:
- 创建新会话 / Create new sessions
- 保存/加载会话状态到 JSON 文件 / Save/load session state to JSON file
- 追加追问轮次 / Append interaction turns
- 损坏文件恢复（重建空会话）/ Corrupted file recovery (rebuild empty session)
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .schemas import InteractionTurn, SessionState

logger = logging.getLogger(__name__)


class SessionManager:
    """多轮追问会话管理器。
    Multi-turn followup session manager.

    管理会话的创建、持久化和轮次追加。会话状态保存为 session.json。
    Manages session creation, persistence, and turn appending.
    Session state is persisted as session.json.

    Args:
        output_dir: 输出目录路径 / Output directory path
    """

    SESSION_FILENAME = "session.json"

    def __init__(self, output_dir: str | Path) -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def session_path(self) -> Path:
        """会话文件路径 / Session file path."""
        return self._output_dir / self.SESSION_FILENAME

    def create(
        self,
        case_id: str,
        report_id: str,
        run_id: str,
        *,
        metadata: dict | None = None,
    ) -> SessionState:
        """创建新会话并持久化。
        Create a new session and persist it.

        Args:
            case_id: 案件 ID / Case ID
            report_id: 报告 ID / Report ID
            run_id: 运行 ID / Run ID
            metadata: 可选元数据 / Optional metadata

        Returns:
            新创建的 SessionState / Newly created SessionState
        """
        session_id = f"session-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        state = SessionState(
            session_id=session_id,
            case_id=case_id,
            report_id=report_id,
            run_id=run_id,
            turns=[],
            created_at=now,
            metadata=metadata,
        )
        self._save(state)
        logger.info("Created new session %s for case %s", session_id, case_id)
        return state

    def load(self) -> SessionState | None:
        """加载已有会话。
        Load an existing session.

        Returns:
            SessionState 或 None（文件不存在时）。
            如果文件损坏，记录警告并返回 None。
            SessionState or None (if file doesn't exist).
            If file is corrupted, logs a warning and returns None.
        """
        path = self.session_path
        if not path.exists():
            return None

        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            return SessionState.model_validate(data)
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning(
                "Session file corrupted (%s), will create new session: %s",
                path,
                exc,
            )
            return None

    def load_or_create(
        self,
        case_id: str,
        report_id: str,
        run_id: str,
        *,
        metadata: dict | None = None,
    ) -> SessionState:
        """加载已有会话，或创建新会话。
        Load existing session, or create a new one.

        Args:
            case_id: 案件 ID / Case ID
            report_id: 报告 ID / Report ID
            run_id: 运行 ID / Run ID
            metadata: 可选元数据 / Optional metadata

        Returns:
            已有或新创建的 SessionState
        """
        existing = self.load()
        if existing is not None:
            logger.info(
                "Loaded existing session %s (%d turns)",
                existing.session_id,
                existing.turn_count,
            )
            return existing
        return self.create(case_id, report_id, run_id, metadata=metadata)

    def append_turn(self, session: SessionState, turn: InteractionTurn) -> SessionState:
        """追加一轮追问并持久化。
        Append a turn and persist the session.

        Args:
            session: 当前会话状态 / Current session state
            turn: 追问轮次 / Interaction turn

        Returns:
            更新后的 SessionState / Updated SessionState
        """
        session.turns.append(turn)
        self._save(session)
        logger.info(
            "Appended turn %s to session %s (total: %d)",
            turn.turn_id,
            session.session_id,
            session.turn_count,
        )
        return session

    def _save(self, state: SessionState) -> None:
        """持久化会话状态到 JSON 文件。
        Persist session state to JSON file.
        """
        data = state.model_dump_json(indent=2)
        self.session_path.write_text(data, encoding="utf-8")
