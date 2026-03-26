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
6. test_full_pipeline_evidence_indexer_to_round_engine
   — 全链路：EvidenceIndexer → IssueExtractor → RoundEngine，验证 AccessController 隔离
"""

from __future__ import annotations

import json
import pytest

from engines.adversarial.round_engine import RoundEngine
from engines.adversarial.schemas import AdversarialResult, AdversarialSummary, RoundConfig
from engines.case_structuring.evidence_indexer.indexer import EvidenceIndexer
from engines.case_structuring.evidence_indexer.schemas import RawMaterial
from engines.case_structuring.issue_extractor.extractor import IssueExtractor
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


# ---------------------------------------------------------------------------
# 全链路集成测试 / Full pipeline: EvidenceIndexer → IssueExtractor → RoundEngine
# ---------------------------------------------------------------------------

_PIPELINE_CASE_ID = "case-full-pipe-001"
_PIPELINE_PLAINTIFF_ID = "party-fp-p-001"
_PIPELINE_DEFENDANT_ID = "party-fp-d-001"

# EvidenceIndexer 生成的 evidence_id = f"evidence-{case_slug}-{idx:03d}"
_P_EV_ID = "evidence-fp-p-001"   # case_slug="fp-p"
_D_EV_ID = "evidence-fp-d-001"   # case_slug="fp-d"

_INDEXER_P_RESPONSE = json.dumps(
    [
        {
            "title": "借条原件",
            "summary": "被告出具借条，载明借款50万元，年利率6%",
            "evidence_type": "documentary",
            "source_id": "mat-fp-p-001",
            "target_facts": ["fact-fp-loan-agreement"],
            "target_issues": [],
        }
    ],
    ensure_ascii=False,
)

_INDEXER_D_RESPONSE = json.dumps(
    [
        {
            "title": "还款转账凭证",
            "summary": "被告已通过银行转账归还20万元",
            "evidence_type": "electronic_data",
            "source_id": "mat-fp-d-001",
            "target_facts": ["fact-fp-repayment"],
            "target_issues": [],
        }
    ],
    ensure_ascii=False,
)

_EXTRACTOR_RESPONSE = json.dumps(
    {
        "issues": [
            {
                "tmp_id": "issue-tmp-fp-001",
                "title": "借贷关系成立与否",
                "issue_type": "factual",
                "parent_tmp_id": None,
                "related_claim_ids": ["claim-fp-001"],
                "related_defense_ids": [],
                "evidence_ids": [_P_EV_ID, _D_EV_ID],
                "fact_propositions": [],
            }
        ],
        "burdens": [
            {
                "issue_tmp_id": "issue-tmp-fp-001",
                "burden_party_id": _PIPELINE_PLAINTIFF_ID,
                "description": "原告举证证明借贷关系成立",
                "proof_standard": "优势证据",
                "legal_basis": "《民法典》第667条",
            }
        ],
        "claim_issue_mapping": [
            {"claim_id": "claim-fp-001", "issue_tmp_ids": ["issue-tmp-fp-001"]}
        ],
        "defense_issue_mapping": [],
    },
    ensure_ascii=False,
)


def _pipeline_round_responses(issue_id: str, p_ev_id: str, d_ev_id: str) -> list[str]:
    def _resp(title: str, ev_id: str) -> str:
        return json.dumps(
            {
                "title": title,
                "body": f"{title}，引用证据 {ev_id}。",
                "issue_ids": [issue_id],
                "evidence_citations": [ev_id],
                "risk_flags": [],
                "arguments": [
                    {
                        "issue_id": issue_id,
                        "position": title,
                        "supporting_evidence_ids": [ev_id],
                        "legal_basis": "《民法典》第667条",
                    }
                ],
                "conflicts": [],
            },
            ensure_ascii=False,
        )

    ev_mgr = json.dumps(
        {
            "title": "证据整理",
            "body": "双方对还款金额存在争议。",
            "issue_ids": [issue_id],
            "evidence_citations": [p_ev_id],
            "risk_flags": [],
            "conflicts": [
                {
                    "issue_id": issue_id,
                    "plaintiff_evidence_ids": [p_ev_id],
                    "defendant_evidence_ids": [d_ev_id],
                    "conflict_description": "原告主张欠款50万，被告主张已还20万",
                }
            ],
        },
        ensure_ascii=False,
    )

    summary = json.dumps(
        {
            "plaintiff_strongest_arguments": [
                {
                    "issue_id": issue_id,
                    "position": "原告有借条和转账记录，证明借款已实际发生",
                    "evidence_ids": [p_ev_id],
                    "reasoning": "直接证明借贷要件",
                }
            ],
            "defendant_strongest_defenses": [
                {
                    "issue_id": issue_id,
                    "position": "被告已还款20万，应从本金扣除",
                    "evidence_ids": [d_ev_id],
                    "reasoning": "有转账凭证",
                }
            ],
            "unresolved_issues": [
                {
                    "issue_id": issue_id,
                    "issue_title": "借贷关系成立与否",
                    "why_unresolved": "双方对还款金额存在争议",
                }
            ],
            "missing_evidence_report": [],
            "overall_assessment": "原告证据链较完整，被告还款证据需核实。",
        },
        ensure_ascii=False,
    )

    return [
        _resp("原告首轮主张：借款关系成立", p_ev_id),
        _resp("被告首轮抗辩：已部分还款", d_ev_id),
        ev_mgr,
        _resp("原告反驳：还款金额不足仍欠30万", p_ev_id),
        _resp("被告反驳：还款凭证已证明还款20万", d_ev_id),
        summary,
    ]


class _SingleResponseMock:
    """固定响应 mock LLM。"""

    def __init__(self, response: str) -> None:
        self._response = response

    async def create_message(self, *, system: str, user: str, **kwargs) -> str:
        return self._response


@pytest.mark.asyncio
async def test_full_pipeline_evidence_indexer_to_round_engine():
    """全链路：EvidenceIndexer → IssueExtractor → RoundEngine，验证 AccessController 隔离。
    Full pipeline: EvidenceIndexer → IssueExtractor → RoundEngine.
    Verifies AccessController isolation across the true end-to-end flow.
    """
    # ── Phase 1: 原告 EvidenceIndexer ─────────────────────────────────────
    p_indexer = EvidenceIndexer(_SingleResponseMock(_INDEXER_P_RESPONSE))
    p_materials = [
        RawMaterial(
            source_id="mat-fp-p-001",
            text="借条。今借到张某人民币伍拾万元整，年利率6%。借款人：李某，2024-01-15。",
            metadata={"document_type": "promissory_note"},
        )
    ]
    p_evidence_list = await p_indexer.index(
        p_materials, _PIPELINE_CASE_ID, _PIPELINE_PLAINTIFF_ID, case_slug="fp-p"
    )
    assert len(p_evidence_list) == 1
    assert p_evidence_list[0].evidence_id == _P_EV_ID

    # ── Phase 2: 被告 EvidenceIndexer ─────────────────────────────────────
    d_indexer = EvidenceIndexer(_SingleResponseMock(_INDEXER_D_RESPONSE))
    d_materials = [
        RawMaterial(
            source_id="mat-fp-d-001",
            text="工商银行电子回单，李某向张某转账200,000元，日期2024-06-01。",
            metadata={"document_type": "bank_transfer_receipt"},
        )
    ]
    d_evidence_list = await d_indexer.index(
        d_materials, _PIPELINE_CASE_ID, _PIPELINE_DEFENDANT_ID, case_slug="fp-d"
    )
    assert len(d_evidence_list) == 1
    assert d_evidence_list[0].evidence_id == _D_EV_ID

    # 设置访问域：原告证据升为 shared_common（模拟质证入卷）
    # 被告证据保持 owner_private
    p_ev = p_evidence_list[0].model_copy(update={"access_domain": AccessDomain.shared_common})
    d_ev = d_evidence_list[0]  # owner_private

    # ── Phase 3: AccessController 隔离验证 ────────────────────────────────
    controller = AccessController()

    p_visible = controller.filter_evidence_for_agent(
        role_code=AgentRole.plaintiff_agent.value,
        owner_party_id=_PIPELINE_PLAINTIFF_ID,
        all_evidence=[p_ev, d_ev],
    )
    p_visible_ids = {e.evidence_id for e in p_visible}
    assert _P_EV_ID in p_visible_ids, "原告应可见 shared_common 证据"
    assert _D_EV_ID not in p_visible_ids, "原告不应可见被告 owner_private 证据"

    d_visible = controller.filter_evidence_for_agent(
        role_code=AgentRole.defendant_agent.value,
        owner_party_id=_PIPELINE_DEFENDANT_ID,
        all_evidence=[p_ev, d_ev],
    )
    d_visible_ids = {e.evidence_id for e in d_visible}
    assert _P_EV_ID in d_visible_ids, "被告应可见 shared_common 证据"
    assert _D_EV_ID in d_visible_ids, "被告应可见自己的 owner_private 证据"

    # ── Phase 4: IssueExtractor ───────────────────────────────────────────
    extractor = IssueExtractor(_SingleResponseMock(_EXTRACTOR_RESPONSE))
    claims = [
        {
            "claim_id": "claim-fp-001",
            "case_id": _PIPELINE_CASE_ID,
            "title": "归还借款本金50万元",
            "description": "请求被告归还借款本金500,000元",
            "related_evidence_ids": [],
        }
    ]
    defenses = [
        {
            "defense_id": "defense-fp-001",
            "case_id": _PIPELINE_CASE_ID,
            "title": "已还款20万元",
            "description": "被告已通过银行转账归还200,000元",
            "against_claim_id": "claim-fp-001",
            "related_evidence_ids": [],
        }
    ]
    evidence_dicts = [p_ev.model_dump(), d_ev.model_dump()]
    issue_tree = await extractor.extract(
        claims=claims,
        defenses=defenses,
        evidence=evidence_dicts,
        case_id=_PIPELINE_CASE_ID,
        case_slug="fp-pipeline",
    )
    assert issue_tree.case_id == _PIPELINE_CASE_ID
    assert len(issue_tree.issues) >= 1
    real_issue_id = issue_tree.issues[0].issue_id

    evidence_index = EvidenceIndex(case_id=_PIPELINE_CASE_ID, evidence=[p_ev, d_ev])

    # ── Phase 5: RoundEngine ──────────────────────────────────────────────
    responses = _pipeline_round_responses(real_issue_id, _P_EV_ID, _D_EV_ID)
    engine = RoundEngine(
        llm_client=SequentialMockLLMClient(responses),
        config=RoundConfig(max_tokens_per_output=1000, max_retries=2),
    )
    result = await engine.run(
        issue_tree=issue_tree,
        evidence_index=evidence_index,
        plaintiff_party_id=_PIPELINE_PLAINTIFF_ID,
        defendant_party_id=_PIPELINE_DEFENDANT_ID,
    )

    # ── Assertions ────────────────────────────────────────────────────────
    assert isinstance(result, AdversarialResult)
    assert result.case_id == _PIPELINE_CASE_ID
    assert result.run_id.startswith("run-adv-")
    assert len(result.rounds) == 3
    assert len(result.evidence_conflicts) >= 1, "应检测到双方证据冲突"
    assert result.summary is not None, "LLM 摘要应存在"
