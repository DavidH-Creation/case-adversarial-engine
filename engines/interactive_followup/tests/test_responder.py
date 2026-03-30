"""
FollowupResponder 单元测试。
Unit tests for FollowupResponder.

测试覆盖 / Test coverage:
- 基本响应：返回 InteractionTurn / Basic response: returns InteractionTurn
- 合约执行：issue_ids 非空 / Contract enforcement: issue_ids non-empty
- 合约执行：evidence_ids 边界（仅报告内证据）/ Evidence boundary enforcement
- 合约执行：statement_class 有效 / Valid statement_class
- 多轮追问：previous_turns 传入 LLM / Multi-turn: previous_turns passed to LLM
- 重试机制：失败后重试 / Retry on LLM failure
- 重试耗尽：抛出 RuntimeError / Exhausted retries raise RuntimeError
- 空问题抛出 ValueError / Empty question raises ValueError
- 不支持案由类型抛出 ValueError / Unsupported case type raises ValueError
- 校验器集成 / Validator integration
- 错误恢复：respond_safe 返回错误 Turn / Error recovery: respond_safe returns error Turn
- 输入净化：长度限制、HTML 过滤、空输入 / Input sanitization
"""

from __future__ import annotations

import json
import pytest

from engines.interactive_followup.responder import FollowupResponder
from engines.interactive_followup.schemas import (
    InteractionTurn,
    StatementClass,
)
from engines.interactive_followup.validator import (
    validate_turn,
    validate_turn_strict,
    ValidationReport,
)
from engines.report_generation.schemas import (
    Burden,
    ClaimIssueMapping,
    EvidenceIndex,
    EvidenceItem,
    FactProposition,
    Issue,
    IssueTree,
    KeyConclusion,
    ReportArtifact,
    ReportSection,
)


# ---------------------------------------------------------------------------
# Mock LLM Client
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
_RUN_ID = "run-civil-loan-test-001"
_REPORT_ID = "report-civil-loan-test-001"

_SAMPLE_EVIDENCE_IDS = [
    "evidence-civil-loan-test-001-01",
    "evidence-civil-loan-test-001-02",
]

_MOCK_LLM_RESPONSE = json.dumps({
    "answer": "根据借条原件（evidence-civil-loan-test-001-01）和转账记录（evidence-civil-loan-test-001-02），"
              "借贷关系依据两份直接证据可认定成立。",
    "issue_ids": ["issue-civil-loan-test-001-001"],
    "evidence_ids": ["evidence-civil-loan-test-001-01", "evidence-civil-loan-test-001-02"],
    "statement_class": "fact",
    "citations": [
        {"evidence_id": "evidence-civil-loan-test-001-01", "quote": "借款金额50万元"},
        {"evidence_id": "evidence-civil-loan-test-001-02", "quote": "2024-01-15转账记录"},
    ],
}, ensure_ascii=False)

_SAMPLE_REPORT = ReportArtifact(
    report_id=_REPORT_ID,
    case_id=_CASE_ID,
    run_id=_RUN_ID,
    title="民间借贷纠纷诊断报告",
    summary="本案为民间借贷纠纷。借贷关系通过借条和转账记录证明成立。",
    sections=[
        ReportSection(
            section_id="sec-test-01",
            section_index=1,
            title="借贷关系成立",
            body="借条原件与银行转账记录相互印证，借贷关系成立证据充分。",
            linked_issue_ids=["issue-civil-loan-test-001-001"],
            linked_output_ids=["output-test-01"],
            linked_evidence_ids=_SAMPLE_EVIDENCE_IDS,
            key_conclusions=[
                KeyConclusion(
                    conclusion_id="concl-test-01-01",
                    text="借贷关系依据借条和转账记录可认定成立",
                    statement_class=StatementClass.fact,
                    supporting_evidence_ids=["evidence-civil-loan-test-001-01"],
                )
            ],
        )
    ],
    created_at="2026-03-24T10:00:00Z",
)

_SAMPLE_ISSUE_TREE = IssueTree(
    case_id=_CASE_ID,
    issues=[
        Issue(
            issue_id="issue-civil-loan-test-001-001",
            case_id=_CASE_ID,
            title="借贷关系成立",
            issue_type="factual",
            parent_issue_id=None,
            evidence_ids=_SAMPLE_EVIDENCE_IDS,
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
            burden_id="burden-test-001",
            case_id=_CASE_ID,
            issue_id="issue-civil-loan-test-001-001",
            burden_party_id="party-plaintiff-001",
            description="原告举证借贷关系成立",
        )
    ],
    claim_issue_mapping=[
        ClaimIssueMapping(claim_id="claim-test-001", issue_ids=["issue-civil-loan-test-001-001"])
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
            target_fact_ids=["fact-loan-delivery-001"],
        ),
    ],
)


