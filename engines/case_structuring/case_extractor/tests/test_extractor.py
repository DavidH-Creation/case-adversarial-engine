"""
CaseExtractor unit tests.
案件提取器单元测试。

Covered scenarios:
- Happy path: complete text → valid YAML with all fields
- Happy path: generated YAML passes _load_case() validation
- Edge: text missing financials → financials None in output
- Edge: text missing defenses → empty defenses list
- Error: empty input → ValueError
- Error: unknown prompt → ValueError
- Validation: extracted YAML passes pipeline requirements
- Schema: LLMExtractionOutput parses correctly
- Prompt: format_documents escapes XML entities
- Slug generation: various name patterns
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from engines.case_structuring.case_extractor.extractor import CaseExtractor, _slugify
from engines.case_structuring.case_extractor.schemas import (
    ExtractedCase,
    LLMExtractionOutput,
    LLMExtractedClaim,
    LLMExtractedDefense,
    LLMExtractedFinancials,
    LLMExtractedLoan,
    LLMExtractedMaterial,
    LLMExtractedParty,
    LLMExtractedRepayment,
    LLMExtractedSummaryRow,
)
from engines.case_structuring.case_extractor.prompts.generic import (
    build_extraction_prompt,
    format_documents,
)


# ---------------------------------------------------------------------------
# Mock LLM client
# ---------------------------------------------------------------------------


class MockLLMClient:
    """Mock LLM client returning predefined JSON responses."""

    def __init__(self, response: str, fail_times: int = 0) -> None:
        self._response = response
        self._fail_times = fail_times
        self.call_count = 0

    async def create_message(self, system: str, user: str, **kwargs) -> str:
        self.call_count += 1
        if self._fail_times > 0 and self.call_count <= self._fail_times:
            raise RuntimeError(f"Simulated LLM failure on attempt {self.call_count}")
        return self._response


# ---------------------------------------------------------------------------
# Factory helpers — build valid LLM JSON responses
# ---------------------------------------------------------------------------


def _make_civil_loan_response(
    *,
    plaintiff_name: str = "王某",
    defendant_name: str = "张某",
    num_materials: int = 3,
    num_claims: int = 2,
    num_defenses: int = 1,
    include_financials: bool = True,
) -> str:
    """Build a complete civil_loan LLM JSON response."""
    materials = []
    for i in range(num_materials):
        side = "plaintiff" if i % 2 == 0 else "defendant"
        prefix = "p" if side == "plaintiff" else "d"
        materials.append({
            "source_id": f"src-{prefix}-{i + 1:03d}",
            "text": f"材料内容 {i + 1}",
            "submitter": side,
            "document_type": "bank_transfer_records" if i == 0 else "loan_note",
        })

    claims = []
    for i in range(num_claims):
        claims.append({
            "claim_id": f"c-{i + 1:03d}",
            "claim_category": "返还借款" if i == 0 else "利息",
            "title": f"诉请 {i + 1}",
            "claim_text": f"诉请详细描述 {i + 1}",
        })

    defenses = []
    for i in range(num_defenses):
        defenses.append({
            "defense_id": f"d-{i + 1:03d}",
            "defense_category": "还款金额争议",
            "against_claim_id": f"c-{i + 1:03d}",
            "title": f"抗辩 {i + 1}",
            "defense_text": f"抗辩详细描述 {i + 1}",
        })

    financials = None
    if include_financials:
        financials = {
            "loans": [{
                "tx_id": "tx-loan-001",
                "date": "2022-02-26",
                "amount": "50000",
                "evidence_id": "src-p-001",
                "principal_base_contribution": True,
            }],
            "repayments": [{
                "tx_id": "tx-repay-001",
                "date": "2022-06-15",
                "amount": "10000",
                "evidence_id": "src-d-002",
                "attributed_to": "principal",
                "attribution_basis": "双方认可",
            }],
            "disputed": [],
            "claim_entries": [{
                "claim_id": "c-001",
                "claim_type": "principal",
                "claimed_amount": "40000",
                "evidence_ids": ["src-p-001"],
            }],
        }

    data = {
        "case_type": "civil_loan",
        "plaintiff": {
            "role": "plaintiff",
            "name": plaintiff_name,
            "party_id": "",
        },
        "defendant": {
            "role": "defendant",
            "name": defendant_name,
            "party_id": "",
        },
        "summary": [
            {"label": "借款", "description": "2022年借款5万元"},
            {"label": "还款", "description": "已还1万元"},
        ],
        "materials": materials,
        "claims": claims,
        "defenses": defenses,
        "financials": financials,
    }
    return json.dumps(data, ensure_ascii=False)


def _make_labor_response(
    *,
    num_claims: int = 2,
    num_defenses: int = 1,
) -> str:
    """Build a labor_dispute LLM JSON response (no financials)."""
    data = {
        "case_type": "labor_dispute",
        "plaintiff": {"role": "plaintiff", "name": "李某", "party_id": ""},
        "defendant": {"role": "defendant", "name": "某公司", "party_id": ""},
        "summary": [{"label": "劳动争议", "description": "违法解除劳动合同"}],
        "materials": [
            {
                "source_id": "src-p-001",
                "text": "劳动合同内容",
                "submitter": "plaintiff",
                "document_type": "labor_contract",
            },
            {
                "source_id": "src-d-001",
                "text": "解除通知书",
                "submitter": "defendant",
                "document_type": "termination_notice",
            },
        ],
        "claims": [
            {
                "claim_id": f"c-{i + 1:03d}",
                "claim_category": "经济补偿金" if i == 0 else "工资差额",
                "title": f"诉请 {i + 1}",
                "claim_text": f"诉请描述 {i + 1}",
            }
            for i in range(num_claims)
        ],
        "defenses": [
            {
                "defense_id": f"d-{i + 1:03d}",
                "defense_category": "合法解除",
                "against_claim_id": f"c-{i + 1:03d}",
                "title": f"抗辩 {i + 1}",
                "defense_text": f"抗辩描述 {i + 1}",
            }
            for i in range(num_defenses)
        ],
        "financials": None,
    }
    return json.dumps(data, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Happy path tests
# ---------------------------------------------------------------------------


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_civil_loan_extraction_produces_valid_case(self):
        """Complete civil loan text → ExtractedCase with all fields."""
        mock = MockLLMClient(_make_civil_loan_response())
        extractor = CaseExtractor(llm_client=mock, model="test-model")
        result = await extractor.extract([("complaint.txt", "起诉状内容...")])

        assert isinstance(result, ExtractedCase)
        assert result.case_type == "civil_loan"
        assert result.parties["plaintiff"]["name"] == "王某"
        assert result.parties["defendant"]["name"] == "张某"
        assert len(result.claims) == 2
        assert len(result.defenses) == 1
        assert result.financials is not None
        assert len(result.financials["loans"]) == 1

    @pytest.mark.asyncio
    async def test_generated_yaml_is_valid(self):
        """Generated YAML can be parsed back and contains required keys."""
        mock = MockLLMClient(_make_civil_loan_response())
        extractor = CaseExtractor(llm_client=mock)
        result = await extractor.extract([("doc.txt", "content")])

        yaml_str = CaseExtractor.to_yaml(result)
        data = yaml.safe_load(yaml_str)

        # Check required keys for _load_case()
        required = ["case_id", "case_slug", "case_type", "parties", "materials", "claims", "defenses"]
        for key in required:
            assert key in data, f"Missing required key: {key}"

    @pytest.mark.asyncio
    async def test_yaml_passes_load_case_validation(self):
        """Extracted YAML passes the same validation as _load_case()."""
        mock = MockLLMClient(_make_civil_loan_response())
        extractor = CaseExtractor(llm_client=mock)
        result = await extractor.extract([("doc.txt", "content")])

        yaml_str = CaseExtractor.to_yaml(result)
        data = yaml.safe_load(yaml_str)

        # Replicate _load_case validation
        required = ["case_id", "case_slug", "case_type", "parties", "materials", "claims", "defenses"]
        missing = [k for k in required if k not in data]
        assert missing == [], f"YAML missing required keys: {missing}"

        # Check party structure
        assert "plaintiff" in data["parties"]
        assert "defendant" in data["parties"]
        assert "party_id" in data["parties"]["plaintiff"]
        assert "name" in data["parties"]["plaintiff"]

    @pytest.mark.asyncio
    async def test_labor_dispute_extraction_no_financials(self):
        """Labor dispute → no financials in output."""
        mock = MockLLMClient(_make_labor_response())
        extractor = CaseExtractor(llm_client=mock)
        result = await extractor.extract([("doc.txt", "content")])

        assert result.case_type == "labor_dispute"
        assert result.financials is None
        yaml_str = CaseExtractor.to_yaml(result)
        data = yaml.safe_load(yaml_str)
        assert "financials" not in data

    @pytest.mark.asyncio
    async def test_multi_file_input(self):
        """Multiple input files are concatenated for extraction."""
        mock = MockLLMClient(_make_civil_loan_response())
        extractor = CaseExtractor(llm_client=mock)
        docs = [
            ("complaint.txt", "起诉状..."),
            ("defense.txt", "答辩状..."),
            ("evidence.txt", "证据清单..."),
        ]
        result = await extractor.extract(docs)
        assert isinstance(result, ExtractedCase)
        assert mock.call_count == 1  # Single LLM call for all docs

    @pytest.mark.asyncio
    async def test_custom_case_id(self):
        """Custom case_id overrides auto-generated one."""
        mock = MockLLMClient(_make_civil_loan_response())
        extractor = CaseExtractor(llm_client=mock)
        result = await extractor.extract(
            [("doc.txt", "content")],
            case_id="my-custom-id",
        )
        assert result.case_id == "my-custom-id"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_missing_financials_for_loan_case(self):
        """Civil loan without financials → financials is None."""
        mock = MockLLMClient(_make_civil_loan_response(include_financials=False))
        extractor = CaseExtractor(llm_client=mock)
        result = await extractor.extract([("doc.txt", "content")])

        assert result.case_type == "civil_loan"
        assert result.financials is None

    @pytest.mark.asyncio
    async def test_empty_defenses(self):
        """No defenses (only complaint) → empty defenses list."""
        mock = MockLLMClient(_make_civil_loan_response(num_defenses=0))
        extractor = CaseExtractor(llm_client=mock)
        result = await extractor.extract([("doc.txt", "content")])

        assert result.defenses == []
        # Should still pass validation
        errors = CaseExtractor.validate(result)
        assert errors == []

    @pytest.mark.asyncio
    async def test_materials_grouped_by_submitter(self):
        """Materials are correctly grouped into plaintiff/defendant."""
        mock = MockLLMClient(_make_civil_loan_response(num_materials=4))
        extractor = CaseExtractor(llm_client=mock)
        result = await extractor.extract([("doc.txt", "content")])

        p_mats = result.materials["plaintiff"]
        d_mats = result.materials["defendant"]
        assert len(p_mats) + len(d_mats) == 4
        for m in p_mats:
            assert m["metadata"]["submitter"] == "plaintiff"
        for m in d_mats:
            assert m["metadata"]["submitter"] == "defendant"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrors:
    @pytest.mark.asyncio
    async def test_empty_input_raises_value_error(self):
        """Empty document list → ValueError."""
        mock = MockLLMClient("")
        extractor = CaseExtractor(llm_client=mock)
        with pytest.raises(ValueError, match="At least one document"):
            await extractor.extract([])

    @pytest.mark.asyncio
    async def test_unknown_prompt_raises_value_error(self):
        """Unknown prompt name → ValueError."""
        mock = MockLLMClient("")
        extractor = CaseExtractor(llm_client=mock)
        with pytest.raises(ValueError, match="Unknown prompt"):
            await extractor.extract([("doc.txt", "content")], prompt_name="nonexistent")

    @pytest.mark.asyncio
    async def test_llm_retry_on_failure(self):
        """LLM failures are retried (via call_llm_with_retry)."""
        mock = MockLLMClient(_make_civil_loan_response(), fail_times=2)
        extractor = CaseExtractor(llm_client=mock, max_retries=3)
        result = await extractor.extract([("doc.txt", "content")])

        assert isinstance(result, ExtractedCase)
        assert mock.call_count == 3  # 2 failures + 1 success


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    @pytest.mark.asyncio
    async def test_complete_case_passes_validation(self):
        """Fully populated case has zero validation errors."""
        mock = MockLLMClient(_make_civil_loan_response())
        extractor = CaseExtractor(llm_client=mock)
        result = await extractor.extract([("doc.txt", "content")])
        errors = CaseExtractor.validate(result)
        assert errors == []

    def test_missing_claims_flagged(self):
        """ExtractedCase with empty claims → validation error."""
        case = ExtractedCase(
            case_id="test",
            case_slug="test",
            case_type="civil_loan",
            parties={
                "plaintiff": {"party_id": "p", "name": "P"},
                "defendant": {"party_id": "d", "name": "D"},
            },
            materials={"plaintiff": [{"source_id": "s1", "text": "t", "metadata": {}}], "defendant": []},
            claims=[],
            defenses=[],
        )
        errors = CaseExtractor.validate(case)
        assert any("claims" in e.lower() for e in errors)

    def test_invalid_defense_reference_flagged(self):
        """Defense referencing non-existent claim → validation error."""
        case = ExtractedCase(
            case_id="test",
            case_slug="test",
            case_type="civil_loan",
            parties={
                "plaintiff": {"party_id": "p", "name": "P"},
                "defendant": {"party_id": "d", "name": "D"},
            },
            materials={"plaintiff": [{"source_id": "s1", "text": "t", "metadata": {}}], "defendant": []},
            claims=[{"claim_id": "c-001", "claim_category": "cat", "title": "t", "claim_text": "t"}],
            defenses=[{
                "defense_id": "d-001",
                "defense_category": "cat",
                "against_claim_id": "c-999",  # non-existent
                "title": "t",
                "defense_text": "t",
            }],
        )
        errors = CaseExtractor.validate(case)
        assert any("c-999" in e for e in errors)

    def test_missing_party_flagged(self):
        """Missing defendant party → validation error."""
        case = ExtractedCase(
            case_id="test",
            case_slug="test",
            case_type="civil_loan",
            parties={"plaintiff": {"party_id": "p", "name": "P"}},
            materials={"plaintiff": [{"source_id": "s1", "text": "t", "metadata": {}}], "defendant": []},
            claims=[{"claim_id": "c-001", "claim_category": "cat", "title": "t", "claim_text": "t"}],
            defenses=[],
        )
        errors = CaseExtractor.validate(case)
        assert any("defendant" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Schema models
# ---------------------------------------------------------------------------


class TestSchemas:
    def test_llm_extraction_output_parses_complete_json(self):
        """LLMExtractionOutput.model_validate on complete JSON."""
        raw = json.loads(_make_civil_loan_response())
        output = LLMExtractionOutput.model_validate(raw)
        assert output.case_type == "civil_loan"
        assert output.plaintiff.name == "王某"
        assert len(output.materials) == 3
        assert len(output.claims) == 2
        assert output.financials is not None
        assert len(output.financials.loans) == 1

    def test_llm_extraction_output_parses_without_financials(self):
        """LLMExtractionOutput with financials=null."""
        raw = json.loads(_make_labor_response())
        output = LLMExtractionOutput.model_validate(raw)
        assert output.case_type == "labor_dispute"
        assert output.financials is None

    def test_extracted_case_model_dump_excludes_none(self):
        """model_dump(exclude_none=True) removes financials when None."""
        case = ExtractedCase(
            case_id="test",
            case_slug="test",
            case_type="labor_dispute",
            parties={"plaintiff": {"party_id": "p", "name": "P"}, "defendant": {"party_id": "d", "name": "D"}},
            materials={"plaintiff": [], "defendant": []},
            claims=[],
            defenses=[],
            financials=None,
        )
        data = case.model_dump(exclude_none=True)
        assert "financials" not in data


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------


class TestPrompts:
    def test_format_documents_escapes_xml(self):
        """format_documents escapes XML entities in filenames and content."""
        docs = [("file<1>.txt", "content with <tags> & ampersands")]
        result = format_documents(docs)
        assert "&lt;" in result  # < escaped in both filename and content
        assert "&gt;" in result  # > escaped
        assert "&amp;" in result  # & escaped
        # Quotes are only escaped in filenames (attribute values), not element text
        docs2 = [('file"name.txt', "text")]
        result2 = format_documents(docs2)
        assert "&quot;" in result2

    def test_format_documents_multiple_files(self):
        """Multiple documents produce multiple XML blocks."""
        docs = [("a.txt", "text A"), ("b.txt", "text B"), ("c.txt", "text C")]
        result = format_documents(docs)
        assert result.count("<document") == 3
        assert result.count("</document>") == 3

    def test_braces_in_document_text_do_not_crash(self):
        """Document text with Python format braces must not cause KeyError."""
        docs = [("contract.txt", "条款约定: {penalty} = {amount} * 0.01")]
        doc_block = format_documents(docs)
        # This would raise KeyError with str.format()
        prompt = build_extraction_prompt(doc_block)
        assert "{penalty}" in prompt
        assert "{amount}" in prompt
        assert "contract.txt" in prompt

    @pytest.mark.asyncio
    async def test_extraction_survives_braces_in_input(self):
        """End-to-end: document with format braces → extraction succeeds."""
        mock = MockLLMClient(_make_civil_loan_response())
        extractor = CaseExtractor(llm_client=mock)
        docs = [("doc.txt", "违约金计算: {penalty_rate} * {days}")]
        result = await extractor.extract(docs)
        assert isinstance(result, ExtractedCase)

    def test_format_documents_empty_list(self):
        """Empty list produces empty string."""
        assert format_documents([]) == ""


# ---------------------------------------------------------------------------
# Slug generation
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_english_names(self):
        slug = _slugify("Wang-v-Zhang")
        assert slug  # non-empty
        assert all(c.isalnum() or c == "-" for c in slug)

    def test_chinese_names_fallback(self):
        """Pure Chinese names → hash-based slug."""
        slug = _slugify("王某-v-张某")
        assert slug
        assert len(slug) <= 40

    def test_mixed_names(self):
        slug = _slugify("Wang某-v-Zhang某")
        assert slug
        assert len(slug) <= 40


# ---------------------------------------------------------------------------
# YAML round-trip compatibility
# ---------------------------------------------------------------------------


class TestYAMLRoundTrip:
    @pytest.mark.asyncio
    async def test_yaml_round_trip_preserves_structure(self):
        """YAML serialize → parse → same structure."""
        mock = MockLLMClient(_make_civil_loan_response())
        extractor = CaseExtractor(llm_client=mock)
        result = await extractor.extract([("doc.txt", "content")])

        yaml_str = CaseExtractor.to_yaml(result)
        parsed = yaml.safe_load(yaml_str)

        assert parsed["case_type"] == result.case_type
        assert parsed["parties"]["plaintiff"]["name"] == "王某"
        assert len(parsed["claims"]) == 2
        assert len(parsed["materials"]["plaintiff"]) > 0

    @pytest.mark.asyncio
    async def test_yaml_has_header_comments(self):
        """Generated YAML starts with header comments."""
        mock = MockLLMClient(_make_civil_loan_response())
        extractor = CaseExtractor(llm_client=mock)
        result = await extractor.extract([("doc.txt", "content")])

        yaml_str = CaseExtractor.to_yaml(result)
        assert yaml_str.startswith("# Auto-extracted case:")
