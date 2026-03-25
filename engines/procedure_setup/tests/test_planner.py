"""
ProcedurePlanner 单元测试。
Unit tests for ProcedurePlanner.

使用 mock LLM 客户端验证：
Tests using mock LLM client verify:
- 输出符合 ProcedureSetupResult schema / Output conforms to ProcedureSetupResult schema
- procedure_states 覆盖全部八个阶段 / procedure_states covers all eight phases
- judge_questions 不含 owner_private / judge_questions excludes owner_private
- output_branching 仅含 admitted_for_discussion / output_branching only admits admitted_for_discussion
- state_id 格式确定性生成 / state_id deterministically generated
- next_state_ids 顺序正确 / next_state_ids in correct order
- trigger_type = "procedure_setup" / trigger_type fixed to "procedure_setup"
- case_id 不匹配时抛出 ValueError / case_id mismatch raises ValueError
- issues 为空时抛出 ValueError / Empty issues raises ValueError
- LLM 重试机制 / LLM retry mechanism
- LLM 失败时返回 failed 结果（不抛出异常）/ LLM failure returns failed result
- 不支持案由类型时抛出 ValueError / Unsupported case type raises ValueError
- JSON 解析（含 markdown 代码块）/ JSON parsing (incl. markdown code blocks)
"""

from __future__ import annotations

import json
import pytest

