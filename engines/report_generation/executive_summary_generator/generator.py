"""
ExecutiveSummaryGenerator — 执行摘要生成器（P2.12）。
Executive Summary Generator — dual-layer output, one-page summary artifact.

职责 / Responsibilities:
1. 从 issue_list 按 outcome_impact 降序选取 Top5 决定性争点（top5_decisive_issues）
2. 从 ActionRecommendation 收集高优先级条目 ID，取前 3（top3_immediate_actions）；
   P1.8 未启用时降级为 "未启用"
3. 从 OptimalAttackChain.top_attacks 收集 attack_node_id，取前 3（top3_adversary_optimal_attacks）
4. 从 AmountCalculationReport.claim_calculation_table 派生最稳诉请文本（current_most_stable_claim）
5. 从 evidence_gap_list 按 roi_rank 升序选取 Top3 gap_id（critical_evidence_gaps）；
   P1.7 未启用时降级为 "未启用"

合约保证 / Contract guarantees:
- 零 LLM 调用（纯规则层，可通过调用链追踪验证）
- top3_immediate_actions = "未启用" 当且仅当 action_recommendation is None
- critical_evidence_gaps = "未启用" 当且仅当 evidence_gap_list is None
- current_most_stable_claim 始终为非空文本
- source_* 字段保证每个字段可回连到后端详细对象
"""
from __future__ import annotations

import uuid

from engines.shared.models import (
    ActionRecommendation,
    AmountCalculationReport,
    ClaimCalculationEntry,
    EvidenceGapItem,
    ExecutiveSummaryArtifact,
    Issue,
    OptimalAttackChain,
    OutcomeImpact,
)

from .schemas import ExecutiveSummaryGeneratorInput

# outcome_impact 排序权重（降序：高值优先）
_IMPACT_WEIGHT: dict[OutcomeImpact | None, int] = {
    OutcomeImpact.high: 3,
    OutcomeImpact.medium: 2,
    OutcomeImpact.low: 1,
    None: 0,
}


