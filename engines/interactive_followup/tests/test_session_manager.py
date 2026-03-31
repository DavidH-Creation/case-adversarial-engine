"""
SessionManager 单元测试。
Unit tests for SessionManager.

测试覆盖 / Test coverage:
- 创建新会话 / Create new session
- 保存和加载 / Save and load round-trip
- 加载不存在的会话 / Load non-existent session
- 追加追问轮次 / Append interaction turn
- 多轮追问持久化 / Multi-turn persistence
- 损坏文件恢复 / Corrupted file recovery
- load_or_create 分支 / load_or_create branching
"""

from __future__ import annotations

import json

import pytest

from engines.interactive_followup.schemas import (
    InteractionTurn,
    SessionState,
    StatementClass,
)
from engines.interactive_followup.session_manager import SessionManager


_CASE_ID = "case-session-test-001"
_REPORT_ID = "report-session-test-001"
_RUN_ID = "run-session-test-001"


def _make_turn(
    turn_id: str, question: str = "测试问题", answer: str = "测试回答"
) -> InteractionTurn:
    """创建测试用 InteractionTurn / Create test InteractionTurn."""
    return InteractionTurn(
        turn_id=turn_id,
        case_id=_CASE_ID,
        report_id=_REPORT_ID,
        run_id=_RUN_ID,
        question=question,
        answer=answer,
        issue_ids=["issue-001"],
        evidence_ids=["evidence-001"],
        statement_class=StatementClass.fact,
    )


class TestSessionManagerCreate:
    """create() 方法测试 / Tests for create() method."""

    def test_create_returns_session_state(self, tmp_path):
        """create() 应返回 SessionState 并持久化文件。"""
        mgr = SessionManager(tmp_path)
        session = mgr.create(_CASE_ID, _REPORT_ID, _RUN_ID)

        assert isinstance(session, SessionState)
        assert session.case_id == _CASE_ID
        assert session.report_id == _REPORT_ID
        assert session.run_id == _RUN_ID
        assert session.session_id.startswith("session-")
        assert session.turn_count == 0
        assert session.created_at is not None
        assert mgr.session_path.exists()

    def test_create_with_metadata(self, tmp_path):
        """create() 应保存可选元数据。"""
        mgr = SessionManager(tmp_path)
        meta = {"source": "test", "version": 2}
        session = mgr.create(_CASE_ID, _REPORT_ID, _RUN_ID, metadata=meta)

        assert session.metadata == meta

    def test_create_makes_output_dir(self, tmp_path):
        """create() 应自动创建不存在的输出目录。"""
        nested = tmp_path / "deep" / "nested" / "dir"
        mgr = SessionManager(nested)
        session = mgr.create(_CASE_ID, _REPORT_ID, _RUN_ID)

        assert nested.exists()
        assert mgr.session_path.exists()


class TestSessionManagerLoad:
    """load() 方法测试 / Tests for load() method."""

    def test_load_returns_none_when_no_file(self, tmp_path):
        """load() 在文件不存在时应返回 None。"""
        mgr = SessionManager(tmp_path)
        assert mgr.load() is None

    def test_load_round_trip(self, tmp_path):
        """save → load 应保持数据一致。"""
        mgr = SessionManager(tmp_path)
        original = mgr.create(_CASE_ID, _REPORT_ID, _RUN_ID)
        loaded = mgr.load()

        assert loaded is not None
        assert loaded.session_id == original.session_id
        assert loaded.case_id == original.case_id
        assert loaded.turn_count == 0

    def test_load_corrupted_file_returns_none(self, tmp_path):
        """load() 在文件损坏时应返回 None（不抛异常）。"""
        mgr = SessionManager(tmp_path)
        # Write garbage to session file
        mgr.session_path.write_text("{{{{not valid json!!!!", encoding="utf-8")

        result = mgr.load()
        assert result is None

    def test_load_invalid_schema_returns_none(self, tmp_path):
        """load() 在 JSON 合法但 schema 不匹配时应返回 None。"""
        mgr = SessionManager(tmp_path)
        # Write valid JSON but wrong structure
        mgr.session_path.write_text('{"foo": "bar"}', encoding="utf-8")

        result = mgr.load()
        assert result is None


