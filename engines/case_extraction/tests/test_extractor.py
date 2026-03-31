"""
CaseExtractor 单元测试。
CaseExtractor unit tests.

覆盖场景 / Covered scenarios:
- 完整文本提取：原被告 + 争议金额 → YAML 含 parties + disputed_amount
- 3 份证据描述 → evidence_list 有 3 条，每条有 description + document_type
- 缺少被告信息 → defendant 字段值为 "unknown"，YAML 含 # TODO: verify
- 金额出现两次且不一致 → disputed_amount 标记 ambiguous
- 空输入 → 明确 ValueError，不生成空 YAML
- LLM 重试逻辑
"""

from __future__ import annotations

import json

import pytest
import yaml

from engines.case_extraction.extractor import CaseExtractor, _inject_todo_comments
from engines.case_extraction.schemas import CaseExtractionResult


# ---------------------------------------------------------------------------
# Mock LLM client
# ---------------------------------------------------------------------------


class MockLLMClient:
    """返回预定义 JSON 响应的 mock LLM 客户端。
    Mock LLM client returning predefined JSON responses."""

    def __init__(self, response: str, fail_times: int = 0) -> None:
        self._response = response
        self._fail_times = fail_times
        self.call_count = 0

    async def create_message(self, system: str, user: str, **kwargs) -> str:
        self.call_count += 1
        if self._fail_times > 0 and self.call_count <= self._fail_times:
            raise RuntimeError(f"Simulated LLM failure on attempt {self.call_count}")
        return self._response


# ---------------------------------------------------------------------------
# 工厂函数 — 构造合法的 LLM 响应
# Factory helpers — build valid LLM responses
# ---------------------------------------------------------------------------


def _make_full_response(
    plaintiff: str = "老王",
    defendants: list[str] | None = None,
    case_type: str = "civil_loan",
    amounts: list[str] | None = None,
    num_evidence: int = 0,
    num_claims: int = 1,
) -> str:
    defendants = defendants or ["小陈"]
    amounts = amounts or ["200000"]

    claims = [
        {
            "claim_category": f"诉讼请求{i}",
            "title": f"请求{i}",
            "claim_text": f"被告偿还款项第{i}项",
        }
        for i in range(1, num_claims + 1)
    ]

    evidence = [
        {
            "description": f"证据{i}描述",
            "document_type": "documentary",
            "submitter": "plaintiff",
        }
        for i in range(1, num_evidence + 1)
    ]

    payload = {
        "case_type": case_type,
        "plaintiff_name": plaintiff,
        "defendant_names": defendants,
        "claims": claims,
        "evidence_list": evidence,
        "disputed_amounts": amounts,
        "case_summary": "原告向被告主张返还借款",
    }
    return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 测试：完整提取（happy path 1）
# Test: full extraction (happy path 1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_full_parties_and_amount():
    """完整文本 → parties（原被告各 1）+ disputed_amount 正确提取。
    Full text → parties (1 plaintiff, 1 defendant) + disputed_amount extracted."""
    mock = MockLLMClient(_make_full_response(amounts=["200000"]))
    extractor = CaseExtractor(mock)

    result = await extractor.extract("原告老王诉被告小陈借款20万元纠纷。")

    assert result.plaintiff.name == "老王"
    assert len(result.defendants) == 1
    assert result.defendants[0].name == "小陈"
    assert result.disputed_amount.amounts == ["200000"]
    assert not result.disputed_amount.is_ambiguous
    assert "parties.plaintiff.name" not in result.unknown_fields
    assert "parties.defendant.name" not in result.unknown_fields


# ---------------------------------------------------------------------------
# 测试：3 份证据（happy path 2）
# Test: 3 evidence items (happy path 2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_three_evidence_items():
    """包含 3 份证据描述的文本 → evidence_list 有 3 条，含 description + document_type。
    Text with 3 evidence descriptions → evidence_list has 3 entries with description + document_type."""
    mock = MockLLMClient(_make_full_response(num_evidence=3))
    extractor = CaseExtractor(mock)

    result = await extractor.extract("案件材料包含银行流水、微信记录、借条三份证据。")

    assert len(result.evidence_list) == 3
    for i, ev in enumerate(result.evidence_list, 1):
        assert ev.description == f"证据{i}描述"
        assert ev.document_type == "documentary"
        assert ev.source_id == f"src-extracted-{i:03d}"


# ---------------------------------------------------------------------------
# 测试：缺少被告信息（edge case）
# Test: missing defendant (edge case)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_missing_defendant_marked_unknown():
    """文本缺少被告信息 → defendant 值为 'unknown'，YAML 含 # TODO: verify 注释。
    Missing defendant → defendant name is 'unknown', YAML contains # TODO: verify."""
    mock = MockLLMClient(_make_full_response(defendants=["unknown"]))
    extractor = CaseExtractor(mock)

    result = await extractor.extract("原告老王提起诉讼，被告信息不详。")

    assert result.defendants[0].name == "unknown"
    assert "parties.defendant.name" in result.unknown_fields

    yaml_str = extractor.to_yaml(result)
    assert "# TODO: verify" in yaml_str
    # 确认 unknown 行有注释 / Confirm unknown lines have comment
    unknown_lines = [ln for ln in yaml_str.splitlines() if "unknown" in ln]
    assert any("# TODO: verify" in ln for ln in unknown_lines)


