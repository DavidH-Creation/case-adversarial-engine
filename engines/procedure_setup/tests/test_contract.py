"""
合约测试 — 使用 benchmark fixtures 验证 Procedure Setup Engine 的输出结构。
Contract tests — validate Procedure Setup Engine output structure against benchmark fixtures.

仅验证结构性合约约束（不验证 LLM 内容）：
Only validates structural contract constraints (not LLM content):
1. 必填顶层字段齐全（state_id, case_id, phase）
2. phase 必须来自合法枚举值
3. 全部八个阶段都存在于 ProcedureState 序列中
4. judge_questions 不包含 owner_private 读取域
5. output_branching 仅包含 admitted_for_discussion 证据状态
6. terminal 状态（output_branching）next_state_ids 为空
7. ProcedureConfig 合约（total_phases = 8）
8. Run 合约（trigger_type = "procedure_setup"）
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixture 路径 / Fixture paths
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "benchmarks" / "fixtures"
_PROCEDURE_FIXTURE = _FIXTURES_DIR / "procedure_states_example.json"

_VALID_PHASES = {
    "case_intake",
    "element_mapping",
    "opening",
    "evidence_submission",
    "evidence_challenge",
    "judge_questions",
    "rebuttal",
    "output_branching",
}
_PHASE_ORDER = [
    "case_intake",
    "element_mapping",
    "opening",
    "evidence_submission",
    "evidence_challenge",
    "judge_questions",
    "rebuttal",
    "output_branching",
]


def _load_fixture(path: Path) -> dict:
    """加载 fixture JSON 文件 / Load fixture JSON file."""
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 合约测试套件 / Contract test suite
# ---------------------------------------------------------------------------


class TestProcedureContractFixtures:
    """基于 gold fixtures 的程序设置合约校验 / Contract validation against gold fixtures."""

    @pytest.fixture(autouse=True)
    def load_fixtures(self):
        data = _load_fixture(_PROCEDURE_FIXTURE)
        self.states: list[dict] = data.get("ProcedureState", [])
        self.config: dict = data.get("ProcedureConfig", {})
        self.events: list[dict] = data.get("TimelineEvent", [])
        self.runs: list[dict] = data.get("Run", [])
        # 建立 phase → state 映射 / Build phase → state map
        self.phase_map: dict[str, dict] = {s["phase"]: s for s in self.states}
        # 找到 procedure_setup Run / Find the procedure_setup Run
        self.setup_run = next(
            (r for r in self.runs if r.get("trigger_type") == "procedure_setup"),
            None,
        )

    # ── 顶层结构 / Top-level structure ────────────────────────────────────────

    def test_fixture_has_procedure_states(self):
        """Fixture 必须包含至少一个 ProcedureState。"""
        assert len(self.states) > 0, "No ProcedureState entries in fixture"

    def test_fixture_has_procedure_config(self):
        """Fixture 必须包含 ProcedureConfig。"""
        assert self.config, "ProcedureConfig is missing in fixture"

    def test_fixture_has_timeline_events(self):
        """Fixture 必须包含至少一个 TimelineEvent。"""
        assert len(self.events) > 0, "No TimelineEvent entries in fixture"

    def test_fixture_has_run(self):
        """Fixture 必须包含 trigger_type='procedure_setup' 的 Run。"""
        assert self.setup_run is not None, "No Run with trigger_type='procedure_setup' in fixture"

    # ── ProcedureState 必填字段 / Required fields ─────────────────────────────

    def test_states_have_required_fields(self):
        """每个 ProcedureState 必须包含所有必填字段。"""
        required = {
            "state_id",
            "case_id",
            "phase",
            "round_index",
            "allowed_role_codes",
            "readable_access_domains",
            "writable_object_types",
            "admissible_evidence_statuses",
            "open_issue_ids",
            "entry_conditions",
            "exit_conditions",
            "next_state_ids",
        }
        for state in self.states:
            missing = required - set(state.keys())
            assert not missing, (
                f"ProcedureState {state.get('state_id', '?')} missing fields: {missing}"
            )

    def test_states_have_valid_phase(self):
        """每个 ProcedureState.phase 必须来自合法枚举值。"""
        for state in self.states:
            phase = state.get("phase")
            assert phase in _VALID_PHASES, (
                f"ProcedureState {state.get('state_id', '?')} has invalid phase: {phase!r}"
            )

    # ── 全阶段覆盖 / Full phase coverage ─────────────────────────────────────

    def test_all_eight_phases_present(self):
        """程序状态序列必须覆盖全部八个阶段。"""
        covered = {s["phase"] for s in self.states}
        missing = set(_PHASE_ORDER) - covered
        assert not missing, f"Missing phases in ProcedureState sequence: {missing}"

    def test_state_count_is_eight(self):
        """程序状态序列必须恰好包含八个状态（一阶段一个）。"""
        assert len(self.states) == 8, f"Expected 8 procedure states, got {len(self.states)}"

    # ── 访问控制约束 / Access control constraints ──────────────────────────────

    def test_judge_questions_no_owner_private(self):
        """judge_questions 阶段不得包含 owner_private 读取域。"""
        state = self.phase_map.get("judge_questions")
        assert state is not None, "judge_questions state missing from fixture"
        domains = state.get("readable_access_domains", [])
        assert "owner_private" not in domains, (
            "judge_questions.readable_access_domains must not contain owner_private"
        )

    def test_output_branching_only_admitted_evidence(self):
        """output_branching 阶段 admissible_evidence_statuses 必须仅含 admitted_for_discussion。"""
        state = self.phase_map.get("output_branching")
        assert state is not None, "output_branching state missing from fixture"
        statuses = state.get("admissible_evidence_statuses", [])
        for status in statuses:
            assert status == "admitted_for_discussion", (
                f"output_branching.admissible_evidence_statuses must only contain "
                f"admitted_for_discussion, got {status!r}"
            )

    # ── 终止状态 / Terminal state ─────────────────────────────────────────────

    def test_output_branching_is_terminal(self):
        """output_branching 是终止状态，next_state_ids 必须为空。"""
        state = self.phase_map.get("output_branching")
        assert state is not None, "output_branching state missing from fixture"
        assert state.get("next_state_ids") == [], (
            "output_branching.next_state_ids must be empty (terminal state)"
        )

    def test_non_terminal_states_have_next_state_ids(self):
        """非终止阶段的 ProcedureState 必须有 next_state_ids。"""
        terminal_phase = "output_branching"
        for state in self.states:
            if state["phase"] == terminal_phase:
                continue
            next_ids = state.get("next_state_ids", [])
            assert len(next_ids) > 0, (
                f"Non-terminal state {state['state_id']} must have non-empty next_state_ids"
            )

    # ── entry/exit conditions 非空 / Non-empty conditions ─────────────────────

    def test_states_have_non_empty_conditions(self):
        """每个 ProcedureState 必须有非空的 entry_conditions 和 exit_conditions。"""
        for state in self.states:
            assert state.get("entry_conditions"), (
                f"ProcedureState {state.get('state_id', '?')} has empty entry_conditions"
            )
            assert state.get("exit_conditions"), (
                f"ProcedureState {state.get('state_id', '?')} has empty exit_conditions"
            )

    # ── round_index 单调递增 / Monotonically increasing round_index ──────────

    def test_round_index_monotonically_increasing(self):
        """ProcedureState.round_index 应按阶段顺序单调递增。"""
        sorted_states = sorted(self.states, key=lambda s: s.get("round_index", -1))
        indices = [s.get("round_index") for s in sorted_states]
        for i, (a, b) in enumerate(zip(indices, indices[1:])):
            assert a < b, f"round_index not strictly increasing at position {i}: {a} >= {b}"

    # ── ProcedureConfig 合约 / ProcedureConfig contract ────────────────────────

    def test_config_has_required_fields(self):
        """ProcedureConfig 必须包含所有必填字段。"""
        required = {
            "case_type",
            "total_phases",
            "evidence_submission_deadline_days",
            "evidence_challenge_window_days",
            "max_rounds_per_phase",
        }
        missing = required - set(self.config.keys())
        assert not missing, f"ProcedureConfig missing fields: {missing}"

    def test_config_total_phases_is_eight(self):
        """ProcedureConfig.total_phases 应为 8。"""
        assert self.config.get("total_phases") == 8, (
            f"ProcedureConfig.total_phases must be 8, got {self.config.get('total_phases')}"
        )

    def test_config_deadlines_positive(self):
        """ProcedureConfig 的期限字段必须大于 0。"""
        assert self.config.get("evidence_submission_deadline_days", 0) > 0
        assert self.config.get("evidence_challenge_window_days", 0) > 0
        assert self.config.get("max_rounds_per_phase", 0) > 0

    # ── TimelineEvent 合约 / TimelineEvent contract ────────────────────────────

    def test_timeline_events_have_required_fields(self):
        """每个 TimelineEvent 必须包含所有必填字段。"""
        required = {
            "event_id",
            "event_type",
            "phase",
            "description",
            "relative_day",
            "is_mandatory",
        }
        for ev in self.events:
            missing = required - set(ev.keys())
            assert not missing, f"TimelineEvent {ev.get('event_id', '?')} missing fields: {missing}"

    def test_timeline_events_have_valid_phase(self):
        """每个 TimelineEvent.phase 必须来自合法枚举值。"""
        for ev in self.events:
            phase = ev.get("phase")
            assert phase in _VALID_PHASES, (
                f"TimelineEvent {ev.get('event_id', '?')} has invalid phase: {phase!r}"
            )

    def test_timeline_events_relative_day_non_negative(self):
        """TimelineEvent.relative_day 必须非负。"""
        for ev in self.events:
            assert ev.get("relative_day", -1) >= 0, (
                f"TimelineEvent {ev.get('event_id', '?')}.relative_day must be >= 0"
            )

    def test_timeline_events_description_non_empty(self):
        """TimelineEvent.description 必须非空。"""
        for ev in self.events:
            desc = ev.get("description", "")
            assert desc and desc.strip(), (
                f"TimelineEvent {ev.get('event_id', '?')}.description is empty"
            )

    # ── Run 合约 / Run contract ──────────────────────────────────────────────

    def test_setup_run_has_required_fields(self):
        """procedure_setup Run 必须包含所有必填字段。"""
        assert self.setup_run is not None
        required = {
            "run_id",
            "case_id",
            "workspace_id",
            "scenario_id",
            "trigger_type",
            "input_snapshot",
            "output_refs",
            "started_at",
            "finished_at",
            "status",
        }
        missing = required - set(self.setup_run.keys())
        assert not missing, f"procedure_setup Run missing fields: {missing}"

    def test_setup_run_trigger_type(self):
        """procedure_setup Run.trigger_type 必须是 'procedure_setup'。"""
        assert self.setup_run is not None
        assert self.setup_run.get("trigger_type") == "procedure_setup"

    def test_setup_run_scenario_id_is_null(self):
        """procedure_setup Run.scenario_id 应为 null（非场景执行）。"""
        assert self.setup_run is not None
        assert self.setup_run.get("scenario_id") is None, (
            "procedure_setup Run.scenario_id must be null"
        )

    def test_setup_run_input_snapshot_structure(self):
        """procedure_setup Run.input_snapshot 必须包含 material_refs 和 artifact_refs。"""
        assert self.setup_run is not None
        snapshot = self.setup_run.get("input_snapshot", {})
        assert "material_refs" in snapshot, "input_snapshot missing material_refs"
        assert "artifact_refs" in snapshot, "input_snapshot missing artifact_refs"

    def test_setup_run_status_completed(self):
        """procedure_setup Run.status 应为 'completed'。"""
        assert self.setup_run is not None
        assert self.setup_run.get("status") == "completed"
