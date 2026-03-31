"""
AlternativeClaimGenerator — 替代主张自动生成引擎（P2.11）。
Alternative Claim Generator — rule-based auto-generation engine for P2.11.

职责 / Responsibilities:
1. 接收 AlternativeClaimGeneratorInput（issues, amount_report）
2. 按三个触发条件检测不稳定主张
3. 按 original_claim_id 去重聚合所有触发信息
4. 返回 list[AlternativeClaimSuggestion]

触发条件 / Trigger conditions（规则层，零 LLM）:
1. Issue.recommended_action = amend_claim
2. Issue.proponent_evidence_strength = weak 且 opponent_attack_strength = strong
3. ClaimCalculationEntry.delta 绝对值超过 claimed_amount × 10%（且 claimed_amount > 0）

合约保证 / Contract guarantees:
- 零 LLM 调用（纯规则层，可通过调用链追踪验证）
- instability_issue_ids 永远非空——AlternativeClaimSuggestion 模型 min_length=1 强制
- 每个 original_claim_id 恰好输出一条建议（去重聚合）
- 无相关争点时，条件3触发的 claim 不生成建议（无法满足 instability_issue_ids 非空约束）
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from decimal import Decimal

from engines.shared.models import (
    AlternativeClaimSuggestion,
    AttackStrength,
    EvidenceStrength,
    Issue,
    RecommendedAction,
)

from .schemas import AlternativeClaimGeneratorInput

# 条件3 delta 阈值（严格大于 10% 才触发）
_DELTA_THRESHOLD = Decimal("0.10")


class _TriggerAccumulator:
    """单个 claim_id 的触发信息聚合器。"""

    def __init__(self) -> None:
        self.issue_ids: set[str] = set()
        self.evidence_ids: set[str] = set()
        self.trigger_descriptions: list[str] = []

    def add(self, issue_id: str, evidence_ids: list[str], description: str) -> None:
        self.issue_ids.add(issue_id)
        self.evidence_ids.update(evidence_ids)
        self.trigger_descriptions.append(description)


class AlternativeClaimGenerator:
    """替代主张自动生成引擎（P2.11）。

    纯规则层，不持有外部状态，可安全复用同一实例。

    使用方式 / Usage:
        generator = AlternativeClaimGenerator()
        results = generator.generate(inp)
    """

    def generate(self, inp: AlternativeClaimGeneratorInput) -> list[AlternativeClaimSuggestion]:
        """执行替代主张自动生成，返回 AlternativeClaimSuggestion 列表。

        Args:
            inp: 引擎输入（含 case_id、run_id、issue_list、amount_report）

        Returns:
            list[AlternativeClaimSuggestion] — 按 original_claim_id 去重，每个 claim 一条
        """
        # claim_id -> 聚合器
        accumulators: dict[str, _TriggerAccumulator] = defaultdict(_TriggerAccumulator)

        # 建立 claim_id -> 关联争点 映射（用于条件3绑定 issue_id）
        claim_to_issues: dict[str, list[Issue]] = defaultdict(list)
        for issue in inp.issue_list:
            for claim_id in issue.related_claim_ids:
                claim_to_issues[claim_id].append(issue)

        self._apply_condition_1(inp.issue_list, accumulators)
        self._apply_condition_2(inp.issue_list, accumulators)
        self._apply_condition_3(
            inp.amount_report.claim_calculation_table, claim_to_issues, accumulators
        )

        return [
            self._build_suggestion(inp, claim_id, acc)
            for claim_id, acc in accumulators.items()
            if acc.issue_ids  # 额外防卫：确保 issue_ids 非空（条件3无关联争点时已被跳过）
        ]

    # ------------------------------------------------------------------
    # 条件判断方法 / Condition evaluation methods
    # ------------------------------------------------------------------

    def _apply_condition_1(
        self,
        issues: list[Issue],
        accumulators: dict[str, _TriggerAccumulator],
    ) -> None:
        """条件1：recommended_action = amend_claim。"""
        for issue in issues:
            if issue.recommended_action != RecommendedAction.amend_claim:
                continue
            for claim_id in issue.related_claim_ids:
                accumulators[claim_id].add(
                    issue_id=issue.issue_id,
                    evidence_ids=list(issue.evidence_ids),
                    description=f"争点「{issue.title}」建议修改主张（recommended_action=amend_claim）",
                )

    def _apply_condition_2(
        self,
        issues: list[Issue],
        accumulators: dict[str, _TriggerAccumulator],
    ) -> None:
        """条件2：proponent_evidence_strength=weak 且 opponent_attack_strength=strong。"""
        for issue in issues:
            if (
                issue.proponent_evidence_strength == EvidenceStrength.weak
                and issue.opponent_attack_strength == AttackStrength.strong
            ):
                for claim_id in issue.related_claim_ids:
                    accumulators[claim_id].add(
                        issue_id=issue.issue_id,
                        evidence_ids=list(issue.evidence_ids),
                        description=(
                            f"争点「{issue.title}」己方证据弱（weak）且对方攻击强（strong）"
                        ),
                    )

    def _apply_condition_3(
        self,
        claim_entries: list,
        claim_to_issues: dict[str, list[Issue]],
        accumulators: dict[str, _TriggerAccumulator],
    ) -> None:
        """条件3：ClaimCalculationEntry.delta 绝对值超过 claimed_amount × 10%。

        跳过条件：
        - delta 为 None（无法复算）
        - claimed_amount = 0（避免除零）
        - 无关联争点（无法绑定 issue_id，不满足 instability_issue_ids 非空约束）
        """
        for entry in claim_entries:
            if entry.delta is None:
                continue
            if entry.claimed_amount == 0:
                continue
            ratio = abs(entry.delta) / entry.claimed_amount
            if ratio <= _DELTA_THRESHOLD:
                continue
            # 必须有关联争点才能绑定 issue_id
            related_issues = claim_to_issues.get(entry.claim_id, [])
            if not related_issues:
                continue
            for issue in related_issues:
                accumulators[entry.claim_id].add(
                    issue_id=issue.issue_id,
                    evidence_ids=list(issue.evidence_ids),
                    description=(
                        f"诉请金额与可复算金额差异 {float(ratio):.1%}（超过10%阈值），"
                        f"claimed={entry.claimed_amount}, calculated={entry.calculated_amount}"
                    ),
                )

    # ------------------------------------------------------------------
    # 建议构建方法 / Suggestion builder
    # ------------------------------------------------------------------

    def _build_suggestion(
        self,
        inp: AlternativeClaimGeneratorInput,
        claim_id: str,
        acc: _TriggerAccumulator,
    ) -> AlternativeClaimSuggestion:
        """从聚合器构建 AlternativeClaimSuggestion。"""
        issue_ids = sorted(acc.issue_ids)
        evidence_ids = sorted(acc.evidence_ids)
        reason_text = "；".join(acc.trigger_descriptions)

        return AlternativeClaimSuggestion(
            suggestion_id=str(uuid.uuid4()),
            case_id=inp.case_id,
            run_id=inp.run_id,
            original_claim_id=claim_id,
            instability_reason=reason_text,
            instability_issue_ids=issue_ids,
            instability_evidence_ids=evidence_ids,
            alternative_claim_text=self._derive_alternative_text(claim_id, acc),
            stability_rationale=self._derive_stability_rationale(acc),
            supporting_evidence_ids=evidence_ids,
        )

    @staticmethod
    def _derive_alternative_text(claim_id: str, acc: _TriggerAccumulator) -> str:
        """从触发信息派生替代主张文本。具体可执行，非泛化建议。"""
        issue_count = len(acc.issue_ids)
        if issue_count == 1:
            return (
                f"针对主张「{claim_id}」，建议明确具体事实依据，"
                f"消除触发不稳定判断的争点，提供完整证据链支撑的修订版诉请"
            )
        return (
            f"针对主张「{claim_id}」，建议综合解决 {issue_count} 个不稳定争点，"
            f"重新组织事实依据并提供完整证据链，形成修订版诉请"
        )

    @staticmethod
    def _derive_stability_rationale(acc: _TriggerAccumulator) -> str:
        """从触发信息派生替代主张更稳固的理由。"""
        return (
            f"替代主张通过解决 {len(acc.trigger_descriptions)} 个不稳定触发条件，"
            f"明确事实依据、补强证据链，降低对方有效攻击概率"
        )
