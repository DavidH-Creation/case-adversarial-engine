"""
EvidenceGapROIRanker — 缺证 ROI 排序模块主类（P1.7）。
Evidence Gap ROI Ranker — main class for P1.7 evidence gap ROI ranking.

职责 / Responsibilities:
1. 接收 EvidenceGapRankerInput（case_id, run_id, gap_items）
2. 按四级优先规则为每个缺证项分配优先组
3. 组 1-3 内保持原始顺序（稳定排序）
4. 组 4 内按 outcome_impact_size DESC → supplement_cost ASC 排序
5. 分配 roi_rank（1-based 连续整数）
6. 返回 EvidenceGapRankingResult

合约保证 / Contract guarantees:
- 零 LLM 调用（纯规则层，可通过调用链追踪验证）
- roi_rank 从 1 开始，连续无空缺
- 空列表输入直接返回空结果
- 同一优先组内排序稳定（Python sorted() 保证）
"""

from __future__ import annotations

from engines.shared.models import (
    EvidenceGapItem,
    OutcomeImpactSize,
    PracticallyObtainable,
    SupplementCost,
)

from .schemas import (
    EvidenceGapDescriptor,
    EvidenceGapRankerInput,
    EvidenceGapRankingResult,
)

# ---------------------------------------------------------------------------
# 排序权重映射（越小越优先）
# ---------------------------------------------------------------------------

# outcome_impact_size 降序映射（小=高优先）
_IMPACT_ORDER: dict[OutcomeImpactSize, int] = {
    OutcomeImpactSize.significant: 0,
    OutcomeImpactSize.moderate: 1,
    OutcomeImpactSize.marginal: 2,
}

# supplement_cost 升序映射（小=低成本=高优先）
_COST_ORDER: dict[SupplementCost, int] = {
    SupplementCost.low: 0,
    SupplementCost.medium: 1,
    SupplementCost.high: 2,
}


class EvidenceGapROIRanker:
    """缺证 ROI 排序器（P1.7）。

    纯规则层，不持有外部状态，可安全复用同一实例。

    使用方式 / Usage:
        ranker = EvidenceGapROIRanker()
        result = ranker.rank(inp)
    """

    def rank(self, inp: EvidenceGapRankerInput) -> EvidenceGapRankingResult:
        """执行缺证 ROI 排序，返回完整结果。

        Args:
            inp: 排序器输入（含 case_id、run_id、gap_items 列表）

        Returns:
            EvidenceGapRankingResult — 含已排序并分配 roi_rank 的 EvidenceGapItem 列表
        """
        if not inp.gap_items:
            return EvidenceGapRankingResult(
                case_id=inp.case_id,
                run_id=inp.run_id,
                ranked_items=[],
            )

        # 按 ROI 规则稳定排序
        sorted_descriptors = sorted(inp.gap_items, key=self._sort_key)

        # 分配 roi_rank（1-based 连续整数）并构建 EvidenceGapItem 列表
        ranked_items = [
            self._build_item(desc, rank=i + 1, case_id=inp.case_id, run_id=inp.run_id)
            for i, desc in enumerate(sorted_descriptors)
        ]

        return EvidenceGapRankingResult(
            case_id=inp.case_id,
            run_id=inp.run_id,
            ranked_items=ranked_items,
        )

    # ------------------------------------------------------------------
    # 排序键 / Sort key
    # ------------------------------------------------------------------

    def _sort_key(self, desc: EvidenceGapDescriptor) -> tuple:
        """计算排序键（tuple 越小越靠前）。

        优先组 1-3：固定 tuple 保证组间顺序正确；组内 tie-breaking 全为 0 以保持稳定。
        优先组 4：按 (3, impact_order, cost_order) 排序。
        """
        obtainable = desc.practically_obtainable
        impact = desc.outcome_impact_size

        # 组 1：yes + significant
        if obtainable == PracticallyObtainable.yes and impact == OutcomeImpactSize.significant:
            return (0, 0, 0)

        # 组 2：yes + moderate
        if obtainable == PracticallyObtainable.yes and impact == OutcomeImpactSize.moderate:
            return (1, 0, 0)

        # 组 3：uncertain + significant
        if (
            obtainable == PracticallyObtainable.uncertain
            and impact == OutcomeImpactSize.significant
        ):
            return (2, 0, 0)

        # 组 4：其余，按 impact DESC → cost ASC
        return (3, _IMPACT_ORDER[impact], _COST_ORDER[desc.supplement_cost])

    # ------------------------------------------------------------------
    # 构建输出对象 / Build output item
    # ------------------------------------------------------------------

    @staticmethod
    def _build_item(
        desc: EvidenceGapDescriptor,
        rank: int,
        case_id: str,
        run_id: str,
    ) -> EvidenceGapItem:
        """将 EvidenceGapDescriptor 转换为带 roi_rank 的 EvidenceGapItem。"""
        return EvidenceGapItem(
            gap_id=desc.gap_id,
            case_id=case_id,
            run_id=run_id,
            related_issue_id=desc.related_issue_id,
            gap_description=desc.gap_description,
            supplement_cost=desc.supplement_cost,
            outcome_impact_size=desc.outcome_impact_size,
            practically_obtainable=desc.practically_obtainable,
            alternative_evidence_paths=desc.alternative_evidence_paths,
            roi_rank=rank,
        )
