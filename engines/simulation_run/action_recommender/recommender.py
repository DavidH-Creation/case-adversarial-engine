"""
ActionRecommender — 行动建议引擎主类（P1.8）。
Action Recommender — hybrid (rule-based + optional LLM strategic layer) engine for P1.8.

职责 / Responsibilities:
1. 接收 ActionRecommenderInput（issues, evidence_gap_list, amount_report, proponent_party_id）
2. 规则层（不变）：从 recommended_action 枚举派生四类结构行动
3. 案型检测：从争点标题关键词推断 dispute_category
4. LLM 策略层（可选）：生成 party-specific 策略建议 + strategic_headline
5. 返回 ActionRecommendation（含扩展字段）

合约保证 / Contract guarantees:
- 无 LLM 客户端时行为完全等价于 v1（纯规则层，向后兼容）
- 每个 ClaimAbandonSuggestion 必须绑定 issue_id 和 abandon_reason——零容忍
- 每个 TrialExplanationPriority 必须绑定 issue_id——零容忍
- evidence_supplement_priorities 中的 gap_id 来自输入的 evidence_gap_list
- LLM 策略层失败不影响规则层输出，仅 strategic 字段为空
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from engines.shared.models import (
    ActionRecommendation,
    ClaimAbandonSuggestion,
    ClaimAmendmentSuggestion,
    DecisionPathTree,
    EvidenceGapItem,
    Issue,
    LLMClient,
    PartyActionPlan,
    Perspective,
    RecommendedAction,
    StrategicRecommendation,
    TrialExplanationPriority,
)

from engines.shared.structured_output import call_structured_llm

from .schemas import ActionRecommenderInput

# tool_use JSON Schema for the strategic layer output
_STRATEGIC_TOOL_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "strategic_headline": {
            "type": "string",
            "description": "一句话战略标题（≤200字）/ One-line strategic headline (≤200 chars)",
        },
        "plaintiff_recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "recommendation_text": {"type": "string"},
                    "linked_issue_ids": {"type": "array", "items": {"type": "string"}},
                    "priority": {"type": "integer"},
                    "rationale": {"type": "string"},
                },
                "required": ["recommendation_text"],
            },
        },
        "defendant_recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "recommendation_text": {"type": "string"},
                    "linked_issue_ids": {"type": "array", "items": {"type": "string"}},
                    "priority": {"type": "integer"},
                    "rationale": {"type": "string"},
                },
                "required": ["recommendation_text"],
            },
        },
    },
}

logger = logging.getLogger(__name__)

# 案型检测关键词映射
_DISPUTE_PATTERNS: dict[str, list[str]] = {
    "borrower_identity": [
        "借款人",
        "主体",
        "适格",
        "代收",
        "代付",
        "名义",
        "实际借款人",
        "账户控制",
    ],
    "amount_dispute": ["金额", "本金", "利息", "计算", "还款", "差额", "违约金"],
    "contract_validity": ["合同效力", "借贷合意", "虚假", "无效", "意思表示"],
    "interest_rate": ["利率", "高利", "四倍", "LPR"],
}


class ActionRecommender:
    """行动建议引擎（P1.8）。

    支持两种模式：
    - 纯规则层（llm_client=None）：等价于 v1，零 LLM 调用
    - 混合模式（llm_client 非 None）：规则层 + LLM 策略层

    使用方式 / Usage:
        # 纯规则层（向后兼容）
        recommender = ActionRecommender()
        result = await recommender.recommend(inp)

        # 混合模式
        recommender = ActionRecommender(llm_client=client, case_type="civil_loan")
        result = await recommender.recommend(inp)
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        *,
        case_type: str = "civil_loan",
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> None:
        self._llm = llm_client
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._prompt_module = self._load_prompt_module(case_type) if llm_client else None

    @staticmethod
    def _load_prompt_module(case_type: str):
        from .prompts import PROMPT_REGISTRY

        if case_type not in PROMPT_REGISTRY:
            available = ", ".join(PROMPT_REGISTRY.keys()) or "(none)"
            raise ValueError(f"不支持的案由类型: '{case_type}'。可用: {available}")
        return PROMPT_REGISTRY[case_type]

    async def recommend(self, inp: ActionRecommenderInput) -> ActionRecommendation:
        """执行行动建议聚合，返回 ActionRecommendation。

        Args:
            inp: 引擎输入（含 case_id、run_id、issue_list、evidence_gap_list、amount_report）

        Returns:
            ActionRecommendation — 含四类结构建议 + 可选的策略层建议
        """
        # ---- 规则层（不变）----
        amendments = self._build_amendments(inp.issue_list)
        abandon_suggestions = self._build_abandon_suggestions(inp.issue_list)
        trial_explanations = self._build_trial_explanations(inp.issue_list)
        gap_ids = self._build_evidence_priorities(inp.evidence_gap_list)

        # ---- 案型检测 ----
        dispute_category = self._detect_dispute_category(inp.issue_list)

        # ---- 案型补充注入（仅当规则层产出不足时）----
        trial_explanations = self._inject_category_specific_actions(
            dispute_category,
            inp.issue_list,
            trial_explanations,
        )

        # ---- LLM 策略层（可选）----
        plaintiff_plan: Optional[PartyActionPlan] = None
        defendant_plan: Optional[PartyActionPlan] = None
        strategic_headline: Optional[str] = None

        if self._llm and self._prompt_module:
            strategic = await self._generate_strategic_layer(inp, dispute_category)
            if strategic:
                plaintiff_plan = strategic.get("plaintiff_plan")
                defendant_plan = strategic.get("defendant_plan")
                strategic_headline = strategic.get("headline")

        # ---- 组装 structural_actions 到 PartyActionPlan ----
        if plaintiff_plan is None and (amendments or trial_explanations):
            plaintiff_plan = PartyActionPlan(
                party_type="plaintiff",
                structural_actions=[s.suggestion_id for s in amendments]
                + [p.priority_id for p in trial_explanations],
            )
        elif plaintiff_plan is not None:
            plaintiff_plan = plaintiff_plan.model_copy(
                update={
                    "structural_actions": [s.suggestion_id for s in amendments]
                    + [p.priority_id for p in trial_explanations]
                }
            )

        if defendant_plan is None and (abandon_suggestions or gap_ids):
            defendant_plan = PartyActionPlan(
                party_type="defendant",
                structural_actions=[s.suggestion_id for s in abandon_suggestions]
                + list(gap_ids[:3]),
            )
        elif defendant_plan is not None:
            defendant_plan = defendant_plan.model_copy(
                update={
                    "structural_actions": [s.suggestion_id for s in abandon_suggestions]
                    + list(gap_ids[:3])
                }
            )

        # ---- v7: 行动建议-路径对齐校验 ----
        if inp.decision_path_tree:
            strategic_headline, plaintiff_plan, defendant_plan = self._align_with_path_tree(
                inp.decision_path_tree,
                strategic_headline,
                plaintiff_plan,
                defendant_plan,
            )
            # ---- v1.5: 路径-行动连接（medium closed loop）----
            amendments, abandon_suggestions, trial_explanations = self._annotate_path_ids(
                inp.decision_path_tree,
                amendments,
                abandon_suggestions,
                trial_explanations,
            )

        return ActionRecommendation(
            recommendation_id=str(uuid.uuid4()),
            case_id=inp.case_id,
            run_id=inp.run_id,
            recommended_claim_amendments=amendments,
            evidence_supplement_priorities=gap_ids,
            trial_explanation_priorities=trial_explanations,
            claims_to_abandon=abandon_suggestions,
            plaintiff_action_plan=plaintiff_plan,
            defendant_action_plan=defendant_plan,
            case_dispute_category=dispute_category,
            strategic_headline=strategic_headline,
        )

    # ------------------------------------------------------------------
    # v1.5: 路径-行动连接注释 / Path-action annotation (medium closed loop)
    # ------------------------------------------------------------------

    @staticmethod
    def _annotate_path_ids(
        tree: DecisionPathTree,
        amendments: list[ClaimAmendmentSuggestion],
        abandon_suggestions: list[ClaimAbandonSuggestion],
        trial_explanations: list[TrialExplanationPriority],
    ) -> tuple[
        list[ClaimAmendmentSuggestion],
        list[ClaimAbandonSuggestion],
        list[TrialExplanationPriority],
    ]:
        """为每条行动建议标注受影响的裁判路径 ID。

        逻辑：若行动绑定的 issue_id 出现在某条路径的 trigger_issue_ids 中，
        则该路径 ID 加入该行动的 impacted_path_ids。

        Returns:
            (annotated_amendments, annotated_abandon_suggestions, annotated_trial_explanations)
        """
        # 构建 issue_id → path_id 的反向索引
        issue_to_paths: dict[str, list[str]] = {}
        for path in tree.paths:
            for iid in path.trigger_issue_ids:
                issue_to_paths.setdefault(iid, []).append(path.path_id)

        def _path_ids_for_issue(issue_id: str) -> list[str]:
            return issue_to_paths.get(issue_id, [])

        annotated_amendments = [
            a.model_copy(
                update={"impacted_path_ids": _path_ids_for_issue(a.amendment_reason_issue_id)}
            )
            for a in amendments
        ]
        annotated_abandon = [
            s.model_copy(
                update={"impacted_path_ids": _path_ids_for_issue(s.abandon_reason_issue_id)}
            )
            for s in abandon_suggestions
        ]
        annotated_trial = [
            t.model_copy(
                update={"impacted_path_ids": _path_ids_for_issue(t.issue_id)}
            )
            for t in trial_explanations
        ]

        return annotated_amendments, annotated_abandon, annotated_trial

    # ------------------------------------------------------------------
    # v7: 行动建议-路径对齐 / Action-path alignment
    # ------------------------------------------------------------------

    @staticmethod
    def _align_with_path_tree(
        tree: DecisionPathTree,
        headline: Optional[str],
        plaintiff_plan: Optional[PartyActionPlan],
        defendant_plan: Optional[PartyActionPlan],
    ) -> tuple[Optional[str], Optional[PartyActionPlan], Optional[PartyActionPlan]]:
        """根据路径树整体态势调整策略建议。

        修订清单一-3/一-6：
        - 若最可能路径对被告有利，原告建议自动下调（去除攻击性表述）
        - 若最可能路径对原告有利，被告建议自动下调

        Returns:
            (adjusted_headline, adjusted_plaintiff_plan, adjusted_defendant_plan)
        """
        most_likely_favored = None
        if tree.most_likely_path:
            for path in tree.paths:
                if path.path_id == tree.most_likely_path:
                    most_likely_favored = path.party_favored
                    break

        if most_likely_favored is None:
            return headline, plaintiff_plan, defendant_plan

        # 清理 headline 中不一致的信号
        _OVERCONFIDENT = ["全额", "稳拿", "必胜", "确保获赔", "完全支持"]
        if headline and most_likely_favored == "defendant":
            for signal in _OVERCONFIDENT:
                if signal in headline:
                    headline = headline.replace(signal, "争取部分支持")
                    logger.info("Path alignment: headline adjusted, removed '%s'", signal)

        # 原告处于劣势时，原告策略建议降级
        if most_likely_favored == "defendant" and plaintiff_plan:
            adjusted_recs = []
            for sr in plaintiff_plan.strategic_recommendations or []:
                _AGGRESSIVE = ["全额主张", "坚持全额", "加大力度", "扩大诉请"]
                text = sr.recommendation_text
                for signal in _AGGRESSIVE:
                    if signal in text:
                        text = text.replace(signal, "争取保底金额")
                adjusted_recs.append(sr.model_copy(update={"recommendation_text": text}))
            plaintiff_plan = plaintiff_plan.model_copy(
                update={"strategic_recommendations": adjusted_recs}
            )

        return headline, plaintiff_plan, defendant_plan

    # ------------------------------------------------------------------
    # 案型检测 / Dispute category detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_dispute_category(issues: list[Issue]) -> str:
        """从争点标题关键词推断案件争议类别。"""
        title_text = " ".join(i.title for i in issues)
        scores: dict[str, int] = {}
        for category, keywords in _DISPUTE_PATTERNS.items():
            scores[category] = sum(1 for kw in keywords if kw in title_text)
        if not any(scores.values()):
            return "general"
        return max(scores, key=scores.get)

    # ------------------------------------------------------------------
    # 案型补充注入 / Category-specific action injection
    # ------------------------------------------------------------------

    _MIN_TRIAL_EXPLANATIONS = 3  # 规则层产出不足阈值
    _MAX_INJECTED = 3  # 每次最多注入条数

    _CATEGORY_KEYWORDS: dict[str, list[str]] = {
        "borrower_identity": ["借款人", "主体", "适格", "合意", "账户控制", "代收", "代付"],
        "amount_dispute": ["本金", "利息", "金额", "计算", "还款"],
    }

    @classmethod
    def _inject_category_specific_actions(
        cls,
        dispute_category: str,
        issues: list[Issue],
        existing: list[TrialExplanationPriority],
    ) -> list[TrialExplanationPriority]:
        """当规则层 trial_explanations 不足时，按案型注入补充建议。

        保守策略：
        - 仅当 existing 数量 < _MIN_TRIAL_EXPLANATIONS 时才注入
        - 严格去重（按 issue_id）
        - 最多注入 _MAX_INJECTED 条
        - category=general 时不注入
        """
        keywords = cls._CATEGORY_KEYWORDS.get(dispute_category)
        if keywords is None or len(existing) >= cls._MIN_TRIAL_EXPLANATIONS:
            return existing

        existing_ids = {p.issue_id for p in existing}
        injected: list[TrialExplanationPriority] = []

        for issue in issues:
            if issue.issue_id in existing_ids:
                continue
            if any(kw in issue.title for kw in keywords):
                injected.append(
                    TrialExplanationPriority(
                        priority_id=str(uuid.uuid4()),
                        issue_id=issue.issue_id,
                        explanation_text=f"庭审重点质证争点「{issue.title}」",
                    )
                )
                existing_ids.add(issue.issue_id)
                if len(injected) >= cls._MAX_INJECTED:
                    break

        if injected:
            logger.info(
                "Category '%s': injected %d trial explanations (rule layer had %d)",
                dispute_category,
                len(injected),
                len(existing),
            )

        return list(existing) + injected

    # ------------------------------------------------------------------
    # LLM 策略层 / Strategic layer
    # ------------------------------------------------------------------

    async def _generate_strategic_layer(
        self,
        inp: ActionRecommenderInput,
        dispute_category: str,
    ) -> Optional[dict[str, Any]]:
        """调用 LLM 生成 party-specific 策略建议。失败返回 None。"""
        try:
            if inp.evidence_index is None:
                logger.warning("evidence_index 未提供，跳过 LLM 策略层")
                return None

            system_prompt = self._prompt_module.SYSTEM_PROMPT
            user_prompt = self._prompt_module.build_user_prompt(
                issue_list=inp.issue_list,
                evidence_index=inp.evidence_index,
                dispute_category=dispute_category,
                proponent_party_id=inp.proponent_party_id,
            )

            data = await call_structured_llm(
                self._llm,
                system=system_prompt,
                user=user_prompt,
                model=self._model,
                tool_name="generate_strategic_recommendations",
                tool_description="生成当事人策略建议和战略标题。"
                "Generate party-specific strategic recommendations and strategic headline.",
                tool_schema=_STRATEGIC_TOOL_SCHEMA,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
            return self._parse_strategic_output(data, inp)

        except Exception:  # noqa: BLE001
            logger.warning("LLM 策略层调用失败，降级为纯规则层输出", exc_info=True)
            return None

    def _parse_strategic_output(
        self,
        data: dict,
        inp: ActionRecommenderInput,
    ) -> dict[str, Any]:
        """解析 LLM 策略层输出，校验后返回结构化结果。"""
        known_issue_ids = {i.issue_id for i in inp.issue_list}

        result: dict[str, Any] = {}
        result["headline"] = (data.get("strategic_headline") or "")[:200] or None

        for party_key, plan_key in [
            ("plaintiff_recommendations", "plaintiff_plan"),
            ("defendant_recommendations", "defendant_plan"),
        ]:
            recs = data.get(party_key, [])
            if not isinstance(recs, list):
                continue
            party_type = "plaintiff" if "plaintiff" in party_key else "defendant"
            strategic_recs: list[StrategicRecommendation] = []
            for rec in recs[:5]:
                if not isinstance(rec, dict):
                    continue
                text = rec.get("recommendation_text", "")
                if not text:
                    continue
                linked = [iid for iid in rec.get("linked_issue_ids", []) if iid in known_issue_ids]
                priority = rec.get("priority", 3)
                if not isinstance(priority, int) or priority < 1 or priority > 5:
                    priority = 3
                strategic_recs.append(
                    StrategicRecommendation(
                        recommendation_text=text[:200],
                        target_party=party_type,
                        linked_issue_ids=linked,
                        priority=priority,
                        rationale=str(rec.get("rationale", ""))[:200],
                    )
                )
            if strategic_recs:
                result[plan_key] = PartyActionPlan(
                    party_type=party_type,
                    strategic_recommendations=strategic_recs,
                )

        return result

    # ------------------------------------------------------------------
    # 规则层构建方法 / Rule-based builders (unchanged from v1)
    # ------------------------------------------------------------------

    def _build_amendments(self, issues: list[Issue]) -> list[ClaimAmendmentSuggestion]:
        """从 recommended_action=amend_claim 的争点派生修改建议。"""
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
        """从 recommended_action=abandon 的争点派生放弃建议。"""
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
        """从 recommended_action=explain_in_trial 的争点派生庭审解释优先事项。"""
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
        """从 evidence_gap_list 按 roi_rank 升序排序，返回 gap_id 列表。"""
        sorted_gaps = sorted(gaps, key=lambda g: g.roi_rank)
        return [g.gap_id for g in sorted_gaps]

    # ------------------------------------------------------------------
    # 文本派生辅助方法 / Text derivation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _amendment_description(issue: Issue) -> str:
        if issue.recommended_action_basis:
            return issue.recommended_action_basis
        return f"建议修改与争点「{issue.title}」相关的诉请"

    @staticmethod
    def _abandon_reason(issue: Issue) -> str:
        if issue.recommended_action_basis:
            return issue.recommended_action_basis
        return f"争点「{issue.title}」证据不足，建议放弃相关诉请以减少败诉风险"

    @staticmethod
    def _explanation_text(issue: Issue) -> str:
        if issue.recommended_action_basis:
            return issue.recommended_action_basis
        return f"庭审中需优先解释争点「{issue.title}」相关事实"
