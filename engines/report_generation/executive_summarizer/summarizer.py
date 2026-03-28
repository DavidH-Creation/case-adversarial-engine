"""
ExecutiveSummarizer — 一页式执行摘要生成引擎（P2.12）。
Executive Summarizer — rule-based executive summary generator for P2.12.

职责 / Responsibilities:
1. 接收 ExecutiveSummarizerInput（issue_list, adversary_attack_chain, amount_report,
   action_recommendation?, evidence_gap_items?）
2. 规则层聚合所有上游产物，生成 ExecutiveSummaryArtifact
3. P1.7/P1.8 缺失时对应字段降级为 "未启用"

合约保证 / Contract guarantees:
- 零 LLM 调用（纯规则层，可通过调用链追踪验证）
- top3_immediate_actions 为 list 时，action_recommendation_id 必须有值
- critical_evidence_gaps 为 list 时，按 roi_rank 升序排列，最多 3 条
- top5_decisive_issues 按 outcome_impact 优先级排序（high > medium > low）
- top3_adversary_optimal_attacks 来自 adversary_attack_chain.top_attacks，不独立生成
"""
from __future__ import annotations

import uuid
from typing import Optional

from engines.shared.models import (
    ActionRecommendation,
    AmountCalculationReport,
    EvidenceGapItem,
    ExecutiveSummaryArtifact,
    Issue,
    OptimalAttackChain,
    OutcomeImpact,
)

from .schemas import ExecutiveSummarizerInput

# outcome_impact 优先级映射（数值越小优先级越高）
_IMPACT_PRIORITY: dict[OutcomeImpact, int] = {
    OutcomeImpact.high: 0,
    OutcomeImpact.medium: 1,
    OutcomeImpact.low: 2,
}


class ExecutiveSummarizer:
    """一页式执行摘要引擎（P2.12）。

    纯规则层，不持有外部状态，可安全复用同一实例。

    使用方式 / Usage:
        summarizer = ExecutiveSummarizer()
        result = summarizer.summarize(inp)
    """

    def summarize(self, inp: ExecutiveSummarizerInput) -> ExecutiveSummaryArtifact:
        """执行摘要聚合，返回 ExecutiveSummaryArtifact。

        Args:
            inp: 引擎输入（含所有上游产物，P1 产物可选）

        Returns:
            ExecutiveSummaryArtifact — 一页式执行摘要
        """
        top5 = self._top5_decisive_issues(inp.issue_list)
        top3_actions, rec_id = self._top3_immediate_actions(inp.action_recommendation)
        top3_attacks = self._top3_adversary_attacks(inp.adversary_attack_chain)
        claim_text = self._current_most_stable_claim(inp.amount_calculation_report)
        critical_gaps = self._critical_evidence_gaps(inp.evidence_gap_items)

        return ExecutiveSummaryArtifact(
            summary_id=str(uuid.uuid4()),
            case_id=inp.case_id,
            run_id=inp.run_id,
            top5_decisive_issues=top5,
            top3_immediate_actions=top3_actions,
            action_recommendation_id=rec_id,
            top3_adversary_optimal_attacks=top3_attacks,
            adversary_attack_chain_id=inp.adversary_attack_chain.chain_id,
            current_most_stable_claim=claim_text,
            amount_report_id=inp.amount_calculation_report.report_id,
            critical_evidence_gaps=critical_gaps,
        )

    # ------------------------------------------------------------------
    # 内部构建方法 / Internal builders
    # ------------------------------------------------------------------

    def _top5_decisive_issues(self, issues: list[Issue]) -> list[str]:
        """按 outcome_impact 优先级排序，返回前 5 个 issue_id。

        优先级：high > medium > low。outcome_impact 为 None 的争点排在最后。
        """
        sorted_issues = sorted(
            issues,
            key=lambda i: _IMPACT_PRIORITY.get(i.outcome_impact, 99),
        )
        return [i.issue_id for i in sorted_issues[:5]]

    def _top3_immediate_actions(
        self, recommendation: Optional[ActionRecommendation]
    ) -> tuple[list[str] | str, Optional[str]]:
        """从 ActionRecommendation 提取 Top3 立即行动。

        P1.8 缺失（recommendation=None）时返回 ("未启用", None)。
        优先级顺序：
        1. claims_to_abandon（最高：立即止损）
        2. evidence_supplement_priorities（ROI 已排序的 gap_id）
        3. recommended_claim_amendments（修改诉请）
        4. trial_explanation_priorities（庭审解释）
        """
        if recommendation is None:
            return "未启用", None

        items: list[str] = []
        items.extend(s.suggestion_id for s in recommendation.claims_to_abandon)
        items.extend(recommendation.evidence_supplement_priorities)
        items.extend(s.suggestion_id for s in recommendation.recommended_claim_amendments)
        items.extend(p.priority_id for p in recommendation.trial_explanation_priorities)

        return items[:3], recommendation.recommendation_id

    def _top3_adversary_attacks(self, chain: OptimalAttackChain) -> list[str]:
        """提取对方 OptimalAttackChain 的 Top3 攻击节点 ID。

        来源必须是已生成的 OptimalAttackChain，不独立生成。
        """
        return [a.attack_node_id for a in chain.top_attacks[:3]]

    def _current_most_stable_claim(self, report: AmountCalculationReport) -> str:
        """从 claim_calculation_table 生成最稳诉请说明文本。

        选取规则（优先级降序）：
        1. delta == 0 的条目（金额完全一致，最稳）
        2. delta 绝对值最小的条目（次稳）
        3. delta 为 None 的条目（不可复算，取第一条）
        4. 表为空时返回占位文本
        """
        table = report.claim_calculation_table
        if not table:
            return f"诉请计算表为空（绑定 AmountCalculationReport {report.report_id}）"

        # 1. Prefer delta == 0
        consistent = [e for e in table if e.delta is not None and e.delta == 0]
        if consistent:
            best = consistent[0]
            return (
                f"最稳诉请：{best.claim_type.value}，"
                f"诉请金额 {best.claimed_amount}，"
                f"与系统计算完全一致（delta=0）"
                f"（绑定 AmountCalculationReport {report.report_id}）"
            )

        # 2. Smallest absolute delta
        calculable = [e for e in table if e.delta is not None]
        if calculable:
            best = min(calculable, key=lambda e: abs(e.delta))
            return (
                f"最稳诉请（最小差异）：{best.claim_type.value}，"
                f"诉请金额 {best.claimed_amount}，"
                f"差异 {best.delta}"
                f"（绑定 AmountCalculationReport {report.report_id}）"
            )

        # 3. Non-calculable fallback
        best = table[0]
        return (
            f"诉请 {best.claim_type.value}，"
            f"诉请金额 {best.claimed_amount}（规则层无法复算）"
            f"（绑定 AmountCalculationReport {report.report_id}）"
        )

    def _critical_evidence_gaps(
        self, gap_items: Optional[list[EvidenceGapItem]]
    ) -> list[str] | str:
        """提取 Top3 关键缺证 gap_id（按 roi_rank 升序）。

        P1.7 缺失（gap_items=None）时返回 "未启用"。
        """
        if gap_items is None:
            return "未启用"
        sorted_gaps = sorted(gap_items, key=lambda g: g.roi_rank)
        return [g.gap_id for g in sorted_gaps[:3]]