class ExecutiveSummaryGenerator:
    """执行摘要生成器（P2.12）。

    纯规则层，不持有外部状态，可安全复用同一实例。

    使用方式 / Usage:
        gen = ExecutiveSummaryGenerator()
        result = gen.generate(inp)
    """

    def generate(self, inp: ExecutiveSummaryGeneratorInput) -> ExecutiveSummaryArtifact:
        """生成执行摘要产物。

        Args:
            inp: 引擎输入（含 case_id、run_id 及各模块产物）

        Returns:
            ExecutiveSummaryArtifact — 一页式执行摘要
        """
        top5 = self._build_top5_decisive_issues(inp.issue_list)
        actions, rec_id = self._build_top3_immediate_actions(inp.action_recommendation)
        attacks, chain_ids = self._build_top3_adversary_attacks(inp.optimal_attack_chains)
        claim_text = self._build_current_most_stable_claim(inp.amount_calculation_report)
        gaps = self._build_critical_evidence_gaps(inp.evidence_gap_list)

        return ExecutiveSummaryArtifact(
            summary_id=str(uuid.uuid4()),
            case_id=inp.case_id,
            run_id=inp.run_id,
            top5_decisive_issues=top5,
            top3_immediate_actions=actions,
            source_recommendation_id=rec_id,
            top3_adversary_optimal_attacks=attacks,
            source_attack_chain_ids=chain_ids,
            current_most_stable_claim=claim_text,
            source_amount_report_id=inp.amount_calculation_report.report_id,
            critical_evidence_gaps=gaps,
        )

    # ------------------------------------------------------------------
    # 内部构建方法 / Internal builders
    # ------------------------------------------------------------------

    def _build_top5_decisive_issues(self, issues: list[Issue]) -> list[str]:
        """按 outcome_impact 降序排序，取前 5 个 issue_id。

        排序权重：high=3 > medium=2 > low=1 > None=0（稳定排序）。
        """
        sorted_issues = sorted(
            issues,
            key=lambda i: _IMPACT_WEIGHT.get(i.outcome_impact, 0),
            reverse=True,
        )
        return [i.issue_id for i in sorted_issues[:5]]

    def _build_top3_immediate_actions(
        self, rec: ActionRecommendation | None
    ) -> tuple[list[str] | str, str | None]:
        """从 ActionRecommendation 收集高优先级条目 ID，取前 3。

        优先级顺序：
        1. claims_to_abandon[].suggestion_id（最紧迫：直接影响败诉风险）
        2. recommended_claim_amendments[].suggestion_id（修改诉请）
        3. evidence_supplement_priorities[]（补证，已按 roi_rank 排序）
        4. trial_explanation_priorities[].priority_id（庭审准备）

        Returns:
            (action_ids 或 "未启用", source_recommendation_id 或 None)
        """
        if rec is None:
            return "未启用", None

        item_ids: list[str] = []

        # 1. claims_to_abandon
        for ab in rec.claims_to_abandon:
            item_ids.append(ab.suggestion_id)
            if len(item_ids) >= 3:
                break

        # 2. recommended_claim_amendments
        if len(item_ids) < 3:
            for am in rec.recommended_claim_amendments:
                item_ids.append(am.suggestion_id)
                if len(item_ids) >= 3:
                    break

        # 3. evidence_supplement_priorities (gap_ids)
        if len(item_ids) < 3:
            for gap_id in rec.evidence_supplement_priorities:
                item_ids.append(gap_id)
                if len(item_ids) >= 3:
                    break

        # 4. trial_explanation_priorities
        if len(item_ids) < 3:
            for tp in rec.trial_explanation_priorities:
                item_ids.append(tp.priority_id)
                if len(item_ids) >= 3:
                    break

        return item_ids[:3], rec.recommendation_id

    def _build_top3_adversary_attacks(
        self, chains: list[OptimalAttackChain]
    ) -> tuple[list[str], list[str]]:
        """从 OptimalAttackChain.top_attacks 收集 attack_node_id，取前 3。

        按链顺序收集，保留来源链 ID 用于溯源。

        Returns:
            (attack_node_ids[:3], chain_ids)
        """
        attack_ids: list[str] = []
        chain_ids: list[str] = [c.chain_id for c in chains]

        for chain in chains:
            for node in chain.top_attacks:
                attack_ids.append(node.attack_node_id)
                if len(attack_ids) >= 3:
                    break
            if len(attack_ids) >= 3:
                break

        return attack_ids[:3], chain_ids

    def _build_current_most_stable_claim(
        self, report: AmountCalculationReport
    ) -> str:
        """从 claim_calculation_table 派生当前最稳诉请版本说明文本。

        策略：
        1. 找 delta=0 的稳定诉请 → 描述为"与计算结果完全吻合"
        2. 无 delta=0 则找 delta 绝对值最小的诉请 → 描述差额
        3. 诉请表为空 → 根据一致性校验结果描述整体状态

        Returns:
            非空描述文本
        """
        table = report.claim_calculation_table

        if not table:
            check = report.consistency_check_result
            if check.verdict_block_active:
                return (
                    f"当前存在未解决的金额口径冲突（来源报告 {report.report_id}），"
                    "裁判判断暂被阻断，建议优先解决冲突后重新计算。"
                )
            return (
                f"诉请计算表（报告 {report.report_id}）暂无条目，"
                "金额一致性校验通过，请补充诉请后重新生成摘要。"
            )

        # 找 delta=0 的最稳定诉请
        stable_entries = [e for e in table if e.delta is not None and e.delta == 0]
        if stable_entries:
            entry = stable_entries[0]
            return (
                f"诉请「{entry.claim_id}」（{entry.claim_type.value}）金额 "
                f"{entry.claimed_amount} 元，与系统可复算金额完全吻合（差额为零），"
                "当前稳定性最高，建议优先维持此诉请不变。"
            )

        # 无 delta=0：找差额最小的
        entries_with_delta = [e for e in table if e.delta is not None]
        if entries_with_delta:
            best = min(entries_with_delta, key=lambda e: abs(e.delta))  # type: ignore[arg-type]
            return (
                f"诉请「{best.claim_id}」（{best.claim_type.value}）与系统计算差额最小"
                f"（差额 {best.delta} 元），相对最稳定；"
                "建议核实差额来源并补充支撑证据。"
            )

        # 所有条目均无 calculated_amount
        entry = table[0]
        return (
            f"诉请「{entry.claim_id}」（{entry.claim_type.value}）金额 "
            f"{entry.claimed_amount} 元，当前无可复算金额，"
            "建议补充完整流水凭证以提升稳定性。"
        )

    def _build_critical_evidence_gaps(
        self, gaps: list[EvidenceGapItem] | None
    ) -> list[str] | str:
        """从 evidence_gap_list 按 roi_rank 升序选取 Top3 gap_id。

        Returns:
            gap_ids[:3] 或 "未启用"（gaps is None 时）
        """
        if gaps is None:
            return "未启用"

        sorted_gaps = sorted(gaps, key=lambda g: g.roi_rank)
        return [g.gap_id for g in sorted_gaps[:3]]
