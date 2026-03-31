"""
issue_evidence_defense_matrix 单元测试。
Tests for engines.report_generation.issue_evidence_defense_matrix module.

验证:
- Happy path: 3 issues，各关联 2 evidence 和 1 defense → 矩阵 3 行，各字段正确
- Happy path: 行按 issue_impact 降序排列（high 在前）
- Edge case: issue 无关联 evidence → evidence_ids=[], evidence_count=0, has_unrebutted_evidence=False
- Edge case: 同一 evidence 关联多个 issue → 出现在多行
- Edge case: DefenseChain 为 None → 所有行 defense_ids=[], 矩阵正常生成
- Edge case: issue_tree 为 None → 返回 None
- Edge case: issue_tree.issues 为空 → 返回 None
- Integration: 完整 report 生成流程（mock LLM）→ 报告包含矩阵表格章节
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from engines.report_generation.issue_evidence_defense_matrix import (
    _safe_enum_value,
    build_issue_evidence_defense_matrix,
    render_matrix_markdown,
)
from engines.report_generation.schemas import (
    IssueEvidenceDefenseMatrix,
    MatrixRow,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_issue(
    issue_id: str,
    title: str = "争点",
    outcome_impact: str | None = "high",
    evidence_ids: list[str] | None = None,
) -> SimpleNamespace:
    """Mock Issue-like object."""
    return SimpleNamespace(
        issue_id=issue_id,
        title=title,
        outcome_impact=SimpleNamespace(value=outcome_impact) if outcome_impact else None,
        evidence_ids=evidence_ids or [],
    )


def _make_evidence(
    evidence_id: str,
    target_issue_ids: list[str],
) -> SimpleNamespace:
    """Mock Evidence-like object."""
    return SimpleNamespace(evidence_id=evidence_id, target_issue_ids=target_issue_ids)


def _make_issue_tree(issues: list) -> SimpleNamespace:
    return SimpleNamespace(issues=issues)


def _make_evidence_index(evidences: list) -> SimpleNamespace:
    return SimpleNamespace(evidence=evidences)


def _make_defense_point(point_id: str, issue_id: str) -> SimpleNamespace:
    return SimpleNamespace(point_id=point_id, issue_id=issue_id)


def _make_defense_chain(defense_points: list) -> SimpleNamespace:
    return SimpleNamespace(defense_points=defense_points)


# ---------------------------------------------------------------------------
# Test: build_issue_evidence_defense_matrix
# ---------------------------------------------------------------------------


class TestBuildMatrix:
    def test_happy_path_three_issues_with_evidence_and_defense(self) -> None:
        """3 issues, each with 2 evidence and 1 defense → 3 rows, correct counts."""
        issues = [
            _make_issue("i-1", "借贷关系", "high"),
            _make_issue("i-2", "还款事实", "medium"),
            _make_issue("i-3", "利息约定", "low"),
        ]
        evidences = [
            _make_evidence("e-1a", ["i-1"]),
            _make_evidence("e-1b", ["i-1"]),
            _make_evidence("e-2a", ["i-2"]),
            _make_evidence("e-2b", ["i-2"]),
            _make_evidence("e-3a", ["i-3"]),
            _make_evidence("e-3b", ["i-3"]),
        ]
        defense_points = [
            _make_defense_point("dp-1", "i-1"),
            _make_defense_point("dp-2", "i-2"),
            _make_defense_point("dp-3", "i-3"),
        ]

        matrix = build_issue_evidence_defense_matrix(
            _make_issue_tree(issues),
            _make_evidence_index(evidences),
            _make_defense_chain(defense_points),
        )

        assert matrix is not None
        assert len(matrix.rows) == 3
        assert matrix.total_issues == 3
        assert matrix.issues_with_evidence == 3

        row1 = next(r for r in matrix.rows if r.issue_id == "i-1")
        assert row1.evidence_count == 2
        assert sorted(row1.evidence_ids) == ["e-1a", "e-1b"]
        assert row1.defense_ids == ["dp-1"]
        assert row1.has_unrebutted_evidence is False

    def test_rows_sorted_by_impact_descending(self) -> None:
        """Rows must be sorted high → medium → low."""
        issues = [
            _make_issue("i-low", "低影响", "low"),
            _make_issue("i-high", "高影响", "high"),
            _make_issue("i-med", "中影响", "medium"),
        ]
        matrix = build_issue_evidence_defense_matrix(
            _make_issue_tree(issues),
            _make_evidence_index([]),
        )

        assert matrix is not None
        assert [r.issue_id for r in matrix.rows] == ["i-high", "i-med", "i-low"]

    def test_issue_without_evidence(self) -> None:
        """Issue with no associated evidence → evidence_ids=[], count=0, has_unrebutted=False."""
        issues = [_make_issue("i-1", "无证据争点", "high")]
        matrix = build_issue_evidence_defense_matrix(
            _make_issue_tree(issues),
            _make_evidence_index([]),
        )

        assert matrix is not None
        row = matrix.rows[0]
        assert row.evidence_ids == []
        assert row.evidence_count == 0
        assert row.has_unrebutted_evidence is False

    def test_evidence_targets_multiple_issues(self) -> None:
        """Evidence with multiple target_issue_ids appears in all target rows."""
        issues = [
            _make_issue("i-1", "争点A"),
            _make_issue("i-2", "争点B"),
        ]
        # One evidence targets both issues
        evidences = [_make_evidence("e-shared", ["i-1", "i-2"])]

        matrix = build_issue_evidence_defense_matrix(
            _make_issue_tree(issues),
            _make_evidence_index(evidences),
        )

        assert matrix is not None
        row1 = next(r for r in matrix.rows if r.issue_id == "i-1")
        row2 = next(r for r in matrix.rows if r.issue_id == "i-2")
        assert "e-shared" in row1.evidence_ids
        assert "e-shared" in row2.evidence_ids

    def test_no_defense_chain_all_rows_empty_defense(self) -> None:
        """defense_chain=None → all rows have empty defense_ids, matrix still built."""
        issues = [
            _make_issue("i-1", "争点", "high"),
        ]
        evidences = [_make_evidence("e-1", ["i-1"])]

        matrix = build_issue_evidence_defense_matrix(
            _make_issue_tree(issues),
            _make_evidence_index(evidences),
            None,
        )

        assert matrix is not None
        assert len(matrix.rows) == 1
        assert matrix.rows[0].defense_ids == []
        assert matrix.rows[0].has_unrebutted_evidence is True

    def test_has_unrebutted_evidence_true_when_evidence_no_defense(self) -> None:
        """Issue with evidence but no defense → has_unrebutted_evidence=True."""
        issues = [_make_issue("i-1", "争点")]
        evidences = [_make_evidence("e-1", ["i-1"])]
        defense_chain = _make_defense_chain([])  # empty chain

        matrix = build_issue_evidence_defense_matrix(
            _make_issue_tree(issues),
            _make_evidence_index(evidences),
            defense_chain,
        )

        assert matrix is not None
        assert matrix.rows[0].has_unrebutted_evidence is True

    def test_has_unrebutted_evidence_false_when_defense_exists(self) -> None:
        """Issue with both evidence and defense → has_unrebutted_evidence=False."""
        issues = [_make_issue("i-1", "争点")]
        evidences = [_make_evidence("e-1", ["i-1"])]
        defense_chain = _make_defense_chain([_make_defense_point("dp-1", "i-1")])

        matrix = build_issue_evidence_defense_matrix(
            _make_issue_tree(issues),
            _make_evidence_index(evidences),
            defense_chain,
        )

        assert matrix is not None
        assert matrix.rows[0].has_unrebutted_evidence is False

    def test_none_issue_tree_returns_none(self) -> None:
        """None issue_tree → None."""
        assert build_issue_evidence_defense_matrix(None, _make_evidence_index([])) is None

    def test_empty_issues_returns_none(self) -> None:
        """Empty issues list → None."""
        assert (
            build_issue_evidence_defense_matrix(_make_issue_tree([]), _make_evidence_index([]))
            is None
        )

    def test_issues_without_outcome_impact(self) -> None:
        """Issues without outcome_impact → impact='', sorted to end."""
        issues = [
            _make_issue("i-no-impact", "无影响度争点", None),
            _make_issue("i-high", "高影响", "high"),
        ]
        matrix = build_issue_evidence_defense_matrix(
            _make_issue_tree(issues),
            _make_evidence_index([]),
        )

        assert matrix is not None
        # high comes before unknown
        assert matrix.rows[0].issue_id == "i-high"
        assert matrix.rows[1].issue_id == "i-no-impact"
        assert matrix.rows[1].issue_impact == ""

    def test_issues_with_evidence_count(self) -> None:
        """issues_with_evidence counts only issues that have ≥1 evidence."""
        issues = [
            _make_issue("i-1"),
            _make_issue("i-2"),
            _make_issue("i-3"),
        ]
        evidences = [_make_evidence("e-1", ["i-1"])]

        matrix = build_issue_evidence_defense_matrix(
            _make_issue_tree(issues),
            _make_evidence_index(evidences),
        )

        assert matrix is not None
        assert matrix.issues_with_evidence == 1

    def test_fallback_to_issue_evidence_ids(self) -> None:
        """When EvidenceIndex has no match, fall back to Issue.evidence_ids."""
        issues = [_make_issue("i-1", "争点", "medium", ["e-fallback"])]
        matrix = build_issue_evidence_defense_matrix(
            _make_issue_tree(issues),
            _make_evidence_index([]),  # no evidences in index
        )

        assert matrix is not None
        assert "e-fallback" in matrix.rows[0].evidence_ids


# ---------------------------------------------------------------------------
# Test: render_matrix_markdown
# ---------------------------------------------------------------------------


class TestRenderMatrixMarkdown:
    def _make_matrix(self, rows: list[MatrixRow]) -> IssueEvidenceDefenseMatrix:
        return IssueEvidenceDefenseMatrix(
            rows=rows,
            total_issues=len(rows),
            issues_with_evidence=sum(1 for r in rows if r.evidence_count > 0),
        )

    def test_markdown_contains_header(self) -> None:
        """Rendered markdown includes the section header."""
        matrix = self._make_matrix([])
        md = render_matrix_markdown(matrix)
        assert "争点-证据-抗辩矩阵" in md
        assert "Issue-Evidence-Defense Matrix" in md

    def test_markdown_contains_table_header_row(self) -> None:
        """Markdown includes correct table column headers."""
        matrix = self._make_matrix([])
        md = render_matrix_markdown(matrix)
        assert "| 争点 |" in md
        assert "| 影响度 |" in md
        assert "| 关联证据数 |" in md
        assert "| 抗辩点数 |" in md
        assert "| 未反驳 |" in md

    def test_markdown_row_content(self) -> None:
        """Each matrix row appears as a markdown table row with correct values."""
        rows = [
            MatrixRow(
                issue_id="i-1",
                issue_label="借贷关系成立",
                issue_impact="high",
                evidence_ids=["e-1", "e-2"],
                defense_ids=["dp-1"],
                evidence_count=2,
                has_unrebutted_evidence=False,
            )
        ]
        md = render_matrix_markdown(self._make_matrix(rows))
        assert "借贷关系成立" in md
        assert "high" in md
        assert "| 2 |" in md
        assert "| 1 |" in md
        assert "否" in md

    def test_unrebutted_renders_as_yes(self) -> None:
        """has_unrebutted_evidence=True renders as '是'."""
        rows = [
            MatrixRow(
                issue_id="i-1",
                issue_label="争点",
                issue_impact="medium",
                evidence_ids=["e-1"],
                defense_ids=[],
                evidence_count=1,
                has_unrebutted_evidence=True,
            )
        ]
        md = render_matrix_markdown(self._make_matrix(rows))
        assert "是" in md

    def test_empty_impact_renders_as_dash(self) -> None:
        """Empty issue_impact renders as '-'."""
        rows = [
            MatrixRow(
                issue_id="i-1",
                issue_label="争点",
                issue_impact="",
                evidence_ids=[],
                defense_ids=[],
                evidence_count=0,
                has_unrebutted_evidence=False,
            )
        ]
        md = render_matrix_markdown(self._make_matrix(rows))
        assert "| - |" in md

    def test_row_count_matches_matrix_rows(self) -> None:
        """Number of data rows in markdown equals len(matrix.rows)."""
        rows = [
            MatrixRow(
                issue_id=f"i-{i}",
                issue_label=f"争点{i}",
                issue_impact="low",
                evidence_ids=[],
                defense_ids=[],
                evidence_count=0,
                has_unrebutted_evidence=False,
            )
            for i in range(5)
        ]
        md = render_matrix_markdown(self._make_matrix(rows))
        # Count data rows (lines starting with | but not the separator line)
        data_rows = [
            line
            for line in md.splitlines()
            if line.startswith("|") and "---" not in line and "争点 |" not in line
        ]
        assert len(data_rows) == 5


# ---------------------------------------------------------------------------
# Test: integration with ReportGenerator (mock LLM)
# ---------------------------------------------------------------------------


class TestMatrixIntegrationWithGenerator:
    @pytest.fixture
    def mock_llm_response(self) -> str:
        return json.dumps(
            {
                "title": "测试报告",
                "summary": "测试摘要",
                "sections": [
                    {
                        "title": "借贷关系",
                        "body": "借贷关系成立。",
                        "linked_issue_ids": ["i-1"],
                        "linked_evidence_ids": ["e-1"],
                        "key_conclusions": [
                            {
                                "text": "借贷关系成立",
                                "statement_class": "fact",
                                "supporting_evidence_ids": ["e-1"],
                            }
                        ],
                    }
                ],
            }
        )

    async def test_report_includes_matrix_section(self, mock_llm_response: str) -> None:
        """Full generate() call with defense_chain → report has matrix section."""
        from engines.report_generation.generator import ReportGenerator
        from engines.report_generation.schemas import (
            EvidenceIndex,
            IssueTree,
        )
        from engines.shared.models import (
            Evidence,
            EvidenceStatus,
            EvidenceType,
            Issue,
            IssueStatus,
            IssueType,
        )

        class MockLLMClient:
            async def create_message(self, system, user, **kwargs):
                return mock_llm_response

        issue_tree = IssueTree(
            case_id="case-test",
            issues=[
                Issue(
                    issue_id="i-1",
                    case_id="case-test",
                    title="借贷关系成立",
                    issue_type=IssueType.factual,
                    evidence_ids=["e-1"],
                    status=IssueStatus.open,
                ),
                Issue(
                    issue_id="i-2",
                    case_id="case-test",
                    title="还款争议",
                    issue_type=IssueType.legal,
                    evidence_ids=[],
                    status=IssueStatus.open,
                ),
            ],
        )
        evidence_index = EvidenceIndex(
            case_id="case-test",
            evidence=[
                Evidence(
                    evidence_id="e-1",
                    case_id="case-test",
                    owner_party_id="p-1",
                    title="借条",
                    source="原告提交",
                    summary="借条一张",
                    evidence_type=EvidenceType.documentary,
                    target_fact_ids=["f-1"],
                    target_issue_ids=["i-1"],
                ),
            ],
        )

        defense_chain = _make_defense_chain([_make_defense_point("dp-1", "i-1")])

        gen = ReportGenerator(MockLLMClient(), case_type="civil_loan")
        report = await gen.generate(
            issue_tree, evidence_index, "run-test", defense_chain=defense_chain
        )

        # Matrix section should be present
        section_titles = [s.title for s in report.sections]
        assert any("矩阵" in t or "Matrix" in t for t in section_titles)

        # Matrix section body should contain the markdown table
        matrix_section = next(
            s for s in report.sections if "矩阵" in s.title or "Matrix" in s.title
        )
        assert "| 争点 |" in matrix_section.body
        # Should have a row per issue
        data_rows = [
            line
            for line in matrix_section.body.splitlines()
            if line.startswith("|") and "---" not in line and "争点 |" not in line
        ]
        assert len(data_rows) == len(issue_tree.issues)

    async def test_report_without_defense_chain_still_has_matrix(
        self, mock_llm_response: str
    ) -> None:
        """generate() without defense_chain also produces matrix section."""
        from engines.report_generation.generator import ReportGenerator
        from engines.report_generation.schemas import EvidenceIndex, IssueTree
        from engines.shared.models import Issue, IssueStatus, IssueType

        class MockLLMClient:
            async def create_message(self, system, user, **kwargs):
                return mock_llm_response

        issue_tree = IssueTree(
            case_id="case-test",
            issues=[
                Issue(
                    issue_id="i-1",
                    case_id="case-test",
                    title="争点A",
                    issue_type=IssueType.factual,
                    status=IssueStatus.open,
                )
            ],
        )
        evidence_index = EvidenceIndex(case_id="case-test", evidence=[])

        gen = ReportGenerator(MockLLMClient(), case_type="civil_loan")
        report = await gen.generate(issue_tree, evidence_index, "run-test")

        section_titles = [s.title for s in report.sections]
        assert any("矩阵" in t or "Matrix" in t for t in section_titles)


# ---------------------------------------------------------------------------
# Test: _safe_enum_value
# ---------------------------------------------------------------------------


class TestSafeEnumValue:
    def test_none_returns_empty_string(self) -> None:
        assert _safe_enum_value(None) == ""

    def test_enum_like_returns_value(self) -> None:
        obj = SimpleNamespace(value="high")
        assert _safe_enum_value(obj) == "high"

    def test_plain_string_returns_itself(self) -> None:
        assert _safe_enum_value("medium") == "medium"
