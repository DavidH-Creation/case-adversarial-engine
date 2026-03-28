"""
CredibilityScorer — 整体可信度折损引擎主类（P2.9）。
Credibility Scorer — rule-based credibility deduction engine for P2.9.

职责 / Responsibilities:
1. 接收 CredibilityScorerInput（amount_report, evidence_list, issue_list）
2. 按 6 条预置规则独立判断触发条件（零 LLM 调用）
3. 每条触发规则生成一个 CredibilityDeduction
4. 汇总为 CredibilityScorecard（base_score=100，final_score 由规则层计算）

合约保证 / Contract guarantees:
- 零 LLM 调用（纯规则层，可通过调用链追踪验证）
- 每条规则最多产生一个 CredibilityDeduction
- final_score = base_score + sum(deduction_points)，由 model_validator 强制校验
- final_score < 60 时 summary 包含可信度警告

预置规则 / Preset rules:
- CRED-01: 存在未解释的金额口径冲突 (-20)
- CRED-02: 关键证据仅有复印件，无原件 (-10)
- CRED-03: 同一证据在不同文件中金额不一致 (-15)
         (实现映射：text_table_amount_consistent == False)
- CRED-04: 证人证言与书证存在明显矛盾 (-10)
- CRED-05: 关键时间节点缺乏证据支撑 (-10)
- CRED-06: 存在被质疑真实性但未给出解释的证据 (-5)
"""
from __future__ import annotations

import uuid

from engines.shared.models import (
    AmountCalculationReport,
    AttackStrength,
    CredibilityDeduction,
    CredibilityScorecard,
    Evidence,
    EvidenceStatus,
    EvidenceStrength,
    EvidenceType,
    Issue,
    Party,
    RecommendedAction,
)
from engines.shared.rule_config import RuleThresholds

from .schemas import CredibilityScorerInput

# 规则定义表（rule_id → (description, deduction_points)）
_RULES: dict[str, tuple[str, int]] = {
    "CRED-01": ("存在未解释的金额口径冲突", -20),
    "CRED-02": ("关键证据仅有复印件，无原件", -10),
    "CRED-03": ("同一证据在不同文件中金额不一致", -15),
    "CRED-04": ("证人证言与书证存在明显矛盾", -10),
    "CRED-05": ("关键时间节点缺乏证据支撑", -10),
    "CRED-06": ("存在被质疑真实性但未给出解释的证据", -5),
    "CRED-07": ("原告构成职业放贷人（放贷频次、对象达标）", -25),
}


