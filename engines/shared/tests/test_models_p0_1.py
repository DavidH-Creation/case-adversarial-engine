"""
P0.1 数据模型单元测试 — 新增枚举和 Issue 扩展字段。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from engines.shared.models import (
    AttackStrength,
    EvidenceStrength,
    ImpactTarget,
    Issue,
    IssueType,
    OutcomeImpact,
    RecommendedAction,
)


class TestOutcomeImpact:
    """OutcomeImpact 枚举完整性。"""

    def test_values(self):
        assert {e.value for e in OutcomeImpact} == {"high", "medium", "low"}

    def test_string_coercion(self):
        assert OutcomeImpact("high") is OutcomeImpact.high


class TestImpactTarget:
    """ImpactTarget 枚举完整性。"""

    def test_values(self):
        expected = {"principal", "interest", "penalty", "attorney_fee", "credibility"}
        assert {e.value for e in ImpactTarget} == expected


class TestEvidenceStrength:
    def test_values(self):
        assert {e.value for e in EvidenceStrength} == {"strong", "medium", "weak"}


class TestAttackStrength:
    def test_values(self):
        assert {e.value for e in AttackStrength} == {"strong", "medium", "weak"}


class TestRecommendedAction:
    def test_values(self):
        expected = {
            "supplement_evidence",
            "amend_claim",
            "abandon",
            "explain_in_trial",
        }
        assert {e.value for e in RecommendedAction} == expected


def _minimal_issue(**overrides) -> Issue:
    """最小合法 Issue 工厂。"""
    defaults = dict(
        issue_id="i-001",
        case_id="case-001",
        title="借款合同是否成立",
        issue_type=IssueType.factual,
    )
    defaults.update(overrides)
    return Issue(**defaults)


class TestIssueP01Fields:
    """Issue P0.1 扩展字段。"""

    def test_defaults_are_none_and_empty(self):
        issue = _minimal_issue()
        assert issue.outcome_impact is None
        assert issue.impact_targets == []
        assert issue.proponent_evidence_strength is None
        assert issue.opponent_attack_strength is None
        assert issue.recommended_action is None
        assert issue.recommended_action_basis is None

    def test_all_fields_set_roundtrip(self):
        issue = _minimal_issue(
            outcome_impact=OutcomeImpact.high,
            impact_targets=["principal", "interest"],
            proponent_evidence_strength=EvidenceStrength.strong,
            opponent_attack_strength=AttackStrength.medium,
            recommended_action=RecommendedAction.supplement_evidence,
            recommended_action_basis="基于借款凭证 ev-001 评估，证据链不完整",
        )
        data = issue.model_dump()
        restored = Issue.model_validate(data)
        assert restored.outcome_impact == OutcomeImpact.high
        assert restored.impact_targets == ["principal", "interest"]
        assert restored.proponent_evidence_strength == EvidenceStrength.strong
        assert restored.opponent_attack_strength == AttackStrength.medium
        assert restored.recommended_action == RecommendedAction.supplement_evidence
        assert restored.recommended_action_basis == "基于借款凭证 ev-001 评估，证据链不完整"

    def test_existing_fields_unaffected(self):
        """P0.1 扩展不影响现有字段。"""
        issue = _minimal_issue(
            evidence_ids=["ev-001"],
            burden_ids=["burden-001"],
        )
        assert issue.evidence_ids == ["ev-001"]
        assert issue.burden_ids == ["burden-001"]

    def test_backward_compat_none_all_p01_fields(self):
        """旧数据（无 P0.1 字段）可正常反序列化。"""
        old_data = {
            "issue_id": "i-old",
            "case_id": "case-001",
            "title": "旧争点",
            "issue_type": "factual",
        }
        issue = Issue.model_validate(old_data)
        assert issue.outcome_impact is None
        assert issue.impact_targets == []
