"""
端到端对抗流程集成测试 — mock LLM 驱动完整三轮对抗。
End-to-end adversarial pipeline integration tests — mock LLM driving full three-round adversarial.

覆盖路径 / Coverage:
1. test_adversarial_pipeline_happy_path
   — mock LLM 驱动完整链路：EvidenceIndex + IssueTree → RoundEngine（三轮）→ AdversarialSummary
2. test_round_engine_produces_three_rounds
   — 验证 AdversarialResult 恰好包含 3 个 RoundState
3. test_adversarial_summary_required_fields
   — AdversarialSummary 包含所有必要字段
4. test_access_controller_plaintiff_cannot_see_defendant_private
   — AccessController 隔离：原告代理无法读取被告 owner_private 证据
5. test_access_controller_defendant_cannot_see_plaintiff_private
   — AccessController 隔离：被告代理无法读取原告 owner_private 证据
"""

from __future__ import annotations

import json
import pytest

from engines.adversarial.round_engine import RoundEngine
from engines.adversarial.schemas import AdversarialResult, AdversarialSummary, RoundConfig
from engines.shared.access_control import AccessController
from engines.shared.models import (
    AccessDomain,
    AgentRole,
    Evidence,
    EvidenceIndex,
    EvidenceType,
    Issue,
    IssueTree,
    IssueType,
)

from .conftest import SequentialMockLLMClient


# ---------------------------------------------------------------------------
# 常量 / Constants
# ---------------------------------------------------------------------------

CASE_ID = "case-adv-integ-001"
PLAINTIFF_ID = "party-p-001"
DEFENDANT_ID = "party-d-001"
ISSUE_ID = "issue-loan-001"
EV_SHARED = "ev-shared-001"
EV_P_PRIVATE = "ev-plaintiff-private-001"
EV_D_PRIVATE = "ev-defendant-private-001"


# ---------------------------------------------------------------------------
# 构建测试数据 / Build test data
# ---------------------------------------------------------------------------

def _make_issue_tree() -> IssueTree:
    """构造包含一个争点的 IssueTree。"""
    return IssueTree(
        case_id=CASE_ID,
        issues=[
            Issue(
                issue_id=ISSUE_ID,
                case_id=CASE_ID,
                title="借贷关系是否成立",
                issue_type=IssueType.factual,
                evidence_ids=[EV_SHARED, EV_P_PRIVATE, EV_D_PRIVATE],
                status=__import__("engines.shared.models", fromlist=["IssueStatus"]).IssueStatus.open,
            )
        ],
    )


def _make_evidence_index() -> EvidenceIndex:
    """构造含三类访问域证据的 EvidenceIndex：shared、原告私有、被告私有。"""
    shared_ev = Evidence(
        evidence_id=EV_SHARED,
        case_id=CASE_ID,
        owner_party_id=PLAINTIFF_ID,
        title="借条原件",
        source="mat-001",
        summary="被告出具借条载明借款50万元",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=["fact-loan-agreement"],
        access_domain=AccessDomain.shared_common,
    )
    plaintiff_private = Evidence(
        evidence_id=EV_P_PRIVATE,
        case_id=CASE_ID,
        owner_party_id=PLAINTIFF_ID,
        title="原告内部法律意见书",
        source="mat-002",
        summary="律师评估原告证据强度（私有）",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=["fact-loan-agreement"],
        access_domain=AccessDomain.owner_private,
    )
    defendant_private = Evidence(
        evidence_id=EV_D_PRIVATE,
        case_id=CASE_ID,
        owner_party_id=DEFENDANT_ID,
        title="被告内部沟通记录",
        source="mat-003",
        summary="被告内部邮件讨论还款计划（私有）",
        evidence_type=EvidenceType.electronic_data,
        target_fact_ids=["fact-loan-agreement"],
        access_domain=AccessDomain.owner_private,
    )
    return EvidenceIndex(
        case_id=CASE_ID,
        evidence=[shared_ev, plaintiff_private, defendant_private],
    )


