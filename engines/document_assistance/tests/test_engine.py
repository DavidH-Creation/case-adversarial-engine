"""
文书辅助引擎单元测试。
Unit tests for DocumentAssistanceEngine.

使用 mock LLM 客户端验证 / Tests using mock LLM client verify:
- Happy path: civil_loan PleadingDraft 所有必填字段非空，evidence_ids_cited ≥1
- Happy path: labor_dispute DefenseStatement defense_claim_items ≥1 条
- Happy path: real_estate CrossExaminationOpinion 针对每个 evidence_id 恰好 1 条意见
- Edge case: EvidenceIndex 为空 → CrossExaminationOpinion items=[], 不抛错
- Edge case: OptimalAttackChain 缺失 → PleadingDraft attack_chain_basis="unavailable"
- Error path: LLM 返回不符合 schema 的 JSON → DocumentGenerationError，含 doc_type 和 case_type
- Error path: LLM 完全失败 → DocumentGenerationError，含 doc_type 和 case_type
- Error path: 无效 (doc_type, case_type) → DocumentGenerationError
- Integration: PROMPT_REGISTRY 覆盖全部 9 个组合
"""

from __future__ import annotations

import json

import pytest

from engines.document_assistance.engine import DocumentAssistanceEngine
from engines.document_assistance.prompts import PROMPT_REGISTRY
from engines.document_assistance.schemas import (
    CrossExaminationOpinion,
    DefenseStatement,
    DocumentAssistanceInput,
    DocumentGenerationError,
    PleadingDraft,
)
from engines.shared.models import (
    Evidence,
    EvidenceIndex,
    EvidenceType,
    Issue,
    IssueTree,
    IssueType,
)


# ---------------------------------------------------------------------------
# Mock LLM 客户端 / Mock LLM client
# ---------------------------------------------------------------------------


class MockLLMClient:
    """返回预定义 JSON 响应的 mock LLM 客户端。"""

    def __init__(self, response: str, fail_times: int = 0) -> None:
        self._response = response
        self._fail_times = fail_times
        self.call_count = 0
        self.last_system: str | None = None
        self.last_user: str | None = None

    async def create_message(self, system: str, user: str, **kwargs) -> str:
        self.call_count += 1
        self.last_system = system
        self.last_user = user
        if self._fail_times > 0:
            self._fail_times -= 1
            raise RuntimeError("Simulated LLM failure")
        return self._response


# ---------------------------------------------------------------------------
# 测试夹具 / Test fixtures
# ---------------------------------------------------------------------------


def _make_evidence(eid: str, owner: str = "party-p") -> Evidence:
    return Evidence(
        evidence_id=eid,
        case_id="case-test",
        title=f"Evidence {eid}",
        source="test-source",
        summary="Test evidence summary",
        evidence_type=EvidenceType.documentary,
        owner_party_id=owner,
        target_fact_ids=["fact-001"],
    )


def _make_issue(iid: str) -> Issue:
    return Issue(
        issue_id=iid,
        case_id="case-test",
        title=f"Issue {iid}",
        issue_type=IssueType.factual,
    )


def _make_issue_tree(n: int = 2) -> IssueTree:
    return IssueTree(
        case_id="case-test",
        issues=[_make_issue(f"issue-{i:03d}") for i in range(1, n + 1)],
    )


def _make_evidence_index(ev_ids: list[str]) -> EvidenceIndex:
    return EvidenceIndex(
        case_id="case-test",
        evidence=[_make_evidence(eid) for eid in ev_ids],
    )


def _make_input(
    doc_type: str,
    case_type: str,
    ev_ids: list[str] | None = None,
    attack_chain=None,
) -> DocumentAssistanceInput:
    if ev_ids is None:
        ev_ids = ["ev-001", "ev-002"]
    return DocumentAssistanceInput(
        case_id="case-test",
        run_id="run-test",
        doc_type=doc_type,
        case_type=case_type,
        issue_tree=_make_issue_tree(2),
        evidence_index=_make_evidence_index(ev_ids),
        case_data={
            "case_id": "case-test",
            "parties": {
                "plaintiff": {"name": "张三", "party_id": "party-p"},
                "defendant": {"name": "李四", "party_id": "party-d"},
            },
        },
        attack_chain=attack_chain,
    )


def _pleading_json(ev_ids: list[str] | None = None) -> str:
    return json.dumps({
        "header": "民间借贷纠纷起诉状 | 案件：case-test",
        "fact_narrative_items": ["2023年1月借款10万元"],
        "legal_claim_items": ["依据《民法典》第六百七十五条"],
        "prayer_for_relief_items": ["请求返还借款本金100000元"],
        "evidence_ids_cited": ev_ids or ["ev-001"],
        "attack_chain_basis": "unavailable",
    })


