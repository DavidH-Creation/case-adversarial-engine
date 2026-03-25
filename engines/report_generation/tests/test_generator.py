"""
ReportGenerator 单元测试。
Unit tests for ReportGenerator.

使用 mock LLM 客户端验证：
Tests using mock LLM client verify:
- 输出符合 ReportArtifact schema / Output conforms to ReportArtifact schema
- 所有顶层争点被覆盖 / All root issues are covered
- citation_completeness = 100%
- 初始状态正确 / Correct initial state
- 输入校验（case_id 不匹配）/ Input validation (case_id mismatch)
- JSON 解析（含 markdown 代码块）/ JSON parsing (incl. markdown code blocks)
- 重试机制 / Retry mechanism
"""

from __future__ import annotations

import json
import pytest

from engines.report_generation.generator import (
    ReportGenerator,
    _extract_json_object,
    _resolve_statement_class,
)
from engines.report_generation.schemas import (
    Burden,
    ClaimIssueMapping,
    DefenseIssueMapping,
    EvidenceIndex,
    EvidenceItem,
    FactProposition,
    Issue,
    IssueTree,
    ReportArtifact,
    StatementClass,
)
from engines.report_generation.validator import (
    validate_report,
    validate_report_strict,
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

_MOCK_LLM_RESPONSE = json.dumps({
    "title": "民间借贷纠纷诊断报告",
    "summary": "本案为民间借贷纠纷。借贷关系通过借条和转账记录证明成立。被告未能举证已还款。",
    "sections": [
        {
            "title": "借贷关系成立",
            "body": "借条原件与银行转账记录相互印证，借贷关系成立证据充分。",
            "linked_issue_ids": ["issue-civil-loan-test-001-001"],
            "linked_evidence_ids": [
                "evidence-civil-loan-test-001-01",
                "evidence-civil-loan-test-001-02",
            ],
            "key_conclusions": [
                {
                    "text": "借贷关系依据借条和转账记录可认定成立",
                    "statement_class": "fact",
                    "supporting_evidence_ids": ["evidence-civil-loan-test-001-01"],
                }
            ],
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
            parent_issue_id=None,  # 顶层争点 / Root issue
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


# ---------------------------------------------------------------------------
# 测试用例 / Test cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_returns_report_artifact():
    """generate 应返回 ReportArtifact 且字段齐全。
    generate() should return a ReportArtifact with all required fields.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    generator = ReportGenerator(llm_client=client, case_type="civil_loan")

    report = await generator.generate(
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    assert isinstance(report, ReportArtifact)
    assert report.case_id == _CASE_ID
    assert report.run_id == _RUN_ID
    assert report.title
    assert report.summary
    assert len(report.sections) >= 1


@pytest.mark.asyncio
async def test_all_root_issues_covered():
    """报告必须覆盖所有顶层争点。
    Report must cover all root-level issues.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    generator = ReportGenerator(llm_client=client, case_type="civil_loan")

    report = await generator.generate(
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    root_issue_ids = {
        issue.issue_id
        for issue in _SAMPLE_ISSUE_TREE.issues
        if issue.parent_issue_id is None
    }
    covered = {iid for sec in report.sections for iid in sec.linked_issue_ids}
    assert root_issue_ids.issubset(covered), (
        f"以下顶层争点未覆盖 / Uncovered root issues: {root_issue_ids - covered}"
    )


@pytest.mark.asyncio
async def test_citation_completeness_100_percent():
    """每条关键结论必须有至少一个支持证据引用。
    Every key conclusion must have at least one supporting evidence ID.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    generator = ReportGenerator(llm_client=client, case_type="civil_loan")

    report = await generator.generate(
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    for sec in report.sections:
        for concl in sec.key_conclusions:
            assert concl.supporting_evidence_ids, (
                f"结论 {concl.conclusion_id} 缺少 supporting_evidence_ids / "
                f"Conclusion {concl.conclusion_id} has no supporting_evidence_ids"
            )


@pytest.mark.asyncio
async def test_sections_have_linked_output_ids():
    """每个章节必须有 linked_output_ids（推演回连）。
    Each section must have linked_output_ids for agent output backlinks.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    generator = ReportGenerator(llm_client=client, case_type="civil_loan")

    report = await generator.generate(
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    for sec in report.sections:
        assert sec.linked_output_ids, (
            f"章节 {sec.section_id} 缺少 linked_output_ids / "
            f"Section {sec.section_id} has no linked_output_ids"
        )


@pytest.mark.asyncio
async def test_summary_length_under_500():
    """summary 不超过 500 字。Summary must be ≤ 500 characters."""
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    generator = ReportGenerator(llm_client=client, case_type="civil_loan")

    report = await generator.generate(
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    assert len(report.summary) <= 500, (
        f"summary 超过 500 字 ({len(report.summary)}) / Summary exceeds 500 chars"
    )


@pytest.mark.asyncio
async def test_long_summary_truncated():
    """超长 summary 应被截断到 500 字以内。
    Oversized summary should be truncated to ≤ 500 chars.
    """
    long_summary = "这是一段很长的摘要。" * 60  # >> 500 chars
    response_with_long_summary = json.dumps({
        "title": "测试报告",
        "summary": long_summary,
        "sections": [{
            "title": "借贷关系成立",
            "body": "分析内容",
            "linked_issue_ids": ["issue-civil-loan-test-001-001"],
            "linked_evidence_ids": ["evidence-civil-loan-test-001-01"],
            "key_conclusions": [{
                "text": "结论",
                "statement_class": "fact",
                "supporting_evidence_ids": ["evidence-civil-loan-test-001-01"],
            }],
        }],
    }, ensure_ascii=False)

    client = MockLLMClient(response_with_long_summary)
    generator = ReportGenerator(llm_client=client, case_type="civil_loan")

    report = await generator.generate(
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    assert len(report.summary) <= 500


@pytest.mark.asyncio
async def test_case_id_mismatch_raises():
    """issue_tree 与 evidence_index 的 case_id 不匹配时应抛出 ValueError。
    Mismatched case_ids between issue_tree and evidence_index should raise ValueError.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    generator = ReportGenerator(llm_client=client, case_type="civil_loan")

    mismatched_evidence = EvidenceIndex(
        case_id="case-different-999",
        evidence=_SAMPLE_EVIDENCE_INDEX.evidence,
    )

    with pytest.raises(ValueError, match="case_id"):
        await generator.generate(
            issue_tree=_SAMPLE_ISSUE_TREE,
            evidence_index=mismatched_evidence,
            run_id=_RUN_ID,
        )


@pytest.mark.asyncio
async def test_empty_issues_raises():
    """issues 为空时应抛出 ValueError。Empty issues should raise ValueError."""
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    generator = ReportGenerator(llm_client=client, case_type="civil_loan")

    empty_tree = IssueTree(
        case_id=_CASE_ID,
        issues=[],
        burdens=[],
        claim_issue_mapping=[],
        defense_issue_mapping=[],
    )

    with pytest.raises(ValueError, match="issues"):
        await generator.generate(
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
        ReportGenerator(llm_client=MockLLMClient(""), case_type="unknown_type_xyz")


@pytest.mark.asyncio
async def test_llm_retry_succeeds_after_failures():
    """LLM 前两次失败后第三次成功应正常返回结果。
    Should succeed after two LLM failures if third attempt succeeds.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE, fail_times=2)
    generator = ReportGenerator(
        llm_client=client, case_type="civil_loan", max_retries=3
    )

    report = await generator.generate(
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    assert report.case_id == _CASE_ID
    assert client.call_count == 3


@pytest.mark.asyncio
async def test_llm_retry_exhausted_raises_runtime_error():
    """LLM 所有重试均失败应抛出 RuntimeError。
    Exhausted retries should raise RuntimeError.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE, fail_times=10)
    generator = ReportGenerator(
        llm_client=client, case_type="civil_loan", max_retries=3
    )

    with pytest.raises(RuntimeError, match="LLM 调用失败"):
        await generator.generate(
            issue_tree=_SAMPLE_ISSUE_TREE,
            evidence_index=_SAMPLE_EVIDENCE_INDEX,
            run_id=_RUN_ID,
        )


@pytest.mark.asyncio
async def test_llm_receives_system_and_user_prompts():
    """LLM 客户端应收到包含案件 ID 的 system 和 user prompt。
    LLM client should receive system and user prompts containing case ID.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    generator = ReportGenerator(llm_client=client, case_type="civil_loan")

    await generator.generate(
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    assert client.call_count == 1
    assert client.last_system is not None
    assert "分析" in client.last_system
    assert client.last_user is not None
    assert _CASE_ID in client.last_user


@pytest.mark.asyncio
async def test_missing_root_issue_auto_supplemented():
    """LLM 漏掉顶层争点时，引擎应自动补充对应章节。
    When LLM misses a root issue, the engine should auto-supplement a section.
    """
    # LLM 返回的报告不包含 issue-civil-loan-test-001-001
    response_missing_issue = json.dumps({
        "title": "不完整报告",
        "summary": "部分分析。",
        "sections": [],  # 空章节列表
    }, ensure_ascii=False)

    client = MockLLMClient(response_missing_issue)
    generator = ReportGenerator(llm_client=client, case_type="civil_loan")

    report = await generator.generate(
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    # 应自动补充章节覆盖顶层争点
    all_linked_issue_ids = {
        iid for sec in report.sections for iid in sec.linked_issue_ids
    }
    assert "issue-civil-loan-test-001-001" in all_linked_issue_ids


# ---------------------------------------------------------------------------
# JSON 解析辅助函数测试 / JSON parsing utility tests
# ---------------------------------------------------------------------------


def test_extract_json_from_markdown_code_block():
    """应能从 markdown 代码块中提取 JSON。
    Should extract JSON from markdown code block.
    """
    text = '分析如下：\n```json\n{"title": "test"}\n```\n结束'
    result = _extract_json_object(text)
    assert result == {"title": "test"}


def test_extract_json_plain_object():
    """应能解析纯 JSON 对象文本。
    Should parse plain JSON object text.
    """
    text = '{"title": "test", "sections": []}'
    result = _extract_json_object(text)
    assert result["title"] == "test"


def test_extract_json_with_surrounding_text():
    """应能从含有前后文的文本中提取 JSON 对象。
    Should extract JSON object from text with surrounding content.
    """
    text = '以下是结果：\n{"title": "test"}\n提取完毕。'
    result = _extract_json_object(text)
    assert result == {"title": "test"}


def test_extract_json_invalid_raises():
    """无法解析时应抛出 ValueError。
    Should raise ValueError when JSON cannot be parsed.
    """
    with pytest.raises(ValueError, match="无法从 LLM 响应中解析"):
        _extract_json_object("这不是JSON内容")


# ---------------------------------------------------------------------------
# statement_class 解析测试 / statement_class resolution tests
# ---------------------------------------------------------------------------


def test_resolve_statement_class_english():
    """英文 statement_class 应正确映射。
    English statement_class values should map correctly.
    """
    assert _resolve_statement_class("fact") == StatementClass.fact
    assert _resolve_statement_class("inference") == StatementClass.inference
    assert _resolve_statement_class("assumption") == StatementClass.assumption


def test_resolve_statement_class_chinese():
    """中文 statement_class 应正确映射。
    Chinese statement_class values should map correctly.
    """
    assert _resolve_statement_class("事实") == StatementClass.fact
    assert _resolve_statement_class("推理") == StatementClass.inference
    assert _resolve_statement_class("假设") == StatementClass.assumption


def test_resolve_statement_class_unknown_defaults_to_inference():
    """未知 statement_class 应回退为 inference。
    Unknown statement_class should default to inference.
    """
    assert _resolve_statement_class("未知类型xyz") == StatementClass.inference


# ---------------------------------------------------------------------------
# 校验器测试 / Validator tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validator_passes_on_valid_report():
    """有效报告应通过校验。
    A valid report should pass validation.
    """
    client = MockLLMClient(_MOCK_LLM_RESPONSE)
    generator = ReportGenerator(llm_client=client, case_type="civil_loan")

    report = await generator.generate(
        issue_tree=_SAMPLE_ISSUE_TREE,
        evidence_index=_SAMPLE_EVIDENCE_INDEX,
        run_id=_RUN_ID,
    )

    known_ids = {e.evidence_id for e in _SAMPLE_EVIDENCE_INDEX.evidence}
    result = validate_report(report, _SAMPLE_ISSUE_TREE, known_ids)
    assert result.is_valid, result.summary()
    assert result.citation_completeness == 1.0
