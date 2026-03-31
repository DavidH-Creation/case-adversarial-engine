"""
AccessController 单元测试。
Unit tests for AccessController.

覆盖路径 / Coverage:
1. 正向：每种合法角色只能看到允许的证据
2. 负向：party_agent 看不到对方的 owner_private
3. 负向：judge_agent / evidence_manager 看不到任何 owner_private
4. 负向：未知 role_code 抛 AccessViolationError
5. 边界：空证据列表返回空
6. 边界：所有证据均可见时返回全部（顺序保持）
"""

from __future__ import annotations

import pytest

from engines.shared.access_control import AccessController, AccessViolationError
from engines.shared.models import (
    AccessDomain,
    AgentRole,
    Evidence,
    EvidenceStatus,
    EvidenceType,
)

# ---------------------------------------------------------------------------
# 测试夹具 / Fixtures
# ---------------------------------------------------------------------------

CASE_ID = "case-ac-test"
PLAINTIFF_PARTY = "party-plaintiff"
DEFENDANT_PARTY = "party-defendant"


def _ev(
    eid: str,
    owner: str,
    domain: AccessDomain,
    status: EvidenceStatus = EvidenceStatus.private,
) -> Evidence:
    return Evidence(
        evidence_id=eid,
        case_id=CASE_ID,
        owner_party_id=owner,
        title=f"证据 {eid}",
        source=f"mat-{eid}",
        summary=f"摘要 {eid}",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=[f"fact-{eid}"],
        access_domain=domain,
        status=status,
    )


# 标准四条测试证据
EV_PLAINTIFF_PRIVATE = _ev("ev-p-priv", PLAINTIFF_PARTY, AccessDomain.owner_private)
EV_DEFENDANT_PRIVATE = _ev("ev-d-priv", DEFENDANT_PARTY, AccessDomain.owner_private)
EV_SHARED = _ev("ev-shared", PLAINTIFF_PARTY, AccessDomain.shared_common, EvidenceStatus.submitted)
EV_ADMITTED = _ev(
    "ev-admitted",
    DEFENDANT_PARTY,
    AccessDomain.admitted_record,
    EvidenceStatus.admitted_for_discussion,
)

ALL_EVIDENCE = [EV_PLAINTIFF_PRIVATE, EV_DEFENDANT_PRIVATE, EV_SHARED, EV_ADMITTED]


@pytest.fixture
def controller() -> AccessController:
    return AccessController()


# ---------------------------------------------------------------------------
# 1. 原告代理 / Plaintiff agent
# ---------------------------------------------------------------------------


class TestPlaintiffAgent:
    def test_sees_own_private(self, controller: AccessController) -> None:
        result = controller.filter_evidence_for_agent(
            AgentRole.plaintiff_agent.value, PLAINTIFF_PARTY, ALL_EVIDENCE
        )
        assert EV_PLAINTIFF_PRIVATE in result

    def test_cannot_see_defendant_private(self, controller: AccessController) -> None:
        result = controller.filter_evidence_for_agent(
            AgentRole.plaintiff_agent.value, PLAINTIFF_PARTY, ALL_EVIDENCE
        )
        assert EV_DEFENDANT_PRIVATE not in result

    def test_sees_shared(self, controller: AccessController) -> None:
        result = controller.filter_evidence_for_agent(
            AgentRole.plaintiff_agent.value, PLAINTIFF_PARTY, ALL_EVIDENCE
        )
        assert EV_SHARED in result

    def test_sees_admitted(self, controller: AccessController) -> None:
        result = controller.filter_evidence_for_agent(
            AgentRole.plaintiff_agent.value, PLAINTIFF_PARTY, ALL_EVIDENCE
        )
        assert EV_ADMITTED in result

    def test_total_count(self, controller: AccessController) -> None:
        result = controller.filter_evidence_for_agent(
            AgentRole.plaintiff_agent.value, PLAINTIFF_PARTY, ALL_EVIDENCE
        )
        # plaintiff_private + shared + admitted = 3（不含 defendant_private）
        assert len(result) == 3


