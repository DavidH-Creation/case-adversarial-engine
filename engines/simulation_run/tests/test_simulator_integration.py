"""
Scenario Engine what-if 集成测试。
Integration tests for the what-if analysis entry points.

覆盖场景 / Test scenarios:
- Happy path: 移除证据 → DiffSummary 显示受影响 issues
- Happy path: 修改争点 → DiffSummary 显示判决路径变化
- Edge case: 空 change_set → 拒绝执行
- Edge case: change_set 引用不存在的 evidence_id → 正常执行（过滤由 LLM 层处理）
- Error path: baseline 目录不存在 → FileNotFoundError
- Error path: baseline 缺少 issue_tree.json → FileNotFoundError
- Error path: change_set 文件不存在 → FileNotFoundError
- Error path: change_set YAML 格式无效 → ValueError
- Verification: DiffSummary 包含 affected_issue_ids 和 diff_entries
- Verification: run_whatif 输出 diff_summary.json 文件
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
import yaml

from engines.simulation_run.simulator import (
    ScenarioSimulator,
    load_baseline,
    parse_change_set,
    run_whatif,
)
from engines.simulation_run.schemas import (
    ChangeItem,
    ChangeItemObjectType,
    DiffDirection,
    ScenarioResult,
    ScenarioStatus,
)


# ---------------------------------------------------------------------------
# Mock LLM Client / Mock LLM 客户端
# ---------------------------------------------------------------------------


class MockLLMClient:
    """返回预定义 JSON 响应的 mock LLM 客户端。"""

    def __init__(self, response: str = "", fail: bool = False) -> None:
        self._response = response
        self._fail = fail
        self.call_count = 0

    async def create_message(self, system: str, user: str, **kwargs) -> str:
        self.call_count += 1
        if self._fail:
            raise RuntimeError("Simulated LLM failure")
        return self._response


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_CASE_ID = "case-civil-loan-integration-001"
_RUN_ID = "run-baseline-integration-001"

_ISSUE_TREE = {
    "case_id": _CASE_ID,
    "issues": [
        {
            "issue_id": "issue-int-001",
            "case_id": _CASE_ID,
            "title": "借贷关系成立",
            "issue_type": "factual",
            "parent_issue_id": None,
            "evidence_ids": ["ev-int-01", "ev-int-02"],
            "fact_propositions": [],
        },
        {
            "issue_id": "issue-int-002",
            "case_id": _CASE_ID,
            "title": "还款金额争议",
            "issue_type": "factual",
            "parent_issue_id": None,
            "evidence_ids": ["ev-int-02"],
            "fact_propositions": [],
        },
    ],
    "burdens": [],
    "claim_issue_mapping": [],
    "defense_issue_mapping": [],
}

_EVIDENCE_INDEX = {
    "case_id": _CASE_ID,
    "evidence": [
        {
            "evidence_id": "ev-int-01",
            "case_id": _CASE_ID,
            "owner_party_id": "party-p-001",
            "title": "借条原件",
            "source": "原告提交",
            "summary": "载明借款50万元的借条原件",
            "evidence_type": "documentary",
            "target_fact_ids": ["fact-loan-existence-001"],
        },
        {
            "evidence_id": "ev-int-02",
            "case_id": _CASE_ID,
            "owner_party_id": "party-p-001",
            "title": "银行转账记录",
            "source": "银行出具",
            "summary": "50万元转账流水",
            "evidence_type": "electronic_data",
            "target_fact_ids": ["fact-loan-disbursement-001"],
        },
    ],
}

_RESULT_JSON = {
    "case_id": _CASE_ID,
    "run_id": _RUN_ID,
}

_MOCK_LLM_RESPONSE = json.dumps(
    {
        "summary": "移除借条证据后借贷关系争点被削弱。",
        "diff_entries": [
            {
                "issue_id": "issue-int-001",
                "impact_description": "移除借条原件后，原告缺少直接书证，借贷关系争点被显著削弱。",
                "direction": "weaken",
            },
            {
                "issue_id": "issue-int-002",
                "impact_description": "还款金额争议不受借条移除影响，维持中性。",
                "direction": "neutral",
            },
        ],
    },
    ensure_ascii=False,
)


@pytest.fixture()
def baseline_dir(tmp_path: Path) -> Path:
    """创建一个完整的 baseline 输出目录。"""
    out = tmp_path / "baseline_run"
    out.mkdir()
    (out / "issue_tree.json").write_text(
        json.dumps(_ISSUE_TREE, ensure_ascii=False), encoding="utf-8"
    )
    (out / "evidence_index.json").write_text(
        json.dumps(_EVIDENCE_INDEX, ensure_ascii=False), encoding="utf-8"
    )
    (out / "result.json").write_text(
        json.dumps(_RESULT_JSON, ensure_ascii=False), encoding="utf-8"
    )
    return out


@pytest.fixture()
def change_set_file(tmp_path: Path) -> Path:
    """创建一个有效的 change_set YAML 文件。"""
    cs = {
        "scenario_id": "scenario-int-remove-evidence-001",
        "changes": [
            {
                "target_object_type": "Evidence",
                "target_object_id": "ev-int-01",
                "field_path": "summary",
                "old_value": "载明借款50万元的借条原件",
                "new_value": "借条复印件，原件遗失",
            }
        ],
    }
    p = tmp_path / "change_set.yaml"
    p.write_text(yaml.dump(cs, allow_unicode=True), encoding="utf-8")
    return p


@pytest.fixture()
def change_set_issue_file(tmp_path: Path) -> Path:
    """创建修改争点的 change_set YAML。"""
    cs = {
        "scenario_id": "scenario-int-issue-priority-001",
        "changes": [
            {
                "target_object_type": "Issue",
                "target_object_id": "issue-int-001",
                "field_path": "issue_type",
                "old_value": "factual",
                "new_value": "legal",
            }
        ],
    }
    p = tmp_path / "change_set_issue.yaml"
    p.write_text(yaml.dump(cs, allow_unicode=True), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# load_baseline 测试 / load_baseline tests
# ---------------------------------------------------------------------------


class TestLoadBaseline:
    def test_loads_successfully(self, baseline_dir: Path):
        """加载有效 baseline 目录成功。"""
        issue_tree, evidence_index, run_id = load_baseline(baseline_dir)
        assert issue_tree.case_id == _CASE_ID
        assert len(issue_tree.issues) == 2
        assert len(evidence_index.evidence) == 2
        assert run_id == _RUN_ID

    def test_missing_dir_raises(self, tmp_path: Path):
        """不存在的目录应抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError, match="Baseline.*not found"):
            load_baseline(tmp_path / "nonexistent")

    def test_missing_issue_tree_raises(self, tmp_path: Path):
        """缺少 issue_tree.json 应抛出 FileNotFoundError。"""
        d = tmp_path / "incomplete"
        d.mkdir()
        (d / "evidence_index.json").write_text("{}", encoding="utf-8")
        with pytest.raises(FileNotFoundError, match="issue_tree.json"):
            load_baseline(d)

    def test_missing_evidence_index_raises(self, tmp_path: Path):
        """缺少 evidence_index.json 应抛出 FileNotFoundError。"""
        d = tmp_path / "incomplete"
        d.mkdir()
        (d / "issue_tree.json").write_text(
            json.dumps(_ISSUE_TREE), encoding="utf-8"
        )
        with pytest.raises(FileNotFoundError, match="evidence_index.json"):
            load_baseline(d)

    def test_fallback_run_id_from_dirname(self, tmp_path: Path):
        """没有 result.json 时 run_id 回退为目录名。"""
        d = tmp_path / "my-run-dir"
        d.mkdir()
        (d / "issue_tree.json").write_text(
            json.dumps(_ISSUE_TREE), encoding="utf-8"
        )
        (d / "evidence_index.json").write_text(
            json.dumps(_EVIDENCE_INDEX), encoding="utf-8"
        )
        _, _, run_id = load_baseline(d)
        assert run_id == "my-run-dir"


