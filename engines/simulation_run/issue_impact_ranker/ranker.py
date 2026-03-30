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

import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

from engines.shared.models import (
    AttackStrength,
    EvidenceStrength,
    ImpactTarget,
    Issue,
    LLMClient,
    OutcomeImpact,
    RecommendedAction,
)

from engines.shared.structured_output import call_structured_llm

from .schemas import (
    IssueImpactRankerInput,
    IssueImpactRankingResult,
    LLMIssueEvaluationOutput,
    LLMSingleIssueEvaluation,
)

# tool_use JSON Schema（模块加载时计算一次）
_TOOL_SCHEMA: dict = LLMIssueEvaluationOutput.model_json_schema()

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
        max_tokens: int = 16000,
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

            # 调用 LLM（结构化输出）
            raw_dict = await self._call_llm_structured(system_prompt, user_prompt)
            logger.info("JSON 解析成功, 顶层键: %s", list(raw_dict.keys()))
            raw_dict = self._normalize_evaluation_keys(raw_dict)
            # 归一化个别评估项的字段名
            if "evaluations" in raw_dict and isinstance(raw_dict["evaluations"], list):
                raw_dict["evaluations"] = [
                    self._normalize_single_eval(item) if isinstance(item, dict) else item
                    for item in raw_dict["evaluations"]
                ]
                if raw_dict["evaluations"]:
                    logger.debug("首条评估项键: %s", list(raw_dict["evaluations"][0].keys()))
            # 收集 rescale 审计信息（_score_rescaled 会被 Pydantic 过滤掉）
            _rescaled_ids = []
            if "evaluations" in raw_dict and isinstance(raw_dict["evaluations"], list):
                for ev_item in raw_dict["evaluations"]:
                    if isinstance(ev_item, dict) and ev_item.pop("_score_rescaled", False):
                        _rescaled_ids.append(ev_item.get("issue_id", "?"))

            llm_output = LLMIssueEvaluationOutput.model_validate(raw_dict)
            logger.info("评估条目数: %d", len(llm_output.evaluations))
            if llm_output.evaluations:
                sample = llm_output.evaluations[0]
                logger.info("首条 issue_id=%s, outcome_impact=%s, importance=%d",
                            sample.issue_id, sample.outcome_impact, sample.importance_score)

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

            meta = {
                "model": self._model,
                "temperature": self._temperature,
                "evaluated_count": len(issues) - len(unevaluated),
                "total_count": len(issues),
                "created_at": now,
            }
            if _rescaled_ids:
                meta["score_rescaled"] = True
                meta["score_rescaled_issue_ids"] = _rescaled_ids

            return IssueImpactRankingResult(
                ranked_issue_tree=ranked_tree,
                evaluation_metadata=meta,
                unevaluated_issue_ids=unevaluated,
                created_at=now,
            )

        except Exception:
            logger.warning("Ranker LLM 调用或解析失败", exc_info=True)
            # LLM 调用或解析失败：原始 issue_tree 保持原顺序，所有评估字段为 None
            return IssueImpactRankingResult(
                ranked_issue_tree=inp.issue_tree,
                evaluation_metadata={"failed": True, "created_at": now},
                unevaluated_issue_ids=[i.issue_id for i in issues],
                created_at=now,
            )

    # ------------------------------------------------------------------
    # LLM 输出归一化 / LLM output normalization
    # ------------------------------------------------------------------

    _EVALUATIONS_ALIASES = (
        "issue_assessments", "assessments", "issues", "issue_evaluations",
        "争点评估", "评估结果",
    )

    @classmethod
    def _normalize_evaluation_keys(cls, raw: dict) -> dict:
        """归一化 LLM 返回的顶层键，确保 evaluations 字段存在。

        LLM 可能用 issue_assessments / assessments / issues 等键名返回评估列表。
        本方法将其统一为 evaluations。同时处理嵌套结构（评估项可能包含子字典）。
        """
        if "evaluations" in raw:
            return raw

        # 尝试别名
        for alias in cls._EVALUATIONS_ALIASES:
            if alias in raw and isinstance(raw[alias], list):
                logger.info("归一化键名: %s → evaluations", alias)
                raw["evaluations"] = raw.pop(alias)
                return raw

        # 尝试找任意值为 list[dict] 的键
        for key, val in list(raw.items()):
            if isinstance(val, list) and val and isinstance(val[0], dict) and "issue_id" in val[0]:
                logger.info("自动检测评估列表键: %s → evaluations", key)
                raw["evaluations"] = raw.pop(key)
                return raw

        # 尝试找任意值为 list[dict] 的键（即使没有 issue_id）
        for key, val in list(raw.items()):
            if isinstance(val, list) and len(val) >= 2 and isinstance(val[0], dict):
                logger.info("推测评估列表键: %s (len=%d) → evaluations", key, len(val))
                raw["evaluations"] = raw.pop(key)
                return raw

        logger.warning("无法找到评估列表键，可用键: %s", list(raw.keys()))
        return raw

    # 单条评估项字段别名映射
    _EVAL_FIELD_ALIASES: dict[str, str] = {
        # issue_id 别名
        "争点id": "issue_id", "争点编号": "issue_id", "id": "issue_id",
        # outcome_impact 别名
        "impact": "outcome_impact", "影响程度": "outcome_impact",
        "outcome_impact_level": "outcome_impact",
        # evidence strength 别名
        "proponent_strength": "proponent_evidence_strength",
        "evidence_strength": "proponent_evidence_strength",
        "opponent_strength": "opponent_attack_strength",
        "attack_strength": "opponent_attack_strength",
        # recommended action 别名
        "action": "recommended_action", "recommendation": "recommended_action",
        "action_basis": "recommended_action_basis",
        "basis": "recommended_action_basis",
        # scoring 别名
        "importance": "importance_score", "关键程度": "importance_score",
        "swing": "swing_score", "摆幅": "swing_score",
        "gap": "evidence_strength_gap", "证据差距": "evidence_strength_gap",
        "depth": "dependency_depth", "层级": "dependency_depth",
        "credibility": "credibility_impact", "可信度冲击": "credibility_impact",
    }

    # dimensions 子键到平铺字段的映射
    _DIMENSION_FIELD_MAP: dict[str, tuple[str, type]] = {
        # 分类维度
        "outcome_impact": ("outcome_impact", str),
        "影响程度": ("outcome_impact", str),
        # 评分维度 — LLM 可能用各种名称
        "importance": ("importance_score", int),
        "importance_score": ("importance_score", int),
        "关键程度": ("importance_score", int),
        "swing": ("swing_score", int),
        "swing_score": ("swing_score", int),
        "结论翻转": ("swing_score", int),
        "evidence_strength_gap": ("evidence_strength_gap", int),
        "evidence_gap": ("evidence_strength_gap", int),
        "证据差距": ("evidence_strength_gap", int),
        "dependency_depth": ("dependency_depth", int),
        "depth": ("dependency_depth", int),
        "层级": ("dependency_depth", int),
        "credibility_impact": ("credibility_impact", int),
        "credibility": ("credibility_impact", int),
        "可信度": ("credibility_impact", int),
        # LLM 可能用的其他维度名（宽泛映射，总比丢弃好）
        "evidence_sufficiency": ("importance_score", int),
        "judicial_attention": ("importance_score", int),
        "controversy_intensity": ("swing_score", int),
        "burden_of_proof_clarity": ("credibility_impact", int),
        # Opus 常用维度名
        "relevance_to_outcome": ("importance_score", int),
        "proof_difficulty": ("evidence_strength_gap", int),
        "legal_clarity": ("credibility_impact", int),
        "judicial_discretion": ("credibility_impact", int),
        "dispute_intensity": ("swing_score", int),
        "chain_dependency": ("dependency_depth", int),
        "reversal_risk": ("swing_score", int),
        "settlement_leverage": ("importance_score", int),
        "plaintiff_prevail_pct": ("swing_score", int),
        # 其他可能的维度名
        "case_impact": ("importance_score", int),
        "evidence_balance": ("evidence_strength_gap", int),
        "controversy": ("swing_score", int),
        "dependency": ("dependency_depth", int),
        "credibility_risk": ("credibility_impact", int),
        # Opus D0X_ 系列（前缀已在匹配时剥离，这里补全无前缀版本）
        "verdict_impact_weight": ("importance_score", int),
        "burden_allocation_rationality": ("credibility_impact", int),
        "factual_determination_difficulty": ("swing_score", int),
        "opposing_defense_strength": ("evidence_strength_gap", int),
        "evidence_chain_completeness": ("importance_score", int),
        "plaintiff_prevail_probability": ("swing_score", int),
        "related_issue_dependency": ("dependency_depth", int),
        "risk_exposure": ("credibility_impact", int),
    }

    @classmethod
    def _normalize_single_eval(cls, item: dict) -> dict:
        """归一化单条评估项的字段名，展平 dimensions 嵌套结构。"""
        # 1. 展平 dimensions 嵌套
        dims = item.pop("dimensions", None) or item.pop("scores", None)
        if isinstance(dims, dict):
            logger.debug("展平 dimensions: %s", list(dims.keys()))
            for dim_name, dim_val in dims.items():
                # 剥离 LLM 喜欢加的编号前缀（如 D01_, D1_, dim01_, 01_）
                stripped = re.sub(r'^[Dd]?\d+[_\-]', '', dim_name)
                mapping = cls._DIMENSION_FIELD_MAP.get(dim_name) or cls._DIMENSION_FIELD_MAP.get(stripped)
                # Layer 2: pattern-based dimension matching if exact map fails
                if mapping is None:
                    lower_name = stripped.lower()
                    if any(p in lower_name for p in ("import", "weight", "关键", "key", "critical")):
                        mapping = ("importance_score", int)
                    elif any(p in lower_name for p in ("swing", "revers", "flip", "翻转")):
                        mapping = ("swing_score", int)
                    elif any(p in lower_name for p in ("gap", "balance", "差距", "completeness")):
                        mapping = ("evidence_strength_gap", int)
                    elif any(p in lower_name for p in ("depth", "depend", "层级", "chain")):
                        mapping = ("dependency_depth", int)
                    elif any(p in lower_name for p in ("credib", "可信", "risk", "burden", "exposure")):
                        mapping = ("credibility_impact", int)
                    if mapping:
                        logger.debug("维度模式匹配: %s → %s", dim_name, mapping[0])

                if mapping is not None:
                    field_name, expected_type = mapping
                    # dim_val 可能是 {"score": 85, "rationale": "..."} 或直接值
                    score = None
                    if isinstance(dim_val, dict):
                        raw = dim_val.get("score", dim_val.get("value", dim_val.get("rating")))
                        if isinstance(raw, (int, float)):
                            score = raw
                        elif isinstance(raw, str) and raw.replace(".", "", 1).lstrip("-").isdigit():
                            score = float(raw)
                    elif isinstance(dim_val, (int, float)):
                        score = dim_val
                    elif isinstance(dim_val, str) and dim_val.replace(".", "", 1).lstrip("-").isdigit():
                        # LLM 返回字符串数字如 "85"
                        score = float(dim_val)
                    elif isinstance(dim_val, str) and expected_type is str:
                        # 字符串枚举值（如 outcome_impact: "high"）直接提升
                        item.setdefault(field_name, dim_val)
                        continue
                    if score is not None:
                        # 多个维度映射到同一字段时取最大值
                        existing = item.get(field_name)
                        if existing is None or (isinstance(existing, (int, float)) and score > existing):
                            item[field_name] = score
                elif isinstance(dim_val, str):
                    # Opus 可能将枚举字段（如 proponent_evidence_strength）
                    # 放在 dimensions 内；直接提升到 item 顶层
                    item.setdefault(dim_name, dim_val)

        # 2. 字段别名归一化
        result = {}
        for key, val in item.items():
            normalized_key = cls._EVAL_FIELD_ALIASES.get(key, key)
            if normalized_key not in result:
                result[normalized_key] = val

        # 3. 量纲检测：如果所有评分维度（importance, swing, credibility）都 ≤ 10，
        #    可能是 LLM 使用了 0-10 量纲，需要 × 10 放大到 0-100
        result = cls._rescale_if_needed(result)
        return result

    @classmethod
    def _rescale_if_needed(cls, result: dict) -> dict:
        """检测并修正 0-10 量纲评分。仅当所有相关字段一致 ≤ 10 时触发。

        不触碰 dependency_depth（语义不同）和 evidence_strength_gap（可为负值）。
        混合量纲（部分 > 10, 部分 ≤ 10）时不做任何处理。
        """
        _RESCALE_FIELDS = ("importance_score", "swing_score", "credibility_impact")
        values = {}
        for field in _RESCALE_FIELDS:
            val = result.get(field)
            if isinstance(val, (int, float)):
                values[field] = val

        if len(values) < 2:
            return result  # 不够样本，不推断

        if max(values.values()) <= 0:
            return result  # 全零，无需放大

        if all(v <= 10 for v in values.values()):
            for field, val in values.items():
                result[field] = val * 10
            result["_score_rescaled"] = True
            logger.warning(
                "Score rescale 0-10→0-100 triggered: fields=%s, original=%s",
                list(values.keys()), {k: v for k, v in values.items()},
            )
        return result

    # ------------------------------------------------------------------
    # 排序 / Sorting
    # ------------------------------------------------------------------

    def _sort_issues(self, issues: list[Issue]) -> list[Issue]:
        """按 composite_score DESC 排序，原有分类排序为 fallback。

        composite_score 为 None 时排末尾。Python sorted() 保证稳定性。
        """
        return sorted(
            issues,
            key=lambda issue: (
                -(issue.composite_score or 0),
                _IMPACT_ORDER.get(issue.outcome_impact, 99),
                _ATTACK_ORDER.get(issue.opponent_attack_strength, 99),
            ),
        )

    # ------------------------------------------------------------------
    # 加权综合评分 / Composite scoring
    # ------------------------------------------------------------------

    # 权重配置：可按案型调整
    _COMPOSITE_WEIGHTS = {
        "importance": 0.30,
        "swing": 0.25,
        "gap_abs": 0.20,
        "credibility": 0.15,
        "depth": 0.10,
    }

    @classmethod
    def _compute_composite_score(cls, issue: Issue) -> float:
        """计算加权综合分。越高 = 争点越关键。

        - importance_score, swing_score, credibility_impact: 直接使用 (0-100)
        - evidence_strength_gap: 取绝对值（差距越大 = 争点越不稳定 = 越需关注）
        - dependency_depth: 浅层加分（根争点=100, depth=1→75, 2→50, 3→25, 4+→0）
        """
        w = cls._COMPOSITE_WEIGHTS
        imp = issue.importance_score or 0
        swi = issue.swing_score or 0
        gap = abs(issue.evidence_strength_gap or 0)
        cred = issue.credibility_impact or 0
        depth = issue.dependency_depth or 0
        depth_score = max(0, 100 - depth * 25)

        return (
            w["importance"] * imp
            + w["swing"] * swi
            + w["gap_abs"] * gap
            + w["credibility"] * cred
            + w["depth"] * depth_score
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
        unmatched = [ev.issue_id for ev in evaluations if ev.issue_id not in known_issue_ids]
        if unmatched:
            logger.warning("LLM 返回的 issue_id 无法匹配: %s", unmatched[:5])

        # Layer 2: fuzzy matching by suffix number when exact match fails
        if not eval_map and evaluations:
            logger.warning("eval_map 完全为空，尝试模糊匹配 issue_id...")
            for ev in evaluations:
                match = re.search(r'(\d{2,})$', ev.issue_id)
                if match:
                    suffix = match.group(1)
                    for kid in known_issue_ids:
                        if kid.endswith(suffix) and kid not in eval_map:
                            eval_map[kid] = ev
                            break
            if eval_map:
                logger.info("模糊匹配成功: %d/%d 条", len(eval_map), len(evaluations))

        logger.info("eval_map 匹配: %d/%d 条评估命中已知争点", len(eval_map), len(evaluations))

        enriched: list[Issue] = []
        unevaluated: list[str] = []
        # 区分"LLM 完全未返回"和"返回了但分类字段校验失败"
        not_in_eval_map: set[str] = set()

        for issue in issues:
            ev = eval_map.get(issue.issue_id)
            if ev is None:
                # LLM 未返回该争点的评估
                unevaluated.append(issue.issue_id)
                not_in_eval_map.add(issue.issue_id)
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

            # v2: 加权评分维度（clamp 到合法范围，不因超范围降级）
            updates["importance_score"] = max(0, min(100, ev.importance_score))
            updates["swing_score"] = max(0, min(100, ev.swing_score))
            updates["evidence_strength_gap"] = max(-100, min(100, ev.evidence_strength_gap))
            updates["dependency_depth"] = max(0, ev.dependency_depth)
            # 规则层覆盖：有 parent_issue_id 的争点深度至少为 1
            if issue.parent_issue_id and updates["dependency_depth"] == 0:
                updates["dependency_depth"] = 1
                logger.info("depth override: %s has parent=%s, forcing depth=1",
                            issue.issue_id, issue.parent_issue_id)
            updates["credibility_impact"] = max(0, min(100, ev.credibility_impact))

            if issue_degraded:
                unevaluated.append(issue.issue_id)

            enriched.append(issue.model_copy(update=updates))

        # 计算 composite_score（需在富化完成后）
        # 仅"LLM 完全未返回"的争点设 composite_score=None
        # "返回了但分类字段校验失败"的争点仍用 v2 评分维度计算 composite_score
        enriched = [
            i.model_copy(update={"composite_score": self._compute_composite_score(i)})
            if i.issue_id not in not_in_eval_map
            else i.model_copy(update={"composite_score": None})
            for i in enriched
        ]

        # 诊断：evaluated 争点的 composite_score 分布
        evaluated_scores = [
            i.composite_score for i in enriched
            if i.composite_score is not None
        ]
        if len(evaluated_scores) >= 3:
            spread = max(evaluated_scores) - min(evaluated_scores)
            if spread < 5.0:
                logger.warning(
                    "Composite scores poorly differentiated: spread=%.1f, "
                    "range=[%.1f, %.1f], count=%d",
                    spread, min(evaluated_scores), max(evaluated_scores),
                    len(evaluated_scores),
                )

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

    async def _call_llm_structured(self, system: str, user: str) -> dict:
        """调用 LLM（结构化输出），失败时抛出异常由 rank() 捕获。"""
        return await call_structured_llm(
            self._llm,
            system=system,
            user=user,
            model=self._model,
            tool_name="evaluate_issues",
            tool_description="对案件所有争点进行五维度批量评估（影响程度、证据强度、建议行动等）。"
                             "Batch-evaluate all case issues across five dimensions: "
                             "outcome impact, evidence strength, recommended action, etc.",
            tool_schema=_TOOL_SCHEMA,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            max_retries=self._max_retries,
        )
