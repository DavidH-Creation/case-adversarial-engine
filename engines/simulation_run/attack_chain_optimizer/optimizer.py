"""
AttackChainOptimizer — 最强攻击链生成模块主类。
Attack Chain Optimizer — main class for P0.4.

职责 / Responsibilities:
1. 接收 AttackChainOptimizerInput（owner_party_id + issue_tree + evidence_index）
2. 一次性调用 LLM 生成恰好 3 个最优攻击节点
3. 规则层：
   a. 过滤 attack_node_id 为空或已出现（去重）的节点
   b. 过滤 attack_description 为空的节点
   c. 过滤 target_issue_id 不在已知争点 ID 集合中的节点
   d. 过滤 supporting_evidence_ids 中的非法证据 ID；若过滤后为空，丢弃节点
   e. 取前 3 个有效节点（截断）
   f. 从有效节点列表生成 recommended_order（保持顺序）
4. LLM 整体失败返回空 OptimalAttackChain，不抛异常

合约保证 / Contract guarantees:
- top_attacks 最多 3 个节点（LLM 失败或有效节点不足时可能更少）
- 所有 AttackNode.attack_node_id 在输出中唯一（去重保证）
- 所有 AttackNode.target_issue_id 均为已知合法 ID
- 所有 AttackNode.supporting_evidence_ids 只含已知合法 ID 且非空
- recommended_order 与 top_attacks 的 attack_node_id 列表完全对应
- LLM 失败时返回空 OptimalAttackChain（case_id/run_id/owner_party_id 保留），不抛异常

注意 / Note:
- P0.4 不应用 v1.2 过渡规则（admitted_record 过滤），因为 spec 未对 attack_chain_optimizer
  明确要求此过滤，且攻击链生成需考虑当事人掌握的全量证据（含 private 证据用于攻防策略规划）。
  与 P0.3 的 DecisionPathTree 生成（需要 admitted_record 证据限制）不同，攻击链是策略层分析。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

logger = logging.getLogger(__name__)

from engines.shared.models import (
    AttackNode,
    LLMClient,
    OptimalAttackChain,
)

from .prompts import PROMPT_REGISTRY
from .schemas import (
    AttackChainOptimizerInput,
    LLMAttackChainOutput,
    LLMAttackNodeItem,
)

# 规则层：最多保留 3 个有效攻击节点
_MAX_ATTACKS = 3


class AttackChainOptimizer:
    """最强攻击链生成器。

    Args:
        llm_client:  符合 LLMClient 协议的客户端实例
        case_type:   案件类型（当前只支持 "civil_loan"）
        model:       LLM 模型标识
        temperature: 生成温度
        max_retries: LLM 调用失败时的最大重试次数（重试次数，不含初次调用；总调用次数 = max_retries + 1）
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

    async def optimize(self, inp: AttackChainOptimizerInput) -> OptimalAttackChain:
        """生成最强攻击链。

        Args:
            inp: 优化器输入

        Returns:
            OptimalAttackChain — 结构化最强攻击链，已完成规则层校验
        """
        # 构建已知 ID 集合（规则层过滤用）
        known_issue_ids: set[str] = {
            issue.issue_id for issue in inp.issue_tree.issues
        }
        known_evidence_ids: set[str] = {
            ev.evidence_id for ev in inp.evidence_index.evidence
        }

        # 调用 LLM
        llm_output = await self._call_llm(inp)
        if llm_output is None:
            return self._empty_chain(inp)

        # 规则层处理攻击节点
        valid_nodes = self._process_attack_nodes(
            llm_output.top_attacks,
            known_issue_ids=known_issue_ids,
            known_evidence_ids=known_evidence_ids,
        )

        # 生成 recommended_order（与 top_attacks 完全对应）
        recommended_order = [node.attack_node_id for node in valid_nodes]

        return OptimalAttackChain(
            chain_id=f"chain-{uuid4().hex[:8]}",
            case_id=inp.case_id,
            run_id=inp.run_id,
            owner_party_id=inp.owner_party_id,
            top_attacks=valid_nodes,
            recommended_order=recommended_order,
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    async def _call_llm(
        self, inp: AttackChainOptimizerInput
    ) -> LLMAttackChainOutput | None:
        """调用 LLM，失败时返回 None（不抛异常）。"""
        system = self._prompts["system"]
        user = self._prompts["build_user"](
            owner_party_id=inp.owner_party_id,
            issue_tree=inp.issue_tree,
            evidence_index=inp.evidence_index,
        )

        for _attempt in range(self._max_retries + 1):
            try:
                raw = await self._llm.create_message(
                    system=system,
                    user=user,
                    model=self._model,
                    temperature=self._temperature,
                )
                return self._parse_llm_output(raw)
            except Exception as e:  # noqa: BLE001
                logger.debug("AttackChainOptimizer LLM 调用失败（attempt=%d）: %s", _attempt, e)

        return None

    def _parse_llm_output(self, raw: str) -> LLMAttackChainOutput | None:
        """解析 LLM 输出 JSON，失败时返回 None。"""
        from engines.shared.json_utils import _extract_json_object
        try:
            data = _extract_json_object(raw)
            return LLMAttackChainOutput.model_validate(data)
        except Exception as e:  # noqa: BLE001
            logger.debug("AttackChainOptimizer LLM 输出解析失败: %s", e)
            return None

    def _process_attack_nodes(
        self,
        llm_nodes: list[LLMAttackNodeItem],
        *,
        known_issue_ids: set[str],
        known_evidence_ids: set[str],
    ) -> list[AttackNode]:
        """规则层处理攻击节点列表，返回最多 _MAX_ATTACKS 个有效节点。

        过滤规则：
        1. attack_node_id 为空或已出现（去重） → 丢弃
        2. attack_description 为空 → 丢弃
        3. target_issue_id 为空或不在 known_issue_ids → 丢弃
        4. supporting_evidence_ids 过滤非法 ID；过滤后为空 → 丢弃节点
        5. 取前 _MAX_ATTACKS 个通过校验的节点
        """
        result: list[AttackNode] = []
        seen_node_ids: set[str] = set()

        for item in llm_nodes:
            if len(result) >= _MAX_ATTACKS:
                break

            # 必填字段校验 + attack_node_id 去重
            if not item.attack_node_id:
                continue
            if item.attack_node_id in seen_node_ids:
                continue
            if not item.attack_description:
                continue
            if not item.target_issue_id or item.target_issue_id not in known_issue_ids:
                continue

            # 过滤 supporting_evidence_ids 中的非法 ID
            clean_evidence_ids = [
                eid for eid in item.supporting_evidence_ids
                if eid in known_evidence_ids
            ]
            # 零容忍：过滤后为空则丢弃节点
            if not clean_evidence_ids:
                continue

            result.append(AttackNode(
                attack_node_id=item.attack_node_id,
                target_issue_id=item.target_issue_id,
                attack_description=item.attack_description,
                success_conditions=item.success_conditions,
                supporting_evidence_ids=clean_evidence_ids,
                counter_measure=item.counter_measure,
                adversary_pivot_strategy=item.adversary_pivot_strategy,
            ))
            seen_node_ids.add(item.attack_node_id)

        return result

    def _empty_chain(self, inp: AttackChainOptimizerInput) -> OptimalAttackChain:
        """LLM 失败时返回空 OptimalAttackChain。"""
        return OptimalAttackChain(
            chain_id=f"chain-failed-{uuid4().hex[:8]}",
            case_id=inp.case_id,
            run_id=inp.run_id,
            owner_party_id=inp.owner_party_id,
            top_attacks=[],
            recommended_order=[],
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
