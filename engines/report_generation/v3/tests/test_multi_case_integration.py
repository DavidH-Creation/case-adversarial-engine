"""Phase 3d: multi-case-type integration tests.

Validates:
  1. All 3 case types pass render contract at the 0.20 final threshold
  2. Cross-contamination checks between case types
  3. Golden artifacts exist and are render-clean
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from engines.report_generation.v3.render_contract import (
    LintSeverity,
    compute_fallback_ratio,
    lint_markdown_render_contract,
)
from engines.report_generation.v3.report_writer import write_v3_report_md

# Import fixture builders from each acceptance test module
from engines.report_generation.v3.tests.test_civil_loan_acceptance import (
    _CASE_DATA as CIVIL_LOAN_CASE_DATA,
    _make_civil_loan_report,
)
from engines.report_generation.v3.tests.test_labor_dispute_acceptance import (
    _CASE_DATA as LABOR_DISPUTE_CASE_DATA,
    _make_labor_dispute_report,
)
from engines.report_generation.v3.tests.test_real_estate_acceptance import (
    _CASE_DATA as REAL_ESTATE_CASE_DATA,
    _make_real_estate_report,
)

_GOLDEN_DIR = Path(__file__).resolve().parent.parent / "golden_artifacts"

# Case-type-specific terms that should NOT appear in other case types' reports
_CIVIL_LOAN_EXCLUSIVE_TERMS = ["借款合意", "借款本金", "还款义务"]
_LABOR_DISPUTE_EXCLUSIVE_TERMS = ["劳动仲裁", "工资报酬", "劳动合同"]
_REAL_ESTATE_EXCLUSIVE_TERMS = ["房屋买卖", "产权过户", "网签备案"]


def _generate_md(report, case_data) -> str:
    """Generate MD report content using write_v3_report_md."""
    with patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER"):
        with patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x):
            with tempfile.TemporaryDirectory() as tmpdir:
                md_path = write_v3_report_md(
                    Path(tmpdir), report, case_data, no_redact=True
                )
                return md_path.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# 1. All 3 case types pass render contract at 0.20
# ═══════════════════════════════════════════════════════════════════════════


class TestAllCaseTypesPassRenderContract:
    """Every case type must pass render contract at the 0.20 final gate."""

    @pytest.mark.parametrize(
        "name,make_report,case_data",
        [
            ("civil_loan", _make_civil_loan_report, CIVIL_LOAN_CASE_DATA),
            ("labor_dispute", _make_labor_dispute_report, LABOR_DISPUTE_CASE_DATA),
            ("real_estate", _make_real_estate_report, REAL_ESTATE_CASE_DATA),
        ],
        ids=["civil_loan", "labor_dispute", "real_estate"],
    )
    def test_render_contract_pass(self, name, make_report, case_data):
        """Case type passes full render contract (no ERRORs)."""
        content = _generate_md(make_report(), case_data)
        results = lint_markdown_render_contract(content)
        errors = [r for r in results if r.severity == LintSeverity.ERROR]
        assert errors == [], f"{name} has ERROR-level violations: {errors}"

    @pytest.mark.parametrize(
        "name,make_report,case_data",
        [
            ("civil_loan", _make_civil_loan_report, CIVIL_LOAN_CASE_DATA),
            ("labor_dispute", _make_labor_dispute_report, LABOR_DISPUTE_CASE_DATA),
            ("real_estate", _make_real_estate_report, REAL_ESTATE_CASE_DATA),
        ],
        ids=["civil_loan", "labor_dispute", "real_estate"],
    )
    def test_fallback_ratio_at_0_20(self, name, make_report, case_data):
        """Fallback ratio must be ≤ 0.20 (Phase 3d final threshold)."""
        content = _generate_md(make_report(), case_data)
        ratio, fb_count, total = compute_fallback_ratio(content)
        assert total > 0, f"{name} has no ## sections"
        assert ratio <= 0.20, (
            f"{name} fallback ratio {ratio:.0%} ({fb_count}/{total}) exceeds 0.20"
        )

    @pytest.mark.parametrize(
        "name,make_report,case_data",
        [
            ("civil_loan", _make_civil_loan_report, CIVIL_LOAN_CASE_DATA),
            ("labor_dispute", _make_labor_dispute_report, LABOR_DISPUTE_CASE_DATA),
            ("real_estate", _make_real_estate_report, REAL_ESTATE_CASE_DATA),
        ],
        ids=["civil_loan", "labor_dispute", "real_estate"],
    )
    def test_four_layer_structure(self, name, make_report, case_data):
        """Report must contain all 4 layer H1 headings."""
        content = _generate_md(make_report(), case_data)
        for layer_title in [
            "# 一、封面摘要",
            "# 二、中立对抗内核",
            "# 三、角色化输出",
            "# 四、附录",
        ]:
            assert layer_title in content, (
                f"{name} missing layer heading: {layer_title}"
            )


# ═══════════════════════════════════════════════════════════════════════════
# 2. Cross-contamination checks
# ═══════════════════════════════════════════════════════════════════════════


class TestCrossContamination:
    """Case-type-specific terms must not leak into other case types."""

    def test_civil_loan_has_no_labor_terms(self):
        content = _generate_md(_make_civil_loan_report(), CIVIL_LOAN_CASE_DATA)
        for term in _LABOR_DISPUTE_EXCLUSIVE_TERMS:
            assert term not in content, (
                f"civil_loan report contains labor_dispute term: '{term}'"
            )

    def test_civil_loan_has_no_real_estate_terms(self):
        content = _generate_md(_make_civil_loan_report(), CIVIL_LOAN_CASE_DATA)
        for term in _REAL_ESTATE_EXCLUSIVE_TERMS:
            assert term not in content, (
                f"civil_loan report contains real_estate term: '{term}'"
            )

    def test_labor_dispute_has_no_civil_loan_terms(self):
        content = _generate_md(
            _make_labor_dispute_report(), LABOR_DISPUTE_CASE_DATA
        )
        for term in _CIVIL_LOAN_EXCLUSIVE_TERMS:
            assert term not in content, (
                f"labor_dispute report contains civil_loan term: '{term}'"
            )

    def test_labor_dispute_has_no_real_estate_terms(self):
        content = _generate_md(
            _make_labor_dispute_report(), LABOR_DISPUTE_CASE_DATA
        )
        for term in _REAL_ESTATE_EXCLUSIVE_TERMS:
            assert term not in content, (
                f"labor_dispute report contains real_estate term: '{term}'"
            )

    def test_real_estate_has_no_civil_loan_terms(self):
        content = _generate_md(
            _make_real_estate_report(), REAL_ESTATE_CASE_DATA
        )
        for term in _CIVIL_LOAN_EXCLUSIVE_TERMS:
            assert term not in content, (
                f"real_estate report contains civil_loan term: '{term}'"
            )

    def test_real_estate_has_no_labor_terms(self):
        content = _generate_md(
            _make_real_estate_report(), REAL_ESTATE_CASE_DATA
        )
        for term in _LABOR_DISPUTE_EXCLUSIVE_TERMS:
            assert term not in content, (
                f"real_estate report contains labor_dispute term: '{term}'"
            )


# ═══════════════════════════════════════════════════════════════════════════
# 3. Golden artifacts exist and are render-clean
# ═══════════════════════════════════════════════════════════════════════════


class TestGoldenArtifacts:
    """Golden artifacts must exist and pass render contract."""

    @pytest.mark.parametrize(
        "case_type",
        ["civil_loan", "labor_dispute", "real_estate"],
    )
    def test_golden_artifact_exists(self, case_type):
        golden = _GOLDEN_DIR / f"{case_type}_v3_golden.md"
        assert golden.exists(), f"Golden artifact missing: {golden}"
        content = golden.read_text(encoding="utf-8")
        assert len(content) > 1000, (
            f"Golden artifact suspiciously small: {len(content)} chars"
        )

    @pytest.mark.parametrize(
        "case_type",
        ["civil_loan", "labor_dispute", "real_estate"],
    )
    def test_golden_artifact_render_clean(self, case_type):
        """Golden artifact passes render contract (no ERRORs)."""
        golden = _GOLDEN_DIR / f"{case_type}_v3_golden.md"
        content = golden.read_text(encoding="utf-8")
        results = lint_markdown_render_contract(content)
        errors = [r for r in results if r.severity == LintSeverity.ERROR]
        assert errors == [], f"{case_type} golden artifact has errors: {errors}"

    @pytest.mark.parametrize(
        "case_type",
        ["civil_loan", "labor_dispute", "real_estate"],
    )
    def test_golden_artifact_fallback_ratio(self, case_type):
        """Golden artifact fallback ratio must be ≤ 0.20."""
        golden = _GOLDEN_DIR / f"{case_type}_v3_golden.md"
        content = golden.read_text(encoding="utf-8")
        ratio, fb_count, total = compute_fallback_ratio(content)
        assert total > 0, f"{case_type} golden artifact has no ## sections"
        assert ratio <= 0.20, (
            f"{case_type} golden artifact fallback {ratio:.0%} ({fb_count}/{total})"
        )

    @pytest.mark.parametrize(
        "case_type",
        ["civil_loan", "labor_dispute", "real_estate"],
    )
    def test_golden_artifact_has_16_sections(self, case_type):
        """All golden artifacts should have 16 ## sections."""
        golden = _GOLDEN_DIR / f"{case_type}_v3_golden.md"
        content = golden.read_text(encoding="utf-8")
        h2s = re.findall(r"(?m)^##\s+(.+?)\s*$", content)
        assert len(h2s) == 16, (
            f"{case_type} golden artifact has {len(h2s)} sections, expected 16: {h2s}"
        )

    @pytest.mark.parametrize(
        "case_type",
        ["civil_loan", "labor_dispute", "real_estate"],
    )
    def test_golden_artifact_no_duplicate_headings(self, case_type):
        golden = _GOLDEN_DIR / f"{case_type}_v3_golden.md"
        content = golden.read_text(encoding="utf-8")
        h2s = re.findall(r"(?m)^##\s+(.+?)\s*$", content)
        assert len(h2s) == len(set(h2s)), (
            f"{case_type} duplicate headings: "
            f"{[h for h in h2s if h2s.count(h) > 1]}"
        )

    def test_golden_case_type_titles_differ(self):
        """Each golden artifact title must reflect its own case type."""
        for case_type in ["civil_loan", "labor_dispute", "real_estate"]:
            golden = _GOLDEN_DIR / f"{case_type}_v3_golden.md"
            content = golden.read_text(encoding="utf-8")
            expected_title = case_type.replace("_", " ").title()
            assert expected_title in content, (
                f"{case_type} golden artifact missing title '{expected_title}'"
            )
