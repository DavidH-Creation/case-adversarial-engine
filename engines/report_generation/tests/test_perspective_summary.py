"""
perspective_summary 单元测试。
Tests for engines.report_generation.perspective_summary module.

验证:
- 原告视角卡片：top_strengths 来自 plaintiff_strongest_arguments[:3]
- 原告视角卡片：top_dangers 来自 defendant-favored 路径（证据数降序）
- 被告视角卡片：top_strengths 来自 defendant_strongest_defenses[:3]
- 被告视角卡片：top_dangers 来自 plaintiff-favored 路径
- 法官视角卡片：strengths = 双方各1条最强论点
- 法官视角卡片：dangers = high+open 争点
- priority_actions 过滤 role
- render_layer1_block_b：包含正确标题和各节内容
- render_layer3：各视角有对应章节标题
- 空 adversarial_result 不崩溃
- None decision_path_tree 不崩溃
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from engines.report_generation.perspective_summary import (
    _filter_actions,
    build_perspective_card,
    render_layer1_block_b,
    render_layer3,
)
from engines.report_generation.schemas import Perspective, PerspectiveCard


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_argument(position: str, issue_id: str = "i-1") -> SimpleNamespace:
    return SimpleNamespace(
        issue_id=issue_id, position=position, evidence_ids=["e-1"], reasoning="x"
    )


def _make_summary(
    plaintiff_strongest: list | None = None,
    defendant_strongest: list | None = None,
    unresolved_issues: list | None = None,
    missing_evidence: list | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        plaintiff_strongest_arguments=plaintiff_strongest or [],
        defendant_strongest_defenses=defendant_strongest or [],
        unresolved_issues=unresolved_issues or [],
        missing_evidence_report=missing_evidence or [],
    )


def _make_adversarial_result(summary: SimpleNamespace | None) -> SimpleNamespace:
    return SimpleNamespace(summary=summary)


def _make_path(
    path_id: str,
    party_favored: str = "neutral",
    key_evidence_ids: list[str] | None = None,
    possible_outcome: str = "结果",
    trigger_condition: str = "条件",
) -> SimpleNamespace:
    return SimpleNamespace(
        path_id=path_id,
        party_favored=party_favored,
        key_evidence_ids=key_evidence_ids or [],
        possible_outcome=possible_outcome,
        trigger_condition=trigger_condition,
    )


def _make_decision_path_tree(paths: list) -> SimpleNamespace:
    return SimpleNamespace(paths=paths)


def _make_issue(
    issue_id: str,
    title: str,
    outcome_impact: str | None = None,
    status: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        issue_id=issue_id,
        title=title,
        outcome_impact=SimpleNamespace(value=outcome_impact) if outcome_impact else None,
        status=SimpleNamespace(value=status) if status else None,
    )


def _make_issue_tree(issues: list) -> SimpleNamespace:
    return SimpleNamespace(issues=issues)


def _make_action(role: str, action: str) -> SimpleNamespace:
    return SimpleNamespace(role=role, action=action)


# ---------------------------------------------------------------------------
# Test: build_perspective_card — PLAINTIFF
# ---------------------------------------------------------------------------


class TestBuildPlaintiffCard:
    def test_top_strengths_from_plaintiff_strongest_arguments(self) -> None:
        summary = _make_summary(
            plaintiff_strongest=[
                _make_argument("原告论点1"),
                _make_argument("原告论点2"),
                _make_argument("原告论点3"),
                _make_argument("原告论点4"),  # beyond max 3
            ]
        )
        result = _make_adversarial_result(summary)
        card = build_perspective_card(Perspective.PLAINTIFF, result)

        assert card.perspective == Perspective.PLAINTIFF
        assert len(card.top_strengths) == 3
        assert "原告论点1" in card.top_strengths
        assert "原告论点3" in card.top_strengths
        assert "原告论点4" not in card.top_strengths

    def test_top_dangers_from_defendant_favored_paths(self) -> None:
        paths = [
            _make_path("path-A", party_favored="defendant", key_evidence_ids=["e-1"]),
            _make_path("path-B", party_favored="defendant", key_evidence_ids=["e-1", "e-2", "e-3"]),
            _make_path("path-C", party_favored="plaintiff"),  # not a danger
        ]
        result = _make_adversarial_result(None)
        card = build_perspective_card(
            Perspective.PLAINTIFF,
            result,
            decision_path_tree=_make_decision_path_tree(paths),
        )

        # max 2 dangers; path-B has most evidence → first
        assert len(card.top_dangers) <= 2
        assert any("path-B" in d for d in card.top_dangers)
        assert not any("path-C" in d for d in card.top_dangers)

    def test_relevant_paths_are_plaintiff_favored(self) -> None:
        paths = [
            _make_path("path-A", party_favored="plaintiff"),
            _make_path("path-B", party_favored="defendant"),
            _make_path("path-C", party_favored="plaintiff"),
        ]
        result = _make_adversarial_result(None)
        card = build_perspective_card(
            Perspective.PLAINTIFF,
            result,
            decision_path_tree=_make_decision_path_tree(paths),
        )

        assert set(card.relevant_paths) == {"path-A", "path-C"}

    def test_priority_actions_filtered_by_role(self) -> None:
        actions = [
            _make_action("plaintiff", "原告行动1"),
            _make_action("defendant", "被告行动"),
            _make_action("plaintiff", "原告行动2"),
        ]
        result = _make_adversarial_result(None)
        card = build_perspective_card(
            Perspective.PLAINTIFF,
            result,
            action_recommendations=actions,
        )

        assert "原告行动1" in card.priority_actions
        assert "原告行动2" in card.priority_actions
        assert "被告行动" not in card.priority_actions

    def test_no_adversarial_result_returns_empty_card(self) -> None:
        card = build_perspective_card(Perspective.PLAINTIFF, None)

        assert card.perspective == Perspective.PLAINTIFF
        assert card.top_strengths == []
        assert card.top_dangers == []

    def test_no_decision_path_tree_gives_no_relevant_paths(self) -> None:
        result = _make_adversarial_result(None)
        card = build_perspective_card(Perspective.PLAINTIFF, result, decision_path_tree=None)

        assert card.relevant_paths == []


# ---------------------------------------------------------------------------
# Test: build_perspective_card — DEFENDANT
# ---------------------------------------------------------------------------


class TestBuildDefendantCard:
    def test_top_strengths_from_defendant_strongest_defenses(self) -> None:
        summary = _make_summary(
            defendant_strongest=[
                _make_argument("被告抗辩1"),
                _make_argument("被告抗辩2"),
            ]
        )
        result = _make_adversarial_result(summary)
        card = build_perspective_card(Perspective.DEFENDANT, result)

        assert card.perspective == Perspective.DEFENDANT
        assert "被告抗辩1" in card.top_strengths
        assert "被告抗辩2" in card.top_strengths

    def test_top_dangers_from_plaintiff_favored_paths(self) -> None:
        paths = [
            _make_path("path-A", party_favored="plaintiff", key_evidence_ids=["e-1", "e-2"]),
            _make_path("path-B", party_favored="defendant"),  # not a danger
        ]
        result = _make_adversarial_result(None)
        card = build_perspective_card(
            Perspective.DEFENDANT,
            result,
            decision_path_tree=_make_decision_path_tree(paths),
        )

        assert any("path-A" in d for d in card.top_dangers)
        assert not any("path-B" in d for d in card.top_dangers)

    def test_relevant_paths_are_defendant_favored(self) -> None:
        paths = [
            _make_path("path-A", party_favored="plaintiff"),
            _make_path("path-B", party_favored="defendant"),
        ]
        result = _make_adversarial_result(None)
        card = build_perspective_card(
            Perspective.DEFENDANT,
            result,
            decision_path_tree=_make_decision_path_tree(paths),
        )

        assert card.relevant_paths == ["path-B"]

    def test_priority_actions_filtered_by_defendant_role(self) -> None:
        actions = [
            _make_action("plaintiff", "原告行动"),
            _make_action("defendant", "被告行动1"),
        ]
        result = _make_adversarial_result(None)
        card = build_perspective_card(
            Perspective.DEFENDANT,
            result,
            action_recommendations=actions,
        )

        assert "被告行动1" in card.priority_actions
        assert "原告行动" not in card.priority_actions


# ---------------------------------------------------------------------------
# Test: build_perspective_card — JUDGE / NEUTRAL
# ---------------------------------------------------------------------------


class TestBuildNeutralCard:
    def test_strengths_include_both_sides(self) -> None:
        summary = _make_summary(
            plaintiff_strongest=[_make_argument("原告最强论点")],
            defendant_strongest=[_make_argument("被告最强抗辩")],
        )
        result = _make_adversarial_result(summary)
        card = build_perspective_card(Perspective.JUDGE, result)

        assert any("原告" in s for s in card.top_strengths)
        assert any("被告" in s for s in card.top_strengths)

    def test_dangers_are_high_impact_open_issues(self) -> None:
        issues = [
            _make_issue("i-1", "高影响争点", outcome_impact="high", status="open"),
            _make_issue("i-2", "低影响争点", outcome_impact="low", status="open"),
            _make_issue("i-3", "已关闭高影响", outcome_impact="high", status="closed"),
        ]
        issue_tree = _make_issue_tree(issues)
        result = _make_adversarial_result(None)
        card = build_perspective_card(Perspective.JUDGE, result, issue_tree=issue_tree)

        assert "高影响争点" in card.top_dangers
        assert "低影响争点" not in card.top_dangers
        assert "已关闭高影响" not in card.top_dangers

    def test_priority_actions_from_unresolved_issues(self) -> None:
        unresolved = [
            SimpleNamespace(issue_id="i-1", issue_title="未决争点A", why_unresolved="x"),
            SimpleNamespace(issue_id="i-2", issue_title="未决争点B", why_unresolved="x"),
        ]
        summary = _make_summary(unresolved_issues=unresolved)
        result = _make_adversarial_result(summary)
        card = build_perspective_card(Perspective.JUDGE, result)

        assert any("未决争点A" in a for a in card.priority_actions)
        assert any("未决争点B" in a for a in card.priority_actions)

    def test_neutral_perspective_also_builds_card(self) -> None:
        result = _make_adversarial_result(None)
        card = build_perspective_card(Perspective.NEUTRAL, result)

        assert card.perspective == Perspective.JUDGE  # neutral uses judge builder


# ---------------------------------------------------------------------------
# Test: render_layer1_block_b
# ---------------------------------------------------------------------------


class TestRenderLayer1BlockB:
    def test_plaintiff_header(self) -> None:
        card = PerspectiveCard(
            perspective=Perspective.PLAINTIFF,
            top_strengths=["论点A"],
            top_dangers=[],
            priority_actions=[],
        )
        md = render_layer1_block_b(card)
        assert "原告视角" in md
        assert "Plaintiff Perspective" in md

    def test_defendant_header(self) -> None:
        card = PerspectiveCard(perspective=Perspective.DEFENDANT)
        md = render_layer1_block_b(card)
        assert "被告视角" in md

    def test_judge_header(self) -> None:
        card = PerspectiveCard(perspective=Perspective.JUDGE)
        md = render_layer1_block_b(card)
        assert "法官视角" in md

    def test_strengths_section_rendered(self) -> None:
        card = PerspectiveCard(
            perspective=Perspective.PLAINTIFF,
            top_strengths=["优势1", "优势2"],
        )
        md = render_layer1_block_b(card)
        assert "优势" in md
        assert "优势1" in md
        assert "优势2" in md

    def test_dangers_section_rendered(self) -> None:
        card = PerspectiveCard(
            perspective=Perspective.PLAINTIFF,
            top_dangers=["风险X"],
        )
        md = render_layer1_block_b(card)
        assert "风险" in md
        assert "风险X" in md

    def test_actions_section_rendered(self) -> None:
        card = PerspectiveCard(
            perspective=Perspective.DEFENDANT,
            priority_actions=["立即申请财产保全"],
        )
        md = render_layer1_block_b(card)
        assert "立即申请财产保全" in md

    def test_empty_card_does_not_crash(self) -> None:
        card = PerspectiveCard(perspective=Perspective.NEUTRAL)
        md = render_layer1_block_b(card)
        assert md  # non-empty, at least the header


# ---------------------------------------------------------------------------
# Test: render_layer3
# ---------------------------------------------------------------------------


class TestRenderLayer3:
    def test_plaintiff_layer3_has_expected_headers(self) -> None:
        card = PerspectiveCard(
            perspective=Perspective.PLAINTIFF,
            top_strengths=["核心主张内容"],
            top_dangers=["被告攻击链"],
            priority_actions=["行动1"],
        )
        md = render_layer3(card, Perspective.PLAINTIFF)
        assert "Layer 3" in md
        assert "原告" in md
        assert "核心主张" in md
        assert "核心主张内容" in md
        assert "被告攻击链" in md

    def test_defendant_layer3_has_expected_headers(self) -> None:
        card = PerspectiveCard(
            perspective=Perspective.DEFENDANT,
            top_strengths=["核心抗辩"],
            top_dangers=["原告风险"],
        )
        md = render_layer3(card, Perspective.DEFENDANT)
        assert "被告" in md
        assert "核心抗辩" in md
        assert "原告补强风险" in md

    def test_judge_layer3_has_expected_headers(self) -> None:
        card = PerspectiveCard(
            perspective=Perspective.JUDGE,
            top_strengths=["[原告] 论点"],
            priority_actions=["待决争点: X"],
        )
        md = render_layer3(card, Perspective.JUDGE)
        assert "法官" in md
        assert "待决事项" in md

    def test_relevant_paths_rendered(self) -> None:
        card = PerspectiveCard(
            perspective=Perspective.PLAINTIFF,
            relevant_paths=["path-A", "path-B"],
        )
        md = render_layer3(card, Perspective.PLAINTIFF)
        assert "path-A" in md
        assert "path-B" in md
        assert "相关裁判路径" in md

    def test_no_relevant_paths_section_absent(self) -> None:
        card = PerspectiveCard(perspective=Perspective.DEFENDANT, relevant_paths=[])
        md = render_layer3(card, Perspective.DEFENDANT)
        assert "相关裁判路径" not in md

    def test_empty_card_returns_non_empty_string(self) -> None:
        card = PerspectiveCard(perspective=Perspective.NEUTRAL)
        md = render_layer3(card, Perspective.NEUTRAL)
        assert md


# ---------------------------------------------------------------------------
# Test: _filter_actions helper
# ---------------------------------------------------------------------------


class TestFilterActions:
    def test_none_returns_empty(self) -> None:
        assert _filter_actions(None, "plaintiff") == []

    def test_empty_list_returns_empty(self) -> None:
        assert _filter_actions([], "plaintiff") == []

    def test_filters_by_role(self) -> None:
        actions = [
            _make_action("plaintiff", "p1"),
            _make_action("defendant", "d1"),
            _make_action("plaintiff", "p2"),
        ]
        result = _filter_actions(actions, "plaintiff")
        assert result == ["p1", "p2"]

    def test_max_3_actions_returned(self) -> None:
        actions = [_make_action("plaintiff", f"行动{i}") for i in range(6)]
        result = _filter_actions(actions, "plaintiff")
        assert len(result) == 3
