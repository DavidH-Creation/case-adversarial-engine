"""
EvidenceWeightScorer — 证据权重评分模块主类。
Evidence Weight Scorer — main class for P1.5.

职责 / Responsibilities:
1. 接收 EvidenceWeightScorerInput（case_id + run_id + evidence_index）
2. 调用 LLM 批量评分所有证据的四个维度
3. 规则层：
   a. evidence_id 必须在已知证据 ID 集合中，否则跳过
   b. 四个枚举字段必须映射为合法枚举值，否则该条跳过
   c. authenticity_risk=high 或 vulnerability=high 时必须有 admissibility_notes，否则跳过
   d. 通过校验的证据更新字段并设 evidence_weight_scored=True
4. LLM 失败或 JSON 解析失败 → 返回原始 EvidenceIndex，不抛异常
5. 空证据列表 → 跳过 LLM 调用，直接返回

合约保证 / Contract guarantees:
- 原始 Evidence 字段不变（只追加/更新权重字段）
- evidence_weight_scored=True 当且仅当四个字段全部成功设置
- authenticity_risk=high 或 vulnerability=high 时必须有 admissibility_notes
- LLM 失败时返回原始 EvidenceIndex（evidence_weight_scored 保持 False），不抛异常
- 空证据列表不调用 LLM
"""
from __future__ import annotations

import logging
from copy import deepcopy

logger = logging.getLogger(__name__)

from engines.shared.models import (
    AuthenticityRisk,
    EvidenceIndex,
    LLMClient,
    ProbativeValue,
    RelevanceScore,
    Vulnerability,
)

from engines.shared.structured_output import call_structured_llm

from .prompts import PROMPT_REGISTRY
from .schemas import (
    EvidenceWeightScorerInput,
    LLMEvidenceWeightItem,
    LLMEvidenceWeightOutput,
)

# tool_use JSON Schema（模块加载时计算一次）
_TOOL_SCHEMA: dict = LLMEvidenceWeightOutput.model_json_schema()

# 枚举映射表（字符串 → 枚举值）
_AUTHENTICITY_RISK_MAP: dict[str, AuthenticityRisk] = {v.value: v for v in AuthenticityRisk}
_RELEVANCE_SCORE_MAP: dict[str, RelevanceScore] = {v.value: v for v in RelevanceScore}
_PROBATIVE_VALUE_MAP: dict[str, ProbativeValue] = {v.value: v for v in ProbativeValue}
_VULNERABILITY_MAP: dict[str, Vulnerability] = {v.value: v for v in Vulnerability}


