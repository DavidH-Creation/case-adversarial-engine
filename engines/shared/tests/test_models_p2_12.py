"""
engines/shared/tests/test_models_p2_12.py

ExecutiveSummaryArtifact 模型合约测试（P2.12）。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from engines.shared.models import ExecutiveSummaryArtifact


# ---------------------------------------------------------------------------
# 辅助构建函数
# ---------------------------------------------------------------------------


def _make_artifact(**overrides) -> ExecutiveSummaryArtifact:
    """构建有效的 ExecutiveSummaryArtifact，允许字段覆盖。"""
    defaults = dict(
        summary_id="SUM-001",
        case_id="CASE-001",
        run_id="RUN-001",
        top5_decisive_issues=["ISS-001", "ISS-002"],
        top3_immediate_actions=["SUG-001", "GAP-001"],
        action_recommendation_id="REC-001",
        top3_adversary_optimal_attacks=["ATK-001", "ATK-002"],
        adversary_attack_chain_id="CHAIN-001",
        current_most_stable_claim="最稳诉请：principal，金额 100000.00（绑定 AmountCalculationReport RPT-001）",
        amount_report_id="RPT-001",
        critical_evidence_gaps=["GAP-001", "GAP-002"],
    )
    defaults.update(overrides)
    return ExecutiveSummaryArtifact(**defaults)


# ---------------------------------------------------------------------------
# 基础构建测试
# ---------------------------------------------------------------------------


class TestExecutiveSummaryArtifactConstruction:
    def test_builds_with_all_fields_present(self):
        artifact = _make_artifact()
        assert artifact.summary_id == "SUM-001"
        assert artifact.case_id == "CASE-001"
        assert artifact.run_id == "RUN-001"

    def test_created_at_auto_generated(self):
        artifact = _make_artifact()
        assert artifact.created_at is not None
        assert "T" in artifact.created_at

    def test_top5_decisive_issues_stored(self):
        artifact = _make_artifact(top5_decisive_issues=["ISS-A", "ISS-B", "ISS-C"])
        assert artifact.top5_decisive_issues == ["ISS-A", "ISS-B", "ISS-C"]

    def test_top5_decisive_issues_allows_empty_list(self):
        artifact = _make_artifact(top5_decisive_issues=[])
        assert artifact.top5_decisive_issues == []

    def test_top5_accepts_up_to_five_issues(self):
        artifact = _make_artifact(top5_decisive_issues=["I1", "I2", "I3", "I4", "I5"])
        assert len(artifact.top5_decisive_issues) == 5

    def test_top3_immediate_actions_as_list(self):
        artifact = _make_artifact(
            top3_immediate_actions=["SUG-001", "SUG-002"],
            action_recommendation_id="REC-XYZ",
        )
        assert artifact.top3_immediate_actions == ["SUG-001", "SUG-002"]
        assert artifact.action_recommendation_id == "REC-XYZ"

    def test_top3_immediate_actions_as_disabled_string(self):
        artifact = _make_artifact(
            top3_immediate_actions="未启用",
            action_recommendation_id=None,
        )
        assert artifact.top3_immediate_actions == "未启用"
        assert artifact.action_recommendation_id is None

    def test_top3_adversary_attacks_stored(self):
        artifact = _make_artifact(top3_adversary_optimal_attacks=["ATK-1", "ATK-2", "ATK-3"])
        assert artifact.top3_adversary_optimal_attacks == ["ATK-1", "ATK-2", "ATK-3"]

    def test_adversary_attack_chain_id_stored(self):
        artifact = _make_artifact(adversary_attack_chain_id="CHAIN-XYZ")
        assert artifact.adversary_attack_chain_id == "CHAIN-XYZ"

    def test_current_most_stable_claim_stored(self):
        text = "最稳诉请：principal，金额 50000（绑定 RPT-001）"
        artifact = _make_artifact(current_most_stable_claim=text)
        assert artifact.current_most_stable_claim == text

    def test_amount_report_id_stored(self):
        artifact = _make_artifact(amount_report_id="RPT-999")
        assert artifact.amount_report_id == "RPT-999"

    def test_critical_evidence_gaps_as_list(self):
        artifact = _make_artifact(critical_evidence_gaps=["GAP-1", "GAP-2", "GAP-3"])
        assert artifact.critical_evidence_gaps == ["GAP-1", "GAP-2", "GAP-3"]

    def test_critical_evidence_gaps_as_disabled_string(self):
        artifact = _make_artifact(critical_evidence_gaps="未启用")
        assert artifact.critical_evidence_gaps == "未启用"


# ---------------------------------------------------------------------------
# 必填字段校验
# ---------------------------------------------------------------------------


class TestRequiredFields:
    def test_missing_summary_id_raises(self):
        with pytest.raises(ValidationError):
            ExecutiveSummaryArtifact(
                case_id="C",
                run_id="R",
                top5_decisive_issues=[],
                top3_immediate_actions="未启用",
                top3_adversary_optimal_attacks=[],
                adversary_attack_chain_id="CHAIN-1",
                current_most_stable_claim="text",
                amount_report_id="RPT-1",
                critical_evidence_gaps="未启用",
            )

    def test_empty_summary_id_raises(self):
        with pytest.raises(ValidationError):
            _make_artifact(summary_id="")

    def test_empty_adversary_attack_chain_id_raises(self):
        with pytest.raises(ValidationError):
            _make_artifact(adversary_attack_chain_id="")

    def test_empty_amount_report_id_accepted(self):
        """amount_report_id is Optional — empty string is valid (no longer required)."""
        artifact = _make_artifact(amount_report_id="")
        assert artifact.amount_report_id == ""

    def test_none_amount_report_id_accepted(self):
        """amount_report_id is Optional — None is the default."""
        artifact = _make_artifact(amount_report_id=None)
        assert artifact.amount_report_id is None

    def test_empty_current_most_stable_claim_deprecated_ok(self):
        """v7: current_most_stable_claim 已废弃，空字符串不再报错（向后兼容）。"""
        artifact = _make_artifact(current_most_stable_claim="")
        assert artifact.current_most_stable_claim == ""


# ---------------------------------------------------------------------------
# model_validator 合约：list + None binding
# ---------------------------------------------------------------------------


class TestTraceabilityValidator:
    def test_list_actions_without_rec_id_raises(self):
        """top3_immediate_actions 为 list 时，action_recommendation_id 必须非 None。"""
        with pytest.raises(ValidationError, match="action_recommendation_id"):
            _make_artifact(
                top3_immediate_actions=["SUG-001"],
                action_recommendation_id=None,
            )

    def test_disabled_actions_with_none_rec_id_ok(self):
        """top3_immediate_actions 为 "未启用" 时，action_recommendation_id 可以为 None。"""
        artifact = _make_artifact(
            top3_immediate_actions="未启用",
            action_recommendation_id=None,
        )
        assert artifact.action_recommendation_id is None

    def test_empty_list_actions_without_rec_id_raises(self):
        """top3_immediate_actions 为空 list 时，action_recommendation_id 也必须非 None。"""
        with pytest.raises(ValidationError, match="action_recommendation_id"):
            _make_artifact(
                top3_immediate_actions=[],
                action_recommendation_id=None,
            )


# ---------------------------------------------------------------------------
# 列表长度上限约束
# ---------------------------------------------------------------------------


class TestMaxLengthConstraints:
    def test_top5_decisive_issues_max_5(self):
        """top5_decisive_issues 超过 5 条时应报错。"""
        with pytest.raises(ValidationError):
            _make_artifact(top5_decisive_issues=["I1", "I2", "I3", "I4", "I5", "I6"])

    def test_top5_decisive_issues_exactly_5_ok(self):
        artifact = _make_artifact(top5_decisive_issues=["I1", "I2", "I3", "I4", "I5"])
        assert len(artifact.top5_decisive_issues) == 5

    def test_top3_adversary_attacks_max_3(self):
        """top3_adversary_optimal_attacks 超过 3 条时应报错。"""
        with pytest.raises(ValidationError):
            _make_artifact(top3_adversary_optimal_attacks=["A1", "A2", "A3", "A4"])

    def test_top3_adversary_attacks_exactly_3_ok(self):
        artifact = _make_artifact(top3_adversary_optimal_attacks=["A1", "A2", "A3"])
        assert len(artifact.top3_adversary_optimal_attacks) == 3

    def test_top3_immediate_actions_list_max_3(self):
        """top3_immediate_actions 为 list 时超过 3 条应报错。"""
        with pytest.raises(ValidationError):
            _make_artifact(
                top3_immediate_actions=["S1", "S2", "S3", "S4"],
                action_recommendation_id="REC-001",
            )

    def test_top3_immediate_actions_list_exactly_3_ok(self):
        artifact = _make_artifact(
            top3_immediate_actions=["S1", "S2", "S3"],
            action_recommendation_id="REC-001",
        )
        assert len(artifact.top3_immediate_actions) == 3

    def test_critical_evidence_gaps_list_max_3(self):
        """critical_evidence_gaps 为 list 时超过 3 条应报错。"""
        with pytest.raises(ValidationError):
            _make_artifact(critical_evidence_gaps=["G1", "G2", "G3", "G4"])

    def test_critical_evidence_gaps_list_exactly_3_ok(self):
        artifact = _make_artifact(critical_evidence_gaps=["G1", "G2", "G3"])
        assert len(artifact.critical_evidence_gaps) == 3