def _defense_json(ev_ids: list[str] | None = None) -> str:
    return json.dumps({
        "header": "答辩状 | 案件：case-test",
        "denial_items": ["否认原告主张的借款金额"],
        "defense_claim_items": ["款项已于2023年6月全部归还，有银行转账记录为证"],
        "counter_prayer_items": ["请求驳回原告全部诉讼请求"],
        "evidence_ids_cited": ev_ids or ["ev-002"],
    })


def _cross_exam_json(ev_ids: list[str] | None = None) -> str:
    ids = ev_ids or ["ev-001", "ev-002"]
    items = [{"evidence_id": eid, "opinion_text": f"对{eid}的质证意见"} for eid in ids]
    return json.dumps({
        "items": items,
        "evidence_ids_cited": ids,
    })


def _make_engine(response: str, fail_times: int = 0) -> DocumentAssistanceEngine:
    return DocumentAssistanceEngine(
        MockLLMClient(response, fail_times=fail_times),
        model="claude-sonnet-4-6",
        temperature=0.0,
        max_retries=1,
    )


# ---------------------------------------------------------------------------
# Happy path: PleadingDraft
# ---------------------------------------------------------------------------


class TestPleadingDraftHappyPath:
    @pytest.mark.asyncio
    async def test_civil_loan_pleading_all_fields_non_empty(self):
        engine = _make_engine(_pleading_json())
        draft = await engine.generate(input=_make_input("pleading", "civil_loan"))

        assert draft.doc_type == "pleading"
        assert draft.case_type == "civil_loan"
        assert draft.case_id == "case-test"
        assert isinstance(draft.content, PleadingDraft)
        content = draft.content

        assert content.header  # non-empty
        assert len(content.fact_narrative_items) >= 1
        assert len(content.legal_claim_items) >= 1
        assert len(content.prayer_for_relief_items) >= 1

    @pytest.mark.asyncio
    async def test_evidence_ids_cited_non_empty(self):
        engine = _make_engine(_pleading_json(["ev-001", "ev-002"]))
        draft = await engine.generate(input=_make_input("pleading", "civil_loan"))
        assert len(draft.evidence_ids_cited) >= 1
        assert "ev-001" in draft.evidence_ids_cited

    @pytest.mark.asyncio
    async def test_attack_chain_basis_unavailable_when_no_attack_chain(self):
        """OptimalAttackChain 产物缺失 → attack_chain_basis="unavailable"。"""
        response = json.dumps({
            "header": "起诉状",
            "fact_narrative_items": ["事实"],
            "legal_claim_items": ["依据"],
            "prayer_for_relief_items": ["请求"],
            "evidence_ids_cited": ["ev-001"],
            "attack_chain_basis": "unavailable",
        })
        engine = _make_engine(response)
        draft = await engine.generate(input=_make_input("pleading", "civil_loan", attack_chain=None))
        assert isinstance(draft.content, PleadingDraft)
        assert draft.content.attack_chain_basis == "unavailable"

    @pytest.mark.asyncio
    async def test_labor_dispute_pleading(self):
        engine = _make_engine(_pleading_json())
        draft = await engine.generate(input=_make_input("pleading", "labor_dispute"))
        assert draft.case_type == "labor_dispute"
        assert isinstance(draft.content, PleadingDraft)

    @pytest.mark.asyncio
    async def test_real_estate_pleading(self):
        engine = _make_engine(_pleading_json())
        draft = await engine.generate(input=_make_input("pleading", "real_estate"))
        assert draft.case_type == "real_estate"
        assert isinstance(draft.content, PleadingDraft)


# ---------------------------------------------------------------------------
# Happy path: DefenseStatement
# ---------------------------------------------------------------------------


class TestDefenseStatementHappyPath:
    @pytest.mark.asyncio
    async def test_labor_dispute_defense_claim_items_non_empty(self):
        """labor_dispute DefenseStatement defense_claim_items 包含 ≥1 条回应原告主张的条目。"""
        engine = _make_engine(_defense_json())
        draft = await engine.generate(input=_make_input("defense", "labor_dispute"))

        assert draft.doc_type == "defense"
        assert isinstance(draft.content, DefenseStatement)
        assert len(draft.content.defense_claim_items) >= 1

    @pytest.mark.asyncio
    async def test_civil_loan_defense(self):
        engine = _make_engine(_defense_json())
        draft = await engine.generate(input=_make_input("defense", "civil_loan"))
        assert isinstance(draft.content, DefenseStatement)
        assert len(draft.evidence_ids_cited) >= 1

    @pytest.mark.asyncio
    async def test_real_estate_defense(self):
        engine = _make_engine(_defense_json(["ev-002"]))
        draft = await engine.generate(input=_make_input("defense", "real_estate"))
        assert isinstance(draft.content, DefenseStatement)
        assert "ev-002" in draft.evidence_ids_cited


