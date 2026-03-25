"""
ScenarioSimulator 单元测试。
Unit tests for ScenarioSimulator.

使用 mock LLM 客户端验证：
Tests using mock LLM client verify:
- 输出符合 ScenarioResult schema / Output conforms to ScenarioResult schema
- diff_summary 为 DiffEntry[] / diff_summary is DiffEntry[]
- affected_issue_ids 覆盖所有 diff_entry / affected_issue_ids covers all diff entries
- trigger_type = "scenario_execution" / trigger_type fixed to "scenario_execution"
- baseline change_set 拒绝执行 / Baseline change_set raises ValueError
- case_id 不匹配时抛出 ValueError / case_id mismatch raises ValueError
- issues 为空时抛出 ValueError / Empty issues raises ValueError
- LLM 重试机制 / LLM retry mechanism
- 非法 issue_id 被过滤 / Invalid issue_ids are filtered
- LLM 无有效输出时补充保底条目 / Fallback entries added when LLM returns nothing
- JSON 解析（含 markdown 代码块）/ JSON parsing (incl. markdown code blocks)
"""

from __future__ import annotations

import json
import pytest

from engines.simulation_run.simulator import (
    ScenarioSimulator,
    _extract_json_object,
    _resolve_direction,
)
from engines.simulation_run.schemas import (
    Burden,
    ChangeItem,
    ChangeItemObjectType,
    ClaimIssueMapping,
    DefenseIssueMapping,
    DiffDirection,
    EvidenceIndex,
    EvidenceItem,
    FactProposition,
    Issue,
    IssueTree,
    ScenarioInput,
    ScenarioResult,
    ScenarioStatus,
)
from engines.simulation_run.validator import (
    validate_scenario,
    validate_scenario_result,
    validate_scenario_result_strict,
)


# ---------------------------------------------------------------------------
# Mock LLM Client / Mock LLM 客户端
# ---------------------------------------------------------------------------


class MockLLMClient:
    """返回预定义 JSON 响应的 mock LLM 客户端。
    Mock LLM client that returns predefined JSON responses.
    """

    def __init__(self, response: str, fail_times: int = 0) -> None:
        self._response = response
        self._fail_times = fail_times
        self.call_count = 0
        self.last_system: str | None = None
        self.last_user: str | None = None

    async def create_message(self, system: str, user: str, **kwargs) -> str:
        self.call_count += 1
        self.last_system = system
        self.last_user = user
        if self._fail_times > 0:
            self._fail_times -= 1
            raise RuntimeError("Simulated LLM failure")
        return self._response


# ---------------------------------------------------------------------------
# 测试数据 / Test fixtures
# ---------------------------------------------------------------------------

_CASE_ID = "case-civil-loan-test-001"
_RUN_ID = "run-scenario-test-001"
_SCENARIO_ID = "scenario-test-evidence-downgrade-001"
_BASELINE_RUN_ID = "run-baseline-test-001"
_WORKSPACE_ID = "workspace-test-001"

_MOCK_LLM_RESPONSE = json.dumps({
    "summary": "借条证据降级对借贷关系争点产生削弱影响。",
    "diff_entries": [
        {
            "issue_id": "issue-civil-loan-test-001-001",
            "impact_description": (
                "借条由原件变为复印件（原件遗失），真实性待核实，"
                "削弱了原告证明借贷关系成立的核心证据效力。"
            ),
            "direction": "weaken",
        }
    ],
}, ensure_ascii=False)

_SAMPLE_ISSUE_TREE = IssueTree(
    case_id=_CASE_ID,
    issues=[
        Issue(
            issue_id="issue-civil-loan-test-001-001",
            case_id=_CASE_ID,
            title="借贷关系成立",
            issue_type="factual",
            parent_issue_id=None,
            evidence_ids=[
                "evidence-civil-loan-test-001-01",
                "evidence-civil-loan-test-001-02",
            ],
            fact_propositions=[
                FactProposition(
                    proposition_id="fp-test-001-01",
                    text="双方存在借贷合意",
                    status="supported",
                    linked_evidence_ids=["evidence-civil-loan-test-001-01"],
                )
            ],
        ),
    ],
    burdens=[
        Burden(
            burden_id="burden-civil-loan-test-001-001",
            case_id=_CASE_ID,
            issue_id="issue-civil-loan-test-001-001",
            burden_party_id="party-plaintiff-001",
            description="原告举证借贷关系成立",
        )
    ],
    claim_issue_mapping=[
        ClaimIssueMapping(
            claim_id="claim-test-001",
            issue_ids=["issue-civil-loan-test-001-001"],
        )
    ],
    defense_issue_mapping=[],
)

