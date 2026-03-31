"""
合约测试 — 使用 benchmark fixtures 验证 Scenario Engine 的输出结构。
Contract tests — validate Scenario Engine output structure against benchmark fixtures.

仅验证结构性合约约束（不验证 LLM 内容）：
Only validates structural contract constraints (not LLM content):
1. 必填顶层字段齐全（scenario_id, case_id, baseline_run_id, change_set, diff_summary）
2. diff_summary 类型合法（"baseline" 字面量 或 DiffEntry[]）
3. 每条 diff_entry 有非空 impact_description
4. 每条 diff_entry.direction 为合法枚举值（strengthen/weaken/neutral）
5. affected_issue_ids 覆盖所有 diff_entry.issue_id
6. baseline anchor 约束（change_set=[] 时 diff_summary = "baseline"）
7. Run 合约（trigger_type = "scenario_execution", scenario_id 非空）
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixture 路径 / Fixture paths
# ---------------------------------------------------------------------------

_FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "benchmarks" / "fixtures"
)
_SCENARIO_FIXTURE = _FIXTURES_DIR / "scenario_diff_example.json"


def _load_fixture(path: Path) -> dict:
    """加载 fixture JSON 文件 / Load fixture JSON file."""
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 合约测试套件 / Contract test suite
# ---------------------------------------------------------------------------


class TestScenarioContractFixtures:
    """基于 gold fixtures 的场景合约校验 / Contract validation against gold fixtures."""

    @pytest.fixture(autouse=True)
    def load_fixtures(self):
        data = _load_fixture(_SCENARIO_FIXTURE)
        self.scenarios: list[dict] = data.get("Scenario", [])
        self.runs: list[dict] = data.get("Run", [])
        # 找到非 baseline 场景 / Find the non-baseline counterfactual scenario
        self.counterfactual = next(
            (s for s in self.scenarios if s.get("change_set")), None
        )
        self.baseline = next(
            (s for s in self.scenarios if not s.get("change_set")), None
        )
        # 找到场景执行 Run / Find the scenario_execution Run
        self.scenario_run = next(
            (r for r in self.runs if r.get("trigger_type") == "scenario_execution"),
            None,
        )

    # ── 顶层结构 / Top-level structure ────────────────────────────────────────

    def test_fixture_has_scenarios(self):
        """Fixture 必须包含至少一个 Scenario。"""
        assert len(self.scenarios) > 0, "No Scenario entries in fixture"

    def test_counterfactual_scenario_exists(self):
        """Fixture 必须包含一个非 baseline（change_set 非空）的场景。"""
        assert self.counterfactual is not None, "No counterfactual scenario in fixture"

    def test_baseline_scenario_exists(self):
        """Fixture 必须包含一个 baseline anchor 场景。"""
        assert self.baseline is not None, "No baseline scenario in fixture"

    def test_scenarios_have_required_fields(self):
        """每个 Scenario 必须包含所有必填字段。"""
        required = {
            "scenario_id", "case_id", "baseline_run_id",
            "change_set", "diff_summary", "affected_issue_ids",
            "affected_evidence_ids", "status",
        }
        for sc in self.scenarios:
            missing = required - set(sc.keys())
            assert not missing, (
                f"Scenario {sc.get('scenario_id', '?')} missing fields: {missing}"
            )

    # ── baseline anchor 约束 / Baseline anchor constraint ────────────────────

    def test_baseline_diff_summary_is_sentinel(self):
        """baseline anchor 的 diff_summary 必须是字面量 'baseline'。"""
        assert self.baseline is not None
        assert self.baseline.get("change_set") == [], "baseline should have empty change_set"
        assert self.baseline.get("diff_summary") == "baseline", (
            "baseline anchor diff_summary must be literal 'baseline'"
        )

    def test_baseline_affected_ids_empty(self):
        """baseline anchor 的 affected_issue_ids 和 affected_evidence_ids 必须为空。"""
        assert self.baseline is not None
        assert self.baseline.get("affected_issue_ids") == []
        assert self.baseline.get("affected_evidence_ids") == []

    # ── 反事实场景结构 / Counterfactual scenario structure ───────────────────

    def test_counterfactual_has_non_empty_change_set(self):
        """反事实场景的 change_set 必须非空。"""
        assert self.counterfactual is not None
        assert len(self.counterfactual.get("change_set", [])) > 0, (
            "Counterfactual scenario must have non-empty change_set"
        )

    def test_counterfactual_diff_summary_is_list(self):
        """反事实场景的 diff_summary 必须是 DiffEntry[] 而非 'baseline' 字面量。"""
        assert self.counterfactual is not None
        diff = self.counterfactual.get("diff_summary")
        assert isinstance(diff, list), (
            f"Counterfactual diff_summary must be a list, got: {type(diff)}"
        )

    def test_diff_entries_have_required_fields(self):
        """每条 diff_entry 必须包含必填字段。"""
        assert self.counterfactual is not None
        required = {"issue_id", "impact_description", "direction"}
        for entry in self.counterfactual.get("diff_summary", []):
            missing = required - set(entry.keys())
            assert not missing, (
                f"diff_entry for issue {entry.get('issue_id', '?')} missing fields: {missing}"
            )

    def test_diff_entry_impact_description_non_empty(self):
        """每条 diff_entry 的 impact_description 必须非空。"""
        assert self.counterfactual is not None
        for entry in self.counterfactual.get("diff_summary", []):
            desc = entry.get("impact_description", "")
            assert desc and desc.strip(), (
                f"diff_entry[{entry.get('issue_id', '?')}].impact_description is empty"
            )

    def test_diff_entry_direction_valid_enum(self):
        """每条 diff_entry.direction 必须为合法枚举值。"""
        assert self.counterfactual is not None
        valid = {"strengthen", "weaken", "neutral"}
        for entry in self.counterfactual.get("diff_summary", []):
            direction = entry.get("direction")
            assert direction in valid, (
                f"diff_entry[{entry.get('issue_id', '?')}].direction invalid: {direction!r}"
            )

    def test_affected_issue_ids_covers_diff_entries(self):
        """affected_issue_ids 必须覆盖所有 diff_entry.issue_id。"""
        assert self.counterfactual is not None
        diff_issue_ids = {e.get("issue_id") for e in self.counterfactual.get("diff_summary", [])}
        affected = set(self.counterfactual.get("affected_issue_ids", []))
        uncovered = diff_issue_ids - affected
        assert not uncovered, (
            f"affected_issue_ids missing diff_entry issue_ids: {uncovered}"
        )

    def test_affected_evidence_ids_from_change_set(self):
        """affected_evidence_ids 应包含 change_set 中 Evidence 类型对象的 ID。"""
        assert self.counterfactual is not None
        change_set_evidence = {
            c["target_object_id"]
            for c in self.counterfactual.get("change_set", [])
            if c.get("target_object_type") == "Evidence"
        }
        affected = set(self.counterfactual.get("affected_evidence_ids", []))
        assert change_set_evidence.issubset(affected), (
            f"affected_evidence_ids missing change_set evidence IDs: "
            f"{change_set_evidence - affected}"
        )

    # ── Run 合约 / Run contract ──────────────────────────────────────────────

    def test_scenario_run_exists(self):
        """Fixture 必须包含 trigger_type='scenario_execution' 的 Run。"""
        assert self.scenario_run is not None, (
            "No Run with trigger_type='scenario_execution' in fixture"
        )

    def test_scenario_run_has_required_fields(self):
        """场景 Run 必须包含所有必填字段。"""
        assert self.scenario_run is not None
        required = {
            "run_id", "case_id", "workspace_id", "scenario_id",
            "trigger_type", "input_snapshot", "output_refs",
            "started_at", "finished_at", "status",
        }
        missing = required - set(self.scenario_run.keys())
        assert not missing, f"scenario Run missing fields: {missing}"

    def test_scenario_run_trigger_type(self):
        """场景 Run.trigger_type 必须是 'scenario_execution'。"""
        assert self.scenario_run is not None
        assert self.scenario_run.get("trigger_type") == "scenario_execution"

    def test_scenario_run_has_non_null_scenario_id(self):
        """场景 Run.scenario_id 必须非空。"""
        assert self.scenario_run is not None
        scenario_id = self.scenario_run.get("scenario_id")
        assert scenario_id is not None and scenario_id != "", (
            "scenario Run.scenario_id must be non-null and non-empty"
        )

    def test_scenario_run_scenario_id_matches_scenario(self):
        """场景 Run.scenario_id 必须与对应 Scenario.scenario_id 一致。"""
        assert self.scenario_run is not None and self.counterfactual is not None
        assert self.scenario_run.get("scenario_id") == self.counterfactual.get("scenario_id"), (
            "Run.scenario_id must match Scenario.scenario_id"
        )

    def test_scenario_run_status_completed(self):
        """场景 Run.status 应为 'completed'。"""
        assert self.scenario_run is not None
        assert self.scenario_run.get("status") == "completed"

    def test_scenario_run_input_snapshot_structure(self):
        """场景 Run.input_snapshot 必须包含 material_refs 和 artifact_refs。"""
        assert self.scenario_run is not None
        snapshot = self.scenario_run.get("input_snapshot", {})
        assert "material_refs" in snapshot, "input_snapshot missing material_refs"
        assert "artifact_refs" in snapshot, "input_snapshot missing artifact_refs"


# ---------------------------------------------------------------------------
# PROMPT_REGISTRY 完整性合约 / PROMPT_REGISTRY completeness contract
# ---------------------------------------------------------------------------


class TestSimulationRunPromptRegistryCompleteness:
    """验证 simulation_run 6 个分析模块的 PROMPT_REGISTRY 覆盖所有 3 个目标案型。
    Verifies all 6 simulation_run analysis modules register civil_loan, labor_dispute, real_estate.
    """

    EXPECTED_CASE_TYPES = {"civil_loan", "labor_dispute", "real_estate"}

    _REGISTRY_MODULES = [
        ("action_recommender", "engines.simulation_run.action_recommender.prompts"),
        ("attack_chain_optimizer", "engines.simulation_run.attack_chain_optimizer.prompts"),
        ("decision_path_tree", "engines.simulation_run.decision_path_tree.prompts"),
        ("defense_chain", "engines.simulation_run.defense_chain.prompts"),
        ("issue_category_classifier", "engines.simulation_run.issue_category_classifier.prompts"),
        ("issue_impact_ranker", "engines.simulation_run.issue_impact_ranker.prompts"),
    ]

    @pytest.mark.parametrize("module_name,module_path", _REGISTRY_MODULES)
    def test_module_has_all_case_types(self, module_name: str, module_path: str):
        """每个 simulation_run 分析模块的 PROMPT_REGISTRY 必须包含全部 3 个案型。"""
        mod = importlib.import_module(module_path)
        registry: dict = mod.PROMPT_REGISTRY
        registered = set(registry.keys())
        missing = self.EXPECTED_CASE_TYPES - registered
        assert not missing, (
            f"{module_name}.PROMPT_REGISTRY missing case types: {missing}. "
            f"Registered: {registered}"
        )

    @pytest.mark.parametrize("module_name,module_path", _REGISTRY_MODULES)
    def test_each_case_type_entry_is_non_empty(self, module_name: str, module_path: str):
        """每个案型在 PROMPT_REGISTRY 中的注册值不得为 None 或空。"""
        mod = importlib.import_module(module_path)
        registry: dict = mod.PROMPT_REGISTRY
        for case_type in self.EXPECTED_CASE_TYPES:
            if case_type not in registry:
                continue  # covered by previous test
            entry = registry[case_type]
            assert entry is not None, (
                f"{module_name}.PROMPT_REGISTRY['{case_type}'] is None"
            )
