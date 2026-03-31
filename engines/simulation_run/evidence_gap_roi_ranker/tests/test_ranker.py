"""
EvidenceGapROIRanker 单元测试。
Unit tests for EvidenceGapROIRanker (P1.7).

测试策略：
- 不依赖 LLM（模块本身也不调用 LLM）
- 分层测试：枚举模型 → 输入 schema 校验 → 排序规则 → 完整 rank() 流程
- 覆盖所有 ROI 规则分组（4 个组的全部边界情况）
- 覆盖合约保证（roi_rank 连续、从 1 开始、稳定排序、零 LLM）
"""

from __future__ import annotations

import pytest

from engines.shared.models import (
    EvidenceGapItem,
    OutcomeImpactSize,
    PracticallyObtainable,
    SupplementCost,
)
from engines.simulation_run.evidence_gap_roi_ranker.ranker import EvidenceGapROIRanker
from engines.simulation_run.evidence_gap_roi_ranker.schemas import (
    EvidenceGapDescriptor,
    EvidenceGapRankerInput,
    EvidenceGapRankingResult,
)


# ---------------------------------------------------------------------------
# 测试辅助工厂 / Test helpers
# ---------------------------------------------------------------------------


def _desc(
    gap_id: str,
    issue_id: str = "issue-001",
    cost: SupplementCost = SupplementCost.medium,
    impact: OutcomeImpactSize = OutcomeImpactSize.moderate,
    obtainable: PracticallyObtainable = PracticallyObtainable.yes,
    alt_paths: list[str] | None = None,
) -> EvidenceGapDescriptor:
    """创建测试用 EvidenceGapDescriptor。"""
    return EvidenceGapDescriptor(
        gap_id=gap_id,
        related_issue_id=issue_id,
        gap_description=f"缺证项 {gap_id} 的描述",
        supplement_cost=cost,
        outcome_impact_size=impact,
        practically_obtainable=obtainable,
        alternative_evidence_paths=alt_paths or [],
    )


def _inp(
    items: list[EvidenceGapDescriptor],
    case_id: str = "case-001",
    run_id: str = "run-001",
) -> EvidenceGapRankerInput:
    """创建测试用 EvidenceGapRankerInput。"""
    return EvidenceGapRankerInput(case_id=case_id, run_id=run_id, gap_items=items)


ranker = EvidenceGapROIRanker()


# ---------------------------------------------------------------------------
# 枚举和模型合约 / Enum and model contracts
# ---------------------------------------------------------------------------


class TestEnums:
    def test_supplement_cost_values(self):
        """SupplementCost 必须包含三个合法值。"""
        assert set(SupplementCost) == {
            SupplementCost.high,
            SupplementCost.medium,
            SupplementCost.low,
        }

    def test_outcome_impact_size_values(self):
        """OutcomeImpactSize 必须包含三个合法值。"""
        assert set(OutcomeImpactSize) == {
            OutcomeImpactSize.significant,
            OutcomeImpactSize.moderate,
            OutcomeImpactSize.marginal,
        }

    def test_practically_obtainable_values(self):
        """PracticallyObtainable 必须包含三个合法值。"""
        assert set(PracticallyObtainable) == {
            PracticallyObtainable.yes,
            PracticallyObtainable.no,
            PracticallyObtainable.uncertain,
        }

    def test_evidence_gap_item_roi_rank_min_1(self):
        """EvidenceGapItem.roi_rank 最小值为 1，0 应报 ValidationError。"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EvidenceGapItem(
                gap_id="g1",
                case_id="c1",
                run_id="r1",
                related_issue_id="issue-001",
                gap_description="test",
                supplement_cost=SupplementCost.low,
                outcome_impact_size=OutcomeImpactSize.significant,
                practically_obtainable=PracticallyObtainable.yes,
                roi_rank=0,  # 非法：最小值为 1
            )

    def test_evidence_gap_item_required_related_issue_id(self):
        """EvidenceGapItem 的 related_issue_id 为空字符串时应报 ValidationError。"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EvidenceGapItem(
                gap_id="g1",
                case_id="c1",
                run_id="r1",
                related_issue_id="",  # 空字符串应报错
                gap_description="test",
                supplement_cost=SupplementCost.low,
                outcome_impact_size=OutcomeImpactSize.significant,
                practically_obtainable=PracticallyObtainable.yes,
                roi_rank=1,
            )