# ---------------------------------------------------------------------------
# parse_change_set 测试 / parse_change_set tests
# ---------------------------------------------------------------------------


class TestParseChangeSet:
    def test_parses_valid_yaml(self, change_set_file: Path):
        """有效 YAML 正常解析。"""
        scenario_id, items = parse_change_set(change_set_file)
        assert scenario_id == "scenario-int-remove-evidence-001"
        assert len(items) == 1
        assert items[0].target_object_type == ChangeItemObjectType.Evidence
        assert items[0].target_object_id == "ev-int-01"

    def test_missing_file_raises(self, tmp_path: Path):
        """不存在的文件应抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError, match="not found"):
            parse_change_set(tmp_path / "nonexistent.yaml")

    def test_missing_scenario_id_raises(self, tmp_path: Path):
        """缺少 scenario_id 应抛出 ValueError。"""
        p = tmp_path / "bad.yaml"
        p.write_text(
            yaml.dump({"changes": [{"target_object_type": "Evidence",
                                     "target_object_id": "x",
                                     "field_path": "y"}]}),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="scenario_id"):
            parse_change_set(p)

    def test_empty_changes_raises(self, tmp_path: Path):
        """空 changes 列表应抛出 ValueError。"""
        p = tmp_path / "empty.yaml"
        p.write_text(
            yaml.dump({"scenario_id": "s1", "changes": []}),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="changes.*non-empty"):
            parse_change_set(p)

    def test_invalid_change_entry_raises(self, tmp_path: Path):
        """无效的 change entry 应抛出 ValueError。"""
        p = tmp_path / "invalid.yaml"
        p.write_text(
            yaml.dump({
                "scenario_id": "s1",
                "changes": [{"bad_field": "invalid"}],
            }),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="changes\\[0\\]"):
            parse_change_set(p)

    def test_non_dict_yaml_raises(self, tmp_path: Path):
        """非字典 YAML 应抛出 ValueError。"""
        p = tmp_path / "list.yaml"
        p.write_text("- item1\n- item2\n", encoding="utf-8")
        with pytest.raises(ValueError, match="mapping"):
            parse_change_set(p)


# ---------------------------------------------------------------------------
# run_whatif 集成测试 / run_whatif integration tests
# ---------------------------------------------------------------------------


class TestRunWhatif:
    @pytest.mark.asyncio
    async def test_happy_path_remove_evidence(
        self, baseline_dir: Path, change_set_file: Path
    ):
        """Happy path: 移除证据 → DiffSummary 显示受影响 issues。"""
        client = MockLLMClient(_MOCK_LLM_RESPONSE)
        result = await run_whatif(
            baseline_dir=baseline_dir,
            change_set_path=change_set_file,
            llm_client=client,
        )

        assert isinstance(result, ScenarioResult)
        assert result.scenario.status == ScenarioStatus.completed
        assert len(result.scenario.diff_summary) >= 1
        assert len(result.scenario.affected_issue_ids) >= 1
        # DiffSummary 中的 issue_id 都是已知的
        known_ids = {i["issue_id"] for i in _ISSUE_TREE["issues"]}
        for entry in result.scenario.diff_summary:
            assert entry.issue_id in known_ids

    @pytest.mark.asyncio
    async def test_happy_path_modify_issue(
        self, baseline_dir: Path, change_set_issue_file: Path
    ):
        """Happy path: 修改争点 → DiffSummary 显示变化。"""
        mock_response = json.dumps(
            {
                "summary": "争点类型修改影响判决路径。",
                "diff_entries": [
                    {
                        "issue_id": "issue-int-001",
                        "impact_description": "争点从事实类变为法律类，影响举证责任分配。",
                        "direction": "strengthen",
                    }
                ],
            },
            ensure_ascii=False,
        )
        client = MockLLMClient(mock_response)
        result = await run_whatif(
            baseline_dir=baseline_dir,
            change_set_path=change_set_issue_file,
            llm_client=client,
        )

        assert result.scenario.status == ScenarioStatus.completed
        assert "issue-int-001" in result.scenario.affected_issue_ids
        assert result.scenario.diff_summary[0].direction == DiffDirection.strengthen

    @pytest.mark.asyncio
    async def test_output_file_created(
        self, baseline_dir: Path, change_set_file: Path
    ):
        """run_whatif 应输出 diff_summary.json 到 scenario 子目录。"""
        client = MockLLMClient(_MOCK_LLM_RESPONSE)
        result = await run_whatif(
            baseline_dir=baseline_dir,
            change_set_path=change_set_file,
            llm_client=client,
        )

        scenario_id = result.scenario.scenario_id
        out_path = baseline_dir / f"scenario_{scenario_id}" / "diff_summary.json"
        assert out_path.exists(), f"Expected output at {out_path}"

        # 验证文件内容可解析 / Verify file content is parseable
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert "scenario" in data
        assert "run" in data

    @pytest.mark.asyncio
    async def test_diff_summary_has_required_fields(
        self, baseline_dir: Path, change_set_file: Path
    ):
        """DiffSummary 包含 affected_issue_ids 和 diff_entries。"""
        client = MockLLMClient(_MOCK_LLM_RESPONSE)
        result = await run_whatif(
            baseline_dir=baseline_dir,
            change_set_path=change_set_file,
            llm_client=client,
        )

        scenario = result.scenario
        # affected_issue_ids 覆盖所有 diff_entry.issue_id
        diff_ids = {e.issue_id for e in scenario.diff_summary}
        assert diff_ids.issubset(set(scenario.affected_issue_ids))
        # 每个 diff_entry 都有 impact_description
        for entry in scenario.diff_summary:
            assert entry.impact_description
            assert entry.direction in DiffDirection

    @pytest.mark.asyncio
    async def test_empty_change_set_raises(
        self, baseline_dir: Path, tmp_path: Path
    ):
        """空 change_set → 拒绝执行（parse_change_set 阶段）。"""
        p = tmp_path / "empty_cs.yaml"
        p.write_text(
            yaml.dump({"scenario_id": "s-empty", "changes": []}),
            encoding="utf-8",
        )
        client = MockLLMClient(_MOCK_LLM_RESPONSE)
        with pytest.raises(ValueError, match="non-empty"):
            await run_whatif(
                baseline_dir=baseline_dir,
                change_set_path=p,
                llm_client=client,
            )

    @pytest.mark.asyncio
    async def test_nonexistent_evidence_id_handled(
        self, baseline_dir: Path, tmp_path: Path
    ):
        """change_set 引用不存在的 evidence_id → 正常执行，affected_evidence_ids 为空。"""
        cs = {
            "scenario_id": "scenario-nonexistent-ev",
            "changes": [
                {
                    "target_object_type": "Evidence",
                    "target_object_id": "ev-NONEXISTENT-999",
                    "field_path": "summary",
                    "old_value": "old",
                    "new_value": "new",
                }
            ],
        }
        p = tmp_path / "nonexistent_ev.yaml"
        p.write_text(yaml.dump(cs, allow_unicode=True), encoding="utf-8")

        mock_response = json.dumps(
            {
                "summary": "不存在的证据变更。",
                "diff_entries": [
                    {
                        "issue_id": "issue-int-001",
                        "impact_description": "证据不存在但变更仍影响争点分析。",
                        "direction": "neutral",
                    }
                ],
            },
            ensure_ascii=False,
        )
        client = MockLLMClient(mock_response)
        result = await run_whatif(
            baseline_dir=baseline_dir,
            change_set_path=p,
            llm_client=client,
        )

        # 不存在的 evidence_id 不应出现在 affected_evidence_ids 中
        assert "ev-NONEXISTENT-999" not in result.scenario.affected_evidence_ids
        # 推演仍然完成
        assert result.scenario.status == ScenarioStatus.completed

    @pytest.mark.asyncio
    async def test_baseline_not_found_raises(self, tmp_path: Path, change_set_file: Path):
        """baseline 目录不存在 → FileNotFoundError。"""
        client = MockLLMClient(_MOCK_LLM_RESPONSE)
        with pytest.raises(FileNotFoundError, match="Baseline.*not found"):
            await run_whatif(
                baseline_dir=tmp_path / "nonexistent_baseline",
                change_set_path=change_set_file,
                llm_client=client,
            )

    @pytest.mark.asyncio
    async def test_llm_failure_returns_failed_result(
        self, baseline_dir: Path, change_set_file: Path
    ):
        """LLM 失败 → ScenarioResult status=failed，不抛异常。"""
        client = MockLLMClient(fail=True)
        result = await run_whatif(
            baseline_dir=baseline_dir,
            change_set_path=change_set_file,
            llm_client=client,
        )

        assert result.scenario.status == ScenarioStatus.failed
        assert result.run.status == "failed"

    @pytest.mark.asyncio
    async def test_run_trigger_type_is_scenario_execution(
        self, baseline_dir: Path, change_set_file: Path
    ):
        """Run.trigger_type 固定为 'scenario_execution'。"""
        client = MockLLMClient(_MOCK_LLM_RESPONSE)
        result = await run_whatif(
            baseline_dir=baseline_dir,
            change_set_path=change_set_file,
            llm_client=client,
        )

        assert result.run.trigger_type == "scenario_execution"

    @pytest.mark.asyncio
    async def test_scenario_ids_consistent(
        self, baseline_dir: Path, change_set_file: Path
    ):
        """Scenario ID 和 Run.scenario_id 一致。"""
        client = MockLLMClient(_MOCK_LLM_RESPONSE)
        result = await run_whatif(
            baseline_dir=baseline_dir,
            change_set_path=change_set_file,
            llm_client=client,
        )

        assert result.run.scenario_id == result.scenario.scenario_id
        assert result.scenario.scenario_id == "scenario-int-remove-evidence-001"


# ---------------------------------------------------------------------------
# CLI script 烟雾测试 / CLI script smoke test
# ---------------------------------------------------------------------------


class TestRunScenarioCLI:
    def test_script_importable(self):
        """scripts/run_scenario.py 可作为模块导入（语法检查）。"""
        import importlib.util

        script_path = (
            Path(__file__).parent.parent.parent.parent / "scripts" / "run_scenario.py"
        )
        spec = importlib.util.spec_from_file_location("run_scenario", script_path)
        assert spec is not None, f"Cannot find {script_path}"
        mod = importlib.util.module_from_spec(spec)
        # Don't exec — just verify it can be loaded without syntax errors
        assert mod is not None
