"""
AlternativeClaimSuggestion 模型约束测试（P2.11）。

验证 Pydantic 强制的合约：
- instability_issue_ids 不允许为空列表
- 所有必需字段不允许为空字符串
"""
from __future__ import annotations

import pytest

from engines.shared.models import AlternativeClaimSuggestion


def make_suggestion(**overrides) -> AlternativeClaimSuggestion:
    """构造合法的最小 AlternativeClaimSuggestion。"""
    defaults = dict(
        suggestion_id="sug1",
        case_id="case1",
        run_id="run1",
        original_claim_id="claim1",
        instability_reason="争点证据不足，对方攻击力强",
        instability_issue_ids=["issue1"],
        alternative_claim_text="建议将诉请金额调整为可复算金额，明确计息起算日",
        stability_rationale="替代主张基于完整流水记录，消除金额争议",
    )
    defaults.update(overrides)
    return AlternativeClaimSuggestion(**defaults)


class TestAlternativeClaimSuggestionModel:
    def test_valid_minimal_suggestion_created(self):
        sug = make_suggestion()
        assert sug.suggestion_id == "sug1"
        assert sug.original_claim_id == "claim1"

    def test_instability_issue_ids_empty_list_raises(self):
        """instability_issue_ids 为空列表时必须抛出 ValidationError（零容忍）。"""
        with pytest.raises(Exception):
            make_suggestion(instability_issue_ids=[])

    def test_instability_issue_ids_non_empty_accepted(self):
        sug = make_suggestion(instability_issue_ids=["i1", "i2"])
        assert sug.instability_issue_ids == ["i1", "i2"]

    def test_instability_evidence_ids_can_be_empty(self):
        """instability_evidence_ids 允许为空列表。"""
        sug = make_suggestion(instability_evidence_ids=[])
        assert sug.instability_evidence_ids == []

    def test_supporting_evidence_ids_defaults_to_empty(self):
        sug = make_suggestion()
        assert sug.supporting_evidence_ids == []

    def test_supporting_evidence_ids_accepted(self):
        sug = make_suggestion(supporting_evidence_ids=["e1", "e2"])
        assert sug.supporting_evidence_ids == ["e1", "e2"]

    def test_created_at_auto_generated(self):
        sug = make_suggestion()
        assert sug.created_at
        assert "T" in sug.created_at  # ISO-8601 format

    def test_suggestion_id_required_non_empty(self):
        with pytest.raises(Exception):
            make_suggestion(suggestion_id="")

    def test_case_id_required_non_empty(self):
        with pytest.raises(Exception):
            make_suggestion(case_id="")

    def test_run_id_required_non_empty(self):
        with pytest.raises(Exception):
            make_suggestion(run_id="")

    def test_original_claim_id_required_non_empty(self):
        with pytest.raises(Exception):
            make_suggestion(original_claim_id="")

    def test_instability_reason_required_non_empty(self):
        with pytest.raises(Exception):
            make_suggestion(instability_reason="")

    def test_alternative_claim_text_required_non_empty(self):
        with pytest.raises(Exception):
            make_suggestion(alternative_claim_text="")

    def test_stability_rationale_required_non_empty(self):
        with pytest.raises(Exception):
            make_suggestion(stability_rationale="")
