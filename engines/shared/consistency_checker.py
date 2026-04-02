"""
ConsistencyChecker — 输出前一致性校验模块（v7）。
Consistency Checker — pre-output consistency validation for v7.

职责 / Responsibilities:
1. 视角一致性：同一 section 不混用中立评估和一方策略建议
2. 推荐一致性：推荐结果与路径树整体态势对齐
3. 可采性闸门：证据可采性不明时限制争点最大权重
4. 强论点降权：被强反证的证据/孤证已降权
5. 行动建议对齐：建议方向与当前立场和路径判断一致

合约保证 / Contract guarantees:
- 纯规则层（零 LLM 调用）
- 校验失败时返回 sections_to_regenerate 列表
- 不修改输入数据，仅返回校验结果
"""

from __future__ import annotations

import logging
from typing import Optional

from engines.shared.models import (
    ActionRecommendation,
    AdmissibilityStatus,
    ConsistencyCheckResult,
    DecisionPathTree,
    Evidence,
    Issue,
    OutcomeImpact,
    Perspective,
    ReportArtifact,
    ReportSection,
)

logger = logging.getLogger(__name__)


class ConsistencyChecker:
    """输出前一致性校验器（v7）。

    纯规则层，不持有外部状态，可安全复用同一实例。

    使用方式 / Usage:
        checker = ConsistencyChecker()
        result = checker.check(
            report=report_artifact,
            decision_tree=decision_tree,
            recommendation=action_recommendation,
            evidence_list=evidence_list,
            issue_list=issue_list,
        )
    """

    def check(
        self,
        report: Optional[ReportArtifact] = None,
        decision_tree: Optional[DecisionPathTree] = None,
        recommendation: Optional[ActionRecommendation] = None,
        evidence_list: Optional[list[Evidence]] = None,
        issue_list: Optional[list[Issue]] = None,
    ) -> ConsistencyCheckResult:
        """执行全部五项一致性校验。

        Args:
            report:         报告产物（用于视角一致性校验）
            decision_tree:  裁判路径树（用于推荐一致性和行动对齐校验）
            recommendation: 行动建议产物（用于推荐一致性和行动对齐校验）
            evidence_list:  证据列表（用于强论点降权和可采性闸门校验）
            issue_list:     争点列表（用于可采性闸门校验）

        Returns:
            ConsistencyCheckResult — 含 overall_pass + 各项结果 + 失败原因 + 需重生成 sections
        """
        failures: list[str] = []
        sections_to_regenerate: list[str] = []

        # 1. 视角一致性
        perspective_ok = self._check_perspective_consistency(
            report,
            failures,
            sections_to_regenerate,
        )

        # 2. 推荐一致性
        recommendation_ok = self._check_recommendation_consistency(
            decision_tree,
            recommendation,
            failures,
            sections_to_regenerate,
        )

        # 3. 可采性闸门
        admissibility_ok = self._check_admissibility_gate(
            evidence_list,
            issue_list,
            failures,
        )

        # 4. 强论点降权
        demotion_ok = self._check_strong_argument_demotion(
            evidence_list,
            issue_list,
            failures,
        )

        # 5. 行动建议对齐
        action_ok = self._check_action_stance_alignment(
            decision_tree,
            recommendation,
            failures,
            sections_to_regenerate,
        )

        overall = all(
            [
                perspective_ok,
                recommendation_ok,
                admissibility_ok,
                demotion_ok,
                action_ok,
            ]
        )

        return ConsistencyCheckResult(
            overall_pass=overall,
            perspective_consistent=perspective_ok,
            recommendation_consistent=recommendation_ok,
            admissibility_gate_passed=admissibility_ok,
            strong_argument_demoted=demotion_ok,
            action_stance_aligned=action_ok,
            failures=failures,
            sections_to_regenerate=list(dict.fromkeys(sections_to_regenerate)),
        )

    # ------------------------------------------------------------------
    # 1. 视角一致性 / Perspective consistency
    # ------------------------------------------------------------------

    def _check_perspective_consistency(
        self,
        report: Optional[ReportArtifact],
        failures: list[str],
        sections_to_regen: list[str],
    ) -> bool:
        """同一 section 内不得混用中立评估和一方策略建议。

        规则：
        - perspective=neutral 的 section 中 key_conclusions 不得含有
          target_party 指向性的行动建议
        - perspective=plaintiff/defendant 的 section 中结论必须服务于该方
        """
        if report is None:
            return True

        ok = True
        for section in report.sections:
            if not hasattr(section, "perspective"):
                continue

            if section.perspective == Perspective.neutral:
                # 检查结论中是否含有偏向性表述（简化检测：检查标题关键词）
                body_lower = section.body.lower() if section.body else ""
                partisan_keywords = [
                    "建议原告",
                    "建议被告",
                    "原告应",
                    "被告应",
                    "plaintiff should",
                    "defendant should",
                ]
                for kw in partisan_keywords:
                    if kw in body_lower:
                        ok = False
                        failures.append(
                            f"section [{section.section_id}] perspective=neutral "
                            f"但包含偏向性表述「{kw}」"
                        )
                        sections_to_regen.append(section.section_id)
                        break
        return ok

    # ------------------------------------------------------------------
    # 2. 推荐一致性 / Recommendation consistency
    # ------------------------------------------------------------------

    def _check_recommendation_consistency(
        self,
        decision_tree: Optional[DecisionPathTree],
        recommendation: Optional[ActionRecommendation],
        failures: list[str],
        sections_to_regen: list[str],
    ) -> bool:
        """若整体态势偏被告、且最可能路径对被告有利，
        则原告侧的建议（如 strategic_headline）不应呈现"全额稳拿"风格。

        修订清单一-3 硬约束：发现冲突时标记需重写。
        """
        if decision_tree is None or recommendation is None:
            return True

        # 判断整体态势
        most_likely = None
        if decision_tree.most_likely_path:
            for path in decision_tree.paths:
                if path.path_id == decision_tree.most_likely_path:
                    most_likely = path
                    break

        if most_likely is None or most_likely.party_favored != "defendant":
            return True  # 非被告有利态势，无需校验

        # 检查 strategic_headline 是否仍在暗示原告全额胜诉
        headline = recommendation.strategic_headline or ""
        overconfident_signals = [
            "全额",
            "稳拿",
            "必胜",
            "确保获赔",
            "完全支持",
            "full recovery",
            "certain win",
        ]
        for signal in overconfident_signals:
            if signal in headline:
                failures.append(
                    f"推荐一致性冲突：最可能路径对被告有利"
                    f"（path={most_likely.path_id}, prob={most_likely.probability:.0%}），"
                    f"但 strategic_headline 含「{signal}」"
                )
                # 标记 recommendation 相关 section 需重生成
                sections_to_regen.append("action_recommendation")
                return False

        return True

    # ------------------------------------------------------------------
    # 3. 可采性闸门 / Admissibility gate
    # ------------------------------------------------------------------

    def _check_admissibility_gate(
        self,
        evidence_list: Optional[list[Evidence]],
        issue_list: Optional[list[Issue]],
        failures: list[str],
    ) -> bool:
        """证据可采性不明（uncertain/weak/excluded）时，
        依赖该证据的争点不得排在 outcome_impact=high 的第一位。

        修订清单一-4：程序性争点不能只因内容严重就排到第一。
        """
        if evidence_list is None or issue_list is None:
            return True

        # 构建"可采性有问题的证据 ID"集合
        problematic_eids: set[str] = set()
        for ev in evidence_list:
            if ev.admissibility_status in (
                AdmissibilityStatus.uncertain,
                AdmissibilityStatus.weak,
                AdmissibilityStatus.excluded,
            ):
                problematic_eids.add(ev.evidence_id)

        if not problematic_eids:
            return True

        ok = True
        for issue in issue_list:
            if issue.outcome_impact != OutcomeImpact.high:
                continue
            # 该争点的所有证据是否都有可采性问题？
            if issue.evidence_ids and all(eid in problematic_eids for eid in issue.evidence_ids):
                ok = False
                failures.append(
                    f"可采性闸门：争点 [{issue.issue_id}]「{issue.title}」"
                    f"标记为 high impact，但其全部证据可采性存疑"
                    f"（{issue.evidence_ids}），应限制其最大权重"
                )
        return ok

    # ------------------------------------------------------------------
    # 4. 强论点降权 / Strong argument demotion
    # ------------------------------------------------------------------

    def _check_strong_argument_demotion(
        self,
        evidence_list: Optional[list[Evidence]],
        issue_list: Optional[list[Issue]],
        failures: list[str],
    ) -> bool:
        """被强反证（dispute_ratio > 0.6）或孤证的证据，
        不应仍排在 top tier 争点的核心证据中。

        修订清单一-5：被 impeachment 的证据不能因"表面直观"仍排进 top tier。
        """
        if evidence_list is None or issue_list is None:
            return True

        # 构建"不稳定证据 ID"集合
        unstable_eids: set[str] = set()
        for ev in evidence_list:
            dr = ev.dispute_ratio
            if dr is not None and dr > 0.6:
                unstable_eids.add(ev.evidence_id)
            # 孤证：仅支持一个争点且有被攻击记录
            if ev.is_attacked_by and len(ev.supports) <= 1:
                unstable_eids.add(ev.evidence_id)

        if not unstable_eids:
            return True

        ok = True
        # 检查 high impact 争点是否仍依赖不稳定证据作为唯一支撑
        for issue in issue_list:
            if issue.outcome_impact != OutcomeImpact.high:
                continue
            if issue.evidence_ids and all(eid in unstable_eids for eid in issue.evidence_ids):
                ok = False
                failures.append(
                    f"强论点降权：争点 [{issue.issue_id}]「{issue.title}」"
                    f"为 high impact，但全部支撑证据均不稳定"
                    f"（被强反证或孤证），应降权"
                )
        return ok

    # ------------------------------------------------------------------
    # 5. 行动建议对齐 / Action-stance alignment
    # ------------------------------------------------------------------

    def _check_action_stance_alignment(
        self,
        decision_tree: Optional[DecisionPathTree],
        recommendation: Optional[ActionRecommendation],
        failures: list[str],
        sections_to_regen: list[str],
    ) -> bool:
        """行动建议必须与当前立场和路径判断一致。

        修订清单一-6：系统判断原告整体劣势时，不输出"全额稳拿"风格的动作建议。
        """
        if decision_tree is None or recommendation is None:
            return True

        # 判断整体态势
        most_likely = None
        if decision_tree.most_likely_path:
            for path in decision_tree.paths:
                if path.path_id == decision_tree.most_likely_path:
                    most_likely = path
                    break

        if most_likely is None:
            return True

        ok = True

        # 如果最可能路径对被告有利，原告 action plan 不应含攻击性建议
        if most_likely.party_favored == "defendant":
            plaintiff_plan = recommendation.plaintiff_action_plan
            if plaintiff_plan and plaintiff_plan.strategic_recommendations:
                for sr in plaintiff_plan.strategic_recommendations:
                    aggressive_signals = [
                        "全额主张",
                        "坚持全额",
                        "加大力度",
                        "扩大诉请",
                    ]
                    for signal in aggressive_signals:
                        if signal in sr.recommendation_text:
                            ok = False
                            failures.append(
                                f"行动对齐冲突：整体态势偏被告"
                                f"（path={most_likely.path_id}），"
                                f"但原告建议含攻击性表述「{signal}」"
                            )
                            sections_to_regen.append("plaintiff_action_plan")
                            break

        # 如果最可能路径对原告有利，被告 action plan 不应暗示"稳赢"
        if most_likely.party_favored == "plaintiff":
            defendant_plan = recommendation.defendant_action_plan
            if defendant_plan and defendant_plan.strategic_recommendations:
                for sr in defendant_plan.strategic_recommendations:
                    overconfident = ["必胜", "稳赢", "原告必败"]
                    for signal in overconfident:
                        if signal in sr.recommendation_text:
                            ok = False
                            failures.append(
                                f"行动对齐冲突：整体态势偏原告"
                                f"（path={most_likely.path_id}），"
                                f"但被告建议含「{signal}」"
                            )
                            sections_to_regen.append("defendant_action_plan")
                            break

        return ok

    def _check_recommendation_consistency(
        self,
        decision_tree: Optional[DecisionPathTree],
        recommendation: Optional[ActionRecommendation],
        failures: list[str],
        sections_to_regen: list[str],
    ) -> bool:
        """Check recommendation consistency without exposing probability wording."""
        if decision_tree is None or recommendation is None:
            return True

        most_likely = None
        if decision_tree.most_likely_path:
            for path in decision_tree.paths:
                if path.path_id == decision_tree.most_likely_path:
                    most_likely = path
                    break

        if most_likely is None or most_likely.party_favored != "defendant":
            return True

        headline = recommendation.strategic_headline or ""
        overconfident_signals = [
            "鍏ㄩ",
            "绋虫嬁",
            "蹇呰儨",
            "纭繚鑾疯禂",
            "瀹屽叏鏀寔",
            "full recovery",
            "certain win",
        ]
        for signal in overconfident_signals:
            if signal in headline:
                failures.append(
                    "推荐一致性冲突：首位路径对被告更有利"
                    f"（path={most_likely.path_id}, favored={most_likely.party_favored}），"
                    f"但 strategic_headline 仍包含“{signal}”。"
                )
                sections_to_regen.append("action_recommendation")
                return False

        return True
