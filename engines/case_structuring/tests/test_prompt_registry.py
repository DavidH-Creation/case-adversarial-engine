"""
多案型 prompt 注册表单元测试。
Unit tests for multi-case-type prompt registry registration.

验证 labor_dispute 和 real_estate 已正确注册到所有引擎的 PROMPT_REGISTRY，
并检查注册模块包含必要的属性。
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# 工具函数 / Helpers
# ---------------------------------------------------------------------------

NEW_CASE_TYPES = ["labor_dispute", "real_estate"]


def _assert_registry_has_case_types(registry: dict, engine_name: str) -> None:
    """断言注册表包含所有新案型。"""
    for ct in NEW_CASE_TYPES:
        assert ct in registry, (
            f"[{engine_name}] PROMPT_REGISTRY missing case_type '{ct}'"
        )


# ---------------------------------------------------------------------------
# issue_extractor
# ---------------------------------------------------------------------------


class TestIssueExtractorRegistry:
    """issue_extractor prompt 注册表测试。"""

    @pytest.fixture(autouse=True)
    def load_registry(self):
        from engines.case_structuring.issue_extractor.prompts import PROMPT_REGISTRY
        self.registry = PROMPT_REGISTRY

    def test_all_new_case_types_registered(self):
        _assert_registry_has_case_types(self.registry, "issue_extractor")

    def test_civil_loan_still_registered(self):
        assert "civil_loan" in self.registry

    @pytest.mark.parametrize("case_type", NEW_CASE_TYPES)
    def test_module_has_system_prompt(self, case_type):
        module = self.registry[case_type]
        assert hasattr(module, "SYSTEM_PROMPT"), (
            f"issue_extractor/{case_type} missing SYSTEM_PROMPT"
        )
        assert isinstance(module.SYSTEM_PROMPT, str)
        assert len(module.SYSTEM_PROMPT) > 50

    @pytest.mark.parametrize("case_type", NEW_CASE_TYPES)
    def test_module_has_extraction_prompt(self, case_type):
        module = self.registry[case_type]
        assert hasattr(module, "EXTRACTION_PROMPT"), (
            f"issue_extractor/{case_type} missing EXTRACTION_PROMPT"
        )
        assert "{case_id}" in module.EXTRACTION_PROMPT
        assert "{input_block}" in module.EXTRACTION_PROMPT

    @pytest.mark.parametrize("case_type", NEW_CASE_TYPES)
    def test_module_has_format_input_block(self, case_type):
        module = self.registry[case_type]
        assert callable(getattr(module, "format_input_block", None)), (
            f"issue_extractor/{case_type} missing callable format_input_block"
        )

    @pytest.mark.parametrize("case_type", NEW_CASE_TYPES)
    def test_format_input_block_runs(self, case_type):
        """format_input_block 可以用空输入正常运行，不应抛出异常。"""
        module = self.registry[case_type]
        result = module.format_input_block([], [], [])
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# evidence_indexer
# ---------------------------------------------------------------------------


class TestEvidenceIndexerRegistry:
    """evidence_indexer prompt 注册表测试。"""

    @pytest.fixture(autouse=True)
    def load_registry(self):
        from engines.case_structuring.evidence_indexer.prompts import PROMPT_REGISTRY
        self.registry = PROMPT_REGISTRY

    def test_all_new_case_types_registered(self):
        _assert_registry_has_case_types(self.registry, "evidence_indexer")

    def test_civil_loan_still_registered(self):
        assert "civil_loan" in self.registry

    @pytest.mark.parametrize("case_type", NEW_CASE_TYPES)
    def test_module_has_system_prompt(self, case_type):
        module = self.registry[case_type]
        assert hasattr(module, "SYSTEM_PROMPT")
        assert isinstance(module.SYSTEM_PROMPT, str)
        assert len(module.SYSTEM_PROMPT) > 50

    @pytest.mark.parametrize("case_type", NEW_CASE_TYPES)
    def test_module_has_extraction_prompt(self, case_type):
        module = self.registry[case_type]
        assert hasattr(module, "EXTRACTION_PROMPT")
        assert "{case_id}" in module.EXTRACTION_PROMPT
        assert "{materials}" in module.EXTRACTION_PROMPT

    @pytest.mark.parametrize("case_type", NEW_CASE_TYPES)
    def test_module_has_format_materials_block(self, case_type):
        module = self.registry[case_type]
        assert callable(getattr(module, "format_materials_block", None)), (
            f"evidence_indexer/{case_type} missing callable format_materials_block"
        )


# ---------------------------------------------------------------------------
# evidence_weight_scorer
# ---------------------------------------------------------------------------


class TestEvidenceWeightScorerRegistry:
    """evidence_weight_scorer prompt 注册表测试。"""

    @pytest.fixture(autouse=True)
    def load_registry(self):
        from engines.case_structuring.evidence_weight_scorer.prompts import PROMPT_REGISTRY
        self.registry = PROMPT_REGISTRY

    def test_all_new_case_types_registered(self):
        _assert_registry_has_case_types(self.registry, "evidence_weight_scorer")

    def test_civil_loan_still_registered(self):
        assert "civil_loan" in self.registry

    @pytest.mark.parametrize("case_type", NEW_CASE_TYPES)
    def test_entry_has_system_key(self, case_type):
        entry = self.registry[case_type]
        assert "system" in entry, (
            f"evidence_weight_scorer/{case_type} registry entry missing 'system' key"
        )
        assert isinstance(entry["system"], str)
        assert len(entry["system"]) > 50

    @pytest.mark.parametrize("case_type", NEW_CASE_TYPES)
    def test_entry_has_build_user_callable(self, case_type):
        entry = self.registry[case_type]
        assert "build_user" in entry, (
            f"evidence_weight_scorer/{case_type} registry entry missing 'build_user' key"
        )
        assert callable(entry["build_user"]), (
            f"evidence_weight_scorer/{case_type} 'build_user' is not callable"
        )


# ---------------------------------------------------------------------------
# adversarial
# ---------------------------------------------------------------------------


class TestAdversarialRegistry:
    """adversarial prompt 注册表测试。"""

    @pytest.fixture(autouse=True)
    def load_registry(self):
        from engines.adversarial.prompts import PROMPT_REGISTRY
        self.registry = PROMPT_REGISTRY

    def test_all_new_case_types_registered(self):
        _assert_registry_has_case_types(self.registry, "adversarial")

    def test_civil_loan_still_registered(self):
        assert "civil_loan" in self.registry

    @pytest.mark.parametrize("case_type", NEW_CASE_TYPES)
    def test_module_has_case_context(self, case_type):
        module = self.registry[case_type]
        assert hasattr(module, "CASE_CONTEXT"), (
            f"adversarial/{case_type} missing CASE_CONTEXT"
        )
        assert isinstance(module.CASE_CONTEXT, str)
        assert len(module.CASE_CONTEXT) > 50

    @pytest.mark.parametrize("case_type", NEW_CASE_TYPES)
    def test_module_has_evidence_review_criteria(self, case_type):
        module = self.registry[case_type]
        assert hasattr(module, "EVIDENCE_REVIEW_CRITERIA"), (
            f"adversarial/{case_type} missing EVIDENCE_REVIEW_CRITERIA"
        )
        assert isinstance(module.EVIDENCE_REVIEW_CRITERIA, str)


# ---------------------------------------------------------------------------
# PromptProfile 枚举
# ---------------------------------------------------------------------------


class TestPromptProfileEnum:
    """PromptProfile 枚举包含新案型。"""

    def test_labor_dispute_in_prompt_profile(self):
        from engines.shared.models import PromptProfile
        assert PromptProfile.labor_dispute.value == "labor_dispute"

    def test_real_estate_in_prompt_profile(self):
        from engines.shared.models import PromptProfile
        assert PromptProfile.real_estate.value == "real_estate"

    def test_civil_loan_still_in_prompt_profile(self):
        from engines.shared.models import PromptProfile
        assert PromptProfile.civil_loan.value == "civil_loan"