# ---------------------------------------------------------------------------
# 测试用例 / Test cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_respond_returns_interaction_turn():
    """respond() 应返回 InteractionTurn 且字段齐全。
    respond() should return an InteractionTurn with all required fields.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    responder = FollowupResponder(llm_client=client, case_type="civil_loan")

    turn = await responder.respond(
        report=_SAMPLE_REPORT,
        question="借条上的签名是否经过鉴定？",
        run_id=_RUN_ID,
    )

    assert isinstance(turn, InteractionTurn)
    assert turn.case_id == _CASE_ID
    assert turn.report_id == _REPORT_ID
    assert turn.run_id == _RUN_ID
    assert turn.turn_id  # non-empty
    assert turn.question == "借条上的签名是否经过鉴定？"
    assert turn.answer


@pytest.mark.asyncio
async def test_issue_ids_non_empty():
    """合约：issue_ids 不能为空。
    Contract: issue_ids must be non-empty.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    responder = FollowupResponder(llm_client=client, case_type="civil_loan")

    turn = await responder.respond(
        report=_SAMPLE_REPORT,
        question="请解释借贷关系如何认定？",
        run_id=_RUN_ID,
    )

    assert turn.issue_ids, "issue_ids must not be empty — contract violation"


@pytest.mark.asyncio
async def test_statement_class_valid():
    """合约：statement_class 必须是合法枚举值。
    Contract: statement_class must be a valid enum value.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    responder = FollowupResponder(llm_client=client, case_type="civil_loan")

    turn = await responder.respond(
        report=_SAMPLE_REPORT,
        question="请解释举证责任分配。",
        run_id=_RUN_ID,
    )

    assert turn.statement_class in StatementClass.__members__.values(), (
        f"Invalid statement_class: {turn.statement_class}"
    )


@pytest.mark.asyncio
async def test_evidence_boundary_enforced():
    """合约：evidence_ids 必须是报告已引用证据的子集。
    Contract: evidence_ids must be subset of report's evidence.
    """
    # LLM 返回一个不在报告中的 evidence_id
    response_with_out_of_scope_evidence = json.dumps({
        "answer": "分析内容",
        "issue_ids": ["issue-civil-loan-test-001-001"],
        "evidence_ids": [
            "evidence-civil-loan-test-001-01",
            "evidence-OUTSIDE-REPORT-999",  # 不在报告中
        ],
        "statement_class": "inference",
        "citations": [],
    }, ensure_ascii=False)

    client = MockLLMClient(response_with_out_of_scope_evidence)
    responder = FollowupResponder(llm_client=client, case_type="civil_loan")

    turn = await responder.respond(
        report=_SAMPLE_REPORT,
        question="有没有其他证据？",
        run_id=_RUN_ID,
    )

    # evidence_ids 中不应包含报告外的证据
    report_evidence_ids = {
        eid
        for sec in _SAMPLE_REPORT.sections
        for eid in sec.linked_evidence_ids
    }
    for eid in turn.evidence_ids:
        assert eid in report_evidence_ids, (
            f"evidence_id {eid!r} is outside report scope — contract violation"
        )


@pytest.mark.asyncio
async def test_issue_ids_fallback_when_llm_returns_empty():
    """LLM 返回空 issue_ids 时，引擎应从报告中推断出默认争点。
    When LLM returns empty issue_ids, engine should infer default issues from report.
    """
    response_empty_issues = json.dumps({
        "answer": "分析内容",
        "issue_ids": [],  # LLM 返回空
        "evidence_ids": ["evidence-civil-loan-test-001-01"],
        "statement_class": "inference",
        "citations": [],
    }, ensure_ascii=False)

    client = MockLLMClient(response_empty_issues)
    responder = FollowupResponder(llm_client=client, case_type="civil_loan")

    turn = await responder.respond(
        report=_SAMPLE_REPORT,
        question="请问主要争点是什么？",
        run_id=_RUN_ID,
    )

    # 合约：issue_ids 不能为空
    assert turn.issue_ids, "issue_ids must be non-empty even if LLM returned empty"


@pytest.mark.asyncio
async def test_multi_turn_includes_previous_turns_in_prompt():
    """多轮追问时，previous_turns 应传入 LLM 的 user prompt。
    For multi-turn, previous_turns should be included in LLM user prompt.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    responder = FollowupResponder(llm_client=client, case_type="civil_loan")

    previous_turn = InteractionTurn(
        turn_id="turn-test-prev-01",
        case_id=_CASE_ID,
        report_id=_REPORT_ID,
        run_id=_RUN_ID,
        question="上一轮问题",
        answer="上一轮回答",
        issue_ids=["issue-civil-loan-test-001-001"],
        evidence_ids=["evidence-civil-loan-test-001-01"],
        statement_class=StatementClass.fact,
    )

    await responder.respond(
        report=_SAMPLE_REPORT,
        question="继续追问",
        previous_turns=[previous_turn],
        run_id=_RUN_ID,
    )

    assert client.last_user is not None
    # previous turn 的 question 应出现在 prompt 中
    assert "上一轮问题" in client.last_user or "上一轮回答" in client.last_user, (
        "Previous turn context must be included in LLM user prompt"
    )


