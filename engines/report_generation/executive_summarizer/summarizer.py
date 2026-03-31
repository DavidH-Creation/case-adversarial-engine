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

from decimal import Decimal

from engines.shared.models import (
    ActionRecommendation,
    AmountCalculationReport,
    ClaimDecomposition,
    ConfidenceMetrics,
    DecisionPathTree,
    EvidenceGapItem,
    ExecutiveSummaryArtifact,
    ExecutiveSummaryStructuredOutput,
    InternalDecisionSummary,
    Issue,
    OptimalAttackChain,
    OutcomeImpact,
)
from engines.simulation_run.defense_chain.schemas import DefenseChainResult

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
        strategic_summary = self._compute_strategic_summary(
            inp.action_recommendation,
            inp.amount_calculation_report,
        )
        critical_gaps = self._critical_evidence_gaps(inp.evidence_gap_items)
        defense_chain_result: DefenseChainResult | None = getattr(inp, "defense_chain_result", None)
        structured = self._build_structured_output(
            issues=inp.issue_list,
            top5_issue_ids=top5,
            top3_actions=top3_actions,
            top3_attacks=top3_attacks,
            critical_gaps=critical_gaps,
            amount_report=inp.amount_calculation_report,
            action_recommendation=inp.action_recommendation,
            defense_chain_result=defense_chain_result,
        )

        # v7: 构建诉请拆分（替代原 current_most_stable_claim）
        decision_tree = getattr(inp, "decision_path_tree", None)
        claim_decomposition = self._build_claim_decomposition(
            inp.amount_calculation_report,
            decision_tree,
        )
        # v7: 内部决策版本
        internal_decision = self._build_internal_decision_summary(
            inp.issue_list,
            decision_tree,
            critical_gaps,
        )
        # v7: 主要风险 + 下一步最优行动
        primary_risk = self._compute_primary_risk(inp.issue_list, top3_attacks)
        next_action = self._compute_next_best_action(
            top3_actions,
            critical_gaps,
            inp.action_recommendation,
        )

        defense_chain_id = defense_chain_result.chain.chain_id if defense_chain_result else None

        return ExecutiveSummaryArtifact(
            summary_id=str(uuid.uuid4()),
            case_id=inp.case_id,
            run_id=inp.run_id,
            top5_decisive_issues=top5,
            top3_immediate_actions=top3_actions,
            action_recommendation_id=rec_id,
            top3_adversary_optimal_attacks=top3_attacks,
            adversary_attack_chain_id=inp.adversary_attack_chain.chain_id,
            defense_chain_id=defense_chain_id,
            current_most_stable_claim=claim_text,
            claim_decomposition=claim_decomposition,
            strategic_summary=strategic_summary,
            amount_report_id=inp.amount_calculation_report.report_id,
            critical_evidence_gaps=critical_gaps,
            structured_output=structured,
            primary_risk=primary_risk,
            next_best_action=next_action,
            internal_decision_summary=internal_decision,
        )

    # ------------------------------------------------------------------
    # 内部构建方法 / Internal builders
    # ------------------------------------------------------------------

    def _top5_decisive_issues(self, issues: list[Issue]) -> list[str]:
        """按 composite_score DESC 排序，fallback 到 outcome_impact 优先级，返回前 5 个 issue_id。

        composite_score 为 None 时按 outcome_impact 排序（向后兼容）。
        """
        sorted_issues = sorted(
            issues,
            key=lambda i: (
                -(i.composite_score or 0),
                _IMPACT_PRIORITY.get(i.outcome_impact, 99),
            ),
        )
        return [i.issue_id for i in sorted_issues[:5]]

    def _top3_immediate_actions(
        self, recommendation: Optional[ActionRecommendation]
    ) -> tuple[list[str] | str, Optional[str]]:
        """从 ActionRecommendation 提取 Top3 立即行动（文本形式）。

        P1.8 缺失（recommendation=None）时返回 ("未启用", None)。
        优先级顺序：
        1. claims_to_abandon（最高：立即止损）→ 返回 abandon_reason 文本
        2. evidence_supplement_priorities（ROI 已排序的 gap_id）→ 保留 gap_id（通常可读）
        3. recommended_claim_amendments（修改诉请）→ 返回 amendment_description 文本
        4. trial_explanation_priorities（庭审解释）→ 返回 explanation_text 文本
        """
        if recommendation is None:
            return "未启用", None

        items: list[str] = []
        items.extend(s.abandon_reason for s in recommendation.claims_to_abandon)
        items.extend(recommendation.evidence_supplement_priorities)
        items.extend(a.amendment_description for a in recommendation.recommended_claim_amendments)
        items.extend(p.explanation_text for p in recommendation.trial_explanation_priorities)

        return items[:3], recommendation.recommendation_id

    def _top3_adversary_attacks(self, chain: OptimalAttackChain) -> list[str]:
        """提取对方 OptimalAttackChain 的 Top3 攻击节点 ID。

        来源必须是已生成的 OptimalAttackChain，不独立生成。
        """
        return [a.attack_node_id for a in chain.top_attacks[:3]]

    def _compute_strategic_summary(
        self,
        action_rec: Optional[ActionRecommendation],
        report: AmountCalculationReport,
    ) -> Optional[str]:
        """生成核心策略摘要（strategic_summary 字段）。

        仅当 ActionRecommendation 包含 strategic_headline 时输出；
        amount_dispute 类型额外附加金额附注。
        """
        if not action_rec or not action_rec.strategic_headline:
            return None
        category = action_rec.case_dispute_category or "general"
        headline = f"核心策略（{category}）：{action_rec.strategic_headline}"
        if category == "amount_dispute":
            amount_note = self._amount_summary(report)
            return f"{headline}（{amount_note}）"
        return headline

    def _current_most_stable_claim(self, report: AmountCalculationReport) -> str:
        """生成最稳诉请说明文本（金额语义，不含策略层）。

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

    def _build_structured_output(
        self,
        issues: list[Issue],
        top5_issue_ids: list[str],
        top3_actions: list[str] | str,
        top3_attacks: list[str],
        critical_gaps: list[str] | str,
        amount_report: AmountCalculationReport,
        action_recommendation: Optional[ActionRecommendation],
        defense_chain_result: Optional[DefenseChainResult] = None,
    ) -> ExecutiveSummaryStructuredOutput:
        """构建 P2 结构化 JSON 输出（纯规则层）。

        从已有叙述性产物中提取关键信息，生成机器可读的结构化摘要。
        """
        # case_overview: 案件基本情况
        issue_count = len(issues)
        high_count = sum(1 for i in issues if i.outcome_impact == OutcomeImpact.high)
        overview = (
            f"案件共有 {issue_count} 个争点，其中 {high_count} 个高影响争点。"
            f"绑定金额报告 {amount_report.report_id}。"
        )
        if action_recommendation and action_recommendation.strategic_headline:
            overview = f"{action_recommendation.strategic_headline}。{overview}"

        # key_findings: 从 top5 争点提取
        issue_map = {i.issue_id: i for i in issues}
        key_findings: list[str] = []
        for issue_id in top5_issue_ids:
            issue = issue_map.get(issue_id)
            if issue is None:
                continue
            impact_str = issue.outcome_impact.value if issue.outcome_impact else "未评估"
            key_findings.append(f"争点「{issue.title}」影响程度：{impact_str}")

        # risk_assessment: 基于高影响争点和攻击链
        if high_count > 0:
            risk_assessment = (
                f"存在 {high_count} 个高影响争点，"
                f"对方最优攻击节点 {len(top3_attacks)} 个，需重点防御。"
            )
        else:
            risk_assessment = f"无高影响争点，整体风险可控，对方攻击节点 {len(top3_attacks)} 个。"
        if isinstance(critical_gaps, list) and critical_gaps:
            risk_assessment += f" 存在 {len(critical_gaps)} 条关键缺证，建议优先补充。"
        if defense_chain_result:
            dc = defense_chain_result.chain
            risk_assessment += (
                f" 原告方已构建 {len(dc.defense_points)} 个防御论点"
                f"（置信度 {dc.confidence_score:.0%}）。"
            )

        # recommended_actions: 来自 top3_immediate_actions
        if isinstance(top3_actions, list):
            recommended_actions = [f"执行行动 {aid}" for aid in top3_actions]
        else:
            recommended_actions = ["P1.8 行动建议未启用，建议人工审查"]

        # confidence_metrics: 基于证据 + 争点评估完整度
        evaluated_count = sum(1 for i in issues if i.outcome_impact is not None)
        evidence_completeness = evaluated_count / issue_count if issue_count > 0 else 0.0

        gaps_count = len(critical_gaps) if isinstance(critical_gaps, list) else 0
        legal_clarity = max(0.0, 1.0 - gaps_count * 0.15)

        overall_confidence = (evidence_completeness + legal_clarity) / 2.0

        confidence_metrics = ConfidenceMetrics(
            overall_confidence=round(overall_confidence, 3),
            evidence_completeness=round(evidence_completeness, 3),
            legal_clarity=round(legal_clarity, 3),
        )

        return ExecutiveSummaryStructuredOutput(
            case_overview=overview,
            key_findings=key_findings,
            risk_assessment=risk_assessment,
            recommended_actions=recommended_actions,
            confidence_metrics=confidence_metrics,
        )

    # ------------------------------------------------------------------
    # v7: 新增构建方法 / v7 builders
    # ------------------------------------------------------------------

    def _build_claim_decomposition(
        self,
        report: AmountCalculationReport,
        decision_tree: Optional[DecisionPathTree],
    ) -> Optional[ClaimDecomposition]:
        """构建 v7 诉请拆分。

        formal_claim:            诉请总额
        fallback_anchor:         路径树最现实路径支持的金额（无路径树时 = formal_claim）
        expected_recovery_range: [lower, upper]
        """
        table = report.claim_calculation_table
        if not table:
            return None

        formal = sum(e.claimed_amount for e in table)
        # 若有计算值，使用最小 delta 对应的 calculated_amount 作为 fallback
        calculable = [e for e in table if e.calculated_amount is not None]
        if calculable:
            fallback_total = sum(e.calculated_amount for e in calculable)
            # 加上不可计算的部分（保守按 claimed_amount 计入）
            non_calc = [e for e in table if e.calculated_amount is None]
            fallback_total += sum(e.claimed_amount for e in non_calc)
        else:
            fallback_total = formal

        # 路径树调整：如果最可能路径对被告有利，fallback 下调 30%
        if decision_tree and decision_tree.most_likely_path:
            for path in decision_tree.paths:
                if path.path_id == decision_tree.most_likely_path:
                    if path.party_favored == "defendant":
                        fallback_total = fallback_total * Decimal("0.7")
                    break

        fallback_total = min(fallback_total, formal)
        # 预期回收区间：下界=fallback*0.7，上界=min(formal, fallback*1.2)
        lower = max(Decimal("0"), fallback_total * Decimal("0.7"))
        upper = min(formal, fallback_total * Decimal("1.2"))

        return ClaimDecomposition(
            formal_claim=formal,
            fallback_anchor=fallback_total,
            expected_recovery_lower=lower,
            expected_recovery_upper=upper,
            decomposition_rationale=(
                f"正式诉请 {formal}，系统计算保底 {fallback_total}，预期回收 [{lower}, {upper}]"
            ),
        )

    def _build_internal_decision_summary(
        self,
        issues: list[Issue],
        decision_tree: Optional[DecisionPathTree],
        critical_gaps: list[str] | str,
    ) -> Optional[InternalDecisionSummary]:
        """构建 v7 内部决策版本摘要。"""
        winner = "uncertain"
        rationale = ""

        if decision_tree and decision_tree.most_likely_path:
            for path in decision_tree.paths:
                if path.path_id == decision_tree.most_likely_path:
                    winner = path.party_favored
                    rationale = (
                        f"最可能路径 {path.path_id} 有利于 {path.party_favored}"
                        f"（概率 {path.probability:.0%}）：{path.trigger_condition}"
                    )
                    break

        priority_gap = None
        gap_rationale = ""
        if isinstance(critical_gaps, list) and critical_gaps:
            priority_gap = critical_gaps[0]
            gap_rationale = f"ROI 排序最高的缺证项 {priority_gap}"

        return InternalDecisionSummary(
            most_likely_winner=winner,
            most_likely_winner_rationale=rationale,
            priority_evidence_to_supplement=priority_gap,
            priority_supplement_rationale=gap_rationale,
        )

    def _compute_primary_risk(
        self,
        issues: list[Issue],
        top3_attacks: list[str],
    ) -> Optional[str]:
        """计算主要风险点（一句话）。"""
        high_issues = [i for i in issues if i.outcome_impact == OutcomeImpact.high]
        if not high_issues:
            return None
        worst = high_issues[0]
        return f"高影响争点「{worst.title}」" + (
            f"面临 {len(top3_attacks)} 个对方攻击节点" if top3_attacks else ""
        )

    def _compute_next_best_action(
        self,
        top3_actions: list[str] | str,
        critical_gaps: list[str] | str,
        recommendation: Optional[ActionRecommendation],
    ) -> Optional[str]:
        """计算下一步最优行动（一句话）。"""
        if isinstance(top3_actions, list) and top3_actions:
            return top3_actions[0]
        if isinstance(critical_gaps, list) and critical_gaps:
            return f"优先补证：{critical_gaps[0]}"
        return None

    @staticmethod
    def _amount_summary(report: AmountCalculationReport) -> str:
        """生成简短的金额附注（用于策略性输出中的金额上下文）。"""
        table = report.claim_calculation_table
        if not table:
            return f"绑定 {report.report_id}"
        consistent = [e for e in table if e.delta is not None and e.delta == 0]
        if consistent:
            best = consistent[0]
            return f"诉请 {best.claim_type.value} {best.claimed_amount} delta=0"
        calculable = [e for e in table if e.delta is not None]
        if calculable:
            best = min(calculable, key=lambda e: abs(e.delta))
            return f"诉请 {best.claim_type.value} {best.claimed_amount} delta={best.delta}"
        return f"绑定 {report.report_id}"