# ---------------------------------------------------------------------------
# 输入 schema 校验 / Input schema validation
# ---------------------------------------------------------------------------


class TestDescriptorSchemaValidation:
    def test_empty_gap_id_raises(self):
        """gap_id 为空字符串时应触发 ValidationError。"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EvidenceGapDescriptor(
                gap_id="",
                related_issue_id="issue-001",
                gap_description="valid desc",
                supplement_cost=SupplementCost.low,
                outcome_impact_size=OutcomeImpactSize.significant,
                practically_obtainable=PracticallyObtainable.yes,
            )

    def test_empty_gap_description_raises(self):
        """gap_description 为空字符串时应触发 ValidationError。"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EvidenceGapDescriptor(
                gap_id="g1",
                related_issue_id="issue-001",
                gap_description="",
                supplement_cost=SupplementCost.low,
                outcome_impact_size=OutcomeImpactSize.significant,
                practically_obtainable=PracticallyObtainable.yes,
            )

    def test_empty_related_issue_id_raises(self):
        """related_issue_id 为空字符串时应触发 ValidationError。"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EvidenceGapDescriptor(
                gap_id="g1",
                related_issue_id="",
                gap_description="valid desc",
                supplement_cost=SupplementCost.low,
                outcome_impact_size=OutcomeImpactSize.significant,
                practically_obtainable=PracticallyObtainable.yes,
            )


# ---------------------------------------------------------------------------
# 空输入 / Empty input
# ---------------------------------------------------------------------------


class TestEmptyInput:
    def test_empty_gap_items_returns_empty_result(self):
        """空 gap_items 列表返回空 ranked_items。"""
        result = ranker.rank(_inp([]))
        assert result.ranked_items == []

    def test_empty_result_preserves_case_and_run_id(self):
        """空输入结果仍包含正确的 case_id 和 run_id。"""
        result = ranker.rank(_inp([], case_id="case-XYZ", run_id="run-ABC"))
        assert result.case_id == "case-XYZ"
        assert result.run_id == "run-ABC"


# ---------------------------------------------------------------------------
# 单项输入 / Single item
# ---------------------------------------------------------------------------


class TestSingleItem:
    def test_single_item_gets_roi_rank_1(self):
        """单条缺证项，roi_rank 必须为 1。"""
        result = ranker.rank(
            _inp(
                [
                    _desc(
                        "g1",
                        impact=OutcomeImpactSize.significant,
                        obtainable=PracticallyObtainable.yes,
                    )
                ]
            )
        )
        assert len(result.ranked_items) == 1
        assert result.ranked_items[0].roi_rank == 1

    def test_single_item_fields_preserved(self):
        """单条缺证项的所有字段被正确复制到 EvidenceGapItem。"""
        desc = _desc(
            "g1",
            issue_id="issue-999",
            cost=SupplementCost.high,
            impact=OutcomeImpactSize.marginal,
            obtainable=PracticallyObtainable.no,
            alt_paths=["path-A", "path-B"],
        )
        result = ranker.rank(_inp([desc]))
        item = result.ranked_items[0]
        assert item.gap_id == "g1"
        assert item.related_issue_id == "issue-999"
        assert item.supplement_cost == SupplementCost.high
        assert item.outcome_impact_size == OutcomeImpactSize.marginal
        assert item.practically_obtainable == PracticallyObtainable.no
        assert item.alternative_evidence_paths == ["path-A", "path-B"]
        assert item.roi_rank == 1


# ---------------------------------------------------------------------------
# 优先组 1：yes + significant（最高优先）
# ---------------------------------------------------------------------------


class TestGroup1:
    def test_yes_significant_gets_top_rank(self):
        """yes+significant 应排在所有其他组之前。"""
        items = [
            _desc("g-low", impact=OutcomeImpactSize.marginal, obtainable=PracticallyObtainable.no),
            _desc(
                "g-group1",
                impact=OutcomeImpactSize.significant,
                obtainable=PracticallyObtainable.yes,
            ),
        ]
        result = ranker.rank(_inp(items))
        assert result.ranked_items[0].gap_id == "g-group1"
        assert result.ranked_items[0].roi_rank == 1

    def test_multiple_group1_items_maintain_original_order(self):
        """同为组 1 的项按原始顺序排列（稳定排序）。"""
        items = [
            _desc(
                "g1a", impact=OutcomeImpactSize.significant, obtainable=PracticallyObtainable.yes
            ),
            _desc(
                "g1b", impact=OutcomeImpactSize.significant, obtainable=PracticallyObtainable.yes
            ),
            _desc(
                "g1c", impact=OutcomeImpactSize.significant, obtainable=PracticallyObtainable.yes
            ),
        ]
        result = ranker.rank(_inp(items))
        ids = [item.gap_id for item in result.ranked_items]
        assert ids == ["g1a", "g1b", "g1c"]
        assert [item.roi_rank for item in result.ranked_items] == [1, 2, 3]


# ---------------------------------------------------------------------------
# 优先组 2：yes + moderate
# ---------------------------------------------------------------------------


class TestGroup2:
    def test_group2_after_group1(self):
        """yes+moderate 排在 yes+significant 之后。"""
        items = [
            _desc("g2", impact=OutcomeImpactSize.moderate, obtainable=PracticallyObtainable.yes),
            _desc("g1", impact=OutcomeImpactSize.significant, obtainable=PracticallyObtainable.yes),
        ]
        result = ranker.rank(_inp(items))
        assert result.ranked_items[0].gap_id == "g1"
        assert result.ranked_items[1].gap_id == "g2"


# ---------------------------------------------------------------------------
# 优先组 3：uncertain + significant
# ---------------------------------------------------------------------------


class TestGroup3:
    def test_group3_after_group2(self):
        """uncertain+significant 排在 yes+moderate 之后。"""
        items = [
            _desc(
                "g3",
                impact=OutcomeImpactSize.significant,
                obtainable=PracticallyObtainable.uncertain,
            ),
            _desc("g2", impact=OutcomeImpactSize.moderate, obtainable=PracticallyObtainable.yes),
        ]
        result = ranker.rank(_inp(items))
        assert result.ranked_items[0].gap_id == "g2"
        assert result.ranked_items[1].gap_id == "g3"

    def test_group3_before_group4(self):
        """uncertain+significant 排在所有组 4 项目之前。"""
        items = [
            _desc(
                "g4",
                impact=OutcomeImpactSize.moderate,
                obtainable=PracticallyObtainable.no,
                cost=SupplementCost.low,
            ),
            _desc(
                "g3",
                impact=OutcomeImpactSize.significant,
                obtainable=PracticallyObtainable.uncertain,
            ),
        ]
        result = ranker.rank(_inp(items))
        assert result.ranked_items[0].gap_id == "g3"
        assert result.ranked_items[1].gap_id == "g4"


# ---------------------------------------------------------------------------
# 优先组 4：其余（impact DESC → cost ASC）
# ---------------------------------------------------------------------------


class TestGroup4:
    def test_group4_sort_by_impact_desc(self):
        """组 4 内按 outcome_impact_size 降序排列（significant>moderate>marginal）。"""
        items = [
            _desc(
                "g4-marginal",
                impact=OutcomeImpactSize.marginal,
                obtainable=PracticallyObtainable.no,
            ),
            _desc(
                "g4-moderate",
                impact=OutcomeImpactSize.moderate,
                obtainable=PracticallyObtainable.no,
            ),
            _desc(
                "g4-significant",
                impact=OutcomeImpactSize.significant,
                obtainable=PracticallyObtainable.no,
            ),
        ]
        result = ranker.rank(_inp(items))
        ids = [item.gap_id for item in result.ranked_items]
        assert ids == ["g4-significant", "g4-moderate", "g4-marginal"]

    def test_group4_same_impact_sort_by_cost_asc(self):
        """组 4 内同 impact 时按 supplement_cost 升序排列（low<medium<high）。"""
        items = [
            _desc(
                "g-high-cost",
                impact=OutcomeImpactSize.moderate,
                obtainable=PracticallyObtainable.no,
                cost=SupplementCost.high,
            ),
            _desc(
                "g-low-cost",
                impact=OutcomeImpactSize.moderate,
                obtainable=PracticallyObtainable.no,
                cost=SupplementCost.low,
            ),
            _desc(
                "g-med-cost",
                impact=OutcomeImpactSize.moderate,
                obtainable=PracticallyObtainable.no,
                cost=SupplementCost.medium,
            ),
        ]
        result = ranker.rank(_inp(items))
        ids = [item.gap_id for item in result.ranked_items]
        assert ids == ["g-low-cost", "g-med-cost", "g-high-cost"]

    def test_group4_yes_marginal_is_group4(self):
        """yes+marginal 属于组 4（不在前三组中）。"""
        items = [
            _desc(
                "g4-yes-marginal",
                impact=OutcomeImpactSize.marginal,
                obtainable=PracticallyObtainable.yes,
                cost=SupplementCost.low,
            ),
            _desc(
                "g3",
                impact=OutcomeImpactSize.significant,
                obtainable=PracticallyObtainable.uncertain,
            ),
        ]
        result = ranker.rank(_inp(items))
        assert result.ranked_items[0].gap_id == "g3"
        assert result.ranked_items[1].gap_id == "g4-yes-marginal"

    def test_group4_yes_marginal_cost_sort(self):
        """yes+marginal 属于组 4，组内按 cost ASC 排序。"""
        items = [
            _desc(
                "yes-marginal-high",
                impact=OutcomeImpactSize.marginal,
                obtainable=PracticallyObtainable.yes,
                cost=SupplementCost.high,
            ),
            _desc(
                "yes-marginal-low",
                impact=OutcomeImpactSize.marginal,
                obtainable=PracticallyObtainable.yes,
                cost=SupplementCost.low,
            ),
        ]
        result = ranker.rank(_inp(items))
        assert result.ranked_items[0].gap_id == "yes-marginal-low"
        assert result.ranked_items[1].gap_id == "yes-marginal-high"

    def test_group4_uncertain_moderate_is_group4(self):
        """uncertain+moderate 属于组 4（不满足组 3 条件 uncertain+significant）。"""
        items = [
            _desc(
                "g4-uncertain-moderate",
                impact=OutcomeImpactSize.moderate,
                obtainable=PracticallyObtainable.uncertain,
                cost=SupplementCost.high,
            ),
            _desc(
                "g3",
                impact=OutcomeImpactSize.significant,
                obtainable=PracticallyObtainable.uncertain,
            ),
        ]
        result = ranker.rank(_inp(items))
        assert result.ranked_items[0].gap_id == "g3"
        assert result.ranked_items[1].gap_id == "g4-uncertain-moderate"

    def test_group4_no_any_impact_is_group4(self):
        """obtainable=no 的任何 impact 均属于组 4，且按 impact DESC 排序。"""
        items = [
            _desc("no-mod", impact=OutcomeImpactSize.moderate, obtainable=PracticallyObtainable.no),
            _desc(
                "no-sig", impact=OutcomeImpactSize.significant, obtainable=PracticallyObtainable.no
            ),
        ]
        result = ranker.rank(_inp(items))
        # 组 4 内 significant > moderate
        assert result.ranked_items[0].gap_id == "no-sig"
        assert result.ranked_items[1].gap_id == "no-mod"

    def test_group4_stable_sort_same_key(self):
        """组 4 内同 impact + 同 cost 时，原始顺序保持不变（稳定排序）。"""
        items = [
            _desc(
                "first",
                impact=OutcomeImpactSize.marginal,
                obtainable=PracticallyObtainable.no,
                cost=SupplementCost.medium,
            ),
            _desc(
                "second",
                impact=OutcomeImpactSize.marginal,
                obtainable=PracticallyObtainable.no,
                cost=SupplementCost.medium,
            ),
        ]
        result = ranker.rank(_inp(items))
        assert result.ranked_items[0].gap_id == "first"
        assert result.ranked_items[1].gap_id == "second"


# ---------------------------------------------------------------------------
# 完整多组混合场景 / Full mixed scenario
# ---------------------------------------------------------------------------


class TestFullMixedScenario:
    def test_all_four_groups_correct_order(self):
        """四个优先组混合输入，最终顺序必须严格符合规则。"""
        items = [
            # 组 4: no+marginal, cost=low
            _desc(
                "g4-1",
                impact=OutcomeImpactSize.marginal,
                obtainable=PracticallyObtainable.no,
                cost=SupplementCost.low,
            ),
            # 组 1: yes+significant
            _desc(
                "g1-1", impact=OutcomeImpactSize.significant, obtainable=PracticallyObtainable.yes
            ),
            # 组 3: uncertain+significant
            _desc(
                "g3-1",
                impact=OutcomeImpactSize.significant,
                obtainable=PracticallyObtainable.uncertain,
            ),
            # 组 2: yes+moderate
            _desc("g2-1", impact=OutcomeImpactSize.moderate, obtainable=PracticallyObtainable.yes),
        ]
        result = ranker.rank(_inp(items))
        ids = [item.gap_id for item in result.ranked_items]
        assert ids == ["g1-1", "g2-1", "g3-1", "g4-1"]

    def test_roi_rank_is_sequential_from_1(self):
        """roi_rank 必须从 1 开始，连续无空缺。"""
        items = [
            _desc("g1", impact=OutcomeImpactSize.significant, obtainable=PracticallyObtainable.yes),
            _desc("g2", impact=OutcomeImpactSize.moderate, obtainable=PracticallyObtainable.yes),
            _desc(
                "g3",
                impact=OutcomeImpactSize.significant,
                obtainable=PracticallyObtainable.uncertain,
            ),
            _desc("g4", impact=OutcomeImpactSize.marginal, obtainable=PracticallyObtainable.no),
        ]
        result = ranker.rank(_inp(items))
        ranks = [item.roi_rank for item in result.ranked_items]
        assert ranks == list(range(1, len(items) + 1))

    def test_result_preserves_case_and_run_id(self):
        """结果中 case_id 和 run_id 来自输入。"""
        result = ranker.rank(
            _inp(
                [_desc("g1")],
                case_id="case-999",
                run_id="run-XYZ",
            )
        )
        assert result.case_id == "case-999"
        assert result.run_id == "run-XYZ"

    def test_result_is_evidence_gap_item_list(self):
        """ranked_items 中每个元素都是 EvidenceGapItem 实例。"""
        result = ranker.rank(_inp([_desc("g1"), _desc("g2")]))
        for item in result.ranked_items:
            assert isinstance(item, EvidenceGapItem)

    def test_no_llm_call_verifiable(self):
        """验证 EvidenceGapROIRanker 不持有 LLM 客户端（零 LLM 调用合约）。"""
        r = EvidenceGapROIRanker()
        assert not hasattr(r, "_llm"), "排序器不应持有 LLM 客户端（零 LLM 调用合约）"

    def test_large_input_roi_rank_count(self):
        """10 个输入项，roi_rank 应为 1-10。"""
        items = [
            _desc(f"g{i}", impact=OutcomeImpactSize.moderate, obtainable=PracticallyObtainable.yes)
            for i in range(10)
        ]
        result = ranker.rank(_inp(items))
        assert len(result.ranked_items) == 10
        assert [item.roi_rank for item in result.ranked_items] == list(range(1, 11))

    def test_result_is_evidence_gap_ranking_result_type(self):
        """返回值必须是 EvidenceGapRankingResult 实例。"""
        result = ranker.rank(_inp([]))
        assert isinstance(result, EvidenceGapRankingResult)

    def test_item_case_id_and_run_id_from_input(self):
        """ranked_items 内每个 EvidenceGapItem 的 case_id/run_id 来自输入。"""
        result = ranker.rank(
            _inp(
                [_desc("g1")],
                case_id="CASE-42",
                run_id="RUN-99",
            )
        )
        item = result.ranked_items[0]
        assert item.case_id == "CASE-42"
        assert item.run_id == "RUN-99"