def _agent_response(title: str, issue_id: str = ISSUE_ID, evidence_ids: list[str] | None = None) -> str:
    """构造 party agent 的 LLM mock 响应。"""
    ev = evidence_ids or [EV_SHARED]
    return json.dumps(
        {
            "title": title,
            "body": f"{title}。详细论述，引用证据 {ev[0]}。",
            "issue_ids": [issue_id],
            "evidence_citations": ev,
            "risk_flags": [],
            "arguments": [
                {
                    "issue_id": issue_id,
                    "position": title,
                    "supporting_evidence_ids": ev,
                    "legal_basis": "《民法典》第667条",
                }
            ],
            "conflicts": [],
        },
        ensure_ascii=False,
    )


def _evidence_manager_response() -> str:
    """构造 EvidenceManagerAgent 的 LLM mock 响应。"""
    return json.dumps(
        {
            "title": "证据整理摘要",
            "body": "原告持有借条和转账记录，被告对转账用途持异议。",
            "issue_ids": [ISSUE_ID],
            "evidence_citations": [EV_SHARED],
            "risk_flags": [],
            "conflicts": [
                {
                    "issue_id": ISSUE_ID,
                    "plaintiff_evidence_ids": [EV_SHARED],
                    "defendant_evidence_ids": [],
                    "conflict_description": "被告否认借款关系，但原告有书面借条",
                }
            ],
        },
        ensure_ascii=False,
    )


def _summary_response() -> str:
    """构造 AdversarialSummarizer 的 LLM mock 响应。"""
    return json.dumps(
        {
            "plaintiff_strongest_arguments": [
                {
                    "issue_id": ISSUE_ID,
                    "position": "原告持有借条和银行转账记录，直接证明借贷关系成立",
                    "evidence_ids": [EV_SHARED],
                    "reasoning": "借条与转账记录相互印证，构成完整证据链",
                }
            ],
            "defendant_strongest_defenses": [
                {
                    "issue_id": ISSUE_ID,
                    "position": "被告主张转账系商业往来款，非借贷",
                    "evidence_ids": [EV_SHARED],
                    "reasoning": "动摇借贷关系的主观合意要件",
                }
            ],
            "unresolved_issues": [
                {
                    "issue_id": ISSUE_ID,
                    "issue_title": "借贷关系是否成立",
                    "why_unresolved": "双方对转账目的各执一词，尚无客观第三方证据",
                }
            ],
            "missing_evidence_report": [
                {
                    "issue_id": ISSUE_ID,
                    "missing_for_party_id": DEFENDANT_ID,
                    "gap_description": "被告缺乏能证明转账系商业往来的书面协议",
                }
            ],
            "overall_assessment": "借贷关系成立的可能性较高，但被告的商业往来抗辩尚未完全排除。",
        },
        ensure_ascii=False,
    )


def _make_sequential_client() -> SequentialMockLLMClient:
    """6 条响应：原告主张、被告主张、证据整理、原告反驳、被告反驳、总结。"""
    return SequentialMockLLMClient(
        responses=[
            _agent_response("原告首轮主张：借款关系成立", evidence_ids=[EV_SHARED, EV_P_PRIVATE]),
            _agent_response("被告首轮抗辩：否认借贷关系", evidence_ids=[EV_SHARED, EV_D_PRIVATE]),
            _evidence_manager_response(),
            _agent_response("原告反驳：被告商业往来说法缺乏依据", evidence_ids=[EV_SHARED]),
            _agent_response("被告反驳：原告转账记录无法证明借贷合意", evidence_ids=[EV_SHARED]),
            _summary_response(),
        ]
    )


# ---------------------------------------------------------------------------
# 测试 / Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_adversarial_pipeline_happy_path():
    """完整对抗流程 happy path：EvidenceIndex → RoundEngine → AdversarialResult（含 summary）。"""
    issue_tree = _make_issue_tree()
    evidence_index = _make_evidence_index()
    client = _make_sequential_client()

    engine = RoundEngine(llm_client=client, config=RoundConfig(temperature=0.0))
    result = await engine.run(
        issue_tree=issue_tree,
        evidence_index=evidence_index,
        plaintiff_party_id=PLAINTIFF_ID,
        defendant_party_id=DEFENDANT_ID,
    )

    assert isinstance(result, AdversarialResult)
    assert result.case_id == CASE_ID
    # AdversarialSummarizer 应已被调用（6th LLM call）
    assert result.summary is not None
    assert isinstance(result.summary, AdversarialSummary)
    # 所有 6 次 LLM 调用都应已使用
    assert client.call_count == 6


