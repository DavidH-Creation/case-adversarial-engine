"""
AdmissibilityEvaluator — 证据可采性评估模块主类。
Admissibility Evaluator — main class for admissibility gate system.

职责 / Responsibilities:
1. 接收 AdmissibilityEvaluatorInput（case_id + run_id + evidence_index）
2. 调用 LLM 批量评估所有证据的可采性
3. 规则层：
   a. evidence_id 必须在已知证据 ID 集合中，否则跳过
   b. admissibility_score 必须在 [0.0, 1.0] 范围内，否则跳过该条
   c. admissibility_score < 0.5 时必须有非空 admissibility_challenges，否则跳过
   d. 通过校验的证据更新三个可采性字段
4. LLM 失败或 JSON 解析失败 → 返回原始 EvidenceIndex（保留默认值），不抛异常
5. 空证据列表 → 跳过 LLM 调用，直接返回

合约保证 / Contract guarantees:
- 原始 Evidence 字段不变（只追加/更新可采性字段）
- admissibility_score 保持在 [0.0, 1.0] 之间（规则层保证）
- admissibility_score < 0.5 时 admissibility_challenges 必须非空
- LLM 失败时返回原始 EvidenceIndex（admissibility_score 保持默认 1.0），不抛异常
- 空证据列表不调用 LLM
"""
from __future__ import annotations

import logging
from copy import deepcopy

logger = logging.getLogger(__name__)

from engines.shared.evidence_state_machine import EvidenceStateMachine
from engines.shared.models import EvidenceIndex, EvidenceStatus, LLMClient

from .prompts import PROMPT_REGISTRY
from .schemas import (
    AdmissibilityEvaluatorInput,
    LLMAdmissibilityItem,
    LLMAdmissibilityOutput,
)

# 评分精度限制
_SCORE_DECIMALS = 2
_SCORE_LOW_THRESHOLD = 0.5  # 低于此值时必须有质疑理由


class AdmissibilityEvaluator:
    """证据可采性评估器。

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

    async def evaluate(self, inp: AdmissibilityEvaluatorInput) -> EvidenceIndex:
        """对证据索引中的所有证据进行可采性评估。

        Args:
            inp: 评估器输入

        Returns:
            更新后的 EvidenceIndex——通过规则层校验的证据已填充三个可采性字段
        """
        if not inp.evidence_index.evidence:
            return inp.evidence_index

        # v2: enforce — only evaluate evidence that has been at least submitted
        non_private = [
            ev.evidence_id for ev in inp.evidence_index.evidence
            if ev.status != EvidenceStatus.private
        ]
        if non_private:
            EvidenceStateMachine().enforce_minimum_status(
                inp.evidence_index,
                EvidenceStatus.submitted,
                evidence_ids=non_private,
            )

        known_ids: set[str] = {ev.evidence_id for ev in inp.evidence_index.evidence}

        llm_output = await self._call_llm(inp)
        if llm_output is None:
            return inp.evidence_index

        assessed_map = self._build_assessed_map(llm_output.evidence_assessments, known_ids)

        updated_evidence = []
        for ev in inp.evidence_index.evidence:
            item = assessed_map.get(ev.evidence_id)
            if item is not None:
                ev = deepcopy(ev)
                ev.admissibility_score = item["admissibility_score"]
                ev.admissibility_challenges = item["admissibility_challenges"]
                if item["exclusion_impact"] is not None:
                    ev.exclusion_impact = item["exclusion_impact"]
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
        self, inp: AdmissibilityEvaluatorInput
    ) -> LLMAdmissibilityOutput | None:
        """调用 LLM，失败时返回 None（不抛异常）。"""
        system = self._prompts["system"]
        user = self._prompts["build_user"](evidence_index=inp.evidence_index)

        from engines.shared.llm_utils import call_llm_with_retry
        try:
            raw = await call_llm_with_retry(
                self._llm,
                system=system,
                user=user,
                model=self._model,
                temperature=self._temperature,
                max_retries=self._max_retries,
            )
            return self._parse_llm_output(raw)
        except Exception as e:  # noqa: BLE001
            logger.debug("AdmissibilityEvaluator LLM 调用失败: %s", type(e).__name__)
            return None

    def _parse_llm_output(self, raw: str) -> LLMAdmissibilityOutput | None:
        """解析 LLM 输出 JSON，失败时返回 None。"""
        from engines.shared.json_utils import _extract_json_object
        try:
            data = _extract_json_object(raw)
            return LLMAdmissibilityOutput.model_validate(data)
        except Exception as e:  # noqa: BLE001
            logger.debug("AdmissibilityEvaluator LLM 输出解析失败: %s", e)
            return None

    def _build_assessed_map(
        self,
        items: list[LLMAdmissibilityItem],
        known_ids: set[str],
    ) -> dict[str, dict]:
        """规则层：校验 LLM 输出，返回 evidence_id → 已校验字段字典的映射。

        过滤规则：
        1. evidence_id 不在 known_ids → 跳过
        2. admissibility_score 不在 [0.0, 1.0] → 跳过该条
        3. admissibility_score < 0.5 但 admissibility_challenges 为空 → 跳过
        """
        result: dict[str, dict] = {}

        for item in items:
            if not item.evidence_id or item.evidence_id not in known_ids:
                continue

            # 分数范围校验
            score = item.admissibility_score
            try:
                score = round(float(score), _SCORE_DECIMALS)
            except (TypeError, ValueError):
                logger.debug(
                    "AdmissibilityEvaluator: 证据 %s score 非法: %r，跳过。",
                    item.evidence_id, item.admissibility_score,
                )
                continue

            if not (0.0 <= score <= 1.0):
                logger.debug(
                    "AdmissibilityEvaluator: 证据 %s score=%.2f 越界，跳过。",
                    item.evidence_id, score,
                )
                continue

            # 低分时必须有质疑理由
            challenges = [c for c in item.admissibility_challenges if c and c.strip()]
            if score < _SCORE_LOW_THRESHOLD and not challenges:
                logger.debug(
                    "AdmissibilityEvaluator: 证据 %s score=%.2f 低但无 challenges，跳过。",
                    item.evidence_id, score,
                )
                continue

            result[item.evidence_id] = {
                "admissibility_score": score,
                "admissibility_challenges": challenges,
                "exclusion_impact": item.exclusion_impact,
            }

        return result
