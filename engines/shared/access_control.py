"""
访问控制器 — 证据可见性过滤的单一入口。
AccessController — single entry point for evidence visibility filtering.

设计原则 / Design principles:
- allowlist 模式：未明确允许的域一律拒绝
- 违规 role_code 抛 AccessViolationError，不静默过滤
- v1 静态规则；v1.5 可在此注入 ProcedureState.readable_access_domains 覆盖

角色访问域规则（v1 静态）/ Role access rules (v1 static):
  plaintiff_agent:  自己的 owner_private + shared_common + admitted_record
  defendant_agent:  自己的 owner_private + shared_common + admitted_record
  judge_agent:      admitted_record 只读
  evidence_manager: shared_common + admitted_record
"""

from __future__ import annotations

from engines.shared.models import AccessDomain, AgentRole, Evidence, ProcedureState


class AccessViolationError(ValueError):
    """未授权的访问尝试。Unauthorized access attempt.

    当 role_code 不在已知角色映射表中时抛出。
    Raised when role_code is not in the known role access map.
    """


# ---------------------------------------------------------------------------
# 静态访问规则表 / Static access rule table
# ---------------------------------------------------------------------------

# 各角色无条件允许访问的域（不含 owner_private 的特殊规则）
# Domains each role may access unconditionally (excluding owner_private logic).
_UNCONDITIONAL_DOMAINS: dict[str, frozenset[AccessDomain]] = {
    AgentRole.plaintiff_agent.value: frozenset({
        AccessDomain.shared_common,
        AccessDomain.admitted_record,
    }),
    AgentRole.defendant_agent.value: frozenset({
        AccessDomain.shared_common,
        AccessDomain.admitted_record,
    }),
    AgentRole.judge_agent.value: frozenset({
        AccessDomain.admitted_record,
    }),
    AgentRole.evidence_manager.value: frozenset({
        AccessDomain.shared_common,
        AccessDomain.admitted_record,
    }),
}

# 允许访问自己 owner_private 的角色集合
# Roles that may see their own party's owner_private evidence.
_CAN_SEE_OWN_PRIVATE: frozenset[str] = frozenset({
    AgentRole.plaintiff_agent.value,
    AgentRole.defendant_agent.value,
})


# ---------------------------------------------------------------------------
# AccessController
# ---------------------------------------------------------------------------


class AccessController:
    """证据可见性过滤器。
    Evidence visibility filter.

    将完整证据列表按角色编码和所属方 party_id 过滤，返回该角色可见的子集。
    Filters the full evidence list by role_code and owner_party_id,
    returning only the subset visible to that agent.

    用法 / Usage::

        controller = AccessController()
        visible = controller.filter_evidence_for_agent(
            role_code="plaintiff_agent",
            owner_party_id="party-plaintiff-001",
            all_evidence=evidence_list,
        )
    """

    def filter_evidence_for_agent(
        self,
        role_code: str,
        owner_party_id: str,
        all_evidence: list[Evidence],
        procedure_state: ProcedureState | None = None,
    ) -> list[Evidence]:
        """返回该角色可见的证据子集（保持原顺序）。
        Return the visible evidence subset for the given agent (preserving order).

        Args:
            role_code:        代理角色编码（来自 AgentRole 枚举值）
            owner_party_id:   该代理所属方的 party_id
            all_evidence:     案件全量证据列表
            procedure_state:  可选，程序阶段状态（v1.5 新增）。
                              提供时在角色级规则之上叠加阶段级过滤。
                              不提供时行为与 v1 完全一致。

        Returns:
            过滤后的证据列表，顺序与输入一致

        Raises:
            AccessViolationError: role_code 不在已知角色映射表中
        """
        if role_code not in _UNCONDITIONAL_DOMAINS:
            raise AccessViolationError(
                f"未知角色编码 {role_code!r}，无法确定访问域。"
                f" / Unknown role_code {role_code!r}: cannot determine access scope."
            )

        unconditional = _UNCONDITIONAL_DOMAINS[role_code]
        can_see_own = role_code in _CAN_SEE_OWN_PRIVATE

        result = [
            e for e in all_evidence
            if _is_visible(e, unconditional, can_see_own, owner_party_id)
        ]

        # v1.5: 当提供 procedure_state 时，叠加阶段级过滤
        if procedure_state is not None:
            allowed_domains = set(procedure_state.readable_access_domains)
            allowed_statuses = set(procedure_state.admissible_evidence_statuses)
            result = [
                e for e in result
                if e.access_domain in allowed_domains
                and e.status in allowed_statuses
            ]

        return result


# ---------------------------------------------------------------------------
# 内部辅助 / Internal helper
# ---------------------------------------------------------------------------


def _is_visible(
    evidence: Evidence,
    unconditional: frozenset[AccessDomain],
    can_see_own_private: bool,
    owner_party_id: str,
) -> bool:
    """判断单条证据对该角色是否可见。
    Determine if a single evidence is visible to the given role.
    """
    domain = evidence.access_domain

    # 无条件允许的域（shared_common / admitted_record）
    if domain in unconditional:
        return True

    # owner_private：只有拥有方的 party_agent 可见
    if (
        can_see_own_private
        and domain == AccessDomain.owner_private
        and evidence.owner_party_id == owner_party_id
    ):
        return True

    return False
