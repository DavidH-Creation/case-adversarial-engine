"""
CaseExtractor — extract structured case data from raw Chinese legal documents.
案件提取器 — 从原始中文法律文书自动提取结构化案件 YAML。

Two-step process:
  1. LLM extracts structured JSON (parties, materials, claims, defenses, financials)
  2. Post-process into pipeline-compatible YAML format and validate

Usage::

    from engines.case_structuring.case_extractor import CaseExtractor

    extractor = CaseExtractor(llm_client=client, model="claude-sonnet-4-6")
    result = await extractor.extract([("complaint.txt", text1), ("defense.txt", text2)])
    yaml_str = extractor.to_yaml(result)
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from engines.shared.models import LLMClient

from engines.shared.json_utils import _extract_json_object
from engines.shared.structured_output import call_structured_llm

from .prompts import PROMPT_REGISTRY
from .schemas import (
    ExtractedCase,
    LLMExtractionOutput,
)

logger = logging.getLogger(__name__)

# Tool schema for structured output — wraps LLMExtractionOutput
_TOOL_SCHEMA: dict = LLMExtractionOutput.model_json_schema()


def _slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    # Keep alphanumeric and hyphens, collapse multiple hyphens
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", text.lower()).strip("-")
    # If mostly Chinese, generate a short hash-based slug
    if not re.search(r"[a-zA-Z]", slug):
        return uuid.uuid4().hex[:12]
    # Remove Chinese chars for the slug
    slug = re.sub(r"[\u4e00-\u9fff]+", "", slug).strip("-")
    return slug[:40] if slug else uuid.uuid4().hex[:12]


class CaseExtractor:
    """Extract structured case information from raw legal documents.

    Args:
        llm_client: LLM client implementing create_message protocol.
        model:      Model ID for extraction (default: balanced tier).
        temperature: LLM temperature (default 0.0 for deterministic output).
        max_tokens:  Max output tokens (default 8192 — extraction can be long).
        max_retries:  Max LLM call retries (default 3).
    """

    def __init__(
        self,
        llm_client: "LLMClient",
        *,
        model: str = "claude-sonnet-4-6",
        temperature: float = 0.0,
        max_tokens: int = 8192,
        max_retries: int = 3,
    ) -> None:
        self._llm = llm_client
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_retries = max_retries

    async def extract(
        self,
        documents: list[tuple[str, str]],
        *,
        case_id: str | None = None,
        prompt_name: str = "generic",
    ) -> ExtractedCase:
        """Extract structured case data from raw documents.

        Args:
            documents:   List of (filename, text_content) tuples.
            case_id:     Optional case ID override. Auto-generated if None.
            prompt_name: Prompt module to use (default: "generic").

        Returns:
            ExtractedCase ready for YAML serialization.

        Raises:
            ValueError: If documents list is empty or prompt not found.
            RuntimeError: If LLM call fails after all retries.
        """
        if not documents:
            raise ValueError("At least one document is required for extraction")

        prompt_module = self._load_prompt(prompt_name)

        # Format documents into XML blocks
        doc_block = prompt_module.format_documents(documents)
        system = prompt_module.SYSTEM_PROMPT
        user = prompt_module.EXTRACTION_PROMPT.format(documents=doc_block)

        # Call LLM with structured output
        raw_data = await self._call_llm(system, user)

        # Parse and validate LLM output
        llm_output = LLMExtractionOutput.model_validate(raw_data)

        # Convert to pipeline-compatible format
        return self._to_extracted_case(llm_output, case_id=case_id)

    async def _call_llm(self, system: str, user: str) -> dict:
        """Call LLM with structured output, falling back to text extraction."""
        if getattr(self._llm, "_supports_structured_output", False):
            return await call_structured_llm(
                self._llm,
                system=system,
                user=user,
                model=self._model,
                tool_name="extract_case",
                tool_description="从法律文书中提取结构化案件信息 / Extract structured case info from legal documents",
                tool_schema=_TOOL_SCHEMA,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                max_retries=self._max_retries,
            )
        # Fallback: free-form text → JSON extraction
        from engines.shared.llm_utils import call_llm_with_retry

        raw = await call_llm_with_retry(
            self._llm,
            system=system,
            user=user,
            model=self._model,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            max_retries=self._max_retries,
        )
        return _extract_json_object(raw)

    def _to_extracted_case(
        self,
        llm: LLMExtractionOutput,
        *,
        case_id: str | None = None,
    ) -> ExtractedCase:
        """Convert LLM output to pipeline-compatible ExtractedCase."""
        missing_fields: list[str] = []

        # Generate IDs
        p_name = llm.plaintiff.name or "原告"
        d_name = llm.defendant.name or "被告"
        slug = _slugify(f"{p_name}-v-{d_name}")
        auto_case_id = case_id or f"case-{llm.case_type}-{uuid.uuid4().hex[:8]}"
        p_id = llm.plaintiff.party_id or f"party-plaintiff-{_slugify(p_name) or 'p'}"
        d_id = llm.defendant.party_id or f"party-defendant-{_slugify(d_name) or 'd'}"

        # Check for missing fields
        if not llm.plaintiff.name:
            missing_fields.append("plaintiff.name")
        if not llm.defendant.name:
            missing_fields.append("defendant.name")
        if not llm.claims:
            missing_fields.append("claims")
        if not llm.materials:
            missing_fields.append("materials")

        # Build parties
        parties = {
            "plaintiff": {"party_id": p_id, "name": p_name},
            "defendant": {"party_id": d_id, "name": d_name},
        }

        # Build summary
        summary = [[row.label, row.description] for row in llm.summary]

        # Build materials grouped by submitter
        p_materials: list[dict[str, Any]] = []
        d_materials: list[dict[str, Any]] = []
        for m in llm.materials:
            entry: dict[str, Any] = {
                "source_id": m.source_id,
                "text": m.text,
                "metadata": {
                    "document_type": m.document_type,
                    "submitter": m.submitter,
                    "status": "admitted_for_discussion",
                },
            }
            if m.submitter == "defendant":
                d_materials.append(entry)
            else:
                p_materials.append(entry)

        materials: dict[str, list[dict[str, Any]]] = {
            "plaintiff": p_materials,
            "defendant": d_materials,
        }

        # Build claims
        claims = [
            {
                "claim_id": c.claim_id,
                "claim_category": c.claim_category,
                "title": c.title,
                "claim_text": c.claim_text,
            }
            for c in llm.claims
        ]

        # Build defenses
        defenses = [
            {
                "defense_id": d.defense_id,
                "defense_category": d.defense_category,
                "against_claim_id": d.against_claim_id,
                "title": d.title,
                "defense_text": d.defense_text,
            }
            for d in llm.defenses
        ]

        # Build financials (only for loan cases)
        financials: dict[str, Any] | None = None
        if llm.financials and llm.case_type == "civil_loan":
            financials = {
                "loans": [loan.model_dump() for loan in llm.financials.loans],
                "repayments": [r.model_dump() for r in llm.financials.repayments],
                "disputed": [d.model_dump() for d in llm.financials.disputed],
                "claim_entries": [ce.model_dump() for ce in llm.financials.claim_entries],
            }

        result = ExtractedCase(
            case_id=auto_case_id,
            case_slug=slug,
            case_type=llm.case_type,
            parties=parties,
            summary=summary,
            materials=materials,
            claims=claims,
            defenses=defenses,
            financials=financials,
        )
        result._missing_fields = missing_fields
        return result

    @staticmethod
    def to_yaml(extracted: ExtractedCase) -> str:
        """Serialize ExtractedCase to YAML string.

        Args:
            extracted: Validated ExtractedCase instance.

        Returns:
            YAML string compatible with scripts/run_case.py _load_case().
        """
        data = extracted.model_dump(exclude_none=True)
        # Remove internal fields
        data.pop("_missing_fields", None)

        # Add header comment
        header = f"# Auto-extracted case: {extracted.case_id}\n"
        header += f"# Case type: {extracted.case_type}\n\n"

        return header + yaml.dump(
            data,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=120,
        )

    @staticmethod
    def validate(extracted: ExtractedCase) -> list[str]:
        """Validate extracted case against pipeline requirements.

        Returns:
            List of validation error messages. Empty = valid.
        """
        errors: list[str] = []

        # Required top-level keys (same as _load_case)
        required = ["case_id", "case_slug", "case_type", "parties", "materials", "claims", "defenses"]
        # Keys where an empty value (empty list/dict/str) is invalid
        must_be_nonempty = {"case_id", "case_slug", "case_type", "parties", "materials", "claims"}
        data = extracted.model_dump(exclude_none=True)
        for key in required:
            if key not in data:
                errors.append(f"Missing required field: {key}")
            elif key in must_be_nonempty and not data[key]:
                errors.append(f"Missing required field: {key}")

        # Party structure
        parties = data.get("parties", {})
        for role in ("plaintiff", "defendant"):
            if role not in parties:
                errors.append(f"Missing party: {role}")
            elif "party_id" not in parties[role] or "name" not in parties[role]:
                errors.append(f"Party '{role}' missing party_id or name")

        # Materials must have at least one entry
        mats = data.get("materials", {})
        if not mats.get("plaintiff") and not mats.get("defendant"):
            errors.append("No materials found for either party")

        # Claims should have valid IDs
        for claim in data.get("claims", []):
            if not claim.get("claim_id"):
                errors.append("Claim missing claim_id")

        # Defenses should reference valid claims
        claim_ids = {c["claim_id"] for c in data.get("claims", [])}
        for defense in data.get("defenses", []):
            if defense.get("against_claim_id") and defense["against_claim_id"] not in claim_ids:
                errors.append(
                    f"Defense {defense.get('defense_id', '?')} references "
                    f"non-existent claim {defense['against_claim_id']}"
                )

        return errors

    @staticmethod
    def _load_prompt(name: str) -> Any:
        """Load a prompt module from the registry."""
        if name not in PROMPT_REGISTRY:
            available = ", ".join(PROMPT_REGISTRY.keys()) or "(none)"
            raise ValueError(f"Unknown prompt: {name}. Available: {available}")
        return PROMPT_REGISTRY[name]