@pytest.mark.asyncio
async def test_empty_question_raises_value_error():
    """空 question 应抛出 ValueError。
    Empty question should raise ValueError.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    responder = FollowupResponder(llm_client=client, case_type="civil_loan")

    with pytest.raises(ValueError, match="question"):
        await responder.respond(
            report=_SAMPLE_REPORT,
            question="",
            run_id=_RUN_ID,
        )


@pytest.mark.asyncio
async def test_unsupported_case_type_raises():
    """不支持的案由类型应在初始化时抛出 ValueError。
    Unsupported case type should raise ValueError on init.
    """
    with pytest.raises(ValueError, match="不支持的案由类型"):
        FollowupResponder(llm_client=MockLLMClient(""), case_type="unknown_type_xyz")


@pytest.mark.asyncio
async def test_llm_retry_succeeds_after_failures():
    """LLM 前两次失败后第三次成功应正常返回。
    Should succeed after two LLM failures if third attempt succeeds.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE, fail_times=2)
    responder = FollowupResponder(
        llm_client=client, case_type="civil_loan", max_retries=3
    )

    turn = await responder.respond(
        report=_SAMPLE_REPORT,
        question="重试测试问题",
        run_id=_RUN_ID,
    )

    assert isinstance(turn, InteractionTurn)
    assert client.call_count == 3


@pytest.mark.asyncio
async def test_llm_retry_exhausted_raises_runtime_error():
    """LLM 所有重试均失败应抛出 RuntimeError。
    Exhausted retries should raise RuntimeError.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE, fail_times=10)
    responder = FollowupResponder(
        llm_client=client, case_type="civil_loan", max_retries=3
    )

    with pytest.raises(RuntimeError, match="LLM 调用失败"):
        await responder.respond(
            report=_SAMPLE_REPORT,
            question="重试耗尽测试",
            run_id=_RUN_ID,
        )


@pytest.mark.asyncio
async def test_turn_id_is_unique_across_calls():
    """每次 respond() 应生成唯一的 turn_id。
    Each respond() call should generate a unique turn_id.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    responder = FollowupResponder(llm_client=client, case_type="civil_loan")

    turn1 = await responder.respond(
        report=_SAMPLE_REPORT,
        question="问题一",
        run_id=_RUN_ID,
    )
    turn2 = await responder.respond(
        report=_SAMPLE_REPORT,
        question="问题二",
        run_id=_RUN_ID,
    )

    assert turn1.turn_id != turn2.turn_id, "turn_id should be unique across calls"


