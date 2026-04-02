"""
类案搜索数据模型测试。
Tests for similar case search data models.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from engines.similar_case_search.schemas import (
    CaseIndexEntry,
    CaseKeywords,
    LLMKeywordsOutput,
    LLMRankedItem,
    RankedCase,
    RelevanceScore,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_case_index_entry(**overrides) -> CaseIndexEntry:
    defaults = {
        "case_number": "(2023)京01民终1234号",
        "court": "北京市第一中级人民法院",
        "cause_of_action": "买卖合同纠纷",
    }
    return CaseIndexEntry(**{**defaults, **overrides})


def _make_relevance_score(**overrides) -> RelevanceScore:
    defaults = {
        "fact_similarity": 0.8,
        "legal_relation_similarity": 0.7,
        "dispute_focus_similarity": 0.75,
        "judgment_reference_value": 0.9,
        "overall": 0.8,
    }
    return RelevanceScore(**{**defaults, **overrides})


# ---------------------------------------------------------------------------
# CaseKeywords
# ---------------------------------------------------------------------------


class TestCaseKeywords:
    def test_valid_minimal(self):
        kw = CaseKeywords(cause_of_action="买卖合同纠纷")
        assert kw.cause_of_action == "买卖合同纠纷"
        assert kw.legal_relations == []
        assert kw.dispute_focuses == []
        assert kw.relevant_statutes == []
        assert kw.search_terms == []

    def test_valid_full(self):
        kw = CaseKeywords(
            cause_of_action="劳动争议",
            legal_relations=["劳动关系"],
            dispute_focuses=["工资待遇"],
            relevant_statutes=["劳动法第50条"],
            search_terms=["劳动争议", "工资"],
        )
        assert kw.cause_of_action == "劳动争议"
        assert len(kw.legal_relations) == 1
        assert len(kw.dispute_focuses) == 1
        assert len(kw.relevant_statutes) == 1
        assert len(kw.search_terms) == 2

    def test_rejects_empty_cause_of_action(self):
        with pytest.raises(ValidationError) as exc_info:
            CaseKeywords(cause_of_action="")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("cause_of_action",) for e in errors)

    def test_rejects_missing_cause_of_action(self):
        with pytest.raises(ValidationError):
            CaseKeywords()  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# CaseIndexEntry
# ---------------------------------------------------------------------------


class TestCaseIndexEntry:
    def test_valid_minimal(self):
        entry = _make_case_index_entry()
        assert entry.case_number == "(2023)京01民终1234号"
        assert entry.court == "北京市第一中级人民法院"
        assert entry.cause_of_action == "买卖合同纠纷"
        assert entry.keywords == []
        assert entry.summary == ""
        assert entry.url == ""

    def test_valid_full(self):
        entry = CaseIndexEntry(
            case_number="(2022)沪02民初999号",
            court="上海市第二中级人民法院",
            cause_of_action="合同纠纷",
            keywords=["合同", "违约"],
            summary="原告主张被告违约",
            url="https://example.com/case/999",
        )
        assert entry.summary == "原告主张被告违约"
        assert entry.url == "https://example.com/case/999"
        assert len(entry.keywords) == 2

    def test_rejects_empty_case_number(self):
        with pytest.raises(ValidationError) as exc_info:
            _make_case_index_entry(case_number="")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("case_number",) for e in errors)

    def test_rejects_empty_court(self):
        with pytest.raises(ValidationError) as exc_info:
            _make_case_index_entry(court="")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("court",) for e in errors)

    def test_rejects_empty_cause_of_action(self):
        with pytest.raises(ValidationError) as exc_info:
            _make_case_index_entry(cause_of_action="")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("cause_of_action",) for e in errors)


# ---------------------------------------------------------------------------
# RelevanceScore
# ---------------------------------------------------------------------------


class TestRelevanceScore:
    def test_valid_boundary_values(self):
        score = RelevanceScore(
            fact_similarity=0.0,
            legal_relation_similarity=1.0,
            dispute_focus_similarity=0.5,
            judgment_reference_value=0.0,
            overall=1.0,
        )
        assert score.fact_similarity == 0.0
        assert score.overall == 1.0

    def test_rejects_overall_above_1(self):
        with pytest.raises(ValidationError) as exc_info:
            _make_relevance_score(overall=1.1)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("overall",) for e in errors)

    def test_rejects_overall_below_0(self):
        with pytest.raises(ValidationError) as exc_info:
            _make_relevance_score(overall=-0.1)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("overall",) for e in errors)

    def test_rejects_fact_similarity_above_1(self):
        with pytest.raises(ValidationError) as exc_info:
            _make_relevance_score(fact_similarity=1.01)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("fact_similarity",) for e in errors)

    def test_rejects_fact_similarity_below_0(self):
        with pytest.raises(ValidationError) as exc_info:
            _make_relevance_score(fact_similarity=-0.01)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("fact_similarity",) for e in errors)


# ---------------------------------------------------------------------------
# RankedCase
# ---------------------------------------------------------------------------


class TestRankedCase:
    def test_valid_creation_with_nested_models(self):
        entry = _make_case_index_entry()
        score = _make_relevance_score()
        ranked = RankedCase(case=entry, relevance=score)
        assert ranked.case.case_number == "(2023)京01民终1234号"
        assert ranked.relevance.overall == 0.8
        assert ranked.analysis == ""

    def test_valid_with_analysis(self):
        entry = _make_case_index_entry()
        score = _make_relevance_score()
        ranked = RankedCase(
            case=entry,
            relevance=score,
            analysis="该案与本案在事实认定方面高度相似。",
        )
        assert ranked.analysis == "该案与本案在事实认定方面高度相似。"

    def test_rejects_missing_case(self):
        score = _make_relevance_score()
        with pytest.raises(ValidationError):
            RankedCase(relevance=score)  # type: ignore[call-arg]

    def test_rejects_missing_relevance(self):
        entry = _make_case_index_entry()
        with pytest.raises(ValidationError):
            RankedCase(case=entry)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# LLM intermediate structures (smoke tests)
# ---------------------------------------------------------------------------


class TestLLMIntermediateModels:
    def test_llm_keywords_output(self):
        output = LLMKeywordsOutput(
            cause_of_action="侵权责任纠纷",
            legal_relations=["侵权关系"],
            search_terms=["侵权", "赔偿"],
        )
        assert output.cause_of_action == "侵权责任纠纷"
        assert output.dispute_focuses == []

    def test_llm_ranked_item(self):
        item = LLMRankedItem(
            case_number="(2021)粤01民终5678号",
            fact_similarity=0.85,
            legal_relation_similarity=0.9,
            dispute_focus_similarity=0.8,
            judgment_reference_value=0.95,
            overall=0.87,
            analysis="参考价值较高",
        )
        assert item.case_number == "(2021)粤01民终5678号"
        assert item.overall == 0.87
        assert item.analysis == "参考价值较高"

    def test_llm_ranked_item_default_analysis(self):
        item = LLMRankedItem(
            case_number="(2020)浙01民终0001号",
            fact_similarity=0.5,
            legal_relation_similarity=0.5,
            dispute_focus_similarity=0.5,
            judgment_reference_value=0.5,
            overall=0.5,
        )
        assert item.analysis == ""
