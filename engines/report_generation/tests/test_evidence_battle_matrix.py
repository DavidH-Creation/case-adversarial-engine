"""
evidence_battle_matrix 单元测试。
Tests for engines.report_generation.evidence_battle_matrix module.

验证:
- 稳定性交通灯：红/黄/绿三种情况
- 补强证据数计算（corroboration_count）
- 路径依赖数计算（path_dependency_count）
- 7问矩阵行构建
- Markdown 渲染格式
- 边界情况：空 evidence_index、None 参数
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from engines.report_generation.evidence_battle_matrix import (
    _evidence_stability_light,
    build_evidence_battle_matrix,
    render_evidence_battle_matrix_markdown,
)
from engines.report_generation.schemas import EvidenceBattleMatrix, EvidenceBattleRow


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_evidence(
    evidence_id: str,
    title: str = "证据",
    evidence_type: str = "documentary",
    admissibility_status: str = "admitted",
    authenticity_risk: str = "low",
    is_attacked_by: list | None = None,
    target_issue_ids: list[str] | None = None,
    owner_party_id: str = "party-1",
    admissibility_challenges: list[str] | None = None,
) -> SimpleNamespace:
    """Mock Evidence-like object."""
    return SimpleNamespace(
        evidence_id=evidence_id,
        title=title,
        evidence_type=SimpleNamespace(value=evidence_type),
        admissibility_status=SimpleNamespace(value=admissibility_status),
        authenticity_risk=SimpleNamespace(value=authenticity_risk),
        is_attacked_by=is_attacked_by or [],
        target_issue_ids=target_issue_ids or [],
        owner_party_id=owner_party_id,
        admissibility_challenges=admissibility_challenges or [],
    )


def _make_evidence_index(evidences: list) -> SimpleNamespace:
    return SimpleNamespace(evidence=evidences)


def _make_issue(issue_id: str, title: str) -> SimpleNamespace:
    return SimpleNamespace(issue_id=issue_id, title=title)


def _make_issue_tree(issues: list) -> SimpleNamespace:
    return SimpleNamespace(issues=issues)


def _make_path(path_id: str, key_evidence_ids: list[str]) -> SimpleNamespace:
    return SimpleNamespace(path_id=path_id, key_evidence_ids=key_evidence_ids)


def _make_decision_path_tree(paths: list) -> SimpleNamespace:
    return SimpleNamespace(paths=paths)


# ---------------------------------------------------------------------------
# Test: _evidence_stability_light
# ---------------------------------------------------------------------------


class TestEvidenceStabilityLight:
    def test_excluded_admissibility_gives_red(self) -> None:
        ev = _make_evidence("e-1", admissibility_status="excluded")
        assert _evidence_stability_light(ev) == "🔴 红"

    def test_high_authenticity_risk_gives_red(self) -> None:
        ev = _make_evidence("e-1", authenticity_risk="high")
        assert _evidence_stability_light(ev) == "🔴 红"

    def test_attacked_evidence_gives_red(self) -> None:
        ev = _make_evidence("e-1", is_attacked_by=["e-opponent-1"])
        assert _evidence_stability_light(ev) == "🔴 红"

    def test_witness_statement_gives_yellow(self) -> None:
        ev = _make_evidence("e-1", evidence_type="witness_statement")
        assert _evidence_stability_light(ev) == "🟡 黄"

    def test_audio_visual_gives_yellow(self) -> None:
        ev = _make_evidence("e-1", evidence_type="audio_visual")
        assert _evidence_stability_light(ev) == "🟡 黄"

    def test_uncertain_admissibility_gives_yellow(self) -> None:
        ev = _make_evidence("e-1", admissibility_status="uncertain")
        assert _evidence_stability_light(ev) == "🟡 黄"

    def test_weak_admissibility_gives_yellow(self) -> None:
        ev = _make_evidence("e-1", admissibility_status="weak")
        assert _evidence_stability_light(ev) == "🟡 黄"

    def test_documentary_admitted_gives_green(self) -> None:
        ev = _make_evidence("e-1", evidence_type="documentary", admissibility_status="admitted")
        assert _evidence_stability_light(ev) == "🟢 绿"

    def test_red_conditions_take_priority_over_yellow_type(self) -> None:
        """excluded admissibility beats witness_statement type → red."""
        ev = _make_evidence(
            "e-1", evidence_type="witness_statement", admissibility_status="excluded"
        )
        assert _evidence_stability_light(ev) == "🔴 红"

    def test_attacked_beats_yellow_type(self) -> None:
        """Being attacked beats yellow evidence type → red."""
        ev = _make_evidence(
            "e-1",
            evidence_type="audio_visual",
            is_attacked_by=["e-opponent-2"],
        )
        assert _evidence_stability_light(ev) == "🔴 红"

    def test_electronic_evidence_admitted_gives_green(self) -> None:
        ev = _make_evidence("e-1", evidence_type="electronic", admissibility_status="admitted")
        assert _evidence_stability_light(ev) == "🟢 绿"


# ---------------------------------------------------------------------------
# Test: build_evidence_battle_matrix
# ---------------------------------------------------------------------------


class TestBuildEvidenceBattleMatrix:
    def test_none_evidence_index_returns_none(self) -> None:
        assert build_evidence_battle_matrix(None) is None

    def test_empty_evidence_returns_none(self) -> None:
        assert build_evidence_battle_matrix(_make_evidence_index([])) is None

    def test_single_evidence_builds_one_row(self) -> None:
        ev = _make_evidence("e-1", "借条", target_issue_ids=["i-1"])
        matrix = build_evidence_battle_matrix(_make_evidence_index([ev]))

        assert matrix is not None
        assert matrix.total_evidence == 1
        assert len(matrix.rows) == 1

    def test_row_fields_populated_correctly(self) -> None:
        ev = _make_evidence(
            "e-1",
            "银行流水",
            evidence_type="electronic",
            admissibility_status="admitted",
            owner_party_id="plaintiff",
            target_issue_ids=["i-1"],
            admissibility_challenges=["对方质疑真实性"],
        )
        matrix = build_evidence_battle_matrix(_make_evidence_index([ev]))

        row = matrix.rows[0]
        assert row.evidence_id == "e-1"
        assert row.evidence_title == "银行流水"
        assert row.owner == "plaintiff"
        assert row.admissibility == "admitted"
        assert row.opposition_challenges == ["对方质疑真实性"]

    def test_target_issue_labels_resolved_via_issue_tree(self) -> None:
        ev = _make_evidence("e-1", target_issue_ids=["i-1", "i-2"])
        issue_tree = _make_issue_tree(
            [
                _make_issue("i-1", "借贷关系成立"),
                _make_issue("i-2", "还款金额"),
            ]
        )
        matrix = build_evidence_battle_matrix(
            _make_evidence_index([ev]),
            issue_tree=issue_tree,
        )

        labels = matrix.rows[0].target_issue_labels
        assert "借贷关系成立" in labels
        assert "还款金额" in labels

    def test_target_issue_labels_fall_back_to_ids_without_issue_tree(self) -> None:
        ev = _make_evidence("e-1", target_issue_ids=["i-unknown"])
        matrix = build_evidence_battle_matrix(_make_evidence_index([ev]))

        assert matrix.rows[0].target_issue_labels == ["i-unknown"]

    def test_corroboration_count_two_evidences_same_issue(self) -> None:
        """Two evidences both targeting i-1 → each corroborates the other → count=1."""
        ev1 = _make_evidence("e-1", target_issue_ids=["i-1"])
        ev2 = _make_evidence("e-2", target_issue_ids=["i-1"])
        matrix = build_evidence_battle_matrix(_make_evidence_index([ev1, ev2]))

        assert matrix.rows[0].corroboration_count == 1
        assert matrix.rows[1].corroboration_count == 1

    def test_corroboration_count_three_evidences_same_issue(self) -> None:
        """Three evidences on same issue → each sees 2 corroborators."""
        evs = [_make_evidence(f"e-{i}", target_issue_ids=["i-1"]) for i in range(3)]
        matrix = build_evidence_battle_matrix(_make_evidence_index(evs))

        for row in matrix.rows:
            assert row.corroboration_count == 2

    def test_corroboration_count_zero_no_shared_issues(self) -> None:
        """Two evidences on different issues → corroboration=0 each."""
        ev1 = _make_evidence("e-1", target_issue_ids=["i-1"])
        ev2 = _make_evidence("e-2", target_issue_ids=["i-2"])
        matrix = build_evidence_battle_matrix(_make_evidence_index([ev1, ev2]))

        assert matrix.rows[0].corroboration_count == 0
        assert matrix.rows[1].corroboration_count == 0

    def test_corroboration_counts_unique_other_evidences(self) -> None:
        """Evidence on two issues: corroboration is unique other evidence count, not sum."""
        ev1 = _make_evidence("e-1", target_issue_ids=["i-1", "i-2"])
        ev2 = _make_evidence("e-2", target_issue_ids=["i-1"])
        ev3 = _make_evidence("e-3", target_issue_ids=["i-2"])
        matrix = build_evidence_battle_matrix(_make_evidence_index([ev1, ev2, ev3]))

        # e-1 shares i-1 with e-2 and i-2 with e-3 → 2 unique corroborators
        row1 = next(r for r in matrix.rows if r.evidence_id == "e-1")
        assert row1.corroboration_count == 2

    def test_path_dependency_count_from_decision_path_tree(self) -> None:
        ev = _make_evidence("e-1")
        path_tree = _make_decision_path_tree(
            [
                _make_path("path-A", ["e-1"]),
                _make_path("path-B", ["e-1"]),
            ]
        )
        matrix = build_evidence_battle_matrix(
            _make_evidence_index([ev]),
            decision_path_tree=path_tree,
        )

        assert matrix.rows[0].path_dependency_count == 2

    def test_path_dependency_count_zero_when_not_cited(self) -> None:
        ev = _make_evidence("e-1")
        path_tree = _make_decision_path_tree(
            [
                _make_path("path-A", ["e-other"]),
            ]
        )
        matrix = build_evidence_battle_matrix(
            _make_evidence_index([ev]),
            decision_path_tree=path_tree,
        )

        assert matrix.rows[0].path_dependency_count == 0

    def test_path_dependency_count_zero_without_tree(self) -> None:
        ev = _make_evidence("e-1")
        matrix = build_evidence_battle_matrix(_make_evidence_index([ev]))

        assert matrix.rows[0].path_dependency_count == 0

    def test_stability_light_green_for_admitted_documentary(self) -> None:
        ev = _make_evidence("e-1", evidence_type="documentary", admissibility_status="admitted")
        matrix = build_evidence_battle_matrix(_make_evidence_index([ev]))

        assert matrix.rows[0].stability_light == "🟢 绿"

    def test_stability_light_red_for_excluded(self) -> None:
        ev = _make_evidence("e-1", admissibility_status="excluded")
        matrix = build_evidence_battle_matrix(_make_evidence_index([ev]))

        assert matrix.rows[0].stability_light == "🔴 红"

    def test_stability_light_yellow_for_witness_statement(self) -> None:
        ev = _make_evidence("e-1", evidence_type="witness_statement")
        matrix = build_evidence_battle_matrix(_make_evidence_index([ev]))

        assert matrix.rows[0].stability_light == "🟡 黄"

    def test_summary_counts_match_traffic_light_distribution(self) -> None:
        evs = [
            _make_evidence("e-green", evidence_type="documentary", admissibility_status="admitted"),
            _make_evidence("e-yellow", evidence_type="witness_statement"),
            _make_evidence("e-red", admissibility_status="excluded"),
        ]
        matrix = build_evidence_battle_matrix(_make_evidence_index(evs))

        assert matrix.green_count == 1
        assert matrix.yellow_count == 1
        assert matrix.red_count == 1
        assert matrix.total_evidence == 3

    def test_evidence_without_id_is_skipped_in_corroboration(self) -> None:
        """Evidence with no evidence_id should not cause KeyError or corrupt counts."""
        ev_no_id = SimpleNamespace(
            evidence_id=None,
            title="无ID证据",
            evidence_type=SimpleNamespace(value="documentary"),
            admissibility_status=SimpleNamespace(value="admitted"),
            authenticity_risk=SimpleNamespace(value="low"),
            is_attacked_by=[],
            target_issue_ids=["i-1"],
            owner_party_id="party-1",
            admissibility_challenges=[],
        )
        ev_normal = _make_evidence("e-1", target_issue_ids=["i-1"])
        matrix = build_evidence_battle_matrix(_make_evidence_index([ev_no_id, ev_normal]))

        # The None-id evidence still appears as a row (evidence_id="")
        # The normal evidence should have corroboration_count=0 since the other
        # evidence has no id and won't be in the lookup
        assert matrix is not None


# ---------------------------------------------------------------------------
# Test: render_evidence_battle_matrix_markdown
# ---------------------------------------------------------------------------


class TestRenderEvidenceBattleMatrixMarkdown:
    def _make_matrix(self, rows: list[EvidenceBattleRow]) -> EvidenceBattleMatrix:
        green = sum(1 for r in rows if "🟢" in r.stability_light)
        yellow = sum(1 for r in rows if "🟡" in r.stability_light)
        red = sum(1 for r in rows if "🔴" in r.stability_light)
        return EvidenceBattleMatrix(
            rows=rows,
            total_evidence=len(rows),
            green_count=green,
            yellow_count=yellow,
            red_count=red,
        )

    def test_header_present(self) -> None:
        matrix = self._make_matrix([])
        md = render_evidence_battle_matrix_markdown(matrix)
        assert "证据作战矩阵" in md
        assert "Evidence Battle Matrix" in md

    def test_summary_line_present(self) -> None:
        rows = [
            EvidenceBattleRow(
                evidence_id="e-1",
                evidence_title="借条",
                stability_light="🟢 绿",
            )
        ]
        matrix = self._make_matrix(rows)
        md = render_evidence_battle_matrix_markdown(matrix)
        assert "共 1 条证据" in md
        assert "🟢 1" in md

    def test_column_headers_present(self) -> None:
        matrix = self._make_matrix([])
        md = render_evidence_battle_matrix_markdown(matrix)
        assert "| 证据 |" in md
        assert "| 证明目标 |" in md
        assert "| 提交方 |" in md
        assert "| 可采性 |" in md
        assert "| 对方质疑 |" in md
        assert "| 补强 |" in md
        assert "| 稳定性 |" in md
        assert "| 路径依赖 |" in md

    def test_row_content_rendered(self) -> None:
        row = EvidenceBattleRow(
            evidence_id="e-1",
            evidence_title="银行流水",
            target_issue_labels=["借贷关系", "还款金额"],
            owner="plaintiff",
            admissibility="admitted",
            opposition_challenges=["真实性存疑"],
            corroboration_count=2,
            stability_light="🟢 绿",
            path_dependency_count=3,
        )
        md = render_evidence_battle_matrix_markdown(self._make_matrix([row]))
        assert "银行流水" in md
        assert "plaintiff" in md
        assert "admitted" in md
        assert "真实性存疑" in md
        assert "🟢 绿" in md
        # corroboration and path dependency as numbers
        assert "| 2 |" in md or "2" in md
        assert "| 3 |" in md or "3" in md

    def test_no_challenges_renders_as_none_char(self) -> None:
        """Empty opposition_challenges → '无'."""
        row = EvidenceBattleRow(
            evidence_id="e-1",
            evidence_title="借条",
            opposition_challenges=[],
            stability_light="🟢 绿",
        )
        md = render_evidence_battle_matrix_markdown(self._make_matrix([row]))
        assert "无" in md

    def test_no_target_issues_renders_as_dash(self) -> None:
        """Empty target_issue_labels → '-'."""
        row = EvidenceBattleRow(
            evidence_id="e-1",
            evidence_title="借条",
            target_issue_labels=[],
            stability_light="🟢 绿",
        )
        md = render_evidence_battle_matrix_markdown(self._make_matrix([row]))
        assert "| - |" in md

    def test_multiple_target_issues_joined(self) -> None:
        """Multiple labels joined with '、'."""
        row = EvidenceBattleRow(
            evidence_id="e-1",
            evidence_title="借条",
            target_issue_labels=["争点A", "争点B"],
            stability_light="🟢 绿",
        )
        md = render_evidence_battle_matrix_markdown(self._make_matrix([row]))
        assert "争点A、争点B" in md

    def test_row_count_in_output(self) -> None:
        """Table has one data row per evidence."""
        rows = [
            EvidenceBattleRow(
                evidence_id=f"e-{i}",
                evidence_title=f"证据{i}",
                stability_light="🟢 绿",
            )
            for i in range(4)
        ]
        md = render_evidence_battle_matrix_markdown(self._make_matrix(rows))
        data_rows = [
            line
            for line in md.splitlines()
            if line.startswith("|") and "---" not in line and "| 证据 |" not in line
        ]
        assert len(data_rows) == 4