# ---------------------------------------------------------------------------
# 测试：金额出现两次且不一致（edge case — ambiguous）
# Test: two different amounts (edge case — ambiguous)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_ambiguous_amounts():
    """金额出现两次且不一致 → disputed_amount 含两个候选值，标记 ambiguous。
    Two different amounts → disputed_amount has two candidates, marked ambiguous."""
    mock = MockLLMClient(_make_full_response(amounts=["100000", "200000"]))
    extractor = CaseExtractor(mock)

    result = await extractor.extract("文中提到借款10万元，又说合计20万元。")

    assert result.disputed_amount.is_ambiguous
    assert len(result.disputed_amount.amounts) == 2
    assert "100000" in result.disputed_amount.amounts
    assert "200000" in result.disputed_amount.amounts
    assert "financials.disputed_amount" in result.unknown_fields

    yaml_str = extractor.to_yaml(result)
    assert "ambiguous" in yaml_str


# ---------------------------------------------------------------------------
# 测试：空输入（error path）
# Test: empty input (error path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_empty_input_raises():
    """空输入 → 明确 ValueError，不生成空 YAML。
    Empty input → ValueError raised, no empty YAML generated."""
    mock = MockLLMClient("{}")
    extractor = CaseExtractor(mock)

    with pytest.raises(ValueError, match="不能为空|cannot be empty"):
        await extractor.extract("")

    with pytest.raises(ValueError):
        await extractor.extract("   ")


# ---------------------------------------------------------------------------
# 测试：LLM 重试逻辑
# Test: LLM retry logic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_retries_on_llm_failure():
    """前 2 次 LLM 调用失败 → 第 3 次成功，最终返回正确结果。
    First 2 LLM calls fail → succeeds on 3rd, returns correct result."""
    mock = MockLLMClient(_make_full_response(), fail_times=2)
    extractor = CaseExtractor(mock, max_retries=3)

    result = await extractor.extract("原告老王诉被告小陈借款纠纷。")

    assert mock.call_count == 3
    assert result.plaintiff.name == "老王"


# ---------------------------------------------------------------------------
# 测试：to_yaml 输出结构
# Test: to_yaml output structure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_to_yaml_structure():
    """to_yaml 输出符合 cases/ schema 结构（含必要顶层字段）。
    to_yaml output conforms to cases/ schema structure (required top-level fields)."""
    mock = MockLLMClient(_make_full_response(num_claims=2, num_evidence=1))
    extractor = CaseExtractor(mock)

    result = await extractor.extract("案件文本。")
    yaml_str = extractor.to_yaml(result, case_slug="test-case")

    data = yaml.safe_load(yaml_str)
    assert "case_id" in data
    assert "case_type" in data
    assert "parties" in data
    assert "plaintiff" in data["parties"]
    assert "defendant" in data["parties"]
    assert "claims" in data
    assert len(data["claims"]) == 2
    assert "materials" in data
    assert "financials" in data
    assert "defenses" in data
    assert data["case_slug"] == "test-case"


# ---------------------------------------------------------------------------
# 测试：多被告
# Test: multiple defendants
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_multiple_defendants():
    """多被告文本 → defendants 列表包含所有被告。
    Multi-defendant text → defendants list contains all defendants."""
    mock = MockLLMClient(_make_full_response(defendants=["小陈", "老庄"]))
    extractor = CaseExtractor(mock)

    result = await extractor.extract("原告老王诉被告小陈、老庄借款纠纷。")

    assert len(result.defendants) == 2
    assert result.defendants[0].name == "小陈"
    assert result.defendants[1].name == "老庄"


# ---------------------------------------------------------------------------
# 测试：_inject_todo_comments 工具函数
# Test: _inject_todo_comments utility
# ---------------------------------------------------------------------------


def test_inject_todo_comments_on_unknown():
    """unknown 值的行应自动追加 # TODO: verify 注释。
    Lines with 'unknown' values get # TODO: verify appended."""
    yaml_input = "name: unknown\nother: value\n"
    result = _inject_todo_comments(yaml_input)
    lines = result.splitlines()
    assert any("# TODO: verify" in ln for ln in lines if "unknown" in ln)
    # 非 unknown 行不应有注释
    non_unknown = [ln for ln in lines if "unknown" not in ln and ln.strip()]
    assert all("# TODO" not in ln for ln in non_unknown)


def test_inject_todo_comments_on_ambiguous():
    """ambiguous 值的行应追加 ambiguous 注释。
    Lines with 'ambiguous' values get ambiguous comment appended."""
    yaml_input = "note: ambiguous\nother: value\n"
    result = _inject_todo_comments(yaml_input)
    assert "ambiguous: multiple values found" in result