class TestSessionManagerLoadOrCreate:
    """load_or_create() 方法测试 / Tests for load_or_create() method."""

    def test_load_or_create_creates_when_no_file(self, tmp_path):
        """无已有会话时应创建新会话。"""
        mgr = SessionManager(tmp_path)
        session = mgr.load_or_create(_CASE_ID, _REPORT_ID, _RUN_ID)

        assert isinstance(session, SessionState)
        assert session.case_id == _CASE_ID
        assert session.turn_count == 0

    def test_load_or_create_loads_existing(self, tmp_path):
        """已有会话时应加载已有会话。"""
        mgr = SessionManager(tmp_path)
        original = mgr.create(_CASE_ID, _REPORT_ID, _RUN_ID)

        loaded = mgr.load_or_create(_CASE_ID, _REPORT_ID, _RUN_ID)
        assert loaded.session_id == original.session_id

    def test_load_or_create_recreates_on_corruption(self, tmp_path):
        """文件损坏时应创建新会话。"""
        mgr = SessionManager(tmp_path)
        mgr.session_path.write_text("corrupted data", encoding="utf-8")

        session = mgr.load_or_create(_CASE_ID, _REPORT_ID, _RUN_ID)
        assert isinstance(session, SessionState)
        assert session.turn_count == 0


class TestSessionManagerAppendTurn:
    """append_turn() 方法测试 / Tests for append_turn() method."""

    def test_append_turn_increments_count(self, tmp_path):
        """追加一轮后 turn_count 应递增。"""
        mgr = SessionManager(tmp_path)
        session = mgr.create(_CASE_ID, _REPORT_ID, _RUN_ID)

        turn = _make_turn("turn-test-01")
        session = mgr.append_turn(session, turn)

        assert session.turn_count == 1
        assert session.turns[0].turn_id == "turn-test-01"

    def test_append_turn_persists(self, tmp_path):
        """追加后持久化应保留轮次数据。"""
        mgr = SessionManager(tmp_path)
        session = mgr.create(_CASE_ID, _REPORT_ID, _RUN_ID)

        turn = _make_turn("turn-test-01", question="持久化测试问题", answer="持久化测试回答")
        mgr.append_turn(session, turn)

        # Reload from disk
        loaded = mgr.load()
        assert loaded is not None
        assert loaded.turn_count == 1
        assert loaded.turns[0].question == "持久化测试问题"
        assert loaded.turns[0].answer == "持久化测试回答"

    def test_multi_turn_append(self, tmp_path):
        """多轮追问应正确累积。"""
        mgr = SessionManager(tmp_path)
        session = mgr.create(_CASE_ID, _REPORT_ID, _RUN_ID)

        for i in range(5):
            turn = _make_turn(
                f"turn-test-{i + 1:02d}", question=f"问题{i + 1}", answer=f"回答{i + 1}"
            )
            session = mgr.append_turn(session, turn)

        assert session.turn_count == 5

        # Verify persistence
        loaded = mgr.load()
        assert loaded is not None
        assert loaded.turn_count == 5
        assert loaded.turns[0].question == "问题1"
        assert loaded.turns[4].question == "问题5"

    def test_session_json_is_valid_json(self, tmp_path):
        """session.json 应为合法 JSON 且可直接被 json.loads 解析。"""
        mgr = SessionManager(tmp_path)
        session = mgr.create(_CASE_ID, _REPORT_ID, _RUN_ID)
        turn = _make_turn("turn-json-test")
        mgr.append_turn(session, turn)

        raw = mgr.session_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        assert data["session_id"] == session.session_id
        assert len(data["turns"]) == 1
