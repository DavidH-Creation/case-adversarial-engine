"""Tests for the V3 user-visible render contract."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from engines.report_generation.v3.models import (
    CoverSummary,
    FourLayerReport,
    Layer1Cover,
    Layer2Core,
    Layer3Perspective,
    Layer4Appendix,
)
from engines.report_generation.v3.report_writer import write_v3_report_md
from engines.report_generation.v3.render_contract import lint_markdown_render_contract


def _minimal_report(**cover_kwargs) -> FourLayerReport:
    return FourLayerReport(
        report_id="rpt-test",
        case_id="case-test",
        run_id="run-test",
        layer1=Layer1Cover(cover_summary=CoverSummary(**cover_kwargs)),
        layer2=Layer2Core(),
        layer3=Layer3Perspective(),
        layer4=Layer4Appendix(),
    )


def test_lint_rejects_internal_tokens() -> None:
    with pytest.raises(ValueError, match="issue-|xexam-|undefined"):
        lint_markdown_render_contract(
            "## Summary\n\nissue-case-001\n\nxexam-evidence-001-issue-001\n\nundefined"
        )


def test_lint_rejects_empty_major_sections() -> None:
    with pytest.raises(ValueError, match="empty major section"):
        lint_markdown_render_contract("## Action Recommendations\n\n## Next Section\n\ncontent")


def test_lint_rejects_placeholder_only_table_rows() -> None:
    with pytest.raises(ValueError, match="placeholder-only table row"):
        lint_markdown_render_contract("## Ranking\n\n| Issue | Impact |\n|---|---|\n| - | - |\n")


@patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
@patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
def test_write_v3_report_md_rejects_polluted_render(_mock_redact) -> None:
    report = _minimal_report(
        neutral_conclusion="undefined",
        winning_move="xexam-evidence-001-issue-case-001",
    )
    case_data = {"case_type": "civil_loan", "parties": {}}

    with TemporaryDirectory() as tmpdir:
        with pytest.raises(ValueError, match="render contract"):
            write_v3_report_md(Path(tmpdir), report, case_data, no_redact=True)


def test_checked_in_v3_sample_report_is_render_clean() -> None:
    sample = Path(__file__).resolve().parents[4] / "outputs" / "v3" / "report.md"
    lint_markdown_render_contract(sample.read_text(encoding="utf-8"))
