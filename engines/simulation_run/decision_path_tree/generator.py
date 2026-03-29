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

import logging
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
_VALID_RESULT_SCOPES = frozenset({
    "principal", "interest", "penalty", "liability_allocation",
    "credibility", "attorney_fee", "costs",
})

logger = logging.getLogger(__name__)

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
            issues=list(inp.ranked_issue_tree.issues),
            evidence_index=inp.evidence_index,
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

        for attempt in range(self._max_retries + 1):
            try:
                raw = await self._llm.create_message(
                    system=system,
                    user=user,
                    model=self._model,
                    temperature=self._temperature,
                )
                result = self._parse_llm_output(raw)
                if result is not None:
                    return result
                logger.warning("Decision tree: attempt %d parse returned None", attempt + 1)
            except Exception:  # noqa: BLE001
                logger.warning("Decision tree: attempt %d LLM call failed", attempt + 1, exc_info=True)

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
                for alias in ("trigger", "path_label", "path_name", "condition", "core_logic", "路径条件"):
                    if alias in p:
                        p["trigger_condition"] = p.pop(alias)
                        break

            # --- possible_outcome (may be a string or a dict) ---
            # First: if already present but is a dict, flatten to readable string
            if isinstance(p.get("possible_outcome"), dict):
                val = p["possible_outcome"]
                parts = []
                for k, v in val.items():
                    if v:
                        parts.append(f"{k}：{v}" if isinstance(v, str) else f"{k}={v}")
                p["possible_outcome"] = "；".join(parts) if parts else str(val)

            if "possible_outcome" not in p:
                for alias in ("outcome", "outcome_detail", "outcome_summary",
                              "final_ruling", "narrative", "judgment_projection",
                              "outcome_type", "裁判结果"):
                    if alias in p:
                        val = p.pop(alias)
                        if isinstance(val, dict):
                            parts = []
                            for k, v in val.items():
                                if v:
                                    parts.append(f"{k}：{v}" if isinstance(v, str) else f"{k}={v}")
                            p["possible_outcome"] = "；".join(parts) if parts else str(val)
                        else:
                            p["possible_outcome"] = str(val)
                        break

            # --- confidence_interval from probability_tier / probability_label ---
            if "confidence_interval" not in p:
                tier_key = None
                for alias in ("probability_tier", "probability_label", "probability"):
                    if alias in p:
                        tier_key = alias
                        break
                if tier_key:
                    tier_map = {
                        "高": (0.65, 0.85), "较高": (0.55, 0.75),
                        "中": (0.35, 0.55), "中等": (0.35, 0.55),
                        "中低": (0.2, 0.4), "较低": (0.1, 0.3), "低": (0.05, 0.2),
                    }
                    tier = p.pop(tier_key, "")
                    if tier in tier_map:
                        lo, hi = tier_map[tier]
                        p["confidence_interval"] = {"lower": lo, "upper": hi}

            # --- Extract trigger_issue_ids from direct list fields or chain structures ---
            if "trigger_issue_ids" not in p or not p["trigger_issue_ids"]:
                # Layer 1: direct list aliases (LLM often puts issue IDs as a flat list)
                for alias in ("pivotal_issues", "key_issues", "relevant_issues",
                              "core_issues", "related_issue_ids"):
                    if alias in p and isinstance(p[alias], list):
                        p["trigger_issue_ids"] = [
                            x for x in p.pop(alias) if isinstance(x, str)
                        ]
                        break

            if "key_evidence_ids" not in p or not p["key_evidence_ids"]:
                # Layer 1: direct list aliases for evidence
                for alias in ("key_evidence_relied", "evidence_relied",
                              "key_evidence", "supporting_evidence",
                              "relied_evidence"):
                    if alias in p and isinstance(p[alias], list):
                        ids = []
                        for x in p.pop(alias):
                            if isinstance(x, str):
                                ids.append(x)
                            elif isinstance(x, dict):
                                eid = x.get("evidence_id", "")
                                if eid:
                                    ids.append(eid)
                        p["key_evidence_ids"] = ids
                        break

            # Layer 1b: extract from chain-like structures (fallback)
            chain = (
                p.get("decision_chain")
                or p.get("key_reasoning_chain")
                or p.get("branch_sequence")
                or p.get("decision_nodes")
                or p.get("reasoning_steps")
                or []
            )
            if isinstance(chain, list) and chain:
                if "trigger_issue_ids" not in p or not p["trigger_issue_ids"]:
                    issue_ids = []
                    seen: set[str] = set()
                    for node in chain:
                        if isinstance(node, dict):
                            for iid_key in ("issue_refs", "issue_id", "issue",
                                            "target_issue", "issues"):
                                val = node.get(iid_key)
                                if isinstance(val, str) and val and val not in seen:
                                    issue_ids.append(val)
                                    seen.add(val)
                                elif isinstance(val, list):
                                    for iid in val:
                                        if isinstance(iid, str) and iid not in seen:
                                            issue_ids.append(iid)
                                            seen.add(iid)
                    p["trigger_issue_ids"] = issue_ids

                if "key_evidence_ids" not in p or not p["key_evidence_ids"]:
                    ev_ids = []
                    seen_ev: set[str] = set()
                    for node in chain:
                        if isinstance(node, dict):
                            for eid_key in ("key_evidence", "evidence", "evidence_ids",
                                            "supporting_evidence"):
                                val = node.get(eid_key)
                                if isinstance(val, str) and val and val not in seen_ev:
                                    ev_ids.append(val)
                                    seen_ev.add(val)
                                elif isinstance(val, list):
                                    for eid in val:
                                        if isinstance(eid, str) and eid not in seen_ev:
                                            ev_ids.append(eid)
                                            seen_ev.add(eid)
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

            # --- v1.5: admissibility_gate aliases ---
            if "admissibility_gate" not in p:
                for alias in (
                    "admission_prerequisites", "evidence_prerequisites",
                    "证据前提", "admissibility_prerequisites",
                ):
                    if alias in p:
                        p["admissibility_gate"] = p.pop(alias)
                        break

            # --- v1.5: result_scope aliases ---
            if "result_scope" not in p:
                for alias in ("judgment_scope", "scope", "裁判范围"):
                    if alias in p:
                        p["result_scope"] = p.pop(alias)
                        break

            # --- v1.5: fallback_path_id aliases ---
            if "fallback_path_id" not in p:
                for alias in ("fallback", "degradation_path", "降级路径"):
                    if alias in p:
                        p["fallback_path_id"] = p.pop(alias)
                        break

            # --- Layer 2: pattern-based fallback for possible_outcome ---
            if "possible_outcome" not in p:
                _OUTCOME_PATS = ("outcome", "result", "ruling", "judgment",
                                 "narrative", "projection", "verdict")
                for key in list(p.keys()):
                    if any(pat in key.lower() for pat in _OUTCOME_PATS):
                        val = p[key]
                        if isinstance(val, str) and len(val) > 5:
                            p["possible_outcome"] = p.pop(key)
                            break
                        elif isinstance(val, dict):
                            p["possible_outcome"] = "；".join(
                                f"{k}={v}" for k, v in val.items() if v
                            )
                            break

            # --- Layer 2: pattern-based fallback for trigger_condition ---
            if "trigger_condition" not in p:
                _TRIGGER_PATS = ("trigger", "condition", "prerequisite",
                                 "premise", "前提")
                for key in list(p.keys()):
                    if any(pat in key.lower() for pat in _TRIGGER_PATS):
                        val = p[key]
                        if isinstance(val, str) and len(val) > 5:
                            p["trigger_condition"] = p.pop(key)
                            break

        return data

    def _parse_llm_output(self, raw: str) -> LLMDecisionPathTreeOutput | None:
        """解析 LLM 输出 JSON，失败时返回 None。
        注意：_extract_json_object 在失败时抛出 ValueError（不返回 None），由此处的
        except Exception 捕获并统一返回 None。
        """
        from engines.shared.json_utils import _extract_json_object
        try:
            logger.info("Decision tree LLM 响应长度: %d chars", len(raw))
            data = _extract_json_object(raw)
            logger.info("JSON 顶层键: %s, paths 数: %s",
                        list(data.keys()),
                        len(data.get("paths", data.get("decision_paths", []))))
            data = self._normalize_llm_json(data)
            # 诊断：记录 paths 第一项的键
            paths_raw = data.get("paths", [])
            if paths_raw and isinstance(paths_raw[0], dict):
                logger.info("Path[0] 键: %s", list(paths_raw[0].keys()))
                logger.debug("Path[0] path_id=%r, trigger_condition=%r, possible_outcome=%r",
                             paths_raw[0].get("path_id", ""),
                             str(paths_raw[0].get("trigger_condition", ""))[:50],
                             str(paths_raw[0].get("possible_outcome", ""))[:50])
            result = LLMDecisionPathTreeOutput.model_validate(data)
            logger.info("解析成功: %d paths, %d blocking",
                        len(result.paths), len(result.blocking_conditions))
            return result
        except Exception:  # noqa: BLE001
            logger.warning("Decision tree LLM 解析失败", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # 文本推断 / Text-based inference
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_issue_ids_from_text(
        text_fields: list[str],
        issues: list,
    ) -> list[str]:
        """从路径文本中推断 trigger_issue_ids。

        按标题长度倒序匹配，避免短标题被长标题子串误命中。
        """
        combined = " ".join(t for t in text_fields if t)
        if not combined.strip():
            return []

        inferred: list[str] = []
        seen: set[str] = set()
        # 按标题长度倒序：先匹配长标题，避免「借贷关系」误命中「借贷关系是否成立」
        sorted_issues = sorted(issues, key=lambda i: len(i.title), reverse=True)
        for issue in sorted_issues:
            if len(issue.title) < 4:
                continue
            if issue.title in combined or issue.issue_id in combined:
                if issue.issue_id not in seen:
                    inferred.append(issue.issue_id)
                    seen.add(issue.issue_id)
        return inferred

    @staticmethod
    def _derive_evidence_ids_from_issues(
        issue_ids: list[str],
        issues: list,
        evidence_index,
    ) -> list[str]:
        """从推断出的 issue_ids 通过 canonical linkage 派生 evidence_ids。

        优先级：
        1. Issue.evidence_ids（争点自带的证据列表）
        2. Evidence.target_issue_ids（证据反向引用争点）
        3. 都没有 → 返回空列表（不做 party-based 猜测）
        """
        issue_id_set = set(issue_ids)
        derived: list[str] = []
        seen: set[str] = set()

        # 1. Issue.evidence_ids
        issue_map = {i.issue_id: i for i in issues}
        for iid in issue_ids:
            iss = issue_map.get(iid)
            if iss and hasattr(iss, "evidence_ids"):
                for eid in iss.evidence_ids:
                    if eid not in seen:
                        derived.append(eid)
                        seen.add(eid)

        # 2. Evidence.target_issue_ids (reverse lookup)
        if not derived and evidence_index is not None:
            for ev in evidence_index.evidence:
                if hasattr(ev, "target_issue_ids"):
                    if any(tid in issue_id_set for tid in ev.target_issue_ids):
                        if ev.evidence_id not in seen:
                            derived.append(ev.evidence_id)
                            seen.add(ev.evidence_id)

        return derived

    def _process_paths(
        self,
        llm_paths: list[LLMDecisionPathItem],
        *,
        known_issue_ids: set[str],
        known_evidence_ids: set[str],
        verdict_block_active: bool,
        issues: list | None = None,
        evidence_index=None,
    ) -> list[DecisionPath]:
        """规则层处理路径列表。"""
        candidates = llm_paths[:_MAX_PATHS]

        result: list[DecisionPath] = []
        for item in candidates:
            # Layer 3: derive possible_outcome from trigger_condition if empty
            if not item.possible_outcome and item.trigger_condition:
                item = item.model_copy(update={"possible_outcome": item.trigger_condition})
                logger.info("Path %s: derived possible_outcome from trigger_condition", item.path_id)

            if not item.path_id or not item.trigger_condition or not item.possible_outcome:
                logger.warning(
                    "Path 跳过: path_id=%r, trigger_condition=%r, possible_outcome=%r",
                    item.path_id[:30] if item.path_id else None,
                    item.trigger_condition[:30] if item.trigger_condition else None,
                    item.possible_outcome[:30] if item.possible_outcome else None,
                )
                continue

            clean_issue_ids = [i for i in item.trigger_issue_ids if i in known_issue_ids]
            clean_evidence_ids = [e for e in item.key_evidence_ids if e in known_evidence_ids]

            # 推断层：如果 LLM 未返回 trigger_issue_ids，从文本推断
            if not clean_issue_ids and issues:
                text_sources = [
                    item.trigger_condition or "",
                    item.possible_outcome or "",
                    item.path_notes or "",
                ]
                clean_issue_ids = self._infer_issue_ids_from_text(text_sources, issues)
                if clean_issue_ids:
                    # 过滤为已知 ID
                    clean_issue_ids = [i for i in clean_issue_ids if i in known_issue_ids]
                    if clean_issue_ids:
                        logger.info("Path %s: inferred %d trigger_issue_ids from text: %s",
                                    item.path_id, len(clean_issue_ids), clean_issue_ids[:3])

            # 推断层：从推断出的 issue_ids 通过 canonical linkage 派生 evidence_ids
            if not clean_evidence_ids and clean_issue_ids and issues:
                clean_evidence_ids = self._derive_evidence_ids_from_issues(
                    clean_issue_ids, issues, evidence_index,
                )
                # 过滤为已知 evidence ID
                clean_evidence_ids = [e for e in clean_evidence_ids if e in known_evidence_ids]
                if clean_evidence_ids:
                    logger.info("Path %s: derived %d key_evidence_ids from issues: %s",
                                item.path_id, len(clean_evidence_ids), clean_evidence_ids[:3])

            # 空字段警告
            if not clean_issue_ids:
                logger.warning(
                    "Path %s: trigger_issue_ids 为空（LLM 未返回且文本推断失败）",
                    item.path_id,
                )
            if not clean_evidence_ids:
                logger.warning(
                    "Path %s: key_evidence_ids 为空（无 canonical linkage 可用）",
                    item.path_id,
                )

            # confidence_interval 处理：
            # - verdict_block_active=True → 强制 None
            # - verdict_block_active=False 且 LLM 未提供 → 合成宽区间（bug fix）
            # - verdict_block_active=False 且 LLM 提供 → 校验后使用
            ci: ConfidenceInterval | None = None
            if verdict_block_active:
                ci = None
            elif item.confidence_interval is not None:
                try:
                    ci = ConfidenceInterval(
                        lower=item.confidence_interval.lower,
                        upper=item.confidence_interval.upper,
                    )
                except Exception:  # noqa: BLE001
                    ci = ConfidenceInterval(lower=0.1, upper=0.9)
            else:
                # Bug fix: LLM 未返回 confidence_interval 但 verdict_block 未激活
                # 合成宽区间作为 "不确定" 信号
                ci = ConfidenceInterval(lower=0.1, upper=0.9)

            # v1.5: 新字段清洗
            clean_gate = [e for e in item.admissibility_gate if e in known_evidence_ids]
            clean_scope = [s for s in item.result_scope if s in _VALID_RESULT_SCOPES]
            fallback = item.fallback_path_id if item.fallback_path_id else None

            result.append(DecisionPath(
                path_id=item.path_id,
                trigger_condition=item.trigger_condition,
                trigger_issue_ids=clean_issue_ids,
                key_evidence_ids=clean_evidence_ids,
                possible_outcome=item.possible_outcome,
                confidence_interval=ci,
                path_notes=item.path_notes,
                admissibility_gate=clean_gate,
                result_scope=clean_scope,
                fallback_path_id=fallback,
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