# ---------------------------------------------------------------------------
# Happy path: CrossExaminationOpinion
# ---------------------------------------------------------------------------


class TestCrossExaminationOpinionHappyPath:
    @pytest.mark.asyncio
    async def test_real_estate_each_evidence_gets_one_opinion(self):
        """real_estate CrossExaminationOpinion 针对每个 evidence_id 生成恰好 1 条意见。"""
        ev_ids = ["ev-001", "ev-002", "ev-003"]
        engine = _make_engine(_cross_exam_json(ev_ids))
        draft = await engine.generate(input=_make_input("cross_exam", "real_estate", ev_ids=ev_ids))

        assert draft.doc_type == "cross_exam"
        assert isinstance(draft.content, CrossExaminationOpinion)
        opinion_ids = {item.evidence_id for item in draft.content.items}
        assert opinion_ids == set(ev_ids)

    @pytest.mark.asyncio
    async def test_civil_loan_cross_exam(self):
        ev_ids = ["ev-001", "ev-002"]
        engine = _make_engine(_cross_exam_json(ev_ids))
        draft = await engine.generate(input=_make_input("cross_exam", "civil_loan", ev_ids=ev_ids))
        assert isinstance(draft.content, CrossExaminationOpinion)
        assert len(draft.content.items) == len(ev_ids)

    @pytest.mark.asyncio
    async def test_labor_dispute_cross_exam(self):
        ev_ids = ["ev-001"]
        engine = _make_engine(_cross_exam_json(ev_ids))
        draft = await engine.generate(input=_make_input("cross_exam", "labor_dispute", ev_ids=ev_ids))
        assert isinstance(draft.content, CrossExaminationOpinion)
        assert draft.content.items[0].evidence_id == "ev-001"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_evidence_index_cross_exam_returns_empty_items(self):
        """EvidenceIndex 为空 → CrossExaminationOpinion items=[], 不抛错, 不调 LLM。"""
        # Use a failing LLM to confirm it's not called
        engine = _make_engine("", fail_times=99)
        inp = _make_input("cross_exam", "civil_loan", ev_ids=[])
        draft = await engine.generate(input=inp)

        assert isinstance(draft.content, CrossExaminationOpinion)
        assert draft.content.items == []
        assert draft.evidence_ids_cited == []
        # LLM should NOT have been called
        assert engine._llm.call_count == 0  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_generated_at_is_set(self):
        engine = _make_engine(_pleading_json())
        draft = await engine.generate(input=_make_input("pleading", "civil_loan"))
        assert draft.generated_at
        assert "T" in draft.generated_at  # ISO8601 format

    @pytest.mark.asyncio
    async def test_retry_on_llm_failure(self):
        """LLM 失败 1 次后重试成功。"""
        engine = _make_engine(_pleading_json(), fail_times=1)
        # max_retries=1 means 1 retry after first failure
        draft = await engine.generate(input=_make_input("pleading", "civil_loan"))
        assert isinstance(draft.content, PleadingDraft)

    @pytest.mark.asyncio
    async def test_cross_exam_extra_items_from_evidence_ids_cited(self):
        """LLM 在 evidence_ids_cited 中引用但 items 里缺少 → engine 补充占位条目。"""
        response = json.dumps({
            "items": [{"evidence_id": "ev-001", "opinion_text": "意见1"}],
            "evidence_ids_cited": ["ev-001", "ev-002"],  # ev-002 not in items
        })
        engine = _make_engine(response)
        draft = await engine.generate(
            input=_make_input("cross_exam", "civil_loan", ev_ids=["ev-001", "ev-002"])
        )
        item_ids = {item.evidence_id for item in draft.content.items}
        assert "ev-001" in item_ids
        assert "ev-002" in item_ids


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestErrorPaths:
    @pytest.mark.asyncio
    async def test_invalid_doc_type_raises_error(self):
        """未注册的 (doc_type, case_type) → DocumentGenerationError。"""
        engine = _make_engine("")
        inp = _make_input("unknown_type", "civil_loan")
        with pytest.raises(DocumentGenerationError, match="doc_type=unknown_type"):
            await engine.generate(input=inp)

    @pytest.mark.asyncio
    async def test_invalid_case_type_raises_error(self):
        engine = _make_engine("")
        inp = _make_input("pleading", "unknown_case")
        with pytest.raises(DocumentGenerationError, match="case_type=unknown_case"):
            await engine.generate(input=inp)

    @pytest.mark.asyncio
    async def test_llm_returns_invalid_json_raises_error(self):
        """LLM 返回无法解析为 schema 的 JSON → DocumentGenerationError，含 doc_type 和 case_type。"""
        engine = _make_engine('{"not_a_valid_field": "oops"}')
        inp = _make_input("pleading", "civil_loan")
        with pytest.raises(DocumentGenerationError) as exc_info:
            await engine.generate(input=inp)
        err_msg = str(exc_info.value)
        assert "doc_type=pleading" in err_msg
        assert "case_type=civil_loan" in err_msg

    @pytest.mark.asyncio
    async def test_llm_all_retries_fail_raises_error(self):
        """LLM 所有重试均失败 → DocumentGenerationError，含 doc_type 和 case_type。"""
        engine = _make_engine("", fail_times=99)
        # max_retries=1 → 2 total attempts
        inp = _make_input("defense", "labor_dispute")
        with pytest.raises(DocumentGenerationError) as exc_info:
            await engine.generate(input=inp)
        err_msg = str(exc_info.value)
        assert "doc_type=defense" in err_msg
        assert "case_type=labor_dispute" in err_msg

    @pytest.mark.asyncio
    async def test_empty_evidence_ids_cited_raises_error(self):
        """LLM 返回 evidence_ids_cited=[] → DocumentGenerationError。"""
        response = json.dumps({
            "header": "起诉状",
            "fact_narrative_items": ["事实"],
            "legal_claim_items": ["依据"],
            "prayer_for_relief_items": ["请求"],
            "evidence_ids_cited": [],  # empty!
            "attack_chain_basis": "unavailable",
        })
        engine = _make_engine(response)
        with pytest.raises(DocumentGenerationError, match="evidence_ids_cited is empty"):
            await engine.generate(input=_make_input("pleading", "civil_loan"))

    @pytest.mark.asyncio
    async def test_error_message_always_contains_doc_type_and_case_type(self):
        """所有 DocumentGenerationError 的消息都包含 doc_type 和 case_type。"""
        engine = _make_engine('{"garbage": true}')
        for doc_type, case_type in [
            ("pleading", "real_estate"),
            ("defense", "labor_dispute"),
        ]:
            inp = _make_input(doc_type, case_type)
            with pytest.raises(DocumentGenerationError) as exc_info:
                await engine.generate(input=inp)
            err = str(exc_info.value)
            assert f"doc_type={doc_type}" in err, f"Expected doc_type in error: {err}"
            assert f"case_type={case_type}" in err, f"Expected case_type in error: {err}"