# ---------------------------------------------------------------------------
# 2. 被告代理 / Defendant agent
# ---------------------------------------------------------------------------


class TestDefendantAgent:
    def test_sees_own_private(self, controller: AccessController) -> None:
        result = controller.filter_evidence_for_agent(
            AgentRole.defendant_agent.value, DEFENDANT_PARTY, ALL_EVIDENCE
        )
        assert EV_DEFENDANT_PRIVATE in result

    def test_cannot_see_plaintiff_private(self, controller: AccessController) -> None:
        result = controller.filter_evidence_for_agent(
            AgentRole.defendant_agent.value, DEFENDANT_PARTY, ALL_EVIDENCE
        )
        assert EV_PLAINTIFF_PRIVATE not in result

    def test_sees_shared(self, controller: AccessController) -> None:
        result = controller.filter_evidence_for_agent(
            AgentRole.defendant_agent.value, DEFENDANT_PARTY, ALL_EVIDENCE
        )
        assert EV_SHARED in result

    def test_sees_admitted(self, controller: AccessController) -> None:
        result = controller.filter_evidence_for_agent(
            AgentRole.defendant_agent.value, DEFENDANT_PARTY, ALL_EVIDENCE
        )
        assert EV_ADMITTED in result

    def test_total_count(self, controller: AccessController) -> None:
        result = controller.filter_evidence_for_agent(
            AgentRole.defendant_agent.value, DEFENDANT_PARTY, ALL_EVIDENCE
        )
        # defendant_private + shared + admitted = 3
        assert len(result) == 3


# ---------------------------------------------------------------------------
# 3. 法官代理 / Judge agent
# ---------------------------------------------------------------------------


class TestJudgeAgent:
    def test_cannot_see_plaintiff_private(self, controller: AccessController) -> None:
        result = controller.filter_evidence_for_agent(
            AgentRole.judge_agent.value, "party-judge", ALL_EVIDENCE
        )
        assert EV_PLAINTIFF_PRIVATE not in result

    def test_cannot_see_defendant_private(self, controller: AccessController) -> None:
        result = controller.filter_evidence_for_agent(
            AgentRole.judge_agent.value, "party-judge", ALL_EVIDENCE
        )
        assert EV_DEFENDANT_PRIVATE not in result

    def test_cannot_see_shared(self, controller: AccessController) -> None:
        result = controller.filter_evidence_for_agent(
            AgentRole.judge_agent.value, "party-judge", ALL_EVIDENCE
        )
        assert EV_SHARED not in result

    def test_sees_admitted(self, controller: AccessController) -> None:
        result = controller.filter_evidence_for_agent(
            AgentRole.judge_agent.value, "party-judge", ALL_EVIDENCE
        )
        assert EV_ADMITTED in result

    def test_total_count(self, controller: AccessController) -> None:
        result = controller.filter_evidence_for_agent(
            AgentRole.judge_agent.value, "party-judge", ALL_EVIDENCE
        )
        assert len(result) == 1


# ---------------------------------------------------------------------------
# 4. 证据管理员 / Evidence manager
# ---------------------------------------------------------------------------


class TestEvidenceManager:
    def test_cannot_see_any_owner_private(self, controller: AccessController) -> None:
        result = controller.filter_evidence_for_agent(
            AgentRole.evidence_manager.value, "party-em", ALL_EVIDENCE
        )
        assert EV_PLAINTIFF_PRIVATE not in result
        assert EV_DEFENDANT_PRIVATE not in result

    def test_sees_shared(self, controller: AccessController) -> None:
        result = controller.filter_evidence_for_agent(
            AgentRole.evidence_manager.value, "party-em", ALL_EVIDENCE
        )
        assert EV_SHARED in result

    def test_sees_admitted(self, controller: AccessController) -> None:
        result = controller.filter_evidence_for_agent(
            AgentRole.evidence_manager.value, "party-em", ALL_EVIDENCE
        )
        assert EV_ADMITTED in result

    def test_total_count(self, controller: AccessController) -> None:
        result = controller.filter_evidence_for_agent(
            AgentRole.evidence_manager.value, "party-em", ALL_EVIDENCE
        )
        assert len(result) == 2