@pytest.mark.asyncio
async def test_llm_receives_report_context_in_prompt():
    """LLM 应收到包含报告摘要的 user prompt。
    LLM user prompt should contain report summary context.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    responder = FollowupResponder(llm_client=client, case_type="civil_loan")

    await responder.respond(
        report=_SAMPLE_REPORT,
        question="报告里提到了什么？",
        run_id=_RUN_ID,
    )

    assert client.call_count == 1
    assert client.last_user is not None
    # report summary 或 case_id 应出现在 prompt 中
    assert _CASE_ID in client.last_user or _SAMPLE_REPORT.summary in client.last_user


@pytest.mark.asyncio
async def test_statement_class_unknown_defaults_to_inference():
    """LLM 返回未知 statement_class 时应默认为 inference。
    Unknown statement_class from LLM should default to inference.
    """
    response_unknown_class = json.dumps({
        "answer": "分析内容",
        "issue_ids": ["issue-civil-loan-test-001-001"],
        "evidence_ids": ["evidence-civil-loan-test-001-01"],
        "statement_class": "unknown_class_xyz",  # 未知值
        "citations": [],
    }, ensure_ascii=False)

    client = MockLLMClient(response_unknown_class)
    responder = FollowupResponder(llm_client=client, case_type="civil_loan")

    turn = await responder.respond(
        report=_SAMPLE_REPORT,
        question="测试未知陈述类型",
        run_id=_RUN_ID,
    )

    assert turn.statement_class == StatementClass.inference


# ---------------------------------------------------------------------------
# 校验器测试 / Validator tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validator_passes_on_valid_turn():
    """有效追问轮次应通过校验。
    A valid turn should pass validation.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    responder = FollowupResponder(llm_client=client, case_type="civil_loan")

    turn = await responder.respond(
        report=_SAMPLE_REPORT,
        question="请分析证据链完整性。",
        run_id=_RUN_ID,
    )

    known_issue_ids = {i.issue_id for i in _SAMPLE_ISSUE_TREE.issues}
    report_evidence_ids = {
        eid for sec in _SAMPLE_REPORT.sections for eid in sec.linked_evidence_ids
    }

    result = validate_turn(turn, known_issue_ids, report_evidence_ids)
    assert result.is_valid, result.summary()


def test_validator_catches_empty_issue_ids():
    """校验器应捕获空 issue_ids 违规。
    Validator should catch empty issue_ids violation.
    """
    bad_turn = InteractionTurn(
        turn_id="turn-bad-001",
        case_id=_CASE_ID,
        report_id=_REPORT_ID,
        run_id=_RUN_ID,
        question="问题",
        answer="回答",
        issue_ids=[],  # 违规：空
        evidence_ids=["evidence-civil-loan-test-001-01"],
        statement_class=StatementClass.fact,
    )

    result = validate_turn(bad_turn, known_issue_ids={"issue-1"})
    assert not result.is_valid
    assert any(e.code == "EMPTY_ISSUE_IDS" for e in result.errors)


def test_validator_catches_dangling_evidence_ref():
    """校验器应捕获悬空证据 ID 引用。
    Validator should catch dangling evidence ID references.
    """
    bad_turn = InteractionTurn(
        turn_id="turn-bad-002",
        case_id=_CASE_ID,
        report_id=_REPORT_ID,
        run_id=_RUN_ID,
        question="问题",
        answer="回答",
        issue_ids=["issue-civil-loan-test-001-001"],
        evidence_ids=["evidence-DOES-NOT-EXIST"],  # 悬空引用
        statement_class=StatementClass.inference,
    )

    report_evidence_ids = {
        eid for sec in _SAMPLE_REPORT.sections for eid in sec.linked_evidence_ids
    }
    result = validate_turn(bad_turn, report_evidence_ids=report_evidence_ids)
    assert not result.is_valid
    assert any(e.code == "EVIDENCE_BOUNDARY_VIOLATION" for e in result.errors)


def test_validator_catches_dangling_issue_ref():
    """校验器应捕获悬空争点 ID 引用。
    Validator should catch dangling issue ID references.
    """
    bad_turn = InteractionTurn(
        turn_id="turn-bad-003",
        case_id=_CASE_ID,
        report_id=_REPORT_ID,
        run_id=_RUN_ID,
        question="问题",
        answer="回答",
        issue_ids=["issue-DOES-NOT-EXIST"],  # 悬空引用
        evidence_ids=[],
        statement_class=StatementClass.assumption,
    )

    known_issue_ids = {"issue-civil-loan-test-001-001"}
    result = validate_turn(bad_turn, known_issue_ids=known_issue_ids)
    assert not result.is_valid
    assert any(e.code == "DANGLING_ISSUE_REF" for e in result.errors)


def test_validate_turn_strict_raises_on_invalid():
    """validate_turn_strict 应在有 error 时抛出 TurnValidationError。
    validate_turn_strict should raise TurnValidationError when errors exist.
    """
    from engines.interactive_followup.validator import TurnValidationError

    bad_turn = InteractionTurn(
        turn_id="turn-strict-test",
        case_id=_CASE_ID,
        report_id=_REPORT_ID,
        run_id=_RUN_ID,
        question="问题",
        answer="回答",
        issue_ids=[],  # 违规
        evidence_ids=[],
        statement_class=StatementClass.inference,
    )

    with pytest.raises(TurnValidationError):
        validate_turn_strict(bad_turn, known_issue_ids={"issue-1"})


