"""
P2.10 数据模型单元测试 — RiskImpactObject / RiskFlag / AgentOutput migration
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from engines.shared.models import (
    AgentOutput,
    ProcedurePhase,
    RiskFlag,
    RiskImpactObject,
    StatementClass,
)


# ---------------------------------------------------------------------------
# RiskImpactObject
# ---------------------------------------------------------------------------


class TestRiskImpactObject:
    def test_all_five_values_exist(self):
        values = {v.value for v in RiskImpactObject}
        assert values == {
            "win_rate",
            "supported_amount",
            "trial_credibility",
            "procedural_stability",
            "evidence_supplement_cost",
        }

    def test_win_rate(self):
        assert RiskImpactObject.win_rate.value == "win_rate"

    def test_supported_amount(self):
        assert RiskImpactObject.supported_amount.value == "supported_amount"

    def test_trial_credibility(self):
        assert RiskImpactObject.trial_credibility.value == "trial_credibility"

    def test_procedural_stability(self):
        assert RiskImpactObject.procedural_stability.value == "procedural_stability"

    def test_evidence_supplement_cost(self):
        assert RiskImpactObject.evidence_supplement_cost.value == "evidence_supplement_cost"


# ---------------------------------------------------------------------------
# RiskFlag
# ---------------------------------------------------------------------------


def _make_risk_flag(**kwargs) -> dict:
    defaults = dict(
        flag_id="rf-001",
        description="越权风险",
        impact_objects=[RiskImpactObject.win_rate],
        impact_objects_scored=True,
    )
    defaults.update(kwargs)
    return defaults


class TestRiskFlag:
    def test_valid_minimal(self):
        rf = RiskFlag(**_make_risk_flag())
        assert rf.flag_id == "rf-001"
        assert rf.description == "越权风险"
        assert rf.impact_objects == [RiskImpactObject.win_rate]
        assert rf.impact_objects_scored is True

    def test_empty_flag_id_raises(self):
        with pytest.raises(ValidationError):
            RiskFlag(**_make_risk_flag(flag_id=""))

    def test_empty_description_raises(self):
        with pytest.raises(ValidationError):
            RiskFlag(**_make_risk_flag(description=""))

    def test_scored_true_empty_impact_objects_raises(self):
        """impact_objects must not be empty when impact_objects_scored=True."""
        with pytest.raises(ValidationError):
            RiskFlag(**_make_risk_flag(impact_objects=[], impact_objects_scored=True))

    def test_scored_false_empty_impact_objects_allowed(self):
        """Legacy-migrated RiskFlag may have empty impact_objects."""
        rf = RiskFlag(**_make_risk_flag(impact_objects=[], impact_objects_scored=False))
        assert rf.impact_objects == []
        assert rf.impact_objects_scored is False

    def test_multiple_impact_objects(self):
        rf = RiskFlag(
            **_make_risk_flag(
                impact_objects=[
                    RiskImpactObject.win_rate,
                    RiskImpactObject.trial_credibility,
                ]
            )
        )
        assert len(rf.impact_objects) == 2

    def test_all_enum_values_accepted(self):
        for v in RiskImpactObject:
            rf = RiskFlag(**_make_risk_flag(impact_objects=[v]))
            assert v in rf.impact_objects

    def test_roundtrip_serialization(self):
        rf = RiskFlag(
            **_make_risk_flag(
                impact_objects=[RiskImpactObject.win_rate, RiskImpactObject.supported_amount]
            )
        )
        data = rf.model_dump()
        restored = RiskFlag.model_validate(data)
        assert restored.impact_objects == rf.impact_objects
        assert restored.impact_objects_scored == rf.impact_objects_scored


# ---------------------------------------------------------------------------
# AgentOutput — risk_flags migration
# ---------------------------------------------------------------------------


def _base_output(**overrides) -> dict:
    defaults = dict(
        output_id="out-p210-001",
        case_id="case-001",
        run_id="run-001",
        state_id="state-001",
        phase=ProcedurePhase.opening,
        round_index=0,
        agent_role_code="plaintiff_agent",
        owner_party_id="party-001",
        issue_ids=["issue-001"],
        title="原告首轮主张",
        body="借贷关系成立。",
        evidence_citations=["ev-001"],
        statement_class=StatementClass.fact,
        risk_flags=[],
        created_at="2026-01-01T00:00:00Z",
    )
    defaults.update(overrides)
    return defaults


class TestAgentOutputRiskFlags:
    def test_empty_list_valid(self):
        out = AgentOutput(**_base_output(risk_flags=[]))
        assert out.risk_flags == []

    def test_native_risk_flag_accepted(self):
        rf = RiskFlag(
            flag_id="rf-001",
            description="越权风险",
            impact_objects=[RiskImpactObject.win_rate],
        )
        out = AgentOutput(**_base_output(risk_flags=[rf]))
        assert len(out.risk_flags) == 1
        assert isinstance(out.risk_flags[0], RiskFlag)

    def test_string_risk_flag_rejected(self):
        """v1.5: str risk_flags no longer accepted, must raise ValidationError."""
        import pytest

        with pytest.raises(Exception):
            AgentOutput(**_base_output(risk_flags=["越权风险", "引用不足"]))

    def test_mixed_str_and_risk_flag_rejected(self):
        """v1.5: mixed list with str elements must also be rejected."""
        import pytest

        rf_native = RiskFlag(
            flag_id="rf-native",
            description="越权风险",
            impact_objects=[RiskImpactObject.win_rate],
        )
        with pytest.raises(Exception):
            AgentOutput(**_base_output(risk_flags=["程序冲突", rf_native]))

    def test_native_flag_roundtrip(self):
        rf = RiskFlag(
            flag_id="rf-001",
            description="越权风险",
            impact_objects=[RiskImpactObject.win_rate, RiskImpactObject.trial_credibility],
        )
        out = AgentOutput(**_base_output(risk_flags=[rf]))
        restored = AgentOutput.model_validate(out.model_dump())
        assert len(restored.risk_flags) == 1
        assert restored.risk_flags[0].flag_id == "rf-001"
        assert RiskImpactObject.win_rate in restored.risk_flags[0].impact_objects

    def test_dict_form_risk_flag_accepted(self):
        """Pydantic should coerce dict -> RiskFlag."""
        rf_dict = {
            "flag_id": "rf-dict",
            "description": "引用不足",
            "impact_objects": ["win_rate", "supported_amount"],
            "impact_objects_scored": True,
        }
        out = AgentOutput(**_base_output(risk_flags=[rf_dict]))
        assert isinstance(out.risk_flags[0], RiskFlag)
        assert out.risk_flags[0].flag_id == "rf-dict"

    def test_default_risk_flags_is_empty_list(self):
        data = _base_output()
        del data["risk_flags"]
        out = AgentOutput(**data)
        assert out.risk_flags == []