# ---------------------------------------------------------------------------
# 5. 未知角色 / Unknown role
# ---------------------------------------------------------------------------


class TestUnknownRole:
    def test_raises_access_violation_error(self, controller: AccessController) -> None:
        with pytest.raises(AccessViolationError, match="未知角色编码"):
            controller.filter_evidence_for_agent("unknown_role", PLAINTIFF_PARTY, ALL_EVIDENCE)

    def test_raises_on_empty_string(self, controller: AccessController) -> None:
        with pytest.raises(AccessViolationError):
            controller.filter_evidence_for_agent("", PLAINTIFF_PARTY, ALL_EVIDENCE)


# ---------------------------------------------------------------------------
# 6. 边界情况 / Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_evidence_list(self, controller: AccessController) -> None:
        result = controller.filter_evidence_for_agent(
            AgentRole.plaintiff_agent.value, PLAINTIFF_PARTY, []
        )
        assert result == []

    def test_order_preserved(self, controller: AccessController) -> None:
        """过滤结果顺序必须与输入一致。"""
        # 原告可见：ev-p-priv, ev-shared, ev-admitted（按输入顺序）
        result = controller.filter_evidence_for_agent(
            AgentRole.plaintiff_agent.value, PLAINTIFF_PARTY, ALL_EVIDENCE
        )
        ids = [e.evidence_id for e in result]
        assert ids == ["ev-p-priv", "ev-shared", "ev-admitted"]

    def test_multiple_own_private_all_visible(self, controller: AccessController) -> None:
        """同一方的多条 owner_private 证据全部可见。"""
        ev2 = _ev("ev-p-priv-2", PLAINTIFF_PARTY, AccessDomain.owner_private)
        ev3 = _ev("ev-p-priv-3", PLAINTIFF_PARTY, AccessDomain.owner_private)
        evidence = [EV_PLAINTIFF_PRIVATE, ev2, ev3, EV_DEFENDANT_PRIVATE]
        result = controller.filter_evidence_for_agent(
            AgentRole.plaintiff_agent.value, PLAINTIFF_PARTY, evidence
        )
        assert EV_PLAINTIFF_PRIVATE in result
        assert ev2 in result
        assert ev3 in result
        assert EV_DEFENDANT_PRIVATE not in result

    def test_party_agent_cannot_see_own_private_with_wrong_owner_party_id(
        self, controller: AccessController
    ) -> None:
        """即使是 plaintiff_agent，但 owner_party_id 传错，也看不到别人的 private。"""
        result = controller.filter_evidence_for_agent(
            AgentRole.plaintiff_agent.value,
            "party-wrong",  # 故意传错 owner
            [EV_PLAINTIFF_PRIVATE, EV_DEFENDANT_PRIVATE],
        )
        # 两条都是 owner_private，但 owner_party_id 都不匹配 "party-wrong"
        assert result == []

    def test_all_admitted_visible_to_all_roles(self, controller: AccessController) -> None:
        """admitted_record 对所有合法角色均可见。"""
        for role, party in [
            (AgentRole.plaintiff_agent.value, PLAINTIFF_PARTY),
            (AgentRole.defendant_agent.value, DEFENDANT_PARTY),
            (AgentRole.judge_agent.value, "party-judge"),
            (AgentRole.evidence_manager.value, "party-em"),
        ]:
            result = controller.filter_evidence_for_agent(role, party, [EV_ADMITTED])
            assert EV_ADMITTED in result, f"{role} should see admitted_record"