from engines.procedure_setup.planner import (
    ProcedurePlanner,
    _make_state_id,
    _build_next_state_ids,
    _sanitize_access_domains,
    _sanitize_evidence_statuses,
)
from engines.procedure_setup.schemas import (
    Burden,
    ClaimIssueMapping,
    DefenseIssueMapping,
    FactProposition,
    Issue,
    IssueTree,
    PHASE_ORDER,
    PartyInfo,
    ProcedureSetupInput,
    ProcedureSetupResult,
)
from engines.procedure_setup.validator import (
    validate_procedure_setup_result,
    validate_procedure_setup_result_strict,
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
# 测试数据 / Test data
# ---------------------------------------------------------------------------

_CASE_ID = "case-civil-loan-test-001"
_RUN_ID = "run-procedure-setup-test-001"
_WORKSPACE_ID = "workspace-test-001"

_MOCK_LLM_RESPONSE = json.dumps({
    "procedure_config": {
        "evidence_submission_deadline_days": 15,
        "evidence_challenge_window_days": 10,
        "max_rounds_per_phase": 3,
        "applicable_laws": ["中华人民共和国民法典", "中华人民共和国民事诉讼法"],
    },
    "procedure_states": [
        {
            "phase": "case_intake",
            "allowed_role_codes": ["plaintiff_agent", "judge_agent"],
            "readable_access_domains": ["shared_common"],
            "writable_object_types": ["Party", "Claim"],
            "admissible_evidence_statuses": ["private"],
            "entry_conditions": ["案件登记完成"],
            "exit_conditions": ["被告已收到应诉通知"],
        },
        {
            "phase": "element_mapping",
            "allowed_role_codes": ["plaintiff_agent", "defendant_agent", "judge_agent"],
            "readable_access_domains": ["shared_common"],
            "writable_object_types": ["Issue", "Burden"],
            "admissible_evidence_statuses": ["private", "submitted"],
            "entry_conditions": ["案件受理完毕"],
            "exit_conditions": ["争点树梳理完成"],
        },
        {
            "phase": "opening",
            "allowed_role_codes": ["plaintiff_agent", "defendant_agent"],
            "readable_access_domains": ["shared_common"],
            "writable_object_types": ["AgentOutput"],
            "admissible_evidence_statuses": ["submitted"],
            "entry_conditions": ["争点梳理完成"],
            "exit_conditions": ["双方陈述完毕"],
        },
        {
            "phase": "evidence_submission",
            "allowed_role_codes": ["plaintiff_agent", "defendant_agent"],
            "readable_access_domains": ["shared_common"],
            "writable_object_types": ["Evidence"],
            "admissible_evidence_statuses": ["private", "submitted"],
            "entry_conditions": ["举证期限开始"],
            "exit_conditions": ["举证期限届满"],
        },
        {
            "phase": "evidence_challenge",
            "allowed_role_codes": ["plaintiff_agent", "defendant_agent", "judge_agent"],
            "readable_access_domains": ["shared_common", "admitted_record"],
            "writable_object_types": ["Evidence", "AgentOutput"],
            "admissible_evidence_statuses": ["submitted", "challenged"],
            "entry_conditions": ["举证期限届满"],
            "exit_conditions": ["质证完毕"],
        },
        {
            "phase": "judge_questions",
            "allowed_role_codes": ["judge_agent"],
            "readable_access_domains": ["shared_common", "admitted_record"],
            "writable_object_types": ["AgentOutput"],
            "admissible_evidence_statuses": ["admitted_for_discussion"],
            "entry_conditions": ["质证完毕"],
            "exit_conditions": ["问询完毕"],
        },
        {
            "phase": "rebuttal",
            "allowed_role_codes": ["plaintiff_agent", "defendant_agent"],
            "readable_access_domains": ["shared_common", "admitted_record"],
            "writable_object_types": ["AgentOutput"],
            "admissible_evidence_statuses": ["admitted_for_discussion"],
            "entry_conditions": ["问询完毕"],
            "exit_conditions": ["辩论完毕"],
        },
        {
            "phase": "output_branching",
            "allowed_role_codes": ["judge_agent"],
            "readable_access_domains": ["shared_common", "admitted_record"],
            "writable_object_types": ["AgentOutput", "ReportArtifact"],
            "admissible_evidence_statuses": ["admitted_for_discussion"],
            "entry_conditions": ["辩论终结"],
            "exit_conditions": ["输出完毕"],
        },
    ],
    "timeline_events": [
        {
            "event_type": "evidence_submission_deadline",
            "phase": "evidence_submission",
            "description": "举证期限届满",
            "relative_day": 15,
            "is_mandatory": True,
        },
        {
            "event_type": "evidence_challenge_deadline",
            "phase": "evidence_challenge",
            "description": "质证期限届满",
            "relative_day": 25,
            "is_mandatory": True,
        },
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
            evidence_ids=["evidence-civil-loan-test-001-01"],
            fact_propositions=[
                FactProposition(
                    proposition_id="fp-test-001-01",
                    text="双方存在借贷合意",
                    status="supported",
                    linked_evidence_ids=["evidence-civil-loan-test-001-01"],
                )
            ],
        ),
        Issue(
            issue_id="issue-civil-loan-test-001-002",
            case_id=_CASE_ID,
            title="还款义务",
            issue_type="factual",
            parent_issue_id="issue-civil-loan-test-001-001",
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

_SAMPLE_SETUP_INPUT = ProcedureSetupInput(
    workspace_id=_WORKSPACE_ID,
    case_id=_CASE_ID,
    case_type="civil",
    parties=[
        PartyInfo(
            party_id="party-plaintiff-001",
            name="张三",
            role_code="plaintiff_agent",
            side="plaintiff",
        ),
        PartyInfo(
            party_id="party-defendant-001",
            name="李四",
            role_code="defendant_agent",
            side="defendant",
        ),
    ],
)


# ---------------------------------------------------------------------------
# 基础功能测试 / Basic functionality tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_returns_procedure_setup_result():
    """plan() 应返回 ProcedureSetupResult 且字段齐全。
    plan() should return a ProcedureSetupResult with all required fields.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    planner = ProcedurePlanner(llm_client=client, case_type="civil_loan")

    result = await planner.plan(
        setup_input=_SAMPLE_SETUP_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        run_id=_RUN_ID,
    )

    assert isinstance(result, ProcedureSetupResult)
    assert result.run.run_id == _RUN_ID
    assert result.run.case_id == _CASE_ID


@pytest.mark.asyncio
async def test_all_eight_phases_covered():
    """procedure_states 必须覆盖全部八个阶段。
    procedure_states must cover all eight phases.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    planner = ProcedurePlanner(llm_client=client, case_type="civil_loan")

    result = await planner.plan(
        setup_input=_SAMPLE_SETUP_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        run_id=_RUN_ID,
    )

    covered_phases = {s.phase for s in result.procedure_states}
    assert covered_phases == set(PHASE_ORDER), (
        f"Missing phases: {set(PHASE_ORDER) - covered_phases}"
    )


@pytest.mark.asyncio
async def test_state_ids_are_deterministic():
    """state_id 应按 pstate-{case_id}-{phase}-001 格式生成。
    state_id should be generated as pstate-{case_id}-{phase}-001.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    planner = ProcedurePlanner(llm_client=client, case_type="civil_loan")

    result = await planner.plan(
        setup_input=_SAMPLE_SETUP_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        run_id=_RUN_ID,
    )

    for state in result.procedure_states:
        expected_id = f"pstate-{_CASE_ID}-{state.phase}-001"
        assert state.state_id == expected_id, (
            f"Expected state_id={expected_id!r}, got {state.state_id!r}"
        )


@pytest.mark.asyncio
async def test_next_state_ids_follow_phase_order():
    """next_state_ids 应按 PHASE_ORDER 顺序引用下一状态。
    next_state_ids should reference the next state in PHASE_ORDER.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    planner = ProcedurePlanner(llm_client=client, case_type="civil_loan")

    result = await planner.plan(
        setup_input=_SAMPLE_SETUP_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        run_id=_RUN_ID,
    )

    phase_map = {s.phase: s for s in result.procedure_states}
    for i, phase in enumerate(PHASE_ORDER[:-1]):
        state = phase_map[phase]
        next_phase = PHASE_ORDER[i + 1]
        expected_next = f"pstate-{_CASE_ID}-{next_phase}-001"
        assert expected_next in state.next_state_ids, (
            f"State {state.state_id} should have next_state_id={expected_next!r}"
        )


@pytest.mark.asyncio
async def test_output_branching_is_terminal():
    """output_branching 状态的 next_state_ids 必须为空。
    output_branching.next_state_ids must be empty.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    planner = ProcedurePlanner(llm_client=client, case_type="civil_loan")

    result = await planner.plan(
        setup_input=_SAMPLE_SETUP_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        run_id=_RUN_ID,
    )

    phase_map = {s.phase: s for s in result.procedure_states}
    terminal = phase_map["output_branching"]
    assert terminal.next_state_ids == [], (
        "output_branching.next_state_ids must be empty"
    )


@pytest.mark.asyncio
async def test_judge_questions_no_owner_private():
    """judge_questions 阶段不得包含 owner_private 读取域。
    judge_questions phase must not include owner_private in readable_access_domains.
    """
    # 故意在 LLM 响应中包含 owner_private（测试引擎清理逻辑）
    # Intentionally include owner_private in LLM response (tests engine sanitization)
    response_with_violation = json.dumps({
        "procedure_config": {
            "evidence_submission_deadline_days": 15,
            "evidence_challenge_window_days": 10,
            "max_rounds_per_phase": 3,
            "applicable_laws": [],
        },
        "procedure_states": [
            {
                "phase": "judge_questions",
                "allowed_role_codes": ["judge_agent"],
                "readable_access_domains": ["owner_private", "shared_common", "admitted_record"],
                "writable_object_types": ["AgentOutput"],
                "admissible_evidence_statuses": ["admitted_for_discussion"],
                "entry_conditions": ["质证完毕"],
                "exit_conditions": ["问询完毕"],
            },
        ],
        "timeline_events": [],
    }, ensure_ascii=False)

    client = MockLLMClient(response_with_violation)
    planner = ProcedurePlanner(llm_client=client, case_type="civil_loan")

    result = await planner.plan(
        setup_input=_SAMPLE_SETUP_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        run_id=_RUN_ID,
    )

    phase_map = {s.phase: s for s in result.procedure_states}
    jq_state = phase_map["judge_questions"]
    assert "owner_private" not in jq_state.readable_access_domains, (
        "Engine must sanitize owner_private from judge_questions.readable_access_domains"
    )


@pytest.mark.asyncio
async def test_output_branching_only_admitted_evidence():
    """output_branching 阶段 admissible_evidence_statuses 必须仅含 admitted_for_discussion。
    output_branching.admissible_evidence_statuses must only contain admitted_for_discussion.
    """
    # 故意在 LLM 响应中包含非法状态（测试引擎清理逻辑）
    # Intentionally include illegal status (tests engine sanitization)
    response_with_violation = json.dumps({
        "procedure_config": {
            "evidence_submission_deadline_days": 15,
            "evidence_challenge_window_days": 10,
            "max_rounds_per_phase": 3,
            "applicable_laws": [],
        },
        "procedure_states": [
            {
                "phase": "output_branching",
                "allowed_role_codes": ["judge_agent"],
                "readable_access_domains": ["admitted_record"],
                "writable_object_types": ["AgentOutput"],
                "admissible_evidence_statuses": ["submitted", "admitted_for_discussion"],
                "entry_conditions": ["辩论终结"],
                "exit_conditions": ["输出完毕"],
            },
        ],
        "timeline_events": [],
    }, ensure_ascii=False)

    client = MockLLMClient(response_with_violation)
    planner = ProcedurePlanner(llm_client=client, case_type="civil_loan")

    result = await planner.plan(
        setup_input=_SAMPLE_SETUP_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        run_id=_RUN_ID,
    )

    phase_map = {s.phase: s for s in result.procedure_states}
    ob_state = phase_map["output_branching"]
    assert ob_state.admissible_evidence_statuses == ["admitted_for_discussion"], (
        "Engine must sanitize output_branching.admissible_evidence_statuses"
    )


@pytest.mark.asyncio
async def test_run_trigger_type_is_procedure_setup():
    """Run.trigger_type 必须固定为 'procedure_setup'。
    Run.trigger_type must be 'procedure_setup'.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    planner = ProcedurePlanner(llm_client=client, case_type="civil_loan")

    result = await planner.plan(
        setup_input=_SAMPLE_SETUP_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        run_id=_RUN_ID,
    )

    assert result.run.trigger_type == "procedure_setup"


@pytest.mark.asyncio
async def test_run_workspace_id_matches():
    """Run.workspace_id 应与 ProcedureSetupInput.workspace_id 一致。
    Run.workspace_id should match ProcedureSetupInput.workspace_id.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    planner = ProcedurePlanner(llm_client=client, case_type="civil_loan")

    result = await planner.plan(
        setup_input=_SAMPLE_SETUP_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        run_id=_RUN_ID,
    )

    assert result.run.workspace_id == _WORKSPACE_ID


@pytest.mark.asyncio
async def test_run_scenario_id_is_none():
    """Run.scenario_id 应为 None（非场景执行）。
    Run.scenario_id should be None (not a scenario execution).
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    planner = ProcedurePlanner(llm_client=client, case_type="civil_loan")

    result = await planner.plan(
        setup_input=_SAMPLE_SETUP_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        run_id=_RUN_ID,
    )

    assert result.run.scenario_id is None


@pytest.mark.asyncio
async def test_procedure_states_have_correct_case_id():
    """每个 ProcedureState.case_id 必须与 setup_input.case_id 一致。
    Every ProcedureState.case_id must match setup_input.case_id.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    planner = ProcedurePlanner(llm_client=client, case_type="civil_loan")

    result = await planner.plan(
        setup_input=_SAMPLE_SETUP_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        run_id=_RUN_ID,
    )

    for state in result.procedure_states:
        assert state.case_id == _CASE_ID, (
            f"ProcedureState {state.state_id}.case_id must be {_CASE_ID!r}"
        )


@pytest.mark.asyncio
async def test_timeline_events_generated():
    """时间线事件应至少包含举证期限事件。
    Timeline events should include at least the evidence submission deadline.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    planner = ProcedurePlanner(llm_client=client, case_type="civil_loan")

    result = await planner.plan(
        setup_input=_SAMPLE_SETUP_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        run_id=_RUN_ID,
    )

    assert len(result.timeline_events) >= 1
    event_types = {ev.event_type for ev in result.timeline_events}
    assert "evidence_submission_deadline" in event_types, (
        "Timeline events must include evidence_submission_deadline"
    )


@pytest.mark.asyncio
async def test_procedure_config_values():
    """ProcedureConfig 应正确反映 LLM 输出和引擎常量。
    ProcedureConfig should correctly reflect LLM output and engine constants.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    planner = ProcedurePlanner(llm_client=client, case_type="civil_loan")

    result = await planner.plan(
        setup_input=_SAMPLE_SETUP_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        run_id=_RUN_ID,
    )

    cfg = result.procedure_config
    assert cfg.total_phases == len(PHASE_ORDER) == 8
    assert cfg.evidence_submission_deadline_days == 15
    assert cfg.evidence_challenge_window_days == 10
    assert cfg.case_type == "civil"


# ---------------------------------------------------------------------------
# 输入校验测试 / Input validation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_case_id_mismatch_raises():
    """setup_input 与 issue_tree 的 case_id 不匹配时应抛出 ValueError。
    Mismatched case_ids should raise ValueError.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    planner = ProcedurePlanner(llm_client=client, case_type="civil_loan")

    mismatched_input = ProcedureSetupInput(
        workspace_id=_WORKSPACE_ID,
        case_id="case-different-999",
        case_type="civil",
        parties=[],
    )

    with pytest.raises(ValueError, match="case_id"):
        await planner.plan(
            setup_input=mismatched_input,
            issue_tree=_SAMPLE_ISSUE_TREE,
            run_id=_RUN_ID,
        )


@pytest.mark.asyncio
async def test_empty_issues_raises():
    """issues 为空时应抛出 ValueError。
    Empty issues should raise ValueError.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    planner = ProcedurePlanner(llm_client=client, case_type="civil_loan")

    empty_tree = IssueTree(
        case_id=_CASE_ID,
        issues=[],
        burdens=[],
        claim_issue_mapping=[],
        defense_issue_mapping=[],
    )

    with pytest.raises(ValueError, match="issues"):
        await planner.plan(
            setup_input=_SAMPLE_SETUP_INPUT,
            issue_tree=empty_tree,
            run_id=_RUN_ID,
        )


@pytest.mark.asyncio
async def test_unsupported_case_type_raises():
    """不支持的案由类型应抛出 ValueError。
    Unsupported case type should raise ValueError.
    """
    with pytest.raises(ValueError, match="不支持的案由类型"):
        ProcedurePlanner(llm_client=MockLLMClient(""), case_type="unknown_xyz")


# ---------------------------------------------------------------------------
# 鲁棒性测试 / Robustness tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_retry_succeeds_after_failures():
    """LLM 前两次失败后第三次成功应正常返回结果。
    Should succeed after two LLM failures if third attempt succeeds.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE, fail_times=2)
    planner = ProcedurePlanner(
        llm_client=client, case_type="civil_loan", max_retries=3
    )

    result = await planner.plan(
        setup_input=_SAMPLE_SETUP_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        run_id=_RUN_ID,
    )

    assert result.run.case_id == _CASE_ID
    assert client.call_count == 3


@pytest.mark.asyncio
async def test_llm_retry_exhausted_returns_failed_result():
    """LLM 所有重试均失败应返回 status='failed' 的结果，不抛出异常。
    Exhausted retries should return a failed ProcedureSetupResult, not raise.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE, fail_times=10)
    planner = ProcedurePlanner(
        llm_client=client, case_type="civil_loan", max_retries=3
    )

    result = await planner.plan(
        setup_input=_SAMPLE_SETUP_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        run_id=_RUN_ID,
    )

    assert isinstance(result, ProcedureSetupResult)
    assert result.run.status == "failed"
    assert result.run.run_id == _RUN_ID
    # 失败时仍应有完整的程序状态（使用默认值）
    # Even on failure, should have complete procedure states (using defaults)
    assert len(result.procedure_states) == len(PHASE_ORDER)


@pytest.mark.asyncio
async def test_parse_failure_returns_failed_result():
    """LLM 返回无法解析的响应时应返回 status='failed' 的结果。
    Unparseable LLM response should return a failed ProcedureSetupResult.
    """
    client = MockLLMClient("这不是合法的JSON，无法解析")
    planner = ProcedurePlanner(
        llm_client=client, case_type="civil_loan", max_retries=1
    )

    result = await planner.plan(
        setup_input=_SAMPLE_SETUP_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        run_id=_RUN_ID,
    )

    assert result.run.status == "failed"


@pytest.mark.asyncio
async def test_failed_result_preserves_ids():
    """失败结果应保留 run_id、case_id、workspace_id 等关键字段。
    Failed result should preserve run_id, case_id, workspace_id.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE, fail_times=10)
    planner = ProcedurePlanner(
        llm_client=client, case_type="civil_loan", max_retries=1
    )

    result = await planner.plan(
        setup_input=_SAMPLE_SETUP_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        run_id=_RUN_ID,
    )

    assert result.run.run_id == _RUN_ID
    assert result.run.case_id == _CASE_ID
    assert result.run.workspace_id == _WORKSPACE_ID
    assert result.run.trigger_type == "procedure_setup"


@pytest.mark.asyncio
async def test_missing_phase_in_llm_response_uses_default():
    """LLM 缺少某阶段时应使用默认配置补全。
    Missing phase in LLM response should be filled with default config.
    """
    # 只提供 5 个阶段，缺少 3 个 / Only provide 5 phases, missing 3
    partial_response = json.dumps({
        "procedure_config": {
            "evidence_submission_deadline_days": 15,
            "evidence_challenge_window_days": 10,
            "max_rounds_per_phase": 3,
            "applicable_laws": [],
        },
        "procedure_states": [
            {
                "phase": "case_intake",
                "allowed_role_codes": ["plaintiff_agent"],
                "readable_access_domains": ["shared_common"],
                "writable_object_types": ["Party"],
                "admissible_evidence_statuses": ["private"],
                "entry_conditions": ["开始"],
                "exit_conditions": ["完成"],
            },
        ],
        "timeline_events": [],
    }, ensure_ascii=False)

    client = MockLLMClient(partial_response)
    planner = ProcedurePlanner(llm_client=client, case_type="civil_loan")

    result = await planner.plan(
        setup_input=_SAMPLE_SETUP_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        run_id=_RUN_ID,
    )

    # 引擎必须补全所有 8 个阶段 / Engine must complete all 8 phases
    assert len(result.procedure_states) == len(PHASE_ORDER)
    covered = {s.phase for s in result.procedure_states}
    assert covered == set(PHASE_ORDER)


@pytest.mark.asyncio
async def test_llm_receives_case_id_in_prompt():
    """LLM 应收到包含 case_id 的 prompt。
    LLM should receive prompts containing case_id.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    planner = ProcedurePlanner(llm_client=client, case_type="civil_loan")

    await planner.plan(
        setup_input=_SAMPLE_SETUP_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        run_id=_RUN_ID,
    )

    assert client.call_count == 1
    assert client.last_system is not None
    assert client.last_user is not None
    assert _CASE_ID in client.last_user


@pytest.mark.asyncio
async def test_input_snapshot_has_issue_refs():
    """Run.input_snapshot 应包含争点的 material_refs。
    Run.input_snapshot should have material_refs for issues.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    planner = ProcedurePlanner(llm_client=client, case_type="civil_loan")

    result = await planner.plan(
        setup_input=_SAMPLE_SETUP_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        run_id=_RUN_ID,
    )

    snapshot = result.run.input_snapshot
    issue_ref_ids = {
        ref.object_id for ref in snapshot.material_refs
        if ref.object_type == "Issue"
    }
    for issue in _SAMPLE_ISSUE_TREE.issues:
        assert issue.issue_id in issue_ref_ids, (
            f"input_snapshot missing material_ref for issue {issue.issue_id}"
        )


# ---------------------------------------------------------------------------
# 校验器集成测试 / Validator integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validator_passes_on_valid_result():
    """有效 ProcedureSetupResult 应通过校验。
    A valid ProcedureSetupResult should pass validation.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    planner = ProcedurePlanner(llm_client=client, case_type="civil_loan")

    result = await planner.plan(
        setup_input=_SAMPLE_SETUP_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        run_id=_RUN_ID,
    )

    known_ids = {i.issue_id for i in _SAMPLE_ISSUE_TREE.issues}
    report = validate_procedure_setup_result(result, _SAMPLE_ISSUE_TREE, known_ids)
    assert report.is_valid, report.summary()


# ---------------------------------------------------------------------------
# 工具函数测试 / Utility function tests
# ---------------------------------------------------------------------------


def test_make_state_id_format():
    """_make_state_id 应生成正确格式的 state_id。
    _make_state_id should generate correctly formatted state_id.
    """
    sid = _make_state_id("case-001", "case_intake")
    assert sid == "pstate-case-001-case_intake-001"


def test_build_next_state_ids_non_terminal():
    """非终止阶段应返回下一阶段的 state_id。
    Non-terminal phase should return next phase's state_id.
    """
    next_ids = _build_next_state_ids("case-001", "case_intake")
    assert next_ids == ["pstate-case-001-element_mapping-001"]


def test_build_next_state_ids_terminal():
    """终止阶段 output_branching 应返回空列表。
    Terminal phase output_branching should return empty list.
    """
    next_ids = _build_next_state_ids("case-001", "output_branching")
    assert next_ids == []


def test_build_next_state_ids_unknown_phase():
    """未知阶段应返回空列表。
    Unknown phase should return empty list.
    """
    next_ids = _build_next_state_ids("case-001", "unknown_phase")
    assert next_ids == []


def test_sanitize_access_domains_removes_owner_private_from_judge_questions():
    """judge_questions 阶段应清除 owner_private。
    owner_private should be removed from judge_questions phase.
    """
    domains = ["owner_private", "shared_common", "admitted_record"]
    result = _sanitize_access_domains(domains, "judge_questions")
    assert "owner_private" not in result
    assert "shared_common" in result
    assert "admitted_record" in result


def test_sanitize_access_domains_preserves_other_phases():
    """非 judge_questions 阶段不应修改访问域。
    Non-judge_questions phases should not modify access domains.
    """
    domains = ["owner_private", "shared_common"]
    result = _sanitize_access_domains(domains, "evidence_submission")
    assert result == domains


def test_sanitize_evidence_statuses_output_branching():
    """output_branching 阶段应仅保留 admitted_for_discussion。
    output_branching phase should only keep admitted_for_discussion.
    """
    statuses = ["submitted", "challenged", "admitted_for_discussion"]
    result = _sanitize_evidence_statuses(statuses, "output_branching")
    assert result == ["admitted_for_discussion"]


def test_sanitize_evidence_statuses_other_phases():
    """非 output_branching 阶段不应修改证据状态。
    Non-output_branching phases should not modify evidence statuses.
    """
    statuses = ["private", "submitted"]
    result = _sanitize_evidence_statuses(statuses, "evidence_submission")
    assert result == statuses


# ---------------------------------------------------------------------------
# JSON 解析集成测试 / JSON parsing integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parse_json_from_markdown_code_block():
    """应能从 LLM 的 markdown 代码块响应中解析 JSON。
    Should parse JSON from LLM markdown code block response.
    """
    wrapped_response = f"分析结果如下：\n```json\n{_MOCK_LLM_RESPONSE}\n```\n解析完毕。"

    client = MockLLMClient(wrapped_response)
    planner = ProcedurePlanner(llm_client=client, case_type="civil_loan")

    result = await planner.plan(
        setup_input=_SAMPLE_SETUP_INPUT,
        issue_tree=_SAMPLE_ISSUE_TREE,
        run_id=_RUN_ID,
    )

    assert result.run.status == "completed"
    assert len(result.procedure_states) == len(PHASE_ORDER)
