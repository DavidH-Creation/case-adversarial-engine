"""
RelevanceRanker 单元测试。

使用 mock LLM 客户端验证：
- 返回 RankedCase 列表且按 overall 降序排列
- 空候选列表返回空结果且不调用 LLM
"""

from __future__ import annotations

import json
import pytest

from engines.similar_case_search.relevance_ranker import RelevanceRanker
from engines.similar_case_search.schemas import CaseIndexEntry, RankedCase


# ---------------------------------------------------------------------------
# Mock LLM Client
# ---------------------------------------------------------------------------


class MockLLMClient:
    def __init__(self, response: str) -> None:
        self._response = response
        self.call_count = 0

    async def create_message(self, *, system: str, user: str, **kwargs) -> str:
        self.call_count += 1
        return self._response


# ---------------------------------------------------------------------------
# 测试数据
# ---------------------------------------------------------------------------

MOCK_RANKER_RESPONSE = json.dumps(
    {
        "ranked_cases": [
            {
                "case_number": "（2024）最高法民再1号",
                "fact_similarity": 0.8,
                "legal_relation_similarity": 0.9,
                "dispute_focus_similarity": 0.7,
                "judgment_reference_value": 0.85,
                "overall": 0.81,
                "analysis": "本案与当前案件均涉及民间借贷利率争议，事实基础高度相似。",
            },
            {
                "case_number": "（2024）沪02民终3号",
                "fact_similarity": 0.6,
                "legal_relation_similarity": 0.7,
                "dispute_focus_similarity": 0.5,
                "judgment_reference_value": 0.6,
                "overall": 0.60,
                "analysis": "均涉及借条效力认定，但争议焦点有所不同。",
            },
        ]
    },
    ensure_ascii=False,
)

SAMPLE_CANDIDATES = [
    CaseIndexEntry(
        case_number="（2024）最高法民再1号",
        court="最高人民法院",
        cause_of_action="民间借贷纠纷",
        keywords=["民间借贷", "利率", "借款合同"],
        summary="借款人主张约定利率过高，法院认定利率上限适用。",
    ),
    CaseIndexEntry(
        case_number="（2024）沪02民终3号",
        court="上海市第二中级人民法院",
        cause_of_action="民间借贷纠纷",
        keywords=["借条", "效力", "债权债务"],
        summary="借条效力认定及还款义务争议案件。",
    ),
]

SAMPLE_CASE_DATA: dict = {
    "parties": {
        "plaintiff_001": {"name": "王五"},
        "defendant_001": {"name": "赵六"},
    },
    "summary": [
        ["案由", "民间借贷纠纷"],
        ["借款金额", "人民币100,000元"],
    ],
    "claims": [
        {"text": "判令被告偿还借款本金100,000元及利息"},
    ],
    "defenses": [
        {"text": "约定利率超过法定上限，应予调整"},
    ],
}


# ---------------------------------------------------------------------------
# 测试用例
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rank_returns_ranked_cases():
    """rank() 应返回 RankedCase 列表，按 overall 降序排列。"""
    client = MockLLMClient(MOCK_RANKER_RESPONSE)
    ranker = RelevanceRanker(llm_client=client)

    results = await ranker.rank(SAMPLE_CASE_DATA, SAMPLE_CANDIDATES)

    assert client.call_count == 1
    assert len(results) == 2
    assert all(isinstance(r, RankedCase) for r in results)

    # 结果应按 overall 降序排列
    assert results[0].relevance.overall >= results[1].relevance.overall
    assert results[0].relevance.overall == pytest.approx(0.81)
    assert results[1].relevance.overall == pytest.approx(0.60)

    # 验证第一名的详细字段
    top = results[0]
    assert top.case.case_number == "（2024）最高法民再1号"
    assert top.relevance.fact_similarity == pytest.approx(0.8)
    assert top.relevance.legal_relation_similarity == pytest.approx(0.9)
    assert top.relevance.dispute_focus_similarity == pytest.approx(0.7)
    assert top.relevance.judgment_reference_value == pytest.approx(0.85)
    assert "民间借贷" in top.analysis


@pytest.mark.asyncio
async def test_rank_empty_candidates():
    """空候选列表应立即返回空列表，不调用 LLM。"""
    client = MockLLMClient(MOCK_RANKER_RESPONSE)
    ranker = RelevanceRanker(llm_client=client)

    results = await ranker.rank(SAMPLE_CASE_DATA, [])

    assert results == []
    assert client.call_count == 0
