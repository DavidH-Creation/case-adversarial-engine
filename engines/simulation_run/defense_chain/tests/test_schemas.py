"""
defense_chain schemas 单元测试。
Unit tests for defense_chain schemas and models.

测试策略：
- Pydantic 模型的 validation 行为
- 默认值、边界值、非法值
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from engines.simulation_run.defense_chain.models import DefensePoint, PlaintiffDefenseChain
from engines.simulation_run.defense_chain.schemas import (
    DefenseChainInput,
    DefenseChainResult,
    LLMDefenseChainOutput,
    LLMDefensePointOutput,
)


# ---------------------------------------------------------------------------
# LLMDefensePointOutput 验证
# ---------------------------------------------------------------------------


class TestLLMDefensePointOutput:
    """LLM 中间模型字段验证。"""

    def test_valid_point_accepted(self):
        point = LLMDefensePointOutput(
            issue_id="ISS-001",
            defense_strategy="策略",
            supporting_argument="论证",
            evidence_ids=["EV-001"],
            priority=1,
        )
        assert point.issue_id == "ISS-001"

    def test_empty_issue_id_rejected(self):
        with pytest.raises(ValidationError):
            LLMDefensePointOutput(
                issue_id="",
                defense_strategy="策略",
            )

    def test_default_values(self):
        point = LLMDefensePointOutput(issue_id="ISS-001")
        assert point.defense_strategy == ""
        assert point.supporting_argument == ""
        assert point.evidence_ids == []
        assert point.priority == 1

    def test_priority_zero_rejected(self):
        with pytest.raises(ValidationError):
            LLMDefensePointOutput(issue_id="ISS-001", priority=0)

    def test_negative_priority_rejected(self):
        with pytest.raises(ValidationError):
            LLMDefensePointOutput(issue_id="ISS-001", priority=-1)


# ---------------------------------------------------------------------------
# LLMDefenseChainOutput 验证
# ---------------------------------------------------------------------------


class TestLLMDefenseChainOutput:
    """LLM 完整输出模型验证。"""

    def test_default_values(self):
        output = LLMDefenseChainOutput()
        assert output.defense_points == []
        assert output.confidence_score == pytest.approx(0.5)
        assert output.strategic_summary == ""

    def test_confidence_clamped_to_range(self):
        with pytest.raises(ValidationError):
            LLMDefenseChainOutput(confidence_score=1.5)

    def test_negative_confidence_rejected(self):
        with pytest.raises(ValidationError):
            LLMDefenseChainOutput(confidence_score=-0.1)

    def test_valid_confidence_boundary_values(self):
        out_zero = LLMDefenseChainOutput(confidence_score=0.0)
        out_one = LLMDefenseChainOutput(confidence_score=1.0)
        assert out_zero.confidence_score == 0.0
        assert out_one.confidence_score == 1.0


# ---------------------------------------------------------------------------
# DefensePoint 模型验证
# ---------------------------------------------------------------------------


class TestDefensePointModel:
    """领域模型 DefensePoint 验证。"""

    def test_valid_point(self):
        point = DefensePoint(
            point_id="PT-001",
            issue_id="ISS-001",
            defense_strategy="策略",
            supporting_argument="论证",
            evidence_ids=["EV-001"],
            priority=1,
        )
        assert point.point_id == "PT-001"

    def test_empty_point_id_rejected(self):
        with pytest.raises(ValidationError):
            DefensePoint(
                point_id="",
                issue_id="ISS-001",
                defense_strategy="策略",
                supporting_argument="论证",
                priority=1,
            )

    def test_empty_strategy_rejected(self):
        with pytest.raises(ValidationError):
            DefensePoint(
                point_id="PT-001",
                issue_id="ISS-001",
                defense_strategy="",
                supporting_argument="论证",
                priority=1,
            )


# ---------------------------------------------------------------------------
# PlaintiffDefenseChain 模型验证
# ---------------------------------------------------------------------------


class TestPlaintiffDefenseChainModel:
    """领域模型 PlaintiffDefenseChain 验证。"""

    def test_valid_chain(self):
        chain = PlaintiffDefenseChain(
            chain_id="CH-001",
            case_id="CASE-001",
            confidence_score=0.8,
        )
        assert chain.chain_id == "CH-001"
        assert chain.defense_points == []
        assert chain.target_issues == []

    def test_confidence_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            PlaintiffDefenseChain(
                chain_id="CH-001",
                case_id="CASE-001",
                confidence_score=2.0,
            )

    def test_created_at_auto_populated(self):
        chain = PlaintiffDefenseChain(
            chain_id="CH-001",
            case_id="CASE-001",
            confidence_score=0.5,
        )
        assert chain.created_at
        assert "T" in chain.created_at


# ---------------------------------------------------------------------------
# DefenseChainInput 验证
# ---------------------------------------------------------------------------


class TestDefenseChainInput:
    """引擎输入 wrapper 验证。"""

    def test_empty_case_id_rejected(self):
        with pytest.raises(ValidationError):
            DefenseChainInput(
                case_id="",
                run_id="RUN-001",
                evidence_index={"case_id": "C", "evidence": []},
                plaintiff_party_id="P-001",
            )

    def test_empty_run_id_rejected(self):
        with pytest.raises(ValidationError):
            DefenseChainInput(
                case_id="CASE-001",
                run_id="",
                evidence_index={"case_id": "C", "evidence": []},
                plaintiff_party_id="P-001",
            )


# ---------------------------------------------------------------------------
# DefenseChainResult 验证
# ---------------------------------------------------------------------------


class TestDefenseChainResult:
    """引擎输出 wrapper 验证。"""

    def test_default_values(self):
        chain = PlaintiffDefenseChain(
            chain_id="CH-001",
            case_id="CASE-001",
            confidence_score=0.0,
        )
        result = DefenseChainResult(chain=chain)
        assert result.unevaluated_issue_ids == []
        assert result.metadata == {}
