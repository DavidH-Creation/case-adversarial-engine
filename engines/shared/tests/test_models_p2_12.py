"""
ExecutiveSummaryArtifact 模型约束测试（P2.12）。

验证 Pydantic 强制的合约：
- top3_immediate_actions 只允许 list[str] 或 "未启用"
- critical_evidence_gaps 只允许 list[str] 或 "未启用"
- 所有必需字段不允许为空字符串
- 溯源字段正常存储
"""
from __future__ import annotations

import pytest

from engines.shared.models import ExecutiveSummaryArtifact


def make_summary(**overrides) -> ExecutiveSummaryArtifact:
    """构造合法的最小 ExecutiveSummaryArtifact。"""
    defaults = dict(
        summary_id="sum1",
        case_id="case1",
        run_id="run1",
        top5_decisive_issues=["issue1", "issue2"],
        top3_immediate_actions=["sug1", "sug2"],
        source_recommendation_id="rec1",
        top3_adversary_optimal_attacks=["atk1", "atk2", "atk3"],
        source_attack_chain_ids=["chain1"],
        current_most_stable_claim="诉请本金 10 万元，与流水完全吻合，无差额，稳定性最高",
        source_amount_report_id="rpt1",
        critical_evidence_gaps=["gap1", "gap2"],
    )
    defaults.update(overrides)
    return ExecutiveSummaryArtifact(**defaults)


class TestExecutiveSummaryArtifactModel:
    def test_valid_minimal_summary_created(self):
        s = make_summary()
        assert s.summary_id == "sum1"
        assert s.case_id == "case1"
        assert s.run_id == "run1"

    # ---- 降级字段约束 ----

    def test_top3_immediate_actions_list_accepted(self):
        s = make_summary(top3_immediate_actions=["id1", "id2", "id3"])
        assert s.top3_immediate_actions == ["id1", "id2", "id3"]

    def test_top3_immediate_actions_disabled_string_accepted(self):
        s = make_summary(
            top3_immediate_actions="未启用",
            source_recommendation_id=None,
        )
        assert s.top3_immediate_actions == "未启用"

    def test_top3_immediate_actions_invalid_string_raises(self):
        with pytest.raises(Exception):
            make_summary(top3_immediate_actions="random_string")

    def test_top3_immediate_actions_empty_list_accepted(self):
        """空列表是合法的（P1.8 启用但无任何建议时）。"""
        s = make_summary(top3_immediate_actions=[])
        assert s.top3_immediate_actions == []

    def test_critical_evidence_gaps_list_accepted(self):
        s = make_summary(critical_evidence_gaps=["gap1", "gap2", "gap3"])
        assert s.critical_evidence_gaps == ["gap1", "gap2", "gap3"]

    def test_critical_evidence_gaps_disabled_string_accepted(self):
        s = make_summary(critical_evidence_gaps="未启用")
        assert s.critical_evidence_gaps == "未启用"

    def test_critical_evidence_gaps_invalid_string_raises(self):
        with pytest.raises(Exception):
            make_summary(critical_evidence_gaps="not_valid")

    def test_critical_evidence_gaps_empty_list_accepted(self):
        s = make_summary(critical_evidence_gaps=[])
        assert s.critical_evidence_gaps == []

    # ---- 必需字段非空 ----

    def test_summary_id_required_non_empty(self):
        with pytest.raises(Exception):
            make_summary(summary_id="")

    def test_case_id_required_non_empty(self):
        with pytest.raises(Exception):
            make_summary(case_id="")

    def test_run_id_required_non_empty(self):
        with pytest.raises(Exception):
            make_summary(run_id="")

    def test_current_most_stable_claim_required_non_empty(self):
        with pytest.raises(Exception):
            make_summary(current_most_stable_claim="")

    def test_source_amount_report_id_required_non_empty(self):
        with pytest.raises(Exception):
            make_summary(source_amount_report_id="")

    # ---- 溯源字段 ----

    def test_source_recommendation_id_none_when_disabled(self):
        s = make_summary(
            top3_immediate_actions="未启用",
            source_recommendation_id=None,
        )
        assert s.source_recommendation_id is None

    def test_source_recommendation_id_set_when_enabled(self):
        s = make_summary(
            top3_immediate_actions=["sug1"],
            source_recommendation_id="rec-abc",
        )
        assert s.source_recommendation_id == "rec-abc"

    def test_source_attack_chain_ids_defaults_empty(self):
        s = make_summary(source_attack_chain_ids=[])
        assert s.source_attack_chain_ids == []

    def test_source_attack_chain_ids_stored(self):
        s = make_summary(source_attack_chain_ids=["c1", "c2"])
        assert s.source_attack_chain_ids == ["c1", "c2"]

    # ---- top5/top3 长度无强制上限 ----

    def test_top5_decisive_issues_can_be_empty(self):
        s = make_summary(top5_decisive_issues=[])
        assert s.top5_decisive_issues == []

    def test_top3_adversary_optimal_attacks_can_be_empty(self):
        s = make_summary(top3_adversary_optimal_attacks=[])
        assert s.top3_adversary_optimal_attacks == []

    # ---- created_at 自动生成 ----

    def test_created_at_auto_generated(self):
        s = make_summary()
        assert s.created_at
        assert "T" in s.created_at