class CredibilityScorer:
    """整体可信度折损引擎（P2.9）。

    纯规则层，不持有外部状态，可安全复用同一实例。

    使用方式 / Usage:
        scorer = CredibilityScorer()
        result = scorer.score(inp)
    """

    def __init__(self, thresholds: RuleThresholds | None = None):
        self._thresholds = thresholds or RuleThresholds()

    def score(self, inp: CredibilityScorerInput) -> CredibilityScorecard:
        """执行可信度折损评分，返回 CredibilityScorecard。

        Args:
            inp: 引擎输入（含 case_id、run_id、amount_report、evidence_list、issue_list）

        Returns:
            CredibilityScorecard — 含所有触发的扣分项和最终得分
        """
        # 构建证据 ID → Evidence 快查映射
        evidence_map: dict[str, Evidence] = {e.evidence_id: e for e in inp.evidence_list}

        deductions: list[CredibilityDeduction] = []

        cred01 = self._check_cred01(inp.amount_report)
        if cred01:
            deductions.append(cred01)

        cred02 = self._check_cred02(inp.evidence_list)
        if cred02:
            deductions.append(cred02)

        cred03 = self._check_cred03(inp.amount_report)
        if cred03:
            deductions.append(cred03)

        cred04 = self._check_cred04(inp.issue_list, evidence_map)
        if cred04:
            deductions.append(cred04)

        cred05 = self._check_cred05(inp.issue_list)
        if cred05:
            deductions.append(cred05)

        cred06 = self._check_cred06(inp.evidence_list)
        if cred06:
            deductions.append(cred06)

        cred07 = self._check_cred07(inp.party_list)
        if cred07:
            deductions.append(cred07)

        base_score = 100
        final_score = base_score + sum(d.deduction_points for d in deductions)
        summary = self._build_summary(final_score, deductions)

        return CredibilityScorecard(
            scorecard_id=str(uuid.uuid4()),
            case_id=inp.case_id,
            run_id=inp.run_id,
            base_score=base_score,
            deductions=deductions,
            final_score=final_score,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # 规则检测方法 / Rule check methods
    # ------------------------------------------------------------------

    def _check_cred01(self, report: AmountCalculationReport) -> CredibilityDeduction | None:
        """CRED-01: 存在未解释的金额口径冲突。"""
        conflicts = report.consistency_check_result.unresolved_conflicts
        if not conflicts:
            return None
        evidence_ids: list[str] = []
        for c in conflicts:
            if c.source_a_evidence_id:
                evidence_ids.append(c.source_a_evidence_id)
            if c.source_b_evidence_id:
                evidence_ids.append(c.source_b_evidence_id)
        desc, pts = _RULES["CRED-01"]
        return CredibilityDeduction(
            deduction_id=str(uuid.uuid4()),
            rule_id="CRED-01",
            rule_description=desc,
            deduction_points=pts,
            trigger_evidence_ids=list(dict.fromkeys(evidence_ids)),  # 去重，保序
        )

    def _check_cred02(self, evidence_list: list[Evidence]) -> CredibilityDeduction | None:
        """CRED-02: 关键证据仅有复印件，无原件（evidence.is_copy_only == True）。"""
        copy_ids = [e.evidence_id for e in evidence_list if e.is_copy_only]
        if not copy_ids:
            return None
        desc, pts = _RULES["CRED-02"]
        return CredibilityDeduction(
            deduction_id=str(uuid.uuid4()),
            rule_id="CRED-02",
            rule_description=desc,
            deduction_points=pts,
            trigger_evidence_ids=copy_ids,
        )

    def _check_cred03(self, report: AmountCalculationReport) -> CredibilityDeduction | None:
        """CRED-03: 同一证据在不同文件中金额不一致。

        实现映射：text_table_amount_consistent == False 表示报告中叙述文本与计算表格金额不一致，
        是"同一材料在不同呈现形式中金额不一致"的可用信号（规则层现有最佳代理）。
        与 CRED-01（unresolved_conflicts 非空，即不同证据间存在口径冲突）为不同信号，无重叠。
        """
        if report.consistency_check_result.text_table_amount_consistent:
            return None
        desc, pts = _RULES["CRED-03"]
        return CredibilityDeduction(
            deduction_id=str(uuid.uuid4()),
            rule_id="CRED-03",
            rule_description=desc,
            deduction_points=pts,
        )

    def _check_cred04(
        self, issue_list: list[Issue], evidence_map: dict[str, Evidence]
    ) -> CredibilityDeduction | None:
        """CRED-04: 证人证言与书证存在明显矛盾。

        触发条件：某 Issue 的 evidence_ids 中同时含有 witness_statement 型和 documentary 型证据，
        且该 Issue 的 opponent_attack_strength == strong。
        """
        trigger_issue_ids: list[str] = []
        trigger_evidence_ids: list[str] = []

        for issue in issue_list:
            if issue.opponent_attack_strength != AttackStrength.strong:
                continue
            types_in_issue = {
                evidence_map[eid].evidence_type
                for eid in issue.evidence_ids
                if eid in evidence_map
            }
            if (
                EvidenceType.witness_statement in types_in_issue
                and EvidenceType.documentary in types_in_issue
            ):
                trigger_issue_ids.append(issue.issue_id)
                trigger_evidence_ids.extend(
                    eid
                    for eid in issue.evidence_ids
                    if eid in evidence_map
                    and evidence_map[eid].evidence_type
                    in (EvidenceType.witness_statement, EvidenceType.documentary)
                )

        if not trigger_issue_ids:
            return None

        desc, pts = _RULES["CRED-04"]
        return CredibilityDeduction(
            deduction_id=str(uuid.uuid4()),
            rule_id="CRED-04",
            rule_description=desc,
            deduction_points=pts,
            trigger_issue_ids=trigger_issue_ids,
            trigger_evidence_ids=list(dict.fromkeys(trigger_evidence_ids)),
        )

    def _check_cred05(self, issue_list: list[Issue]) -> CredibilityDeduction | None:
        """CRED-05: 关键时间节点缺乏证据支撑。

        触发条件：存在 proponent_evidence_strength == weak 且
        recommended_action == supplement_evidence 的争点。
        """
        trigger_issue_ids = [
            issue.issue_id
            for issue in issue_list
            if (
                issue.proponent_evidence_strength == EvidenceStrength.weak
                and issue.recommended_action == RecommendedAction.supplement_evidence
            )
        ]
        if not trigger_issue_ids:
            return None
        desc, pts = _RULES["CRED-05"]
        return CredibilityDeduction(
            deduction_id=str(uuid.uuid4()),
            rule_id="CRED-05",
            rule_description=desc,
            deduction_points=pts,
            trigger_issue_ids=trigger_issue_ids,
        )

    def _check_cred06(self, evidence_list: list[Evidence]) -> CredibilityDeduction | None:
        """CRED-06: 存在被质疑真实性但未给出解释的证据。

        触发条件：evidence.status == challenged 且 admissibility_notes 为空/None。
        """
        trigger_ids = [
            e.evidence_id
            for e in evidence_list
            if e.status == EvidenceStatus.challenged and not e.admissibility_notes
        ]
        if not trigger_ids:
            return None
        desc, pts = _RULES["CRED-06"]
        return CredibilityDeduction(
            deduction_id=str(uuid.uuid4()),
            rule_id="CRED-06",
            rule_description=desc,
            deduction_points=pts,
            trigger_evidence_ids=trigger_ids,
        )

    def _check_cred07(self, party_list: list[Party]) -> CredibilityDeduction | None:
        """CRED-07: 原告构成职业放贷人。

        触发条件：原告方（side="plaintiff"）的 litigation_history 中，
        lending_case_count 达到阈值且 distinct_borrower_count 达到阈值，
        且时间窗口在上限内。仅检查原告，被告满足条件不触发。
        """
        t = self._thresholds
        for party in party_list:
            if party.side != "plaintiff":
                continue
            hist = party.litigation_history
            if hist is None:
                continue
            if (
                hist.lending_case_count >= t.prof_lender_min_cases
                and hist.distinct_borrower_count >= t.prof_lender_min_borrowers
                and hist.time_span_months <= t.prof_lender_max_span_months
            ):
                desc, pts = _RULES["CRED-07"]
                return CredibilityDeduction(
                    deduction_id=str(uuid.uuid4()),
                    rule_id="CRED-07",
                    rule_description=desc,
                    deduction_points=pts,
                )
        return None

    # ------------------------------------------------------------------
    # 摘要生成 / Summary builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_summary(final_score: int, deductions: list[CredibilityDeduction]) -> str:
        """生成可信度摘要说明。final_score < 60 时包含可信度警告。"""
        if not deductions:
            return f"案件可信度良好，无扣分项，最终得分 {final_score} 分。"

        rule_list = "、".join(d.rule_id for d in deductions)
        base = f"触发扣分规则：{rule_list}，最终可信度得分 {final_score} 分。"
        if final_score < 60:
            return f"【可信度警告】{base} 得分低于 60 分，建议在报告显著位置标注可信度风险。"
        return base