# ---------------------------------------------------------------------------
# 错误恢复测试 / Error recovery tests (respond_safe)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_respond_safe_returns_turn_on_llm_failure():
    """respond_safe() 在 LLM 完全失败时应返回包含错误信息的 InteractionTurn（不抛异常）。
    respond_safe() should return an error InteractionTurn when LLM fails (no exception).
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE, fail_times=100)
    responder = FollowupResponder(
        llm_client=client, case_type="civil_loan", max_retries=2
    )

    turn = await responder.respond_safe(
        report=_SAMPLE_REPORT,
        question="错误恢复测试",
        run_id=_RUN_ID,
    )

    assert isinstance(turn, InteractionTurn)
    assert "[系统错误]" in turn.answer or "[System Error]" in turn.answer
    assert turn.case_id == _CASE_ID
    assert turn.issue_ids  # should have fallback issue_ids


@pytest.mark.asyncio
async def test_respond_safe_succeeds_normally():
    """respond_safe() 在 LLM 正常时应返回正常 InteractionTurn。
    respond_safe() should return normal InteractionTurn when LLM succeeds.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    responder = FollowupResponder(llm_client=client, case_type="civil_loan")

    turn = await responder.respond_safe(
        report=_SAMPLE_REPORT,
        question="正常追问测试",
        run_id=_RUN_ID,
    )

    assert isinstance(turn, InteractionTurn)
    assert "[系统错误]" not in turn.answer
    assert turn.answer  # non-empty real answer


@pytest.mark.asyncio
async def test_respond_safe_still_raises_on_invalid_input():
    """respond_safe() 对无效输入（空问题）仍应抛出 ValueError。
    respond_safe() should still raise ValueError for invalid input.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    responder = FollowupResponder(llm_client=client, case_type="civil_loan")

    with pytest.raises(ValueError, match="question"):
        await responder.respond_safe(
            report=_SAMPLE_REPORT,
            question="",
            run_id=_RUN_ID,
        )


# ---------------------------------------------------------------------------
# 输入净化测试 / Input sanitization tests (sanitize_question)
# ---------------------------------------------------------------------------


class TestSanitizeQuestion:
    """sanitize_question() 测试 / Tests for sanitize_question()."""

    def test_normal_input_passes_through(self):
        """正常输入应原样返回（去除首尾空白）。"""
        from engines.interactive_followup.validator import sanitize_question
        assert sanitize_question("  请问借贷关系如何认定？  ") == "请问借贷关系如何认定？"

    def test_empty_input_raises(self):
        """空输入应抛出 ValueError。"""
        from engines.interactive_followup.validator import sanitize_question
        with pytest.raises(ValueError, match="不能为空|cannot be empty"):
            sanitize_question("")

    def test_whitespace_only_raises(self):
        """仅空白字符应抛出 ValueError。"""
        from engines.interactive_followup.validator import sanitize_question
        with pytest.raises(ValueError, match="不能为空|cannot be empty"):
            sanitize_question("   \n\t  ")

    def test_html_tags_removed(self):
        """HTML 标签应被移除。"""
        from engines.interactive_followup.validator import sanitize_question
        result = sanitize_question("请问<script>alert('xss')</script>这个问题")
        assert "<script>" not in result
        assert "alert" not in result
        assert "请问" in result
        assert "这个问题" in result

    def test_html_only_input_raises(self):
        """仅含 HTML 标签的输入在标签移除后应抛出 ValueError。"""
        from engines.interactive_followup.validator import sanitize_question
        with pytest.raises(ValueError, match="HTML"):
            sanitize_question("<script>alert(1)</script>")

    def test_truncation_at_max_length(self):
        """超长输入应截断至 MAX_QUESTION_LENGTH。"""
        from engines.interactive_followup.validator import sanitize_question, MAX_QUESTION_LENGTH
        long_input = "测" * (MAX_QUESTION_LENGTH + 500)
        result = sanitize_question(long_input)
        assert len(result) == MAX_QUESTION_LENGTH

    def test_input_at_max_length_not_truncated(self):
        """恰好 MAX_QUESTION_LENGTH 长度的输入不应被截断。"""
        from engines.interactive_followup.validator import sanitize_question, MAX_QUESTION_LENGTH
        exact_input = "A" * MAX_QUESTION_LENGTH
        result = sanitize_question(exact_input)
        assert len(result) == MAX_QUESTION_LENGTH

    def test_style_tags_removed(self):
        """<style> 标签也应被移除。"""
        from engines.interactive_followup.validator import sanitize_question
        result = sanitize_question("正文<style>body{display:none}</style>继续")
        assert "<style>" not in result
        assert "正文" in result
