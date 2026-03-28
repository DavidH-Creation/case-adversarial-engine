"""EvidenceStateMachine 单元测试 — v1.5 证据生命周期状态机。

覆盖：
- 合法迁移（5 条路径）
- 非法迁移（拦截所有非法路径）
- access_domain 自动耦合
- 业务规则（owner submit / non-owner challenge / 终态）
- bulk_submit
- 泄露防护
"""

import pytest

from engines.shared.models import (
    AccessDomain,
    Evidence,
    EvidenceStatus,
    EvidenceType,
)
from engines.shared.evidence_state_machine import (
    EvidenceStateMachine,
    IllegalTransitionError,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

PLAINTIFF = "party-plaintiff-001"
DEFENDANT = "party-defendant-001"


def _make_evidence(
    *,
    evidence_id: str = "ev-001",
    owner: str = PLAINTIFF,
    status: EvidenceStatus = EvidenceStatus.private,
    access_domain: AccessDomain = AccessDomain.owner_private,
    **overrides,
) -> Evidence:
    defaults = dict(
        evidence_id=evidence_id,
        case_id="case-001",
        owner_party_id=owner,
        title="借条",
        source="原告提交",
        summary="载明借款金额 10 万元。",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=["fact-001"],
        access_domain=access_domain,
        status=status,
    )
    defaults.update(overrides)
    return Evidence(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

SM = EvidenceStateMachine()


class TestLegalTransitions:
    """5 条合法迁移路径。"""

    def test_private_to_submitted(self):
        ev = _make_evidence(status=EvidenceStatus.private)
        result = SM.submit(ev, actor_party_id=PLAINTIFF)
        assert result.status == EvidenceStatus.submitted
        assert result.access_domain == AccessDomain.shared_common

    def test_submitted_to_challenged(self):
        ev = _make_evidence(
            status=EvidenceStatus.submitted,
            access_domain=AccessDomain.shared_common,
        )
        result = SM.challenge(ev, challenger_party_id=DEFENDANT, reason="金额不符")
        assert result.status == EvidenceStatus.challenged
        assert result.access_domain == AccessDomain.shared_common

    def test_submitted_to_admitted(self):
        ev = _make_evidence(
            status=EvidenceStatus.submitted,
            access_domain=AccessDomain.shared_common,
        )
        result = SM.admit(ev)
        assert result.status == EvidenceStatus.admitted_for_discussion
        assert result.access_domain == AccessDomain.admitted_record

    def test_challenged_to_admitted(self):
        ev = _make_evidence(
            status=EvidenceStatus.challenged,
            access_domain=AccessDomain.shared_common,
            challenged_by_party_ids=[DEFENDANT],
        )
        result = SM.admit(ev)
        assert result.status == EvidenceStatus.admitted_for_discussion
        assert result.access_domain == AccessDomain.admitted_record

    def test_challenged_to_submitted(self):
        """质疑撤回 — challenged -> submitted。"""
        ev = _make_evidence(
            status=EvidenceStatus.challenged,
            access_domain=AccessDomain.shared_common,
            challenged_by_party_ids=[DEFENDANT],
        )
        result = SM.transition(
            ev,
            new_status=EvidenceStatus.submitted,
            actor_party_id=DEFENDANT,
            reason="撤回质疑",
        )
        assert result.status == EvidenceStatus.submitted
        assert result.access_domain == AccessDomain.shared_common


class TestIllegalTransitions:
    """所有非法路径必须抛 IllegalTransitionError。"""

    def test_private_to_challenged(self):
        ev = _make_evidence(status=EvidenceStatus.private)
        with pytest.raises(IllegalTransitionError):
            SM.transition(ev, EvidenceStatus.challenged, DEFENDANT, "无法质疑未提交证据")

    def test_private_to_admitted(self):
        ev = _make_evidence(status=EvidenceStatus.private)
        with pytest.raises(IllegalTransitionError):
            SM.transition(ev, EvidenceStatus.admitted_for_discussion, PLAINTIFF, "跳过提交")

    def test_admitted_to_any(self):
        """终态不允许任何迁移。"""
        ev = _make_evidence(
            status=EvidenceStatus.admitted_for_discussion,
            access_domain=AccessDomain.admitted_record,
        )
        for target in EvidenceStatus:
            if target == EvidenceStatus.admitted_for_discussion:
                continue
            with pytest.raises(IllegalTransitionError):
                SM.transition(ev, target, PLAINTIFF, "非法")

    def test_challenged_to_private(self):
        ev = _make_evidence(
            status=EvidenceStatus.challenged,
            access_domain=AccessDomain.shared_common,
        )
        with pytest.raises(IllegalTransitionError):
            SM.transition(ev, EvidenceStatus.private, PLAINTIFF, "非法回退")

    def test_submitted_to_private(self):
        ev = _make_evidence(
            status=EvidenceStatus.submitted,
            access_domain=AccessDomain.shared_common,
        )
        with pytest.raises(IllegalTransitionError):
            SM.transition(ev, EvidenceStatus.private, PLAINTIFF, "非法回退")


class TestAccessDomainCoupling:
    """每次迁移后 access_domain 自动跟随 status。"""

    def test_submit_sets_shared_common(self):
        ev = _make_evidence()
        result = SM.submit(ev, PLAINTIFF)
        assert result.access_domain == AccessDomain.shared_common

    def test_challenge_keeps_shared_common(self):
        ev = _make_evidence(
            status=EvidenceStatus.submitted,
            access_domain=AccessDomain.shared_common,
        )
        result = SM.challenge(ev, DEFENDANT, "伪造")
        assert result.access_domain == AccessDomain.shared_common

    def test_admit_sets_admitted_record(self):
        ev = _make_evidence(
            status=EvidenceStatus.submitted,
            access_domain=AccessDomain.shared_common,
        )
        result = SM.admit(ev)
        assert result.access_domain == AccessDomain.admitted_record


class TestSubmitConstraints:
    """只有 owner 可以 submit。"""

    def test_owner_can_submit(self):
        ev = _make_evidence(owner=PLAINTIFF)
        result = SM.submit(ev, actor_party_id=PLAINTIFF)
        assert result.status == EvidenceStatus.submitted

    def test_non_owner_cannot_submit(self):
        ev = _make_evidence(owner=PLAINTIFF)
        with pytest.raises(IllegalTransitionError, match="owner"):
            SM.submit(ev, actor_party_id=DEFENDANT)

    def test_submit_sets_submitted_by_party_id(self):
        ev = _make_evidence()
        result = SM.submit(ev, PLAINTIFF)
        assert result.submitted_by_party_id == PLAINTIFF


class TestChallengeConstraints:
    """只有非 owner 可以 challenge。"""

    def test_non_owner_can_challenge(self):
        ev = _make_evidence(
            owner=PLAINTIFF,
            status=EvidenceStatus.submitted,
            access_domain=AccessDomain.shared_common,
        )
        result = SM.challenge(ev, challenger_party_id=DEFENDANT, reason="伪造")
        assert result.status == EvidenceStatus.challenged

    def test_owner_cannot_challenge_own_evidence(self):
        ev = _make_evidence(
            owner=PLAINTIFF,
            status=EvidenceStatus.submitted,
            access_domain=AccessDomain.shared_common,
        )
        with pytest.raises(IllegalTransitionError, match="owner"):
            SM.challenge(ev, challenger_party_id=PLAINTIFF, reason="不合理")

    def test_challenge_appends_to_challenged_by_party_ids(self):
        ev = _make_evidence(
            owner=PLAINTIFF,
            status=EvidenceStatus.submitted,
            access_domain=AccessDomain.shared_common,
        )
        result = SM.challenge(ev, DEFENDANT, "金额不符")
        assert DEFENDANT in result.challenged_by_party_ids


class TestTerminalState:
    """admitted_for_discussion 是终态。"""

    def test_no_transition_from_admitted(self):
        ev = _make_evidence(
            status=EvidenceStatus.admitted_for_discussion,
            access_domain=AccessDomain.admitted_record,
        )
        with pytest.raises(IllegalTransitionError):
            SM.submit(ev, PLAINTIFF)

    def test_cannot_challenge_admitted(self):
        ev = _make_evidence(
            status=EvidenceStatus.admitted_for_discussion,
            access_domain=AccessDomain.admitted_record,
        )
        with pytest.raises(IllegalTransitionError):
            SM.challenge(ev, DEFENDANT, "无效")


class TestBulkSubmit:
    """批量提交。"""

    def test_bulk_submit_transitions_selected_evidence(self):
        from engines.shared.models import EvidenceIndex

        ev1 = _make_evidence(evidence_id="ev-001", owner=PLAINTIFF)
        ev2 = _make_evidence(evidence_id="ev-002", owner=PLAINTIFF)
        ev3 = _make_evidence(evidence_id="ev-003", owner=PLAINTIFF)
        index = EvidenceIndex(
            case_id="case-001",
            job_id="job-001",
            run_id="run-001",
            raw_materials=[],
            evidence=[ev1, ev2, ev3],
        )
        result = SM.bulk_submit(index, party_id=PLAINTIFF, evidence_ids=["ev-001", "ev-003"])
        statuses = {e.evidence_id: e.status for e in result.evidence}
        assert statuses["ev-001"] == EvidenceStatus.submitted
        assert statuses["ev-002"] == EvidenceStatus.private  # untouched
        assert statuses["ev-003"] == EvidenceStatus.submitted

    def test_bulk_submit_skips_already_submitted(self):
        from engines.shared.models import EvidenceIndex

        ev = _make_evidence(
            evidence_id="ev-001",
            owner=PLAINTIFF,
            status=EvidenceStatus.submitted,
            access_domain=AccessDomain.shared_common,
            submitted_by_party_id=PLAINTIFF,
        )
        index = EvidenceIndex(
            case_id="case-001",
            job_id="job-001",
            run_id="run-001",
            raw_materials=[],
            evidence=[ev],
        )
        result = SM.bulk_submit(index, party_id=PLAINTIFF, evidence_ids=["ev-001"])
        assert result.evidence[0].status == EvidenceStatus.submitted  # no error, no change


class TestPrivateLeakageGuard:
    """提交后证据不再在 owner_private 域。"""

    def test_submitted_evidence_not_in_owner_private(self):
        ev = _make_evidence()
        result = SM.submit(ev, PLAINTIFF)
        assert result.access_domain != AccessDomain.owner_private

    def test_admitted_evidence_in_admitted_record(self):
        ev = _make_evidence(
            status=EvidenceStatus.submitted,
            access_domain=AccessDomain.shared_common,
        )
        result = SM.admit(ev)
        assert result.access_domain == AccessDomain.admitted_record
