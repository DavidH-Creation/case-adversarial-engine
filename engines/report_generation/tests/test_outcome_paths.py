"""
outcome_paths 单元测试。
Tests for engines.report_generation.outcome_paths module.

验证:
- Happy path: 三个来源产物均完整 → CaseOutcomePaths 4 条路径全部填充
- Happy path: WIN path 包含原告有利路径的触发条件 + key_evidence_ids
- Happy path: SUPPLEMENT path 包含 top3 gap 的 key_actions
- Edge case: decision_tree=None → WIN/LOSE trigger_conditions=["insufficient_data"]
- Edge case: mediation_range=None → MEDIATION trigger_conditions=["insufficient_data"]
- Edge case: gap_result=None → SUPPLEMENT trigger_conditions=["insufficient_data"]
- Edge case: verdict_block_active=True → WIN/LOSE risk_points 为空
- Edge case: gap_result 为空列表 → SUPPLEMENT key_actions=[]，不抛错
- Edge case: 无 plaintiff 路径 → WIN trigger_conditions=["insufficient_data"]
- Integration: CaseOutcomePaths 可序列化为 JSON
- Integration: render_outcome_paths_md_lines 输出包含 4 条路径标签
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from engines.report_generation.outcome_paths import (
    build_case_outcome_paths,
    render_outcome_paths_md_lines,
    _build_win_path,
    _build_lose_path,
    _build_mediation_path,
    _build_supplement_path,
)
from engines.report_generation.schemas import (
    CaseOutcomePaths,
    OutcomePath,
    OutcomePathType,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_path(
    path_id: str = "path-001",
    party_favored: str = "plaintiff",
    trigger_condition: str = "借条原件经鉴定为真",
    key_evidence_ids: list[str] | None = None,
    counter_evidence_ids: list[str] | None = None,
    probability_rationale: str = "证据链完整，胜诉概率高",
) -> SimpleNamespace:
    return SimpleNamespace(
        path_id=path_id,
        party_favored=party_favored,
        trigger_condition=trigger_condition,
        key_evidence_ids=key_evidence_ids or ["ev-001", "ev-002"],
        counter_evidence_ids=counter_evidence_ids or ["ev-003"],
        probability_rationale=probability_rationale,
        path_notes="",
    )


def _make_decision_tree(paths: list) -> SimpleNamespace:
    return SimpleNamespace(paths=paths, blocking_conditions=[])


def _make_mediation_range(
    min_amount: str = "30000",
    max_amount: str = "70000",
    suggested_amount: str = "50000",
    rationale: str = "诉请总额 100,000 元；综合置信区间 30%~70%",
) -> SimpleNamespace:
    return SimpleNamespace(
        min_amount=Decimal(min_amount),
        max_amount=Decimal(max_amount),
        suggested_amount=Decimal(suggested_amount),
        rationale=rationale,
    )


def _make_gap_item(
    gap_id: str,
    gap_description: str,
    roi_rank: int,
) -> SimpleNamespace:
    return SimpleNamespace(
        gap_id=gap_id,
        gap_description=gap_description,
        roi_rank=roi_rank,
    )


def _make_gap_result(items: list) -> SimpleNamespace:
    return SimpleNamespace(ranked_items=items)


# ---------------------------------------------------------------------------
# Test: build_case_outcome_paths — happy paths
# ---------------------------------------------------------------------------


class TestBuildCaseOutcomePathsHappy:
    def test_all_sources_present_returns_four_paths(self) -> None:
        """3 个来源产物均完整 → CaseOutcomePaths 4 条路径全部填充。"""
        tree = _make_decision_tree(
            [
                _make_path("p-1", "plaintiff", "借条真实，借款关系成立"),
                _make_path(
                    "p-2",
                    "defendant",
                    "抗辩转账为赠与",
                    key_evidence_ids=[],
                    counter_evidence_ids=["ev-c1"],
                ),
            ]
        )
        med = _make_mediation_range()
        gap = _make_gap_result(
            [
                _make_gap_item("gap-1", "缺借条原件", 1),
                _make_gap_item("gap-2", "缺银行流水", 2),
                _make_gap_item("gap-3", "缺证人证词", 3),
            ]
        )

        result = build_case_outcome_paths(tree, med, gap)

        assert isinstance(result, CaseOutcomePaths)
        assert result.win_path.path_type == OutcomePathType.WIN
        assert result.lose_path.path_type == OutcomePathType.LOSE
        assert result.mediation_path.path_type == OutcomePathType.MEDIATION
        assert result.supplement_path.path_type == OutcomePathType.SUPPLEMENT

    def test_all_source_artifacts_populated(self) -> None:
        """source_artifact 字段均有值。"""
        tree = _make_decision_tree([_make_path()])
        med = _make_mediation_range()
        gap = _make_gap_result([_make_gap_item("g1", "缺证据", 1)])

        result = build_case_outcome_paths(tree, med, gap)

        assert result.win_path.source_artifact == "decision_path_tree"
        assert result.lose_path.source_artifact == "decision_path_tree"
        assert result.mediation_path.source_artifact == "mediation_range"
        assert result.supplement_path.source_artifact == "evidence_gap_ranker"

    def test_win_path_trigger_conditions_from_plaintiff_paths(self) -> None:
        """WIN path 的 trigger_conditions 包含 plaintiff-favored 路径的触发条件。"""
        trigger = "借条原件经笔迹鉴定为真实"
        tree = _make_decision_tree(
            [
                _make_path("p-1", "plaintiff", trigger),
                _make_path("p-2", "defendant", "抗辩证据充分"),
            ]
        )

        result = build_case_outcome_paths(tree)

        assert trigger in result.win_path.trigger_conditions
        assert "抗辩证据充分" not in result.win_path.trigger_conditions

    def test_win_path_required_evidence_ids_from_key_evidence(self) -> None:
        """WIN path 的 required_evidence_ids 来自 plaintiff 路径的 key_evidence_ids。"""
        tree = _make_decision_tree(
            [
                _make_path("p-1", "plaintiff", key_evidence_ids=["ev-001", "ev-002"]),
            ]
        )

        result = build_case_outcome_paths(tree)

        assert "ev-001" in result.win_path.required_evidence_ids
        assert "ev-002" in result.win_path.required_evidence_ids

    def test_lose_path_trigger_conditions_from_defendant_paths(self) -> None:
        """LOSE path 的 trigger_conditions 包含 defendant-favored 路径的触发条件。"""
        trigger = "转账记录显示为赠与性质"
        tree = _make_decision_tree(
            [
                _make_path("p-1", "plaintiff", "原告证据充分"),
                _make_path("p-2", "defendant", trigger),
            ]
        )

        result = build_case_outcome_paths(tree)

        assert trigger in result.lose_path.trigger_conditions

    def test_supplement_path_top3_key_actions(self) -> None:
        """SUPPLEMENT path 包含 top3 gap 的 key_actions（按 roi_rank 排序）。"""
        gap = _make_gap_result(
            [
                _make_gap_item("g1", "补充银行流水", 1),
                _make_gap_item("g2", "补充借条原件", 2),
                _make_gap_item("g3", "补充证人证词", 3),
                _make_gap_item("g4", "补充公证材料", 4),  # 应被排除
            ]
        )

        result = build_case_outcome_paths(gap_result=gap)

        assert "补充银行流水" in result.supplement_path.key_actions
        assert "补充借条原件" in result.supplement_path.key_actions
        assert "补充证人证词" in result.supplement_path.key_actions
        assert "补充公证材料" not in result.supplement_path.key_actions
        assert len(result.supplement_path.key_actions) == 3

    def test_supplement_path_required_evidence_ids(self) -> None:
        """SUPPLEMENT path 的 required_evidence_ids 包含 top3 gap_id。"""
        gap = _make_gap_result(
            [
                _make_gap_item("gap-A", "缺证据A", 1),
                _make_gap_item("gap-B", "缺证据B", 2),
                _make_gap_item("gap-C", "缺证据C", 3),
            ]
        )

        result = build_case_outcome_paths(gap_result=gap)

        assert result.supplement_path.required_evidence_ids == ["gap-A", "gap-B", "gap-C"]

    def test_mediation_path_key_actions_contain_range(self) -> None:
        """MEDIATION path 包含调解区间 key_actions。"""
        med = _make_mediation_range("30000", "70000", "50000")

        result = build_case_outcome_paths(mediation_range=med)

        assert any("30,000" in a or "30000" in a for a in result.mediation_path.key_actions)
        assert any("70,000" in a or "70000" in a for a in result.mediation_path.key_actions)
        assert any("50,000" in a or "50000" in a for a in result.mediation_path.key_actions)

    def test_mediation_path_trigger_conditions_from_rationale(self) -> None:
        """MEDIATION path 的 trigger_conditions 来自 MediationRange.rationale。"""
        rationale = "诉请总额 100,000 元；综合置信区间 30%~90%"
        med = _make_mediation_range(rationale=rationale)

        result = build_case_outcome_paths(mediation_range=med)

        assert rationale in result.mediation_path.trigger_conditions


# ---------------------------------------------------------------------------
# Test: build_case_outcome_paths — edge cases / missing sources
# ---------------------------------------------------------------------------


class TestBuildCaseOutcomePathsMissingSources:
    def test_decision_tree_none_win_insufficient(self) -> None:
        """decision_tree=None → WIN trigger_conditions=["insufficient_data"]。"""
        result = build_case_outcome_paths(decision_tree=None)
        assert result.win_path.trigger_conditions == ["insufficient_data"]
        assert result.win_path.source_artifact == ""

    def test_decision_tree_none_lose_insufficient(self) -> None:
        """decision_tree=None → LOSE trigger_conditions=["insufficient_data"]。"""
        result = build_case_outcome_paths(decision_tree=None)
        assert result.lose_path.trigger_conditions == ["insufficient_data"]

    def test_decision_tree_none_other_paths_unaffected(self) -> None:
        """decision_tree=None → MEDIATION 和 SUPPLEMENT 路径不受影响。"""
        med = _make_mediation_range()
        gap = _make_gap_result([_make_gap_item("g1", "desc", 1)])

        result = build_case_outcome_paths(decision_tree=None, mediation_range=med, gap_result=gap)

        assert result.mediation_path.trigger_conditions != ["insufficient_data"]
        assert result.supplement_path.trigger_conditions != ["insufficient_data"]

    def test_mediation_range_none_mediation_insufficient(self) -> None:
        """mediation_range=None → MEDIATION trigger_conditions=["insufficient_data"]。"""
        result = build_case_outcome_paths(mediation_range=None)
        assert result.mediation_path.trigger_conditions == ["insufficient_data"]
        assert result.mediation_path.source_artifact == ""

    def test_mediation_range_none_other_paths_unaffected(self) -> None:
        """mediation_range=None → WIN/LOSE/SUPPLEMENT 路径不受影响。"""
        tree = _make_decision_tree([_make_path("p1", "plaintiff", "条件A")])
        gap = _make_gap_result([_make_gap_item("g1", "补充证据", 1)])

        result = build_case_outcome_paths(tree, None, gap)

        assert result.win_path.trigger_conditions != ["insufficient_data"]
        assert result.supplement_path.trigger_conditions != ["insufficient_data"]

    def test_gap_result_none_supplement_insufficient(self) -> None:
        """gap_result=None → SUPPLEMENT trigger_conditions=["insufficient_data"]。"""
        result = build_case_outcome_paths(gap_result=None)
        assert result.supplement_path.trigger_conditions == ["insufficient_data"]
        assert result.supplement_path.source_artifact == ""

    def test_gap_result_empty_list_no_error(self) -> None:
        """gap_result 有对象但 ranked_items 为空 → key_actions=[]，不抛错。"""
        gap = _make_gap_result([])
        result = build_case_outcome_paths(gap_result=gap)
        assert result.supplement_path.key_actions == []
        assert result.supplement_path.required_evidence_ids == []
        assert result.supplement_path.source_artifact == "evidence_gap_ranker"

    def test_no_plaintiff_paths_win_insufficient(self) -> None:
        """无 plaintiff 路径 → WIN trigger_conditions=["insufficient_data"]。"""
        tree = _make_decision_tree(
            [
                _make_path("p1", "defendant", "被告证据充分"),
                _make_path("p2", "neutral", "争议中性"),
            ]
        )
        result = build_case_outcome_paths(tree)
        assert result.win_path.trigger_conditions == ["insufficient_data"]

    def test_no_defendant_paths_lose_insufficient(self) -> None:
        """无 defendant 路径 → LOSE trigger_conditions=["insufficient_data"]。"""
        tree = _make_decision_tree(
            [
                _make_path("p1", "plaintiff", "原告有利"),
            ]
        )
        result = build_case_outcome_paths(tree)
        assert result.lose_path.trigger_conditions == ["insufficient_data"]

    def test_all_sources_none_all_insufficient(self) -> None:
        """所有来源均 None → 4 条路径均为 insufficient_data。"""
        result = build_case_outcome_paths()
        for path in [
            result.win_path,
            result.lose_path,
            result.mediation_path,
            result.supplement_path,
        ]:
            assert path.trigger_conditions == ["insufficient_data"]


# ---------------------------------------------------------------------------
# Test: verdict_block_active
# ---------------------------------------------------------------------------


class TestVerdictBlockActive:
    def test_verdict_block_active_true_win_risk_points_empty(self) -> None:
        """verdict_block_active=True → WIN risk_points 为空。"""
        tree = _make_decision_tree(
            [
                _make_path("p1", "plaintiff", probability_rationale="置信度 85%"),
            ]
        )
        result = build_case_outcome_paths(tree, verdict_block_active=True)
        assert result.win_path.risk_points == []

    def test_verdict_block_active_true_lose_risk_points_empty(self) -> None:
        """verdict_block_active=True → LOSE risk_points 为空。"""
        tree = _make_decision_tree(
            [
                _make_path("p1", "defendant", probability_rationale="置信度 60%"),
            ]
        )
        result = build_case_outcome_paths(tree, verdict_block_active=True)
        assert result.lose_path.risk_points == []

    def test_verdict_block_active_false_still_keeps_risk_points_empty(self) -> None:
        """verdict_block_active=False is now a compatibility no-op for risk_points."""
        rationale = "证据链完整，胜诉概率高"
        tree = _make_decision_tree(
            [
                _make_path("p1", "plaintiff", probability_rationale=rationale),
            ]
        )
        result = build_case_outcome_paths(tree, verdict_block_active=False)
        assert result.win_path.risk_points == []


# ---------------------------------------------------------------------------
# Test: supplement path ranking
# ---------------------------------------------------------------------------


class TestSupplementPathRanking:
    def test_sorts_by_roi_rank_ascending(self) -> None:
        """ranked_items 按 roi_rank 升序取前 3。"""
        gap = _make_gap_result(
            [
                _make_gap_item("g3", "第三优先", 3),
                _make_gap_item("g1", "第一优先", 1),
                _make_gap_item("g2", "第二优先", 2),
                _make_gap_item("g4", "第四优先", 4),
            ]
        )
        result = build_case_outcome_paths(gap_result=gap)
        assert result.supplement_path.key_actions == ["第一优先", "第二优先", "第三优先"]

    def test_only_one_gap_item(self) -> None:
        """只有 1 条缺证项 → key_actions 只有 1 条。"""
        gap = _make_gap_result([_make_gap_item("g1", "唯一缺证", 1)])
        result = build_case_outcome_paths(gap_result=gap)
        assert result.supplement_path.key_actions == ["唯一缺证"]


# ---------------------------------------------------------------------------
# Test: integration — JSON serialization
# ---------------------------------------------------------------------------


class TestIntegrationJsonSerialization:
    def test_case_outcome_paths_json_serializable(self) -> None:
        """CaseOutcomePaths 可序列化为 JSON。"""
        tree = _make_decision_tree(
            [
                _make_path("p1", "plaintiff", "条件A"),
                _make_path("p2", "defendant", "条件B", counter_evidence_ids=["ev-c1"]),
            ]
        )
        med = _make_mediation_range()
        gap = _make_gap_result([_make_gap_item("g1", "补证A", 1)])

        result = build_case_outcome_paths(tree, med, gap)
        json_str = result.model_dump_json()

        assert "WIN" in json_str
        assert "LOSE" in json_str
        assert "MEDIATION" in json_str
        assert "SUPPLEMENT" in json_str

    def test_model_dump_returns_dict(self) -> None:
        """model_dump() 返回包含 4 条路径的字典。"""
        result = build_case_outcome_paths()
        d = result.model_dump()
        assert "win_path" in d
        assert "lose_path" in d
        assert "mediation_path" in d
        assert "supplement_path" in d


# ---------------------------------------------------------------------------
# Test: integration — Markdown rendering
# ---------------------------------------------------------------------------


class TestIntegrationMarkdownRendering:
    def test_render_contains_all_four_path_labels(self) -> None:
        """render_outcome_paths_md_lines 输出包含 4 条路径标签。"""
        tree = _make_decision_tree([_make_path("p1", "plaintiff", "条件A")])
        med = _make_mediation_range()
        gap = _make_gap_result([_make_gap_item("g1", "描述", 1)])

        result = build_case_outcome_paths(tree, med, gap)
        lines = render_outcome_paths_md_lines(result)
        content = "\n".join(lines)

        assert "WIN" in content
        assert "LOSE" in content
        assert "MEDIATION" in content
        assert "SUPPLEMENT" in content

    def test_render_contains_trigger_conditions(self) -> None:
        """render_outcome_paths_md_lines 包含 trigger_conditions 内容。"""
        trigger = "借条真实有效且借款已交付"
        tree = _make_decision_tree([_make_path("p1", "plaintiff", trigger)])

        result = build_case_outcome_paths(tree)
        lines = render_outcome_paths_md_lines(result)
        content = "\n".join(lines)

        assert trigger in content

    def test_render_is_list_of_strings(self) -> None:
        """render_outcome_paths_md_lines 返回字符串列表。"""
        result = build_case_outcome_paths()
        lines = render_outcome_paths_md_lines(result)
        assert isinstance(lines, list)
        assert all(isinstance(line, str) for line in lines)

    def test_render_insufficient_data_visible(self) -> None:
        """当路径为 insufficient_data 时，渲染结果中可见该标记。"""
        result = build_case_outcome_paths()  # all None sources
        lines = render_outcome_paths_md_lines(result)
        content = "\n".join(lines)
        assert "insufficient_data" in content


# ---------------------------------------------------------------------------
# Test: internal builders (直接测试各 builder 函数)
# ---------------------------------------------------------------------------


class TestInternalBuilders:
    def test_build_win_path_none_tree(self) -> None:
        path = _build_win_path(None, False)
        assert path.path_type == OutcomePathType.WIN
        assert path.trigger_conditions == ["insufficient_data"]

    def test_build_lose_path_none_tree(self) -> None:
        path = _build_lose_path(None, False)
        assert path.path_type == OutcomePathType.LOSE
        assert path.trigger_conditions == ["insufficient_data"]

    def test_build_mediation_path_none(self) -> None:
        path = _build_mediation_path(None)
        assert path.path_type == OutcomePathType.MEDIATION
        assert path.trigger_conditions == ["insufficient_data"]

    def test_build_supplement_path_none(self) -> None:
        path = _build_supplement_path(None)
        assert path.path_type == OutcomePathType.SUPPLEMENT
        assert path.trigger_conditions == ["insufficient_data"]

    def test_build_win_path_deduplicates_evidence_ids(self) -> None:
        """多条 plaintiff 路径共享 evidence_id 时去重。"""
        tree = _make_decision_tree(
            [
                _make_path("p1", "plaintiff", key_evidence_ids=["ev-001", "ev-002"]),
                _make_path("p2", "plaintiff", key_evidence_ids=["ev-002", "ev-003"]),
            ]
        )
        path = _build_win_path(tree, False)
        assert len(set(path.required_evidence_ids)) == len(path.required_evidence_ids)
        assert "ev-001" in path.required_evidence_ids
        assert "ev-003" in path.required_evidence_ids
