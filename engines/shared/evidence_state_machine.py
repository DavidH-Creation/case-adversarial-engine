"""
证据生命周期状态机 — v1.5 核心基础设施。
Evidence lifecycle state machine — v1.5 core infrastructure.

设计原则 / Design principles:
- 纯确定性，零 LLM 调用
- 强制合法迁移，非法路径抛 IllegalTransitionError
- access_domain 自动跟随 status（不允许手动设置）
- Pydantic 不可变模式：每次迁移返回新 Evidence 副本

合法迁移 / Legal transitions:
  private -> submitted               (owner 提交到 shared pool)
  submitted -> challenged            (对方质疑)
  submitted -> admitted_for_discussion (无质疑，直接采纳)
  challenged -> admitted_for_discussion (质疑解决，法官采纳)
  challenged -> submitted            (质疑撤回)

终态 / Terminal state:
  admitted_for_discussion — 不允许任何后续迁移
"""

from __future__ import annotations

from engines.shared.models import (
    AccessDomain,
    Evidence,
    EvidenceIndex,
    EvidenceStatus,
)


class IllegalTransitionError(ValueError):
    """非法状态迁移。Illegal evidence state transition."""


class EvidenceStatusViolation(ValueError):
    """证据未达到要求的最低状态。Evidence does not meet minimum status requirement."""


# ---------------------------------------------------------------------------
# 状态排序 / Status ordering (for enforce_minimum_status)
# ---------------------------------------------------------------------------

_STATUS_ORDER: dict[EvidenceStatus, int] = {
    EvidenceStatus.private: 0,
    EvidenceStatus.submitted: 1,
    EvidenceStatus.challenged: 2,
    EvidenceStatus.admitted_for_discussion: 3,
}


# ---------------------------------------------------------------------------
# 合法迁移表 / Legal transition table
# ---------------------------------------------------------------------------

_LEGAL_TRANSITIONS: dict[EvidenceStatus, frozenset[EvidenceStatus]] = {
    EvidenceStatus.private: frozenset({EvidenceStatus.submitted}),
    EvidenceStatus.submitted: frozenset({
        EvidenceStatus.challenged,
        EvidenceStatus.admitted_for_discussion,
    }),
    EvidenceStatus.challenged: frozenset({
        EvidenceStatus.admitted_for_discussion,
        EvidenceStatus.submitted,
    }),
    EvidenceStatus.admitted_for_discussion: frozenset(),  # terminal
}

# Status -> access_domain 自动耦合
_DOMAIN_MAP: dict[EvidenceStatus, AccessDomain] = {
    EvidenceStatus.private: AccessDomain.owner_private,
    EvidenceStatus.submitted: AccessDomain.shared_common,
    EvidenceStatus.challenged: AccessDomain.shared_common,
    EvidenceStatus.admitted_for_discussion: AccessDomain.admitted_record,
}


class EvidenceStateMachine:
    """证据生命周期状态机。

    每次操作返回一份新的 Evidence 副本（不修改原对象）。
    """

    # ------------------------------------------------------------------
    # 通用迁移入口
    # ------------------------------------------------------------------

    def transition(
        self,
        evidence: Evidence,
        new_status: EvidenceStatus,
        actor_party_id: str,
        reason: str,
    ) -> Evidence:
        """执行状态迁移，返回新 Evidence。

        Args:
            evidence:        当前证据对象
            new_status:      目标状态
            actor_party_id:  执行迁移的 party_id
            reason:          迁移原因（审计用）

        Raises:
            IllegalTransitionError: 非法迁移路径
        """
        current = evidence.status
        allowed = _LEGAL_TRANSITIONS.get(current, frozenset())

        if new_status not in allowed:
            raise IllegalTransitionError(
                f"非法迁移 {current.value} -> {new_status.value}。"
                f" / Illegal transition {current.value} -> {new_status.value}."
            )

        updates: dict = {
            "status": new_status,
            "access_domain": _DOMAIN_MAP[new_status],
        }

        # 业务规则：submit 时设置 submitted_by_party_id
        if current == EvidenceStatus.private and new_status == EvidenceStatus.submitted:
            if actor_party_id != evidence.owner_party_id:
                raise IllegalTransitionError(
                    f"只有 owner ({evidence.owner_party_id}) 可以提交证据，"
                    f"当前 actor: {actor_party_id}。"
                    f" / Only owner can submit evidence."
                )
            updates["submitted_by_party_id"] = actor_party_id

        # 业务规则：challenge 时追加 challenged_by_party_ids
        if new_status == EvidenceStatus.challenged:
            if actor_party_id == evidence.owner_party_id:
                raise IllegalTransitionError(
                    f"owner ({evidence.owner_party_id}) 不能质疑自己的证据。"
                    f" / Owner cannot challenge own evidence."
                )
            existing = list(evidence.challenged_by_party_ids)
            if actor_party_id not in existing:
                existing.append(actor_party_id)
            updates["challenged_by_party_ids"] = existing

        return evidence.model_copy(update=updates)

    # ------------------------------------------------------------------
    # 便捷方法
    # ------------------------------------------------------------------

    def submit(self, evidence: Evidence, actor_party_id: str) -> Evidence:
        """private -> submitted。"""
        return self.transition(
            evidence, EvidenceStatus.submitted, actor_party_id, "提交证据"
        )

    def challenge(
        self, evidence: Evidence, challenger_party_id: str, reason: str = ""
    ) -> Evidence:
        """submitted -> challenged。"""
        return self.transition(
            evidence, EvidenceStatus.challenged, challenger_party_id, reason
        )

    def admit(self, evidence: Evidence) -> Evidence:
        """submitted/challenged -> admitted_for_discussion。"""
        return self.transition(
            evidence, EvidenceStatus.admitted_for_discussion, "system", "采纳"
        )

    def enforce_minimum_status(
        self,
        evidence_index: EvidenceIndex,
        min_status: EvidenceStatus,
        *,
        evidence_ids: list[str] | None = None,
    ) -> None:
        """校验证据是否达到最低状态要求。

        Validate that evidence items meet a minimum status threshold.

        Args:
            evidence_index:  证据索引
            min_status:      要求的最低状态
            evidence_ids:    可选，只检查指定 ID 的证据；为 None 时检查全部

        Raises:
            EvidenceStatusViolation: 存在不满足条件的证据
        """
        min_order = _STATUS_ORDER[min_status]
        id_filter = set(evidence_ids) if evidence_ids else None

        violations: list[str] = []
        for ev in evidence_index.evidence:
            if id_filter is not None and ev.evidence_id not in id_filter:
                continue
            if _STATUS_ORDER[ev.status] < min_order:
                violations.append(
                    f"{ev.evidence_id}: {ev.status.value} (需要 {min_status.value})"
                )

        if violations:
            detail = "; ".join(violations[:5])
            raise EvidenceStatusViolation(
                f"{len(violations)} 条证据未达到 {min_status.value} 状态: {detail}"
                f" / {len(violations)} evidence items below {min_status.value}: {detail}"
            )

    def bulk_submit(
        self,
        evidence_index: EvidenceIndex,
        party_id: str,
        evidence_ids: list[str],
    ) -> EvidenceIndex:
        """批量提交指定证据。已经不是 private 状态的跳过（幂等）。"""
        id_set = set(evidence_ids)
        new_evidence = []
        for ev in evidence_index.evidence:
            if ev.evidence_id in id_set and ev.status == EvidenceStatus.private:
                new_evidence.append(self.submit(ev, party_id))
            else:
                new_evidence.append(ev)
        return evidence_index.model_copy(update={"evidence": new_evidence})