@pytest.mark.asyncio
async def test_round_engine_produces_three_rounds():
    """RoundEngine 必须产出恰好 3 个 RoundState（claim, evidence, rebuttal）。"""
    from engines.adversarial.schemas import RoundPhase

    issue_tree = _make_issue_tree()
    evidence_index = _make_evidence_index()
    engine = RoundEngine(llm_client=_make_sequential_client(), config=RoundConfig(temperature=0.0))
    result = await engine.run(
        issue_tree=issue_tree,
        evidence_index=evidence_index,
        plaintiff_party_id=PLAINTIFF_ID,
        defendant_party_id=DEFENDANT_ID,
    )

    assert len(result.rounds) == 3
    phases = [r.phase for r in result.rounds]
    assert phases == [RoundPhase.claim, RoundPhase.evidence, RoundPhase.rebuttal]


@pytest.mark.asyncio
async def test_adversarial_summary_required_fields():
    """AdversarialSummary 必须包含所有 5 个必要字段且非空。"""
    issue_tree = _make_issue_tree()
    evidence_index = _make_evidence_index()
    engine = RoundEngine(llm_client=_make_sequential_client(), config=RoundConfig(temperature=0.0))
    result = await engine.run(
        issue_tree=issue_tree,
        evidence_index=evidence_index,
        plaintiff_party_id=PLAINTIFF_ID,
        defendant_party_id=DEFENDANT_ID,
    )

    summary = result.summary
    assert summary is not None

    # 5 个必要字段全部存在
    assert hasattr(summary, "plaintiff_strongest_arguments")
    assert hasattr(summary, "defendant_strongest_defenses")
    assert hasattr(summary, "unresolved_issues")
    assert hasattr(summary, "missing_evidence_report")
    assert hasattr(summary, "overall_assessment")

    # 内容非空
    assert len(summary.plaintiff_strongest_arguments) >= 1
    assert len(summary.defendant_strongest_defenses) >= 1
    assert summary.overall_assessment.strip() != ""

    # 每个 StrongestArgument 必须有 evidence_ids
    for arg in summary.plaintiff_strongest_arguments:
        assert len(arg.evidence_ids) >= 1
    for defense in summary.defendant_strongest_defenses:
        assert len(defense.evidence_ids) >= 1


def test_access_controller_plaintiff_cannot_see_defendant_private():
    """AccessController 隔离：原告代理看不到被告 owner_private 证据。"""
    evidence_index = _make_evidence_index()
    controller = AccessController()

    visible = controller.filter_evidence_for_agent(
        role_code=AgentRole.plaintiff_agent.value,
        owner_party_id=PLAINTIFF_ID,
        all_evidence=evidence_index.evidence,
    )

    visible_ids = {e.evidence_id for e in visible}
    # 原告可见：shared + 自己的 private
    assert EV_SHARED in visible_ids
    assert EV_P_PRIVATE in visible_ids
    # 原告不可见：被告的 private
    assert EV_D_PRIVATE not in visible_ids


def test_access_controller_defendant_cannot_see_plaintiff_private():
    """AccessController 隔离：被告代理看不到原告 owner_private 证据。"""
    evidence_index = _make_evidence_index()
    controller = AccessController()

    visible = controller.filter_evidence_for_agent(
        role_code=AgentRole.defendant_agent.value,
        owner_party_id=DEFENDANT_ID,
        all_evidence=evidence_index.evidence,
    )

    visible_ids = {e.evidence_id for e in visible}
    # 被告可见：shared + 自己的 private
    assert EV_SHARED in visible_ids
    assert EV_D_PRIVATE in visible_ids
    # 被告不可见：原告的 private
    assert EV_P_PRIVATE not in visible_ids
