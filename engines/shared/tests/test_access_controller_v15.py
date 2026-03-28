"""AccessController v1.5 ProcedureState 驱动访问控制测试。"""

import pytest

from engines.shared.access_control import AccessController
from engines.shared.models import (
    AccessDomain,
    AgentRole,
    Evidence,
    EvidenceStatus,
    EvidenceType,
    ProcedurePhase,
    ProcedureState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_evidence(
    evidence_id: str,
    owner_party_id: str,
    status: EvidenceStatus,
    access_domain: AccessDomain,
):
    return Evidence(
        evidence_id=evidence_id,
        case_id="case-001",
        owner_party_id=owner_party_id,
        title=f"证据 {evidence_id}",
        source="来源",
        summary="摘要",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=["fact-001"],
        target_issue_ids=["issue-001"],
        access_domain=access_domain,
        status=status,
        challenged_by_party_ids=[],
    )


def _make_all_evidence():
    """构建覆盖所有状态/域的证据集。"""
    return [
        _make_evidence(
            "ev-priv-p", "party-plaintiff",
            EvidenceStatus.private, AccessDomain.owner_private,
        ),
        _make_evidence(
            "ev-sub", "party-plaintiff",
            EvidenceStatus.submitted, AccessDomain.shared_common,
        ),
        _make_evidence(
            "ev-chal", "party-plaintiff",
            EvidenceStatus.challenged, AccessDomain.shared_common,
        ),
        _make_evidence(
            "ev-adm", "party-plaintiff",
            EvidenceStatus.admitted_for_discussion, AccessDomain.admitted_record,
        ),
    ]


# ---------------------------------------------------------------------------
# 向后兼容
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """procedure_state=None 时行为与 v1 完全一致。"""

    def test_none_procedure_state_returns_v1_behavior(self):
        ctrl = AccessController()
        all_ev = _make_all_evidence()
        result = ctrl.filter_evidence_for_agent(
            role_code=AgentRole.plaintiff_agent.value,
            owner_party_id="party-plaintiff",
            all_evidence=all_ev,
            procedure_state=None,
        )
        # plaintiff sees: own private + shared + admitted = all 4
        assert len(result) == 4

    def test_omit_procedure_state_returns_v1_behavior(self):
        """不传 procedure_state 参数。"""
        ctrl = AccessController()
        all_ev = _make_all_evidence()
        result = ctrl.filter_evidence_for_agent(
            role_code=AgentRole.plaintiff_agent.value,
            owner_party_id="party-plaintiff",
            all_evidence=all_ev,
        )
        assert len(result) == 4


# ---------------------------------------------------------------------------
# judge_questions 阶段
# ---------------------------------------------------------------------------


class TestJudgeQuestionsPhase:
    """judge_questions 阶段只看到 admitted_for_discussion。"""

    def test_judge_sees_only_admitted(self):
        ctrl = AccessController()
        state = ProcedureState(
            phase=ProcedurePhase.judge_questions,
            readable_access_domains=[AccessDomain.admitted_record],
            admissible_evidence_statuses=[
                EvidenceStatus.admitted_for_discussion,
            ],
        )
        result = ctrl.filter_evidence_for_agent(
            role_code=AgentRole.judge_agent.value,
            owner_party_id="system",
            all_evidence=_make_all_evidence(),
            procedure_state=state,
        )
        assert len(result) == 1
        assert result[0].evidence_id == "ev-adm"
        assert result[0].status == EvidenceStatus.admitted_for_discussion

    def test_plaintiff_in_judge_phase_sees_only_admitted(self):
        """即使是 plaintiff，在 judge_questions 阶段也只看 admitted。"""
        ctrl = AccessController()
        state = ProcedureState(
            phase=ProcedurePhase.judge_questions,
            readable_access_domains=[AccessDomain.admitted_record],
            admissible_evidence_statuses=[
                EvidenceStatus.admitted_for_discussion,
            ],
        )
        result = ctrl.filter_evidence_for_agent(
            role_code=AgentRole.plaintiff_agent.value,
            owner_party_id="party-plaintiff",
            all_evidence=_make_all_evidence(),
            procedure_state=state,
        )
        assert len(result) == 1
        assert result[0].evidence_id == "ev-adm"


# ---------------------------------------------------------------------------
# evidence_challenge 阶段
# ---------------------------------------------------------------------------


class TestEvidenceChallengePhase:
    """evidence_challenge 阶段看到 submitted + own private。"""

    def test_plaintiff_sees_submitted_and_own_private(self):
        ctrl = AccessController()
        state = ProcedureState(
            phase=ProcedurePhase.evidence_challenge,
            readable_access_domains=[
                AccessDomain.owner_private,
                AccessDomain.shared_common,
            ],
            admissible_evidence_statuses=[
                EvidenceStatus.private,
                EvidenceStatus.submitted,
                EvidenceStatus.challenged,
            ],
        )
        result = ctrl.filter_evidence_for_agent(
            role_code=AgentRole.plaintiff_agent.value,
            owner_party_id="party-plaintiff",
            all_evidence=_make_all_evidence(),
            procedure_state=state,
        )
        ev_ids = {e.evidence_id for e in result}
        # own private + submitted + challenged (all shared_common)
        assert "ev-priv-p" in ev_ids
        assert "ev-sub" in ev_ids
        assert "ev-chal" in ev_ids
        assert "ev-adm" not in ev_ids  # admitted_record not in readable_access_domains

    def test_judge_in_challenge_phase_sees_nothing(self):
        """judge 在 evidence_challenge 阶段看不到任何东西
        （judge 本身只有 admitted_record 域权限）。
        """
        ctrl = AccessController()
        state = ProcedureState(
            phase=ProcedurePhase.evidence_challenge,
            readable_access_domains=[
                AccessDomain.owner_private,
                AccessDomain.shared_common,
            ],
            admissible_evidence_statuses=[
                EvidenceStatus.submitted,
                EvidenceStatus.challenged,
            ],
        )
        result = ctrl.filter_evidence_for_agent(
            role_code=AgentRole.judge_agent.value,
            owner_party_id="system",
            all_evidence=_make_all_evidence(),
            procedure_state=state,
        )
        # judge only has admitted_record role access,
        # but procedure_state doesn't include admitted_record domain
        # → intersection is empty
        assert len(result) == 0


# ---------------------------------------------------------------------------
# 自定义阶段状态
# ---------------------------------------------------------------------------


class TestCustomProcedureState:
    def test_status_filter_works(self):
        """只允许 admitted 状态。"""
        ctrl = AccessController()
        state = ProcedureState(
            phase=ProcedurePhase.output_branching,
            readable_access_domains=[
                AccessDomain.shared_common,
                AccessDomain.admitted_record,
            ],
            admissible_evidence_statuses=[
                EvidenceStatus.admitted_for_discussion,
            ],
        )
        result = ctrl.filter_evidence_for_agent(
            role_code=AgentRole.plaintiff_agent.value,
            owner_party_id="party-plaintiff",
            all_evidence=_make_all_evidence(),
            procedure_state=state,
        )
        # submitted/challenged are shared_common domain but wrong status
        assert len(result) == 1
        assert result[0].evidence_id == "ev-adm"
