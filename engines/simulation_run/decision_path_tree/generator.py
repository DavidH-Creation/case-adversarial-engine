"""
DecisionPathTreeGenerator — 裁判路径树生成模块主类。
Decision Path Tree Generator — main class for P0.3.

职责 / Responsibilities:
1. 接收 DecisionPathTreeInput（ranked_issue_tree + evidence_index + amount_report）
2. 只将 status 为 admitted_for_discussion 的证据纳入，其余不传入 LLM 也不加入 known_evidence_ids
3. 一次性调用 LLM 生成 3-6 条裁判路径和阻断条件
4. 规则层：
   a. verdict_block_active=True → 强制清空所有 confidence_interval
   b. confidence_interval 有效性校验（lower <= upper，超出范围清空）
   c. 过滤 trigger_issue_ids / key_evidence_ids / blocking_condition IDs 中的非法值
   d. 路径数截断（>6 → 6）
   e. 从 AmountConsistencyCheck.unresolved_conflicts 自动注入 amount_conflict BlockingCondition
5. LLM 整体失败返回空 DecisionPathTree，不抛异常

合约保证 / Contract guarantees:
- private 证据不传入 LLM，不计入 known_evidence_ids
- verdict_block_active=True 时所有 paths 的 confidence_interval 为 None
- confidence_interval lower > upper 时清空
- key_evidence_ids / trigger_issue_ids 只含已知合法 ID
- paths 数量不超过 6
- unresolved_conflicts 非空时自动注入 amount_conflict BlockingCondition（条件 ID 不重复）
- LLM 失败时返回空 DecisionPathTree（case_id/run_id 保留），不抛异常
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from engines.shared.models import (
    AmountConflict,
    BlockingCondition,
    BlockingConditionType,
    ConfidenceInterval,
    DecisionPath,
    DecisionPathTree,
    EvidenceIndex,
    EvidenceStatus,
    LLMClient,
)

from .prompts import PROMPT_REGISTRY
from .schemas import (
    DecisionPathTreeInput,
    LLMBlockingConditionItem,
    LLMDecisionPathItem,
    LLMDecisionPathTreeOutput,
)

_MAX_PATHS = 6

# v1.5: 只有 admitted_for_discussion 状态的证据进入裁判路径树
_ADMITTED_STATUSES: frozenset[EvidenceStatus] = frozenset({
    EvidenceStatus.admitted_for_discussion,
})


class DecisionPathTreeGenerator:
    """裁判路径树生成器。

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

    async def generate(self, inp: DecisionPathTreeInput) -> DecisionPathTree:
        """生成裁判路径树。

        Args:
            inp: 生成器输入

        Returns:
            DecisionPathTree — 结构化裁判路径树，已完成规则层校验
        """
        check = inp.amount_calculation_report.consistency_check_result

        # 只取 admitted_for_discussion 状态的证据
        admitted_evidences = [
            ev for ev in inp.evidence_index.evidence
            if ev.status in _ADMITTED_STATUSES
        ]
        admitted_index = EvidenceIndex(
            case_id=inp.evidence_index.case_id,
            evidence=admitted_evidences,
        )

        # 构建已知 ID 集合（规则层过滤用）
        known_issue_ids: set[str] = {
            issue.issue_id for issue in inp.ranked_issue_tree.issues
        }
        known_evidence_ids: set[str] = {ev.evidence_id for ev in admitted_evidences}

        # 调用 LLM（传入过滤后的证据索引）
        llm_output = await self._call_llm(inp, admitted_index)
        if llm_output is None:
            return self._empty_tree(inp)

        # 规则层处理路径
        cleaned_paths = self._process_paths(
            llm_output.paths,
            known_issue_ids=known_issue_ids,
            known_evidence_ids=known_evidence_ids,
            verdict_block_active=check.verdict_block_active,
        )

        # 规则层处理阻断条件
        cleaned_blocking = self._process_blocking_conditions(
            llm_output.blocking_conditions,
            unresolved_conflicts=check.unresolved_conflicts,
            known_issue_ids=known_issue_ids,
            known_evidence_ids=known_evidence_ids,
        )

        return DecisionPathTree(
            tree_id=f"tree-{uuid4().hex[:8]}",
            case_id=inp.case_id,
            run_id=inp.run_id,
            paths=cleaned_paths,
            blocking_conditions=cleaned_blocking,
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    async def _call_llm(
        self, inp: DecisionPathTreeInput, admitted_index: EvidenceIndex
    ) -> LLMDecisionPathTreeOutput | None:
        """调用 LLM，失败时返回 None（不抛异常）。"""
        system = self._prompts["system"]
        user = self._prompts["build_user"](
            issue_tree=inp.ranked_issue_tree,
            evidence_index=admitted_index,
            amount_report=inp.amount_calculation_report,
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
            except Exception:  # noqa: BLE001
                pass

        return None

    @staticmethod
    def _normalize_llm_json(data: dict) -> dict:
        """Normalize alternative field names LLM may use.

        LLM sometimes returns 'decision_paths' instead of 'paths',
        or uses completely different sub-structures (decision_chain, outcome objects, etc.).
        This method maps them back to the expected schema.
        """
        # Top-level: decision_paths → paths
        if "paths" not in data and "decision_paths" in data:
            data["paths"] = data.pop("decision_paths")

        # Normalize individual path items
        for p in data.get("paths", []):
            if not isinstance(p, dict):
                continue

            # --- trigger_condition ---
            if "trigger_condition" not in p:
                for alias in ("trigger", "path_label", "condition", "路径条件"):
                    if alias in p:
                        p["trigger_condition"] = p.pop(alias)
                        break

            # --- possible_outcome (may be a string or a dict) ---
            if "possible_outcome" not in p:
                for alias in ("outcome", "outcome_detail", "裁判结果"):
                    if alias in p:
                        val = p.pop(alias)
                        if isinstance(val, dict):
                            # Flatten dict to string: "judgment (principal_awarded=X)"
                            parts = []
                            if "judgment" in val:
                                parts.append(val["judgment"])
                            if val.get("principal_awarded") is not None:
                                parts.append(f"本金裁定={val['principal_awarded']}")
                            if val.get("interest_supported"):
                                parts.append("利息支持")
                            if val.get("costs_borne_by"):
                                parts.append(f"诉讼费={val['costs_borne_by']}")
                            p["possible_outcome"] = "；".join(parts) if parts else str(val)
                        else:
                            p["possible_outcome"] = str(val)
                        break

            # --- confidence_interval from probability_tier ---
            if "confidence_interval" not in p and "probability_tier" in p:
                tier_map = {
                    "高": (0.65, 0.85), "较高": (0.55, 0.75),
                    "中": (0.35, 0.55), "中等": (0.35, 0.55),
                    "中低": (0.2, 0.4), "较低": (0.1, 0.3), "低": (0.05, 0.2),
                }
                tier = p.pop("probability_tier", "")
                if tier in tier_map:
                    lo, hi = tier_map[tier]
                    p["confidence_interval"] = {"lower": lo, "upper": hi}

            # --- Extract trigger_issue_ids + key_evidence_ids from decision_chain ---
            chain = p.get("decision_chain") or p.get("key_reasoning_chain") or []
            if isinstance(chain, list) and chain:
                if "trigger_issue_ids" not in p or not p["trigger_issue_ids"]:
                    issue_ids = []
                    seen = set()
                    for node in chain:
                        if isinstance(node, dict):
                            for iid in node.get("issue_refs", []):
                                if iid not in seen:
                                    issue_ids.append(iid)
                                    seen.add(iid)
                    p["trigger_issue_ids"] = issue_ids

                if "key_evidence_ids" not in p or not p["key_evidence_ids"]:
                    ev_ids = []
                    seen = set()
                    for node in chain:
                        if isinstance(node, dict):
                            for eid in node.get("key_evidence", []):
                                if eid not in seen:
                                    ev_ids.append(eid)
                                    seen.add(eid)
                    p["key_evidence_ids"] = ev_ids

            # --- path_notes aliases ---
            if "path_notes" not in p:
                for alias in ("risk_notes", "notes", "备注"):
                    if alias in p:
                        p["path_notes"] = p.pop(alias)
                        break

            # Flatten decision_chain to path_notes if still missing
            if "path_notes" not in p and isinstance(chain, list) and chain:
                notes_parts = []
                for node in chain:
                    if isinstance(node, dict):
                        q = node.get("question", "")
                        r = node.get("ruling", "")
                        if q and r:
                            notes_parts.append(f"{q} → {r}")
                p["path_notes"] = "; ".join(notes_parts) if notes_parts else ""

        return data

    def _parse_llm_output(self, raw: str) -> LLMDecisionPathTreeOutput | None:
        """解析 LLM 输出 JSON，失败时返回 None。
        注意：_extract_json_object 在失败时抛出 ValueError（不返回 None），由此处的
        except Exception 捕获并统一返回 None。
        """
        from engines.shared.json_utils import _extract_json_object
        try:
            data = _extract_json_object(raw)
            data = self._normalize_llm_json(data)
            return LLMDecisionPathTreeOutput.model_validate(data)
        except Exception:  # noqa: BLE001
            return None

    def _process_paths(
        self,
        llm_paths: list[LLMDecisionPathItem],
        *,
        known_issue_ids: set[str],
        known_evidence_ids: set[str],
        verdict_block_active: bool,
    ) -> list[DecisionPath]:
        """规则层处理路径列表。"""
        candidates = llm_paths[:_MAX_PATHS]

        result: list[DecisionPath] = []
        for item in candidates:
            if not item.path_id or not item.trigger_condition or not item.possible_outcome:
                continue

            clean_issue_ids = [i for i in item.trigger_issue_ids if i in known_issue_ids]
            clean_evidence_ids = [e for e in item.key_evidence_ids if e in known_evidence_ids]

            ci: ConfidenceInterval | None = None
            if not verdict_block_active and item.confidence_interval is not None:
                try:
                    ci = ConfidenceInterval(
                        lower=item.confidence_interval.lower,
                        upper=item.confidence_interval.upper,
                    )
                except Exception:  # noqa: BLE001
                    ci = None  # lower > upper 或越界 → 清空

            result.append(DecisionPath(
                path_id=item.path_id,
                trigger_condition=item.trigger_condition,
                trigger_issue_ids=clean_issue_ids,
                key_evidence_ids=clean_evidence_ids,
                possible_outcome=item.possible_outcome,
                confidence_interval=ci,
                path_notes=item.path_notes,
            ))

        return result

    def _process_blocking_conditions(
        self,
        llm_conditions: list[LLMBlockingConditionItem],
        *,
        unresolved_conflicts: list[AmountConflict],
        known_issue_ids: set[str],
        known_evidence_ids: set[str],
    ) -> list[BlockingCondition]:
        """规则层处理阻断条件，并自动注入来自 unresolved_conflicts 的 amount_conflict。"""
        result: list[BlockingCondition] = []
        seen_condition_ids: set[str] = set()

        for item in llm_conditions:
            if not item.condition_id or not item.description:
                continue
            try:
                ctype = BlockingConditionType(item.condition_type)
            except ValueError:
                continue

            clean_issue_ids = [i for i in item.linked_issue_ids if i in known_issue_ids]
            clean_evidence_ids = [e for e in item.linked_evidence_ids if e in known_evidence_ids]

            result.append(BlockingCondition(
                condition_id=item.condition_id,
                condition_type=ctype,
                description=item.description,
                linked_issue_ids=clean_issue_ids,
                linked_evidence_ids=clean_evidence_ids,
            ))
            seen_condition_ids.add(item.condition_id)

        # 自动注入 unresolved_conflicts → amount_conflict（去重：auto_id 固定格式 bc-auto-<conflict_id>）
        for conflict in unresolved_conflicts:
            auto_id = f"bc-auto-{conflict.conflict_id}"
            if auto_id in seen_condition_ids:
                continue

            ev_ids = [
                ev_id for ev_id in (
                    conflict.source_a_evidence_id,
                    conflict.source_b_evidence_id,
                )
                if ev_id and ev_id in known_evidence_ids
            ]

            result.append(BlockingCondition(
                condition_id=auto_id,
                condition_type=BlockingConditionType.amount_conflict,
                description=conflict.conflict_description,
                linked_issue_ids=[],
                linked_evidence_ids=ev_ids,
            ))

        return result

    def _empty_tree(self, inp: DecisionPathTreeInput) -> DecisionPathTree:
        """LLM 失败时返回空 DecisionPathTree。"""
        return DecisionPathTree(
            tree_id=f"tree-failed-{uuid4().hex[:8]}",
            case_id=inp.case_id,
            run_id=inp.run_id,
            paths=[],
            blocking_conditions=[],
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
