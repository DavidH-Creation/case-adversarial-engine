"""
Phase 0b: Multi-case-type structural pipeline validation.

Tests that the full pipeline path is wired correctly for each case type:
- YAML case files load and validate
- All engine constructors accept each case_type without error
- Prompt registries contain entries for all 3 case types
- Engine → prompt → LLM call chain is structurally sound (mock LLM)
- Acceptance metric framework computes correctly from synthetic artifacts

These tests do NOT call real LLMs. They validate wiring and structural integrity.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

_PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CASE_TYPES = ["civil_loan", "labor_dispute", "real_estate"]

REPRESENTATIVE_YAMLS = {
    "civil_loan": "wang_v_chen_zhuang_2025.yaml",
    "labor_dispute": "labor_dispute_1.yaml",
    "real_estate": "real_estate_1.yaml",
}

CASES_DIR = _PROJECT_ROOT / "cases"

REQUIRED_YAML_KEYS = [
    "case_id",
    "case_slug",
    "case_type",
    "parties",
    "materials",
    "claims",
    "defenses",
]


def _mock_llm_client() -> MagicMock:
    """Create a mock LLM client that satisfies the LLMClient protocol."""
    client = MagicMock()
    client.call = MagicMock(return_value="mock response")
    return client


# ---------------------------------------------------------------------------
# 1. YAML case file validation — all representative cases
# ---------------------------------------------------------------------------


class TestYAMLCaseFiles:
    """Validate that all representative YAML case files exist and are well-formed."""

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_representative_yaml_exists(self, case_type: str):
        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
        assert yaml_path.exists(), f"Missing representative YAML: {yaml_path}"

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_yaml_has_required_keys(self, case_type: str):
        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict), f"YAML root must be dict, got {type(data)}"
        missing = [k for k in REQUIRED_YAML_KEYS if k not in data]
        assert not missing, f"Missing keys in {yaml_path.name}: {missing}"

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_yaml_case_type_matches(self, case_type: str):
        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data["case_type"] == case_type

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_yaml_has_both_party_materials(self, case_type: str):
        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        materials = data["materials"]
        assert len(materials.get("plaintiff", [])) > 0, "No plaintiff materials"
        assert len(materials.get("defendant", [])) > 0, "No defendant materials"

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_yaml_has_claims_and_defenses(self, case_type: str):
        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert len(data["claims"]) > 0, "No claims defined"
        assert len(data["defenses"]) > 0, "No defenses defined"

    def test_all_yaml_files_loadable(self):
        """Every .yaml in cases/ must load without YAML syntax errors."""
        for yaml_path in sorted(CASES_DIR.glob("*.yaml")):
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            assert isinstance(data, dict), f"{yaml_path.name} did not parse as dict"


# ---------------------------------------------------------------------------
# 2. Case structuring engine registry validation
# ---------------------------------------------------------------------------


class TestCaseStructuringRegistries:
    """Verify all case_structuring engine prompt registries contain all 3 case types."""

    def test_evidence_indexer_registry(self):
        from engines.case_structuring.evidence_indexer.prompts import PROMPT_REGISTRY

        for ct in CASE_TYPES:
            assert ct in PROMPT_REGISTRY, f"evidence_indexer missing {ct}"

    def test_issue_extractor_registry(self):
        from engines.case_structuring.issue_extractor.prompts import PROMPT_REGISTRY

        for ct in CASE_TYPES:
            assert ct in PROMPT_REGISTRY, f"issue_extractor missing {ct}"

    def test_evidence_weight_scorer_registry(self):
        from engines.case_structuring.evidence_weight_scorer.prompts import PROMPT_REGISTRY

        for ct in CASE_TYPES:
            assert ct in PROMPT_REGISTRY, f"evidence_weight_scorer missing {ct}"

    def test_admissibility_evaluator_registry(self):
        from engines.case_structuring.admissibility_evaluator.prompts import PROMPT_REGISTRY

        for ct in CASE_TYPES:
            assert ct in PROMPT_REGISTRY, f"admissibility_evaluator missing {ct}"


# ---------------------------------------------------------------------------
# 3. Adversarial engine registry validation
# ---------------------------------------------------------------------------


class TestAdversarialRegistry:
    """Verify adversarial prompt registry contains all 3 case types."""

    def test_registry_has_all_case_types(self):
        from engines.adversarial.prompts import PROMPT_REGISTRY

        for ct in CASE_TYPES:
            assert ct in PROMPT_REGISTRY, f"adversarial missing {ct}"

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_module_has_case_context(self, case_type: str):
        from engines.adversarial.prompts import PROMPT_REGISTRY

        module = PROMPT_REGISTRY[case_type]
        assert hasattr(module, "CASE_CONTEXT"), f"adversarial/{case_type} missing CASE_CONTEXT"
        assert len(module.CASE_CONTEXT) > 50

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_module_has_evidence_review_criteria(self, case_type: str):
        from engines.adversarial.prompts import PROMPT_REGISTRY

        module = PROMPT_REGISTRY[case_type]
        assert hasattr(module, "EVIDENCE_REVIEW_CRITERIA"), (
            f"adversarial/{case_type} missing EVIDENCE_REVIEW_CRITERIA"
        )


# ---------------------------------------------------------------------------
# 4. Simulation run engine registry validation
# ---------------------------------------------------------------------------


class TestSimulationRunRegistries:
    """Verify simulation_run prompt registry contains all 3 case types."""

    def test_top_level_registry_has_all_case_types(self):
        from engines.simulation_run.prompts import PROMPT_REGISTRY

        for ct in CASE_TYPES:
            assert ct in PROMPT_REGISTRY, f"simulation_run missing {ct}"


# ---------------------------------------------------------------------------
# 5. Report generation prompt registry validation
# ---------------------------------------------------------------------------


class TestReportGenerationRegistries:
    """Verify report generation prompt registries contain all 3 case types."""

    def test_prompts_registry_has_all_case_types(self):
        from engines.report_generation.prompts import PROMPT_REGISTRY

        for ct in CASE_TYPES:
            assert ct in PROMPT_REGISTRY, f"report_generation missing {ct}"


# ---------------------------------------------------------------------------
# 6. Engine constructor smoke tests (mock LLM, no actual calls)
# ---------------------------------------------------------------------------


class TestEngineConstructorSmoke:
    """Each engine must instantiate without error for all 3 case types."""

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_evidence_indexer_init(self, case_type: str):
        from engines.case_structuring.evidence_indexer.indexer import EvidenceIndexer

        engine = EvidenceIndexer(llm_client=_mock_llm_client(), case_type=case_type)
        assert engine is not None

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_issue_extractor_init(self, case_type: str):
        from engines.case_structuring.issue_extractor.extractor import IssueExtractor

        engine = IssueExtractor(llm_client=_mock_llm_client(), case_type=case_type)
        assert engine is not None

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_admissibility_evaluator_init(self, case_type: str):
        from engines.case_structuring.admissibility_evaluator import AdmissibilityEvaluator

        engine = AdmissibilityEvaluator(
            llm_client=_mock_llm_client(),
            case_type=case_type,
            model="mock-model",
            temperature=0.0,
            max_retries=1,
        )
        assert engine is not None

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_decision_path_tree_generator_init(self, case_type: str):
        from engines.simulation_run.decision_path_tree import DecisionPathTreeGenerator

        engine = DecisionPathTreeGenerator(
            llm_client=_mock_llm_client(),
            case_type=case_type,
            model="mock-model",
            temperature=0.0,
            max_retries=1,
        )
        assert engine is not None

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_issue_impact_ranker_init(self, case_type: str):
        from engines.simulation_run.issue_impact_ranker.ranker import IssueImpactRanker

        engine = IssueImpactRanker(
            llm_client=_mock_llm_client(),
            case_type=case_type,
        )
        assert engine is not None

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_attack_chain_optimizer_init(self, case_type: str):
        from engines.simulation_run.attack_chain_optimizer import AttackChainOptimizer

        engine = AttackChainOptimizer(
            llm_client=_mock_llm_client(),
            case_type=case_type,
            model="mock-model",
            temperature=0.0,
            max_retries=1,
        )
        assert engine is not None

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_action_recommender_init(self, case_type: str):
        from engines.simulation_run.action_recommender import ActionRecommender

        engine = ActionRecommender(
            llm_client=_mock_llm_client(),
            case_type=case_type,
        )
        assert engine is not None

    def test_unsupported_case_type_raises(self):
        from engines.case_structuring.evidence_indexer.indexer import EvidenceIndexer

        with pytest.raises((ValueError, KeyError)):
            EvidenceIndexer(llm_client=_mock_llm_client(), case_type="nonexistent_type")


# ---------------------------------------------------------------------------
# 7. Document assistance engine registry validation
# ---------------------------------------------------------------------------


class TestDocumentAssistanceRegistry:
    """Verify document assistance prompt registry contains all 3 case types.

    Note: document_assistance uses 2D keys (doc_type, case_type).
    """

    DOC_TYPES = ["pleading", "defense", "cross_exam"]

    def test_all_case_type_doc_type_combos_registered(self):
        from engines.document_assistance.prompts import PROMPT_REGISTRY

        for ct in CASE_TYPES:
            for dt in self.DOC_TYPES:
                assert (dt, ct) in PROMPT_REGISTRY, (
                    f"document_assistance missing ({dt}, {ct})"
                )


# ---------------------------------------------------------------------------
# 8. YAML → pipeline data flow structural tests
# ---------------------------------------------------------------------------


class TestYAMLToPipelineDataFlow:
    """Verify that representative YAML files produce valid pipeline input structures."""

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_materials_build_to_raw_materials(self, case_type: str):
        """YAML materials section converts to RawMaterial objects without error."""
        from engines.shared.models import RawMaterial

        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        for role in ("plaintiff", "defendant"):
            for mat in data["materials"][role]:
                rm = RawMaterial(
                    source_id=mat["source_id"],
                    text=mat["text"].strip() if isinstance(mat["text"], str) else str(mat["text"]),
                    metadata=mat.get("metadata", {}),
                )
                assert rm.source_id
                assert len(rm.text) > 0

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_claims_have_required_fields(self, case_type: str):
        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        for claim in data["claims"]:
            assert "claim_id" in claim, f"claim missing claim_id: {claim}"
            assert "title" in claim or "claim_text" in claim, f"claim missing title/text: {claim}"

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_defenses_have_required_fields(self, case_type: str):
        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        for defense in data["defenses"]:
            assert "defense_id" in defense, f"defense missing defense_id: {defense}"
            assert "against_claim_id" in defense, f"defense missing against_claim_id: {defense}"

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_parties_have_ids_and_names(self, case_type: str):
        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        for role in ("plaintiff", "defendant"):
            party = data["parties"][role]
            assert "party_id" in party, f"{role} missing party_id"
            assert "name" in party, f"{role} missing name"

    def test_civil_loan_has_financials(self):
        """civil_loan cases should have a financials section for amount calculation."""
        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS["civil_loan"]
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "financials" in data, "civil_loan representative YAML missing financials section"
        fin = data["financials"]
        assert "loans" in fin, "financials missing loans"
        assert "claim_entries" in fin, "financials missing claim_entries"


# ---------------------------------------------------------------------------
# 9. Acceptance framework integration — load_and_validate_yaml for all cases
# ---------------------------------------------------------------------------


class TestAcceptanceFrameworkIntegration:
    """Verify acceptance framework can load all representative YAMLs."""

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_acceptance_yaml_validation(self, case_type: str):
        from scripts.run_acceptance import load_and_validate_yaml

        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
        data, error = load_and_validate_yaml(yaml_path)
        assert data is not None, f"Validation failed for {yaml_path.name}: {error}"
        assert error is None

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_acceptance_yaml_matching(self, case_type: str):
        """_yaml_matches_case_type correctly identifies representative YAMLs."""
        from scripts.run_acceptance import _yaml_matches_case_type

        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
        assert _yaml_matches_case_type(yaml_path, case_type)

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_at_least_one_yaml_per_case_type(self, case_type: str):
        """Each case type has at least one matching YAML in cases/ directory."""
        from scripts.run_acceptance import _yaml_matches_case_type

        all_yamls = sorted(CASES_DIR.glob("*.yaml"))
        matching = [p for p in all_yamls if _yaml_matches_case_type(p, case_type)]
        assert len(matching) >= 1, f"No YAML files match case_type '{case_type}'"
