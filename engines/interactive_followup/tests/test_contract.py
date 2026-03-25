"""
合同测试 — 使用 benchmark fixtures 验证 InteractionTurn 的输出结构。
Contract tests — validate InteractionTurn output structure against benchmark fixtures.

仅验证结构性合约约束（不验证 LLM 内容）：
Only validates structural contract constraints (not LLM content):
1. 每个 turn 包含所有必填顶层字段 / Each turn has all required top-level fields
2. issue_ids 非空 / issue_ids is non-empty
3. statement_class 为合法枚举值 / statement_class is a valid enum value
4. evidence_ids 存在（允许为空，但须为列表）/ evidence_ids is a list (can be empty)
5. answer 非空 / answer is non-empty
6. question 非空 / question is non-empty
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixture 路径 / Fixture paths
# ---------------------------------------------------------------------------

_FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "benchmarks" / "fixtures"
)
_OUTPUT_FIXTURE = _FIXTURES_DIR / "interaction_turn_example.json"


def _load_fixture(path: Path) -> list[dict]:
    """加载 fixture JSON 文件（数组格式）/ Load fixture JSON file (array format)."""
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 合同测试套件 / Contract test suite
# ---------------------------------------------------------------------------


class TestInteractionTurnContractFixtures:
    """基于 gold fixtures 的追问合约校验 / Contract validation against gold fixtures."""

    @pytest.fixture(autouse=True)
    def load_fixtures(self):
        self.turns = _load_fixture(_OUTPUT_FIXTURE)
        assert isinstance(self.turns, list), "Fixture must be a JSON array"

    # ── 顶层结构 / Top-level structure ────────────────────────────────────────

    def test_fixture_non_empty(self):
        """fixture 数组不能为空。"""
        assert len(self.turns) > 0, "interaction_turn_example.json must not be empty"

    def test_turns_have_required_top_level_keys(self):
        """每个 turn 必须包含所有必填顶层字段。"""
        required = {
            "turn_id", "case_id", "report_id", "run_id",
            "question", "answer", "issue_ids", "evidence_ids", "statement_class",
        }
        for turn in self.turns:
            missing = required - set(turn.keys())
            assert not missing, (
                f"Turn {turn.get('turn_id', '?')} missing fields: {missing}"
            )

    # ── 问答内容校验 / Q&A content validation ────────────────────────────────

    def test_question_non_empty(self):
        """question 不能为空。"""
        for turn in self.turns:
            assert turn.get("question", "").strip(), (
                f"Turn {turn.get('turn_id', '?')} has empty question"
            )

    def test_answer_non_empty(self):
        """answer 不能为空。"""
        for turn in self.turns:
            assert turn.get("answer", "").strip(), (
                f"Turn {turn.get('turn_id', '?')} has empty answer"
            )

    # ── 争点绑定校验 / Issue binding validation ──────────────────────────────

    def test_issue_ids_non_empty(self):
        """issue_ids 不能为空，每轮追问必须绑定至少一个争点。"""
        for turn in self.turns:
            issue_ids = turn.get("issue_ids", [])
            assert len(issue_ids) > 0, (
                f"Turn {turn.get('turn_id', '?')} has empty issue_ids"
            )

    def test_issue_ids_are_strings(self):
        """issue_ids 中每个元素必须为非空字符串。"""
        for turn in self.turns:
            for iid in turn.get("issue_ids", []):
                assert isinstance(iid, str) and iid.strip(), (
                    f"Turn {turn.get('turn_id', '?')} has invalid issue_id: {iid!r}"
                )

    # ── 证据引用校验 / Evidence citation validation ──────────────────────────

    def test_evidence_ids_is_list(self):
        """evidence_ids 必须为列表。"""
        for turn in self.turns:
            assert isinstance(turn.get("evidence_ids"), list), (
                f"Turn {turn.get('turn_id', '?')} evidence_ids must be a list"
            )

    def test_evidence_ids_are_strings(self):
        """evidence_ids 中每个元素必须为非空字符串。"""
        for turn in self.turns:
            for eid in turn.get("evidence_ids", []):
                assert isinstance(eid, str) and eid.strip(), (
                    f"Turn {turn.get('turn_id', '?')} has invalid evidence_id: {eid!r}"
                )

    # ── 陈述分类校验 / Statement class validation ────────────────────────────

    def test_statement_class_valid_enum(self):
        """statement_class 必须为合法枚举值。"""
        valid = {"fact", "inference", "assumption"}
        for turn in self.turns:
            sc = turn.get("statement_class")
            assert sc in valid, (
                f"Turn {turn.get('turn_id', '?')} "
                f"has invalid statement_class: {sc!r}"
            )

    # ── ID 一致性校验 / ID consistency validation ─────────────────────────────

    def test_turn_ids_unique(self):
        """turn_id 在所有轮次中唯一。"""
        ids = [t.get("turn_id") for t in self.turns]
        assert len(ids) == len(set(ids)), (
            f"存在重复的 turn_id: {ids}"
        )

    def test_same_case_id_across_turns(self):
        """同一 fixture 内所有 turn 应属于同一 case_id。"""
        case_ids = {t.get("case_id") for t in self.turns}
        assert len(case_ids) == 1, (
            f"Multiple case_ids found in fixture: {case_ids}"
        )
