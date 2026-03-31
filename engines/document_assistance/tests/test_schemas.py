"""
文书辅助引擎 schema 单元测试。
Unit tests for document assistance engine schemas.

测试内容 / Tests:
- PleadingDraft、DefenseStatement、CrossExaminationOpinion 正确 validate
- DocumentDraft 包装三种文书类型
- DocumentAssistanceInput 正确 validate
- DocumentGenerationError 是 Exception 子类
- 所有字段默认值正确
"""

from __future__ import annotations

import pytest

from engines.document_assistance.schemas import (
    CrossExaminationOpinion,
    CrossExaminationOpinionItem,
    DefenseStatement,
    DocumentAssistanceInput,
    DocumentDraft,
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
# 测试夹具 / Fixtures
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


def _make_issue_tree(n_issues: int = 2) -> IssueTree:
    return IssueTree(
        case_id="case-test",
        issues=[_make_issue(f"issue-{i:03d}") for i in range(1, n_issues + 1)],
    )


def _make_evidence_index(ev_ids: list[str]) -> EvidenceIndex:
    return EvidenceIndex(
        case_id="case-test",
        evidence=[_make_evidence(eid) for eid in ev_ids],
    )


# ---------------------------------------------------------------------------
# PleadingDraft
# ---------------------------------------------------------------------------


class TestPleadingDraft:
    def test_valid_minimal(self):
        draft = PleadingDraft(
            header="民间借贷纠纷起诉状 | 案件：case-001",
            fact_narrative_items=["2023年1月1日，原告向被告出借10万元"],
            legal_claim_items=["依据《民法典》第六百七十五条"],
            prayer_for_relief_items=["请求返还借款本金100000元"],
            evidence_ids_cited=["ev-001"],
        )
        assert draft.attack_chain_basis == "unavailable"
        assert len(draft.evidence_ids_cited) == 1

    def test_attack_chain_basis_custom(self):
        draft = PleadingDraft(
            header="起诉状",
            fact_narrative_items=["事实"],
            legal_claim_items=["法律依据"],
            prayer_for_relief_items=["请求"],
            evidence_ids_cited=["ev-001"],
            attack_chain_basis="攻击链：优先攻击主体争议",
        )
        assert draft.attack_chain_basis == "攻击链：优先攻击主体争议"

    def test_evidence_ids_cited_required(self):
        """evidence_ids_cited 字段是必填字段，缺失时 ValidationError。"""
        with pytest.raises(Exception):
            PleadingDraft(
                header="起诉状",
                fact_narrative_items=["事实"],
                legal_claim_items=["依据"],
                prayer_for_relief_items=["请求"],
                # evidence_ids_cited 缺失
            )

    def test_multiple_evidence_ids(self):
        draft = PleadingDraft(
            header="起诉状",
            fact_narrative_items=["事实1", "事实2"],
            legal_claim_items=["依据1"],
            prayer_for_relief_items=["请求1", "请求2"],
            evidence_ids_cited=["ev-001", "ev-002", "ev-003"],
        )
        assert len(draft.evidence_ids_cited) == 3


# ---------------------------------------------------------------------------
# DefenseStatement
# ---------------------------------------------------------------------------


class TestDefenseStatement:
    def test_valid_minimal(self):
        stmt = DefenseStatement(
            header="答辩状 | 案件：case-001",
            denial_items=["否认原告主张的借款金额"],
            defense_claim_items=["款项已于2023年6月全部归还，有银行转账记录为证"],
            counter_prayer_items=["请求驳回原告全部诉讼请求"],
            evidence_ids_cited=["ev-002"],
        )
        assert len(stmt.defense_claim_items) >= 1
        assert len(stmt.evidence_ids_cited) >= 1

    def test_multiple_defense_claims(self):
        stmt = DefenseStatement(
            header="答辩状",
            denial_items=["否认1", "否认2"],
            defense_claim_items=["抗辩1", "抗辩2", "抗辩3"],
            counter_prayer_items=["请求驳回"],
            evidence_ids_cited=["ev-001", "ev-002"],
        )
        assert len(stmt.defense_claim_items) == 3


# ---------------------------------------------------------------------------
# CrossExaminationOpinion
# ---------------------------------------------------------------------------


class TestCrossExaminationOpinion:
    def test_valid_with_items(self):
        opinion = CrossExaminationOpinion(
            items=[
                CrossExaminationOpinionItem(
                    evidence_id="ev-001", opinion_text="对该借条真实性有异议，签名笔迹存疑"
                ),
                CrossExaminationOpinionItem(
                    evidence_id="ev-002", opinion_text="银行流水真实但与本案借贷关系无法对应"
                ),
            ],
            evidence_ids_cited=["ev-001", "ev-002"],
        )
        assert len(opinion.items) == 2
        assert opinion.items[0].evidence_id == "ev-001"

    def test_empty_items_default(self):
        """items 默认为空列表（EvidenceIndex 为空时的边界情况）。"""
        opinion = CrossExaminationOpinion()
        assert opinion.items == []
        assert opinion.evidence_ids_cited == []

    def test_per_evidence_exactly_one_item(self):
        """每个 evidence_id 对应恰好 1 条意见。"""
        ev_ids = ["ev-001", "ev-002", "ev-003"]
        items = [
            CrossExaminationOpinionItem(evidence_id=eid, opinion_text=f"意见 {eid}")
            for eid in ev_ids
        ]
        opinion = CrossExaminationOpinion(items=items, evidence_ids_cited=ev_ids)
        assert len(opinion.items) == len(ev_ids)
        cited_in_items = {item.evidence_id for item in opinion.items}
        assert cited_in_items == set(ev_ids)


# ---------------------------------------------------------------------------
# DocumentDraft
# ---------------------------------------------------------------------------


class TestDocumentDraft:
    def _pleading(self) -> PleadingDraft:
        return PleadingDraft(
            header="起诉状",
            fact_narrative_items=["事实"],
            legal_claim_items=["依据"],
            prayer_for_relief_items=["请求"],
            evidence_ids_cited=["ev-001"],
        )

    def test_wrap_pleading(self):
        draft = DocumentDraft(
            doc_type="pleading",
            case_type="civil_loan",
            case_id="case-001",
            run_id="run-001",
            content=self._pleading(),
            evidence_ids_cited=["ev-001"],
            generated_at="2026-03-31T00:00:00Z",
        )
        assert draft.doc_type == "pleading"
        assert draft.case_type == "civil_loan"
        assert isinstance(draft.content, PleadingDraft)

    def test_wrap_defense(self):
        stmt = DefenseStatement(
            header="答辩状",
            denial_items=["否认"],
            defense_claim_items=["抗辩"],
            counter_prayer_items=["驳回"],
            evidence_ids_cited=["ev-002"],
        )
        draft = DocumentDraft(
            doc_type="defense",
            case_type="labor_dispute",
            case_id="case-002",
            run_id="run-002",
            content=stmt,
            evidence_ids_cited=["ev-002"],
            generated_at="2026-03-31T00:00:00Z",
        )
        assert draft.doc_type == "defense"
        assert isinstance(draft.content, DefenseStatement)

    def test_wrap_cross_exam(self):
        opinion = CrossExaminationOpinion(
            items=[CrossExaminationOpinionItem(evidence_id="ev-001", opinion_text="意见")],
            evidence_ids_cited=["ev-001"],
        )
        draft = DocumentDraft(
            doc_type="cross_exam",
            case_type="real_estate",
            case_id="case-003",
            run_id="run-003",
            content=opinion,
            evidence_ids_cited=["ev-001"],
            generated_at="2026-03-31T00:00:00Z",
        )
        assert draft.doc_type == "cross_exam"
        assert isinstance(draft.content, CrossExaminationOpinion)

    def test_serialization_roundtrip(self):
        """DocumentDraft 可序列化为 JSON 再还原。"""
        original = DocumentDraft(
            doc_type="pleading",
            case_type="civil_loan",
            case_id="case-001",
            run_id="run-001",
            content=self._pleading(),
            evidence_ids_cited=["ev-001"],
            generated_at="2026-03-31T00:00:00Z",
        )
        json_str = original.model_dump_json()
        # Should not raise
        data = DocumentDraft.model_validate_json(json_str)
        assert data.doc_type == original.doc_type
        assert data.evidence_ids_cited == original.evidence_ids_cited


# ---------------------------------------------------------------------------
# DocumentAssistanceInput
# ---------------------------------------------------------------------------


class TestDocumentAssistanceInput:
    def test_valid_with_defaults(self):
        inp = DocumentAssistanceInput(
            case_id="case-001",
            run_id="run-001",
            doc_type="pleading",
            case_type="civil_loan",
            issue_tree=_make_issue_tree(2),
            evidence_index=_make_evidence_index(["ev-001", "ev-002"]),
        )
        assert inp.case_data == {}
        assert inp.attack_chain is None

    def test_with_case_data(self):
        inp = DocumentAssistanceInput(
            case_id="case-002",
            run_id="run-002",
            doc_type="defense",
            case_type="labor_dispute",
            issue_tree=_make_issue_tree(1),
            evidence_index=_make_evidence_index(["ev-001"]),
            case_data={"parties": {"plaintiff": {"name": "张三"}}},
        )
        assert inp.case_data["parties"]["plaintiff"]["name"] == "张三"


# ---------------------------------------------------------------------------
# DocumentGenerationError
# ---------------------------------------------------------------------------


class TestDocumentGenerationError:
    def test_is_exception(self):
        assert issubclass(DocumentGenerationError, Exception)

    def test_message_contains_doc_type_and_case_type(self):
        err = DocumentGenerationError(
            "LLM call failed for doc_type=pleading, case_type=civil_loan: timeout"
        )
        assert "doc_type=pleading" in str(err)
        assert "case_type=civil_loan" in str(err)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(DocumentGenerationError, match="doc_type=defense"):
            raise DocumentGenerationError(
                "Schema validation failed for doc_type=defense, case_type=real_estate"
            )
