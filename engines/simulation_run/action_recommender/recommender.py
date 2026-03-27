"""
ActionRecommender — 行动建议引擎主类（P1.8）。
Action Recommender — rule-based aggregation engine for P1.8.

职责 / Responsibilities:
1. 接收 ActionRecommenderInput（issues, evidence_gap_list, amount_report）
2. 从 recommended_action=amend_claim 的争点派生 ClaimAmendmentSuggestion
3. 从 recommended_action=abandon 的争点派生 ClaimAbandonSuggestion
4. 从 recommended_action=explain_in_trial 的争点派生 TrialExplanationPriority
5. 从 evidence_gap_list 按 roi_rank 升序派生 evidence_supplement_priorities（gap_id 列表）
6. 返回 ActionRecommendation

合约保证 / Contract guarantees:
- 零 LLM 调用（纯规则层，可通过调用链追踪验证）
- 每个 ClaimAbandonSuggestion 必须绑定 issue_id 和 abandon_reason——零容忍
- 每个 TrialExplanationPriority 必须绑定 issue_id——零容忍
- evidence_supplement_priorities 中的 gap_id 来自输入的 evidence_gap_list
"""
from __future__ import annotations

import uuid

from engines.shared.models import (
    ActionRecommendation,
    ClaimAbandonSuggestion,
    ClaimAmendmentSuggestion,
    EvidenceGapItem,
    Issue,
    RecommendedAction,
    TrialExplanationPriority,
)

from .schemas import ActionRecommenderInput


class ActionRecommender:
    """行动建议引擎（P1.8）。

    纯规则层，不持有外部状态，可安全复用同一实例。

    使用方式 / Usage:
        recommender = ActionRecommender()
        result = recommender.recommend(inp)
    """

    def recommend(self, inp: ActionRecommenderInput) -> ActionRecommendation:
        """执行行动建议聚合，返回 ActionRecommendation。

        Args:
            inp: 引擎输入（含 case_id、run_id、issue_list、evidence_gap_list、amount_report）

        Returns:
            ActionRecommendation — 含四类建议列表
        """
        amendments = self._build_amendments(inp.issue_list)
        abandon_suggestions = self._build_abandon_suggestions(inp.issue_list)
        trial_explanations = self._build_trial_explanations(inp.issue_list)
        gap_ids = self._build_evidence_priorities(inp.evidence_gap_list)

        return ActionRecommendation(
            recommendation_id=str(uuid.uuid4()),
            case_id=inp.case_id,
            run_id=inp.run_id,
            recommended_claim_amendments=amendments,
            evidence_supplement_priorities=gap_ids,
            trial_explanation_priorities=trial_explanations,
            claims_to_abandon=abandon_suggestions,
        )

    # ------------------------------------------------------------------
    # 内部构建方法 / Internal builders
    # ------------------------------------------------------------------

    def _build_amendments(self, issues: list[Issue]) -> list[ClaimAmendmentSuggestion]:
        """从 recommended_action=amend_claim 的争点派生修改建议。

        每个 related_claim_id 生成一条 ClaimAmendmentSuggestion。
        争点无 related_claim_ids 时跳过。
        """
        result: list[ClaimAmendmentSuggestion] = []
        for issue in issues:
            if issue.recommended_action != RecommendedAction.amend_claim:
                continue
            for claim_id in issue.related_claim_ids:
                result.append(
                    ClaimAmendmentSuggestion(
                        suggestion_id=str(uuid.uuid4()),
                        original_claim_id=claim_id,
                        amendment_description=self._amendment_description(issue),
                        amendment_reason_issue_id=issue.issue_id,
                        amendment_reason_evidence_ids=list(issue.evidence_ids),
                    )
                )
        return result

    def _build_abandon_suggestions(self, issues: list[Issue]) -> list[ClaimAbandonSuggestion]:
        """从 recommended_action=abandon 的争点派生放弃建议。

        每个 related_claim_id 生成一条 ClaimAbandonSuggestion。
        争点无 related_claim_ids 时跳过。
        """
        result: list[ClaimAbandonSuggestion] = []
        for issue in issues:
            if issue.recommended_action != RecommendedAction.abandon:
                continue
            for claim_id in issue.related_claim_ids:
                result.append(
                    ClaimAbandonSuggestion(
                        suggestion_id=str(uuid.uuid4()),
                        claim_id=claim_id,
                        abandon_reason=self._abandon_reason(issue),
                        abandon_reason_issue_id=issue.issue_id,
                    )
                )
        return result

    def _build_trial_explanations(self, issues: list[Issue]) -> list[TrialExplanationPriority]:
        """从 recommended_action=explain_in_trial 的争点派生庭审解释优先事项。

        每个争点生成一条 TrialExplanationPriority。
        """
        result: list[TrialExplanationPriority] = []
        for issue in issues:
            if issue.recommended_action != RecommendedAction.explain_in_trial:
                continue
            result.append(
                TrialExplanationPriority(
                    priority_id=str(uuid.uuid4()),
                    issue_id=issue.issue_id,
                    explanation_text=self._explanation_text(issue),
                )
            )
        return result

    def _build_evidence_priorities(self, gaps: list[EvidenceGapItem]) -> list[str]:
        """从 evidence_gap_list 按 roi_rank 升序排序，返回 gap_id 列表。

        roi_rank=1 代表最高优先级，排在列表最前。
        """
        sorted_gaps = sorted(gaps, key=lambda g: g.roi_rank)
        return [g.gap_id for g in sorted_gaps]

    # ------------------------------------------------------------------
    # 文本派生辅助方法 / Text derivation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _amendment_description(issue: Issue) -> str:
        """从争点信息派生修改建议描述。

        优先使用 recommended_action_basis，否则使用 issue.title。
        """
        if issue.recommended_action_basis:
            return issue.recommended_action_basis
        return f"建议修改与争点「{issue.title}」相关的诉请"

    @staticmethod
    def _abandon_reason(issue: Issue) -> str:
        """从争点信息派生放弃理由。

        优先使用 recommended_action_basis，否则使用 issue.title。
        """
        if issue.recommended_action_basis:
            return issue.recommended_action_basis
        return f"争点「{issue.title}」证据不足，建议放弃相关诉请以减少败诉风险"

    @staticmethod
    def _explanation_text(issue: Issue) -> str:
        """从争点信息派生庭审解释文本。

        优先使用 recommended_action_basis，否则使用 issue.title。
        """
        if issue.recommended_action_basis:
            return issue.recommended_action_basis
        return f"庭审中需优先解释争点「{issue.title}」相关事实"
