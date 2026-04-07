"""
DefenseChainOptimizer — 原告方防御链优化器（P2）。
Plaintiff Defense Chain Optimizer (P2).

职责 / Responsibilities:
1. 接收争点列表 + 证据索引 + 原告方 ID
2. 调用 LLM 生成每个争点的防御论点
3. 规则层：校验证据 ID 合法性、枚举字段合法性
4. 按 priority 排序，构建 PlaintiffDefenseChain
5. LLM 失败时返回降级结果（不抛异常）

合约保证 / Contract guarantees:
- evidence_ids 引用非法时清空，不丢弃整条论点
- priority 冲突时按输入顺序重新编号
- LLM 整体失败时返回 failed 结果（空 defense_points）
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from engines.shared.json_utils import _extract_json_object
from engines.shared.models import LLMClient

from .models import DefensePoint, PlaintiffDefenseChain
from .schemas import DefenseChainInput, DefenseChainResult, LLMDefenseChainOutput

logger = logging.getLogger(__name__)


class DefenseChainOptimizer:
    """原告方防御链优化器。

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
        self._case_type = case_type
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
            raise ValueError(f"不支持的案由类型: '{case_type}'。可用: {available}")
        return PROMPT_REGISTRY[case_type]

    async def optimize(self, inp: DefenseChainInput) -> DefenseChainResult:
        """执行防御链优化。

        Args:
            inp: 优化器输入（含争点列表、证据索引、原告方 ID）

        Returns:
            DefenseChainResult — 含 PlaintiffDefenseChain 和元信息
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        chain_id = str(uuid.uuid4())
        issues = list(inp.issues)

        if not issues:
            return DefenseChainResult(
                chain=PlaintiffDefenseChain(
                    chain_id=chain_id,
                    case_id=inp.case_id,
                    confidence_score=0.0,
                    created_at=now,
                ),
                metadata={"issue_count": 0, "created_at": now},
            )

        known_issue_ids: set[str] = {i.issue_id for i in issues}
        known_evidence_ids: set[str] = {e.evidence_id for e in inp.evidence_index.evidence}

        try:
            from .prompts import plugin

            system_prompt = self._prompt_module.SYSTEM_PROMPT
            user_prompt = plugin.get_prompt(
                "defense_chain",
                self._case_type,
                {
                    "issues": issues,
                    "evidence_index": inp.evidence_index,
                    "plaintiff_party_id": inp.plaintiff_party_id,
                },
            )

            raw_response = await self._call_llm_with_retry(system_prompt, user_prompt)
            logger.info("LLM 原始响应长度: %d chars", len(raw_response))

            raw_dict = _extract_json_object(raw_response)
            llm_output = LLMDefenseChainOutput.model_validate(raw_dict)
            logger.info("防御论点数: %d", len(llm_output.defense_points))

            defense_points, unevaluated = self._apply_defense_points(
                llm_output=llm_output,
                known_issue_ids=known_issue_ids,
                known_evidence_ids=known_evidence_ids,
            )

            # 按 priority 升序排序，冲突时保持相对顺序
            defense_points.sort(key=lambda p: p.priority)
            # 重新编号确保连续
            for idx, point in enumerate(defense_points, start=1):
                object.__setattr__(point, "priority", idx) if hasattr(
                    point, "__setattr__"
                ) else None
                defense_points[idx - 1] = point.model_copy(update={"priority": idx})

            evidence_support = sorted({eid for p in defense_points for eid in p.evidence_ids})

            chain = PlaintiffDefenseChain(
                chain_id=chain_id,
                case_id=inp.case_id,
                target_issues=[p.issue_id for p in defense_points],
                defense_points=defense_points,
                evidence_support=evidence_support,
                confidence_score=max(0.0, min(1.0, llm_output.confidence_score)),
                strategic_summary=llm_output.strategic_summary,
                created_at=now,
            )

            return DefenseChainResult(
                chain=chain,
                unevaluated_issue_ids=unevaluated,
                metadata={
                    "model": self._model,
                    "temperature": self._temperature,
                    "evaluated_count": len(issues) - len(unevaluated),
                    "total_count": len(issues),
                    "created_at": now,
                },
            )

        except Exception:
            logger.warning("DefenseChainOptimizer LLM 调用或解析失败", exc_info=True)
            return DefenseChainResult(
                chain=PlaintiffDefenseChain(
                    chain_id=chain_id,
                    case_id=inp.case_id,
                    confidence_score=0.0,
                    created_at=now,
                ),
                unevaluated_issue_ids=[i.issue_id for i in issues],
                metadata={"failed": True, "created_at": now},
            )

    # ------------------------------------------------------------------
    # 规则层 / Rule layer
    # ------------------------------------------------------------------

    def _apply_defense_points(
        self,
        llm_output: LLMDefenseChainOutput,
        known_issue_ids: set[str],
        known_evidence_ids: set[str],
    ) -> tuple[list[DefensePoint], list[str]]:
        """校验并构建 DefensePoint 列表。

        - 过滤引用不存在 issue_id 的论点
        - 过滤证据引用中的非法 evidence_id
        - 补全缺失的必要字段（strategy/argument 为空时标记为 unevaluated）
        """
        points: list[DefensePoint] = []
        unevaluated: list[str] = []
        evaluated_issue_ids: set[str] = set()

        for raw_point in llm_output.defense_points:
            if raw_point.issue_id not in known_issue_ids:
                logger.warning("LLM 返回未知 issue_id: %s（已忽略）", raw_point.issue_id)
                continue

            # 过滤非法证据引用
            valid_evidence_ids = [
                eid for eid in raw_point.evidence_ids if eid in known_evidence_ids
            ]
            if len(valid_evidence_ids) < len(raw_point.evidence_ids):
                invalid = set(raw_point.evidence_ids) - set(valid_evidence_ids)
                logger.warning(
                    "issue %s 的防御论点含非法 evidence_ids: %s（已过滤）",
                    raw_point.issue_id,
                    invalid,
                )

            if not raw_point.defense_strategy or not raw_point.supporting_argument:
                logger.warning(
                    "issue %s 的防御论点缺少 strategy 或 argument（已标记为 unevaluated）",
                    raw_point.issue_id,
                )
                unevaluated.append(raw_point.issue_id)
                continue

            points.append(
                DefensePoint(
                    point_id=str(uuid.uuid4()),
                    issue_id=raw_point.issue_id,
                    defense_strategy=raw_point.defense_strategy,
                    supporting_argument=raw_point.supporting_argument,
                    evidence_ids=valid_evidence_ids,
                    priority=max(1, raw_point.priority),
                )
            )
            evaluated_issue_ids.add(raw_point.issue_id)

        # 记录 LLM 完全遗漏的争点
        for issue_id in known_issue_ids:
            if issue_id not in evaluated_issue_ids and issue_id not in unevaluated:
                unevaluated.append(issue_id)

        return points, unevaluated

    # ------------------------------------------------------------------
    # LLM 调用（带重试）/ LLM call with retry
    # ------------------------------------------------------------------

    async def _call_llm_with_retry(self, system: str, user: str) -> str:
        from engines.shared.llm_utils import call_llm_with_retry

        return await call_llm_with_retry(
            self._llm,
            system=system,
            user=user,
            model=self._model,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            max_retries=self._max_retries,
        )
