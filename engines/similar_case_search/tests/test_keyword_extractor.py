"""
KeywordExtractor 单元测试。

使用 mock LLM 客户端验证：
- 返回 CaseKeywords 且字段正确
- 用户提示词中包含案件上下文信息
"""

from __future__ import annotations

import json
import pytest

from engines.similar_case_search.keyword_extractor import KeywordExtractor
from engines.similar_case_search.schemas import CaseKeywords


# ---------------------------------------------------------------------------
# Mock LLM Client
# ---------------------------------------------------------------------------


class MockLLMClient:
    """返回预定义 JSON 响应的 mock LLM 客户端。"""

    def __init__(self, response: str) -> None:
        self._response = response
        self.call_count = 0
        self.last_system: str | None = None
        self.last_user: str | None = None

    async def create_message(self, *, system: str, user: str, **kwargs) -> str:
        self.call_count += 1
        self.last_system = system
        self.last_user = user
        return self._response


# ---------------------------------------------------------------------------
# 测试数据
# ---------------------------------------------------------------------------

MOCK_LLM_RESPONSE = json.dumps(
    {
        "cause_of_action": "民间借贷纠纷",
        "legal_relations": ["借贷关系", "债权债务关系"],
        "dispute_focuses": ["借款事实是否成立", "还款义务是否履行"],
        "relevant_statutes": ["《民法典》第667条", "《民法典》第674条"],
        "search_terms": ["民间借贷", "借款合同", "还款义务", "债权债务"],
    },
    ensure_ascii=False,
)

SAMPLE_CASE_DATA: dict = {
    "parties": {
        "plaintiff_001": {"name": "张三"},
        "defendant_001": {"name": "李四"},
    },
    "summary": [
        ["案由", "民间借贷纠纷"],
        ["借款金额", "人民币50,000元"],
    ],
    "claims": [
        {"text": "判令被告偿还借款本金50,000元"},
        {"text": "判令被告支付逾期利息"},
    ],
    "defenses": [
        {"text": "借款已全额偿还"},
    ],
    "case_type": "civil",
}


# ---------------------------------------------------------------------------
# 测试用例
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_returns_case_keywords():
    """extract() 应返回 CaseKeywords 且所有字段非空。"""
    client = MockLLMClient(MOCK_LLM_RESPONSE)
    extractor = KeywordExtractor(llm_client=client)

    result = await extractor.extract(SAMPLE_CASE_DATA)

    assert isinstance(result, CaseKeywords)
    assert result.cause_of_action == "民间借贷纠纷"
    assert len(result.legal_relations) >= 1
    assert len(result.dispute_focuses) >= 1
    assert len(result.relevant_statutes) >= 1
    assert len(result.search_terms) >= 1


@pytest.mark.asyncio
async def test_extract_includes_case_context_in_prompt():
    """用户提示词应包含当事人姓名及案件摘要信息。"""
    client = MockLLMClient(MOCK_LLM_RESPONSE)
    extractor = KeywordExtractor(llm_client=client)

    await extractor.extract(SAMPLE_CASE_DATA)

    assert client.call_count == 1
    assert client.last_user is not None
    # 原告姓名应出现在提示词中
    assert "张三" in client.last_user
    # 被告姓名应出现在提示词中
    assert "李四" in client.last_user