class EvidenceWeightScorer:
    """证据权重评分器。

    Args:
        llm_client:  符合 LLMClient 协议的客户端实例
        case_type:   案件类型（当前只支持 "civil_loan"）
        model:       LLM 模型标识
        temperature: 生成温度
        max_retries: LLM 失败最大重试次数（重试次数，不含初次调用；总调用次数 = max_retries + 1）
    """

    def __init__(
        self,
        llm_client: LLMClient,
        case_type: str = "civil_loan",
        *,
        model: str,
        temperature: float,
        max_retries: int,
    ) -> None:
        if case_type not in PROMPT_REGISTRY:
            raise ValueError(f"不支持的案件类型: {case_type}")
        self._llm = llm_client
        self._prompts = PROMPT_REGISTRY[case_type]
        self._model = model
        self._temperature = temperature
        self._max_retries = max_retries

    async def score(self, inp: EvidenceWeightScorerInput) -> EvidenceIndex:
        """对证据索引中的所有证据进行四维权重评分。

        Args:
            inp: 评分器输入

        Returns:
            更新后的 EvidenceIndex——通过规则层校验的证据已填充四个权重字段
        """
        # 空证据列表 → 跳过 LLM 调用
        if not inp.evidence_index.evidence:
            return inp.evidence_index

        # 构建已知 ID 集合（规则层过滤用）
        known_ids: set[str] = {ev.evidence_id for ev in inp.evidence_index.evidence}

        # 调用 LLM
        llm_output = await self._call_llm(inp)
        if llm_output is None:
            return inp.evidence_index

        # 规则层：构建 evidence_id → 已校验字段字典的映射
        scored_map = self._build_scored_map(llm_output.evidence_weights, known_ids)

        # 更新证据对象（深拷贝，不修改输入）
        updated_evidence = []
        for ev in inp.evidence_index.evidence:
            item = scored_map.get(ev.evidence_id)
            if item is not None:
                ev = deepcopy(ev)
                ev.authenticity_risk = item["authenticity_risk"]
                ev.relevance_score = item["relevance_score"]
                ev.probative_value = item["probative_value"]
                ev.vulnerability = item["vulnerability"]
                if item["admissibility_notes"]:
                    ev.admissibility_notes = item["admissibility_notes"]
                ev.evidence_weight_scored = True
            updated_evidence.append(ev)

        return EvidenceIndex(
            case_id=inp.evidence_index.case_id,
            evidence=updated_evidence,
            extraction_metadata=inp.evidence_index.extraction_metadata,
        )

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    async def _call_llm(
        self, inp: EvidenceWeightScorerInput
    ) -> LLMEvidenceWeightOutput | None:
        """调用 LLM（结构化输出优先，fallback 到 json_utils），失败时返回 None（不抛异常）。
        Call LLM (structured output first, fallback to json_utils); returns None on failure.
        """
        system = self._prompts["system"]
        user = self._prompts["build_user"](evidence_index=inp.evidence_index)

        try:
            data = await call_structured_llm(
                self._llm,
                system=system,
                user=user,
                model=self._model,
                tool_name="score_evidence_weights",
                tool_description="对案件证据进行四维度权重评分（真实性风险、相关度、证明力、脆弱性）。"
                                 "Score case evidence on four dimensions: authenticity risk, "
                                 "relevance, probative value, and vulnerability.",
                tool_schema=_TOOL_SCHEMA,
                temperature=self._temperature,
                max_retries=self._max_retries,
            )
            return LLMEvidenceWeightOutput.model_validate(data)
        except Exception as e:  # noqa: BLE001
            logger.debug("EvidenceWeightScorer LLM 调用或解析失败: %s", type(e).__name__)
            return None

    def _build_scored_map(
        self,
        items: list[LLMEvidenceWeightItem],
        known_ids: set[str],
    ) -> dict[str, dict]:
        """规则层：校验 LLM 输出，返回 evidence_id → 已校验字段字典的映射。

        过滤规则：
        1. evidence_id 不在 known_ids → 跳过
        2. 任一枚举字段无法映射为合法枚举值 → 跳过该条
        3. authenticity_risk=high 或 vulnerability=high 但 admissibility_notes 为空 → 跳过
        """
        result: dict[str, dict] = {}

        for item in items:
            if not item.evidence_id or item.evidence_id not in known_ids:
                continue

            # 枚举校验
            ar = _AUTHENTICITY_RISK_MAP.get(item.authenticity_risk)
            rs = _RELEVANCE_SCORE_MAP.get(item.relevance_score)
            pv = _PROBATIVE_VALUE_MAP.get(item.probative_value)
            vl = _VULNERABILITY_MAP.get(item.vulnerability)

            if ar is None or rs is None or pv is None or vl is None:
                logger.debug(
                    "EvidenceWeightScorer: 证据 %s 枚举值非法，跳过。"
                    " authenticity_risk=%r, relevance_score=%r,"
                    " probative_value=%r, vulnerability=%r",
                    item.evidence_id,
                    item.authenticity_risk,
                    item.relevance_score,
                    item.probative_value,
                    item.vulnerability,
                )
                continue

            # admissibility_notes 强制要求
            notes = item.admissibility_notes
            if (ar == AuthenticityRisk.high or vl == Vulnerability.high) and not notes:
                logger.debug(
                    "EvidenceWeightScorer: 证据 %s 高风险但缺少 admissibility_notes，跳过。",
                    item.evidence_id,
                )
                continue

            result[item.evidence_id] = {
                "authenticity_risk": ar,
                "relevance_score": rs,
                "probative_value": pv,
                "vulnerability": vl,
                "admissibility_notes": notes,
            }

        return result
