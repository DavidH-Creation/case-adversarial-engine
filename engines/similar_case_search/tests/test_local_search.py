"""
Tests for LocalCaseSearcher.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engines.similar_case_search.local_search import LocalCaseSearcher
from engines.similar_case_search.schemas import CaseKeywords

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_INDEX = [
    {
        "case_number": "（2024）最高法民再1号",
        "court": "最高人民法院",
        "cause_of_action": "民间借贷纠纷",
        "keywords": ["民间借贷", "利率上限", "LPR四倍"],
        "summary": "借款利率超过LPR四倍部分不受保护",
        "url": "",
    },
    {
        "case_number": "（2024）京01民终2号",
        "court": "北京市第一中级人民法院",
        "cause_of_action": "买卖合同纠纷",
        "keywords": ["买卖合同", "质量瑕疵", "违约金"],
        "summary": "货物存在质量瑕疵时买方可主张减少价款",
        "url": "",
    },
    {
        "case_number": "（2024）沪02民终3号",
        "court": "上海市第二中级人民法院",
        "cause_of_action": "民间借贷纠纷",
        "keywords": ["民间借贷", "借条", "还款期限"],
        "summary": "借条约定还款期限届满后方可起诉",
        "url": "",
    },
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def index_file(tmp_path: Path) -> Path:
    """Write SAMPLE_INDEX to a temporary JSON file and return its path."""
    p = tmp_path / "court_cases_index.json"
    p.write_text(json.dumps(SAMPLE_INDEX, ensure_ascii=False), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_search_by_cause_of_action(index_file: Path) -> None:
    """案由"民间借贷纠纷"应匹配 2 条记录。"""
    searcher = LocalCaseSearcher(index_path=index_file)
    keywords = CaseKeywords(cause_of_action="民间借贷纠纷")
    results = searcher.search(keywords)

    case_numbers = {r.case_number for r in results}
    assert len(results) == 2
    assert "（2024）最高法民再1号" in case_numbers
    assert "（2024）沪02民终3号" in case_numbers


def test_search_by_keywords(index_file: Path) -> None:
    """search_terms=["借条", "还款"] 应命中 entry 3。"""
    searcher = LocalCaseSearcher(index_path=index_file)
    keywords = CaseKeywords(
        cause_of_action="其他纠纷",
        search_terms=["借条", "还款"],
    )
    results = searcher.search(keywords)

    assert len(results) >= 1
    assert results[0].case_number == "（2024）沪02民终3号"


def test_search_with_max_results(index_file: Path) -> None:
    """max_results=1 应只返回 1 条结果。"""
    searcher = LocalCaseSearcher(index_path=index_file)
    keywords = CaseKeywords(cause_of_action="民间借贷纠纷")
    results = searcher.search(keywords, max_results=1)

    assert len(results) == 1


def test_search_no_match(index_file: Path) -> None:
    """不匹配任何案例时应返回空列表。"""
    searcher = LocalCaseSearcher(index_path=index_file)
    keywords = CaseKeywords(
        cause_of_action="知识产权纠纷",
        search_terms=["专利侵权"],
    )
    results = searcher.search(keywords)

    assert results == []


def test_missing_index_file(tmp_path: Path) -> None:
    """索引文件不存在时应返回空列表，不抛异常。"""
    nonexistent = tmp_path / "no_such_file.json"
    searcher = LocalCaseSearcher(index_path=nonexistent)
    keywords = CaseKeywords(cause_of_action="民间借贷纠纷")
    results = searcher.search(keywords)

    assert results == []
