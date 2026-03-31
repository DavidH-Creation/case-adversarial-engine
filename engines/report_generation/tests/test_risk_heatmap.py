"""
risk_heatmap 单元测试。
Tests for engines.report_generation.risk_heatmap module.

验证:
- Happy path: 多个 issues → 正确数量的 HeatmapRow，颜色正确
- Edge case: 无 ranked_issues → None
- Edge case: 空 issues 列表 → None
- Edge case: 缺失字段 → 优雅降级（使用空字符串）
- 分类逻辑: 各种 impact × attack × evidence 组合 → 正确 RiskLevel
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from engines.report_generation.risk_heatmap import (
    HeatmapRow,
    RiskLevel,
    RISK_EMOJI,
    RISK_LABEL_ZH,
    _classify_risk,
    build_risk_heatmap,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_issue(
    issue_id: str = "issue-001",
    title: str = "借贷关系成立",
    outcome_impact: str = "high",
    opponent_attack_strength: str = "strong",
    proponent_evidence_strength: str = "medium",
    recommended_action: str = "supplement_evidence",
) -> SimpleNamespace:
    """Create a mock ranked issue using SimpleNamespace with enum-like .value attrs."""
    return SimpleNamespace(
        issue_id=issue_id,
        title=title,
        issue_type=SimpleNamespace(value="factual"),
        outcome_impact=SimpleNamespace(value=outcome_impact) if outcome_impact else None,
        opponent_attack_strength=SimpleNamespace(value=opponent_attack_strength)
        if opponent_attack_strength
        else None,
        proponent_evidence_strength=SimpleNamespace(value=proponent_evidence_strength)
        if proponent_evidence_strength
        else None,
        recommended_action=SimpleNamespace(value=recommended_action)
        if recommended_action
        else None,
    )


def _make_ranked(issues: list) -> SimpleNamespace:
    """Wrap issues list into a ranked_issues-like object."""
    return SimpleNamespace(issues=issues)


# ---------------------------------------------------------------------------
# Test: build_risk_heatmap
# ---------------------------------------------------------------------------


class TestBuildRiskHeatmap:
    def test_happy_path_three_issues(self) -> None:
        """3 个 issues → 3 行 HeatmapRow，每行字段正确。"""
        issues = [
            _make_issue("i-1", "争点A", "high", "strong", "weak", "abandon"),
            _make_issue("i-2", "争点B", "medium", "weak", "strong", "explain_in_trial"),
            _make_issue("i-3", "争点C", "low", "medium", "medium", "supplement_evidence"),
        ]
        rows = build_risk_heatmap(_make_ranked(issues))
        assert rows is not None
        assert len(rows) == 3
        assert rows[0].issue_id == "i-1"
        assert rows[0].risk_level == RiskLevel.unfavorable
        assert rows[1].risk_level == RiskLevel.favorable
        assert rows[2].risk_level == RiskLevel.neutral

    def test_returns_none_when_none(self) -> None:
        """None input → None."""
        assert build_risk_heatmap(None) is None

    def test_returns_none_when_empty_issues(self) -> None:
        """Empty issues list → None."""
        assert build_risk_heatmap(_make_ranked([])) is None

    def test_returns_none_when_no_issues_attr(self) -> None:
        """Object without .issues → None."""
        assert build_risk_heatmap(SimpleNamespace()) is None

    def test_missing_fields_graceful(self) -> None:
        """Issue with None fields → still produces row with empty strings."""
        issue = _make_issue("i-1", "Test", None, None, None, None)
        rows = build_risk_heatmap(_make_ranked([issue]))
        assert rows is not None
        assert len(rows) == 1
        assert rows[0].outcome_impact == ""
        assert rows[0].attack_strength == ""
        assert rows[0].evidence_strength == ""
        assert rows[0].recommended_action == ""

    def test_row_fields_populated(self) -> None:
        """Verify all HeatmapRow fields populated correctly."""
        issue = _make_issue("i-1", "借贷关系成立", "high", "weak", "strong", "explain_in_trial")
        rows = build_risk_heatmap(_make_ranked([issue]))
        row = rows[0]
        assert row.issue_id == "i-1"
        assert row.title == "借贷关系成立"
        assert row.outcome_impact == "high"
        assert row.attack_strength == "weak"
        assert row.evidence_strength == "strong"
        assert row.recommended_action == "explain_in_trial"
        assert row.risk_level == RiskLevel.favorable


# ---------------------------------------------------------------------------
# Test: _classify_risk
# ---------------------------------------------------------------------------


class TestClassifyRisk:
    @pytest.mark.parametrize(
        "impact,attack,evidence,expected",
        [
            # Unfavorable cases
            ("high", "strong", "medium", RiskLevel.unfavorable),
            ("high", "strong", "strong", RiskLevel.unfavorable),
            ("medium", "strong", "weak", RiskLevel.unfavorable),
            ("low", "strong", "weak", RiskLevel.unfavorable),
            ("high", "medium", "weak", RiskLevel.unfavorable),
            # Favorable cases
            ("low", "weak", "medium", RiskLevel.favorable),
            ("low", "weak", "weak", RiskLevel.favorable),
            ("medium", "weak", "strong", RiskLevel.favorable),
            ("high", "weak", "strong", RiskLevel.favorable),
            ("medium", "weak", "medium", RiskLevel.favorable),
            # Neutral cases
            ("medium", "medium", "medium", RiskLevel.neutral),
            ("high", "medium", "strong", RiskLevel.neutral),
            ("low", "medium", "weak", RiskLevel.neutral),
        ],
    )
    def test_classification_matrix(self, impact, attack, evidence, expected) -> None:
        assert _classify_risk(impact, attack, evidence) == expected

    def test_empty_strings_neutral(self) -> None:
        """Missing values (empty strings) → neutral."""
        assert _classify_risk("", "", "") == RiskLevel.neutral


# ---------------------------------------------------------------------------
# Test: constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_emoji_mapping_complete(self) -> None:
        for level in RiskLevel:
            assert level in RISK_EMOJI

    def test_label_mapping_complete(self) -> None:
        for level in RiskLevel:
            assert level in RISK_LABEL_ZH