# ---------------------------------------------------------------------------
# PROMPT_REGISTRY 覆盖测试 / Registry coverage test
# ---------------------------------------------------------------------------


class TestPromptRegistryCoverage:
    def test_all_nine_combinations_registered(self):
        """PROMPT_REGISTRY 覆盖全部 9 个 (doc_type, case_type) 组合。"""
        expected = {
            ("pleading",   "civil_loan"),
            ("defense",    "civil_loan"),
            ("cross_exam", "civil_loan"),
            ("pleading",   "labor_dispute"),
            ("defense",    "labor_dispute"),
            ("cross_exam", "labor_dispute"),
            ("pleading",   "real_estate"),
            ("defense",    "real_estate"),
            ("cross_exam", "real_estate"),
        }
        assert set(PROMPT_REGISTRY.keys()) == expected

    def test_each_entry_has_system_prompt_and_callable(self):
        for key, value in PROMPT_REGISTRY.items():
            system, builder = value
            assert isinstance(system, str), f"{key}: system should be str"
            assert len(system) > 0, f"{key}: system should be non-empty"
            assert callable(builder), f"{key}: builder should be callable"

    def test_user_prompt_builders_return_strings(self):
        """所有 build_user_prompt 函数返回非空字符串。"""
        issue_tree = IssueTree(
            case_id="case-test",
            issues=[Issue(
                issue_id="issue-001",
                case_id="case-test",
                title="借款人主体争议",
                issue_type=IssueType.factual,
            )],
        )
        ev_index = EvidenceIndex(
            case_id="case-test",
            evidence=[Evidence(
                evidence_id="ev-001",
                case_id="case-test",
                title="借条",
                source="test",
                summary="借款10万元",
                evidence_type=EvidenceType.documentary,
                owner_party_id="party-p",
                target_fact_ids=["fact-001"],
            )],
        )
        case_data = {
            "case_id": "case-test",
            "parties": {
                "plaintiff": {"name": "张三", "party_id": "party-p"},
                "defendant": {"name": "李四", "party_id": "party-d"},
            },
        }
        for key, (system, builder) in PROMPT_REGISTRY.items():
            result = builder(
                issue_tree=issue_tree,
                evidence_index=ev_index,
                case_data=case_data,
                attack_chain=None,
            )
            assert isinstance(result, str), f"{key}: build_user_prompt should return str"
            assert len(result) > 0, f"{key}: build_user_prompt should return non-empty string"