_SAMPLE_EVIDENCE_INDEX = EvidenceIndex(
    case_id=_CASE_ID,
    evidence=[
        EvidenceItem(
            evidence_id="evidence-civil-loan-test-001-01",
            case_id=_CASE_ID,
            owner_party_id="party-plaintiff-001",
            title="借条原件",
            source="原告提交",
            summary="载明借款50万元的借条原件",
            evidence_type="documentary",
            target_fact_ids=["fact-loan-existence-001"],
        ),
        EvidenceItem(
            evidence_id="evidence-civil-loan-test-001-02",
            case_id=_CASE_ID,
            owner_party_id="party-plaintiff-001",
            title="银行转账记录",
            source="银行出具",
            summary="50万元转账流水",
            evidence_type="electronic_data",
            target_fact_ids=["fact-loan-disbursement-001"],
        ),
    ],
)

_SAMPLE_CHANGE_SET = [
    ChangeItem(
        target_object_type=ChangeItemObjectType.Evidence,
        target_object_id="evidence-civil-loan-test-001-01",
        field_path="summary",
        old_value="载明借款50万元的借条原件",
        new_value="借条复印件，原件遗失，金额50万元",
    )
]

_SAMPLE_SCENARIO_INPUT = ScenarioInput(
    scenario_id=_SCENARIO_ID,
    baseline_run_id=_BASELINE_RUN_ID,
    change_set=_SAMPLE_CHANGE_SET,
    workspace_id=_WORKSPACE_ID,
)


