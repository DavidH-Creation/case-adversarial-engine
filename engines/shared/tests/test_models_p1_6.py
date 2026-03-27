"""
P1.6 数据模型单元测试 — 新增枚举和 Issue 扩展字段。
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from engines.shared.models import (
    Issue,
    IssueCategory,
    IssueType,
)


class TestIssueCategory:
    """IssueCategory 枚举测试。"""

    def test_all_values_exist(self):
        assert IssueCategory.fact_issue.value == "fact_issue"
        assert IssueCategory.legal_issue.value == "legal_issue"
        assert IssueCategory.calculation_issue.value == "calculation_issue"
        assert IssueCategory.procedure_credibility_issue.value == "procedure_credibility_issue"

    def test_exactly_four_values(self):
        assert len(IssueCategory) == 4


class TestIssueIssueCategoryField:
    """Issue.issue_category 扩展字段测试。"""

    def _make_base_issue(self, **kwargs) -> Issue:
        return Issue(
            issue_id="i-001",
            case_id="case-001",
            title="测试争点",
            issue_type=IssueType.factual,
            **kwargs,
        )

    def test_issue_category_defaults_to_none(self):
        issue = self._make_base_issue()
        assert issue.issue_category is None

    def test_issue_category_can_be_set_to_fact_issue(self):
        issue = self._make_base_issue(issue_category=IssueCategory.fact_issue)
        assert issue.issue_category == IssueCategory.fact_issue

    def test_issue_category_can_be_set_to_calculation_issue(self):
        issue = self._make_base_issue(issue_category=IssueCategory.calculation_issue)
        assert issue.issue_category == IssueCategory.calculation_issue

    def test_issue_category_and_issue_type_coexist(self):
        """issue_category 与 issue_type 并列存在，互不影响。"""
        issue = self._make_base_issue(issue_category=IssueCategory.legal_issue)
        assert issue.issue_type == IssueType.factual
        assert issue.issue_category == IssueCategory.legal_issue

    def test_invalid_issue_category_raises(self):
        with pytest.raises(ValidationError):
            self._make_base_issue(issue_category="invalid_category")
