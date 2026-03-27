"""
IssueImpactRanker — 争点影响排序模块主类。
Issue Impact Ranker — main class for P0.1 issue impact ranking.

职责 / Responsibilities:
1. 接收 IssueTree + EvidenceIndex + AmountCalculationReport + proponent_party_id
2. 一次性调用 LLM 对所有争点进行五维度批量评估
3. 规则层：解析枚举、校验证据绑定、过滤非法 ID、降级处理
4. 按 outcome_impact DESC → opponent_attack_strength DESC 排序
5. 返回富化后的 IssueImpactRankingResult

合约保证 / Contract guarantees:
- outcome_impact / recommended_action 必须枚举值，否则清空并记入 unevaluated
- strength 非 None 时 evidence_ids 必须非空且合法，否则清空并记入 unevaluated
- recommended_action 非 None 时 basis 必须非空，否则清空并记入 unevaluated
- LLM 返回未知 issue_id 被过滤忽略
- LLM 整体失败返回 failed 结果（原始顺序，全部争点进 unevaluated），不抛异常
- 空争点树不调用 LLM，直接返回
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from engines.shared.json_utils import _extract_json_object
from engines.shared.models import (
    AttackStrength,
    EvidenceStrength,
    ImpactTarget,
    Issue,
    LLMClient,
    OutcomeImpact,
    RecommendedAction,
)

from .schemas import (
    IssueImpactRankerInput,
    IssueImpactRankingResult,
    LLMIssueEvaluationOutput,
    LLMSingleIssueEvaluation,
)

# 排序权重映射（None → 99 排末尾）
_IMPACT_ORDER: dict[OutcomeImpact, int] = {
    OutcomeImpact.high: 0,
    OutcomeImpact.medium: 1,
    OutcomeImpact.low: 2,
}
_ATTACK_ORDER: dict[AttackStrength, int] = {
    AttackStrength.strong: 0,
    AttackStrength.medium: 1,
    AttackStrength.weak: 2,
}


class IssueImpactRanker:
    """争点影响排序器。

    Args:
        llm_client:  符合 LLMClient 协议的客户端实例
        case_type:   案由类型，默认 "civil_loan"
        model:       LLM 模型名称
        temperature: LLM 温度参数
        max_tokens:  LLM 最大输出 token 数
        max_retries: LLM 调用失败时的最大重试次数
    """

    def __init__(
        self,
        llm_client: LLMClient,
        case_type: str = "civil_loan",
        *,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.0,
        max_tokens: int = 8192,
        max_retries: int = 3,
    ) -> None:
        self._llm = llm_client
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_retries = max_retries
        self._prompt_module = self._load_prompt_module(case_type)

    @staticmethod
    def _load_prompt_module(case_type: str):
        """加载案由对应的 prompt 模板模块。"""
        from .prompts import PROMPT_REGISTRY

        if case_type not in PROMPT_REGISTRY:
            available = ", ".join(PROMPT_REGISTRY.keys()) or "(none)"
            raise ValueError(
                f"不支持的案由类型: '{case_type}'。可用: {available}"
            )
        return PROMPT_REGISTRY[case_type]

    async def rank(self, inp: IssueImpactRankerInput) -> IssueImpactRankingResult:
        """执行争点影响排序。

        Args:
            inp: 排序器输入（含争点树、证据索引、金额报告、主张方 ID）

        Returns:
            IssueImpactRankingResult — 含排序后的富化争点树
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        issues = list(inp.issue_tree.issues)

        # 空争点树：直接返回，不调用 LLM
        if not issues:
            return IssueImpactRankingResult(
                ranked_issue_tree=inp.issue_tree,
                evaluation_metadata={},
                unevaluated_issue_ids=[],
                created_at=now,
            )

        known_issue_ids: set[str] = {i.issue_id for i in issues}
        known_evidence_ids: set[str] = {
            e.evidence_id for e in inp.evidence_index.evidence
        }

        try:
            # 构建 prompt
            system_prompt = self._prompt_module.SYSTEM_PROMPT
            user_prompt = self._prompt_module.build_user_prompt(
                issue_tree=inp.issue_tree,
                evidence_index=inp.evidence_index,
                proponent_party_id=inp.proponent_party_id,
                amount_check=inp.amount_calculation_report.consistency_check_result,
            )

            # 调用 LLM（带重试）
            raw_response = await self._call_llm_with_retry(system_prompt, user_prompt)

            # 解析 JSON
            raw_dict = _extract_json_object(raw_response)
            llm_output = LLMIssueEvaluationOutput.model_validate(raw_dict)

            # 规则层：校验 + 富化
            enriched_issues, unevaluated = self._apply_evaluations(
                issues=issues,
                evaluations=llm_output.evaluations,
                known_issue_ids=known_issue_ids,
                known_evidence_ids=known_evidence_ids,
            )

            # 规则层：排序
            sorted_issues = self._sort_issues(enriched_issues)
            ranked_tree = inp.issue_tree.model_copy(update={"issues": sorted_issues})

            return IssueImpactRankingResult(
                ranked_issue_tree=ranked_tree,
                evaluation_metadata={
                    "model": self._model,
                    "temperature": self._temperature,
                    "evaluated_count": len(issues) - len(unevaluated),
                    "total_count": len(issues),
                    "created_at": now,
                },
                unevaluated_issue_ids=unevaluated,
                created_at=now,
            )

        except Exception:
            # LLM 调用或解析失败：原始 issue_tree 保持原顺序，所有评估字段为 None
            return IssueImpactRankingResult(
                ranked_issue_tree=inp.issue_tree,
                evaluation_metadata={"failed": True, "created_at": now},
                unevaluated_issue_ids=[i.issue_id for i in issues],
                created_at=now,
            )

    # ------------------------------------------------------------------
    # 排序 / Sorting
    # ------------------------------------------------------------------

    def _sort_issues(self, issues: list[Issue]) -> list[Issue]:
        """按 outcome_impact DESC → opponent_attack_strength DESC 稳定排序。

        None 值排末尾（权重 99）。Python sorted() 保证稳定性。
        """
        return sorted(
            issues,
            key=lambda issue: (
                _IMPACT_ORDER.get(issue.outcome_impact, 99),
                _ATTACK_ORDER.get(issue.opponent_attack_strength, 99),
            ),
        )

    # ------------------------------------------------------------------
    # 规则层：校验 + 富化 / Validation and enrichment
    # ------------------------------------------------------------------

    def _apply_evaluations(
        self,
        issues: list[Issue],
        evaluations: list[LLMSingleIssueEvaluation],
        known_issue_ids: set[str],
        known_evidence_ids: set[str],
    ) -> tuple[list[Issue], list[str]]:
        """将 LLM 评估结果校验后富化到 Issue 对象。

        校验失败规则（任一失败 → 清空对应字段，记入 unevaluated_issue_ids）：
        - outcome_impact: 必须是合法枚举值
        - proponent_evidence_strength: 必须有 ≥1 条已知 evidence_id
        - opponent_attack_strength: 必须有 ≥1 条已知 evidence_id
        - recommended_action: basis 必须非空

        Returns:
            (enriched_issues, unevaluated_issue_ids)
        """
        # 构建 eval_map（过滤未知 issue_id）
        eval_map: dict[str, LLMSingleIssueEvaluation] = {
            ev.issue_id: ev
            for ev in evaluations
            if ev.issue_id in known_issue_ids
        }

        enriched: list[Issue] = []
        unevaluated: list[str] = []

        for issue in issues:
            ev = eval_map.get(issue.issue_id)
            if ev is None:
                # LLM 未返回该争点的评估
                unevaluated.append(issue.issue_id)
                enriched.append(issue)
                continue

            updates: dict[str, Any] = {}
            issue_degraded = False

            # outcome_impact
            oi = self._resolve_outcome_impact(ev.outcome_impact)
            if oi is not None:
                updates["outcome_impact"] = oi
            else:
                issue_degraded = True

            # impact_targets（宽松：忽略非法值，不因此降级整条评估）
            updates["impact_targets"] = self._resolve_impact_targets(ev.impact_targets)

            # proponent_evidence_strength：需有有效证据引用
            pes = self._resolve_evidence_strength(ev.proponent_evidence_strength)
            valid_proponent_ids = [
                eid for eid in ev.proponent_evidence_ids if eid in known_evidence_ids
            ]
            if pes is not None and valid_proponent_ids:
                updates["proponent_evidence_strength"] = pes
            elif pes is not None:
                issue_degraded = True  # 有强度值但无有效证据引用 → 降级

            # opponent_attack_strength：需有有效证据引用
            oas = self._resolve_attack_strength(ev.opponent_attack_strength)
            valid_opponent_ids = [
                eid for eid in ev.opponent_attack_evidence_ids if eid in known_evidence_ids
            ]
            if oas is not None and valid_opponent_ids:
                updates["opponent_attack_strength"] = oas
            elif oas is not None:
                issue_degraded = True

            # recommended_action：需有非空 basis
            ra = self._resolve_recommended_action(ev.recommended_action)
            basis = ev.recommended_action_basis.strip()
            if ra is not None and basis:
                updates["recommended_action"] = ra
                updates["recommended_action_basis"] = basis
            elif ra is not None:
                issue_degraded = True

            if issue_degraded:
                unevaluated.append(issue.issue_id)

            enriched.append(issue.model_copy(update=updates))

        return enriched, unevaluated

    # ------------------------------------------------------------------
    # 枚举解析辅助 / Enum resolution helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_outcome_impact(raw: str) -> Optional[OutcomeImpact]:
        _MAP = {
            "high": OutcomeImpact.high,
            "medium": OutcomeImpact.medium,
            "low": OutcomeImpact.low,
        }
        return _MAP.get(raw.strip().lower())

    @staticmethod
    def _resolve_evidence_strength(raw: str) -> Optional[EvidenceStrength]:
        _MAP = {
            "strong": EvidenceStrength.strong,
            "medium": EvidenceStrength.medium,
            "weak": EvidenceStrength.weak,
        }
        return _MAP.get(raw.strip().lower())

    @staticmethod
    def _resolve_attack_strength(raw: str) -> Optional[AttackStrength]:
        _MAP = {
            "strong": AttackStrength.strong,
            "medium": AttackStrength.medium,
            "weak": AttackStrength.weak,
        }
        return _MAP.get(raw.strip().lower())

    @staticmethod
    def _resolve_recommended_action(raw: str) -> Optional[RecommendedAction]:
        _MAP = {
            "supplement_evidence": RecommendedAction.supplement_evidence,
            "amend_claim": RecommendedAction.amend_claim,
            "abandon": RecommendedAction.abandon,
            "explain_in_trial": RecommendedAction.explain_in_trial,
        }
        return _MAP.get(raw.strip().lower())

    @staticmethod
    def _resolve_impact_targets(raw: list[str]) -> list[ImpactTarget]:
        _MAP = {
            "principal": ImpactTarget.principal,
            "interest": ImpactTarget.interest,
            "penalty": ImpactTarget.penalty,
            "attorney_fee": ImpactTarget.attorney_fee,
            "credibility": ImpactTarget.credibility,
        }
        return [_MAP[t.strip().lower()] for t in raw if t.strip().lower() in _MAP]

    # ------------------------------------------------------------------
    # LLM 调用（带重试）/ LLM call with retry
    # ------------------------------------------------------------------

    async def _call_llm_with_retry(self, system: str, user: str) -> str:
        """调用 LLM 并在失败时重试。

        Raises:
            RuntimeError: 超过最大重试次数
        """
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                return await self._llm.create_message(
                    system=system,
                    user=user,
                    model=self._model,
                    temperature=self._temperature,
                    max_tokens=self._max_tokens,
                )
            except Exception as e:
                last_error = e
                if attempt < self._max_retries:
                    continue
                break
        raise RuntimeError(
            f"LLM 调用失败，已重试 {self._max_retries} 次。最后错误: {last_error}"
        )