# ---------------------------------------------------------------------------
# 基础功能测试 / Basic functionality tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_simulate_returns_scenario_result():
    """simulate 应返回 ScenarioResult 且字段齐全。
    simulate() should return a ScenarioResult with all required fields.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    simulator = ScenarioSimulator(llm_client=client, case_type="civil_loan")

    result = await simulator.simulate(
        scenario_input=_SAMPLE_SCENARIO_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    assert isinstance(result, ScenarioResult)
    assert result.scenario.scenario_id == _SCENARIO_ID
    assert result.scenario.case_id == _CASE_ID
    assert result.run.run_id == _RUN_ID


@pytest.mark.asyncio
async def test_diff_summary_is_list():
    """diff_summary 应为 DiffEntry[]（非 baseline anchor 场景）。
    diff_summary should be DiffEntry[] for non-baseline scenarios.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    simulator = ScenarioSimulator(llm_client=client, case_type="civil_loan")

    result = await simulator.simulate(
        scenario_input=_SAMPLE_SCENARIO_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    assert isinstance(result.scenario.diff_summary, list), (
        "diff_summary should be DiffEntry[] for counterfactual scenarios"
    )
    assert len(result.scenario.diff_summary) >= 1


@pytest.mark.asyncio
async def test_affected_issue_ids_covers_diff_entries():
    """affected_issue_ids 必须覆盖所有 diff_entry.issue_id。
    affected_issue_ids must cover all diff_entry.issue_id values.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    simulator = ScenarioSimulator(llm_client=client, case_type="civil_loan")

    result = await simulator.simulate(
        scenario_input=_SAMPLE_SCENARIO_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    diff_issue_ids = {e.issue_id for e in result.scenario.diff_summary}
    affected = set(result.scenario.affected_issue_ids)
    assert diff_issue_ids.issubset(affected), (
        f"affected_issue_ids missing: {diff_issue_ids - affected}"
    )


@pytest.mark.asyncio
async def test_run_trigger_type_is_scenario_execution():
    """Run.trigger_type 必须固定为 'scenario_execution'。
    Run.trigger_type must be 'scenario_execution'.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    simulator = ScenarioSimulator(llm_client=client, case_type="civil_loan")

    result = await simulator.simulate(
        scenario_input=_SAMPLE_SCENARIO_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    assert result.run.trigger_type == "scenario_execution"


@pytest.mark.asyncio
async def test_run_scenario_id_matches():
    """Run.scenario_id 必须与 Scenario.scenario_id 一致。
    Run.scenario_id must match Scenario.scenario_id.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    simulator = ScenarioSimulator(llm_client=client, case_type="civil_loan")

    result = await simulator.simulate(
        scenario_input=_SAMPLE_SCENARIO_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    assert result.run.scenario_id == result.scenario.scenario_id


@pytest.mark.asyncio
async def test_run_workspace_id_set():
    """Run.workspace_id 应与 ScenarioInput.workspace_id 一致。
    Run.workspace_id should match ScenarioInput.workspace_id.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    simulator = ScenarioSimulator(llm_client=client, case_type="civil_loan")

    result = await simulator.simulate(
        scenario_input=_SAMPLE_SCENARIO_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    assert result.run.workspace_id == _WORKSPACE_ID


@pytest.mark.asyncio
async def test_scenario_status_completed():
    """成功执行后 Scenario.status 应为 'completed'。
    Scenario.status should be 'completed' after successful simulation.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    simulator = ScenarioSimulator(llm_client=client, case_type="civil_loan")

    result = await simulator.simulate(
        scenario_input=_SAMPLE_SCENARIO_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    assert result.scenario.status == ScenarioStatus.completed


@pytest.mark.asyncio
async def test_affected_evidence_ids_from_change_set():
    """affected_evidence_ids 应包含 change_set 中 Evidence 类型的 ID。
    affected_evidence_ids should include Evidence IDs from change_set.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    simulator = ScenarioSimulator(llm_client=client, case_type="civil_loan")

    result = await simulator.simulate(
        scenario_input=_SAMPLE_SCENARIO_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    assert "evidence-civil-loan-test-001-01" in result.scenario.affected_evidence_ids


@pytest.mark.asyncio
async def test_run_input_snapshot_has_material_refs():
    """Run.input_snapshot 应包含争点和证据的 material_refs。
    Run.input_snapshot should have material_refs for issues and evidence.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    simulator = ScenarioSimulator(llm_client=client, case_type="civil_loan")

    result = await simulator.simulate(
        scenario_input=_SAMPLE_SCENARIO_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    snapshot = result.run.input_snapshot
    assert len(snapshot.material_refs) >= 1, "input_snapshot should have material_refs"


# ---------------------------------------------------------------------------
# 输入校验测试 / Input validation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_baseline_change_set_raises():
    """change_set 为空（baseline anchor）时应拒绝执行，抛出 ValueError。
    Empty change_set (baseline anchor) should raise ValueError.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    simulator = ScenarioSimulator(llm_client=client, case_type="civil_loan")

    baseline_input = ScenarioInput(
        scenario_id="scenario-baseline-test",
        baseline_run_id=_BASELINE_RUN_ID,
        change_set=[],  # 空 change_set = baseline anchor
        workspace_id=_WORKSPACE_ID,
    )

    with pytest.raises(ValueError, match="baseline"):
        await simulator.simulate(
            scenario_input=baseline_input,
            issue_tree=_SAMPLE_ISSUE_TREE,
            evidence_index=_SAMPLE_EVIDENCE_INDEX,
            run_id=_RUN_ID,
        )


@pytest.mark.asyncio
async def test_case_id_mismatch_raises():
    """issue_tree 与 evidence_index 的 case_id 不匹配时应抛出 ValueError。
    Mismatched case_ids should raise ValueError.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    simulator = ScenarioSimulator(llm_client=client, case_type="civil_loan")

    mismatched_evidence = EvidenceIndex(
        case_id="case-different-999",
        evidence=_SAMPLE_EVIDENCE_INDEX.evidence,
    )

    with pytest.raises(ValueError, match="case_id"):
        await simulator.simulate(
            scenario_input=_SAMPLE_SCENARIO_INPUT,
            issue_tree=_SAMPLE_ISSUE_TREE,
            evidence_index=mismatched_evidence,
            run_id=_RUN_ID,
        )


@pytest.mark.asyncio
async def test_empty_issues_raises():
    """issues 为空时应抛出 ValueError。
    Empty issues should raise ValueError.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    simulator = ScenarioSimulator(llm_client=client, case_type="civil_loan")

    empty_tree = IssueTree(
        case_id=_CASE_ID,
        issues=[],
        burdens=[],
        claim_issue_mapping=[],
        defense_issue_mapping=[],
    )

    with pytest.raises(ValueError, match="issues"):
        await simulator.simulate(
            scenario_input=_SAMPLE_SCENARIO_INPUT,
            issue_tree=empty_tree,
            evidence_index=_SAMPLE_EVIDENCE_INDEX,
            run_id=_RUN_ID,
        )


@pytest.mark.asyncio
async def test_unsupported_case_type_raises():
    """不支持的案由类型应抛出 ValueError。
    Unsupported case type should raise ValueError.
    """
    with pytest.raises(ValueError, match="不支持的案由类型"):
        ScenarioSimulator(llm_client=MockLLMClient(""), case_type="unknown_xyz")


# ---------------------------------------------------------------------------
# 鲁棒性测试 / Robustness tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_issue_id_filtered():
    """LLM 返回非法 issue_id 时应被过滤。
    Unknown issue_ids returned by LLM should be filtered out.
    """
    response_with_invalid_id = json.dumps({
        "summary": "",
        "diff_entries": [
            {
                "issue_id": "UNKNOWN-ISSUE-ID-XYZ",
                "impact_description": "这是一个不存在的争点",
                "direction": "weaken",
            },
            {
                "issue_id": "issue-civil-loan-test-001-001",
                "impact_description": "借条证据削弱了借贷关系证明。",
                "direction": "weaken",
            },
        ],
    }, ensure_ascii=False)

    client = MockLLMClient(response_with_invalid_id)
    simulator = ScenarioSimulator(llm_client=client, case_type="civil_loan")

    result = await simulator.simulate(
        scenario_input=_SAMPLE_SCENARIO_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    issue_ids = {e.issue_id for e in result.scenario.diff_summary}
    assert "UNKNOWN-ISSUE-ID-XYZ" not in issue_ids, (
        "Invalid issue_id should be filtered from diff_summary"
    )
    assert "issue-civil-loan-test-001-001" in issue_ids


@pytest.mark.asyncio
async def test_empty_diff_entries_triggers_fallback():
    """LLM 返回空 diff_entries 时应触发保底条目（覆盖所有争点）。
    Empty diff_entries from LLM should trigger fallback covering all issues.
    """
    empty_response = json.dumps({
        "summary": "",
        "diff_entries": [],
    }, ensure_ascii=False)

    client = MockLLMClient(empty_response)
    simulator = ScenarioSimulator(llm_client=client, case_type="civil_loan")

    result = await simulator.simulate(
        scenario_input=_SAMPLE_SCENARIO_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    assert len(result.scenario.diff_summary) >= 1, (
        "Fallback diff entries should be generated when LLM returns empty list"
    )
    for entry in result.scenario.diff_summary:
        assert entry.direction == DiffDirection.neutral


@pytest.mark.asyncio
async def test_llm_retry_succeeds_after_failures():
    """LLM 前两次失败后第三次成功应正常返回结果。
    Should succeed after two LLM failures if third attempt succeeds.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE, fail_times=2)
    simulator = ScenarioSimulator(
        llm_client=client, case_type="civil_loan", max_retries=3
    )

    result = await simulator.simulate(
        scenario_input=_SAMPLE_SCENARIO_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    assert result.scenario.case_id == _CASE_ID
    assert client.call_count == 3


@pytest.mark.asyncio
async def test_llm_retry_exhausted_returns_failed_result():
    """LLM 所有重试均失败应返回 status='failed' 的 ScenarioResult，不抛出异常。
    Exhausted retries should return a ScenarioResult with status='failed', not raise.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE, fail_times=10)
    simulator = ScenarioSimulator(
        llm_client=client, case_type="civil_loan", max_retries=3
    )

    result = await simulator.simulate(
        scenario_input=_SAMPLE_SCENARIO_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    assert isinstance(result, ScenarioResult)
    assert result.scenario.status == ScenarioStatus.failed
    assert result.run.status == "failed"
    assert result.scenario.scenario_id == _SCENARIO_ID
    assert result.run.run_id == _RUN_ID


@pytest.mark.asyncio
async def test_failed_result_preserves_ids():
    """失败结果应保留 scenario_id、case_id、run_id 等关键字段。
    Failed result should preserve scenario_id, case_id, run_id.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE, fail_times=10)
    simulator = ScenarioSimulator(
        llm_client=client, case_type="civil_loan", max_retries=1
    )

    result = await simulator.simulate(
        scenario_input=_SAMPLE_SCENARIO_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    assert result.scenario.case_id == _CASE_ID
    assert result.scenario.baseline_run_id == _BASELINE_RUN_ID
    assert result.run.workspace_id == _WORKSPACE_ID
    assert result.run.trigger_type == "scenario_execution"
    # diff_summary 为空列表 / diff_summary is empty list for failed result
    assert result.scenario.diff_summary == []


@pytest.mark.asyncio
async def test_parse_failure_returns_failed_result():
    """LLM 返回无法解析的响应时应返回 status='failed' 的 ScenarioResult。
    Unparseable LLM response should return ScenarioResult with status='failed'.
    """
    client = MockLLMClient("这不是合法的JSON，无法解析")
    simulator = ScenarioSimulator(
        llm_client=client, case_type="civil_loan", max_retries=1
    )

    result = await simulator.simulate(
        scenario_input=_SAMPLE_SCENARIO_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    assert result.scenario.status == ScenarioStatus.failed
    assert result.run.status == "failed"


@pytest.mark.asyncio
async def test_llm_receives_system_and_user_prompts():
    """LLM 应收到包含 case_id 和 scenario_id 的 prompt。
    LLM should receive prompts containing case_id and scenario_id.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    simulator = ScenarioSimulator(llm_client=client, case_type="civil_loan")

    await simulator.simulate(
        scenario_input=_SAMPLE_SCENARIO_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    assert client.call_count == 1
    assert client.last_system is not None
    assert client.last_user is not None
    assert _CASE_ID in client.last_user
    assert _SCENARIO_ID in client.last_user


# ---------------------------------------------------------------------------
# 校验器集成测试 / Validator integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validator_passes_on_valid_result():
    """有效 ScenarioResult 应通过校验。
    A valid ScenarioResult should pass validation.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    simulator = ScenarioSimulator(llm_client=client, case_type="civil_loan")

    result = await simulator.simulate(
        scenario_input=_SAMPLE_SCENARIO_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    known_ids = {i.issue_id for i in _SAMPLE_ISSUE_TREE.issues}
    vr = validate_scenario_result(result, _SAMPLE_ISSUE_TREE, known_ids)
    assert vr.is_valid, vr.summary()


# ---------------------------------------------------------------------------
# JSON 解析辅助函数测试 / JSON parsing utility tests
# ---------------------------------------------------------------------------


def test_extract_json_from_markdown_code_block():
    """应能从 markdown 代码块中提取 JSON。
    Should extract JSON from markdown code block.
    """
    text = '分析如下：\n```json\n{"diff_entries": []}\n```\n结束'
    result = _extract_json_object(text)
    assert result == {"diff_entries": []}


def test_extract_json_plain_object():
    """应能解析纯 JSON 对象文本。
    Should parse plain JSON object text.
    """
    text = '{"diff_entries": [], "summary": "test"}'
    result = _extract_json_object(text)
    assert result["summary"] == "test"


def test_extract_json_with_surrounding_text():
    """应能从含有前后文的文本中提取 JSON 对象。
    Should extract JSON object from text with surrounding content.
    """
    text = '以下是结果：\n{"diff_entries": []}\n提取完毕。'
    result = _extract_json_object(text)
    assert result == {"diff_entries": []}


def test_extract_json_invalid_raises():
    """无法解析时应抛出 ValueError。
    Should raise ValueError when JSON cannot be parsed.
    """
    with pytest.raises(ValueError, match="无法从 LLM 响应中解析"):
        _extract_json_object("这不是JSON内容")


# ---------------------------------------------------------------------------
# direction 解析测试 / direction resolution tests
# ---------------------------------------------------------------------------


def test_resolve_direction_english():
    """英文 direction 值应正确映射。
    English direction values should map correctly.
    """
    assert _resolve_direction("strengthen") == DiffDirection.strengthen
    assert _resolve_direction("weaken") == DiffDirection.weaken
    assert _resolve_direction("neutral") == DiffDirection.neutral


def test_resolve_direction_chinese():
    """中文 direction 值应正确映射。
    Chinese direction values should map correctly.
    """
    assert _resolve_direction("增强") == DiffDirection.strengthen
    assert _resolve_direction("削弱") == DiffDirection.weaken
    assert _resolve_direction("中性") == DiffDirection.neutral


def test_resolve_direction_unknown_defaults_to_neutral():
    """未知 direction 值应回退为 neutral。
    Unknown direction should default to neutral.
    """
    assert _resolve_direction("未知类型xyz") == DiffDirection.neutral
