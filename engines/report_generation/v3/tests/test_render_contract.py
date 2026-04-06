"""Tests for the V3 user-visible render contract."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock

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
from engines.report_generation.v3.render_contract import (
    LintSeverity,
    compute_fallback_ratio,
    lint_markdown_render_contract,
)


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


# ---------------------------------------------------------------------------
# User-clean rule tests: raw_json_leak (ERROR)
# ---------------------------------------------------------------------------


def test_lint_detects_raw_json_object_leak() -> None:
    with pytest.raises(ValueError, match="raw JSON"):
        lint_markdown_render_contract('## Data\n\n{"key": "value"}')


def test_lint_detects_raw_json_array_leak() -> None:
    with pytest.raises(ValueError, match="raw JSON"):
        lint_markdown_render_contract('## Data\n\n[{"key": "value"}]')


# ---------------------------------------------------------------------------
# User-clean rule tests: orphan_citation (ERROR)
# ---------------------------------------------------------------------------


def test_lint_detects_orphan_citation() -> None:
    with pytest.raises(ValueError, match="orphan"):
        lint_markdown_render_contract(
            "## Evidence\n\nSee [src-missing-001] for details.",
            evidence_ids={"src-real-001"},
        )


def test_lint_skips_orphan_check_without_evidence_ids() -> None:
    # No error when evidence_ids is not provided
    lint_markdown_render_contract("## Evidence\n\nSee [src-abc] for details.")


def test_lint_allows_valid_citation() -> None:
    lint_markdown_render_contract(
        "## Evidence\n\nSee [src-real-001] for details with enough text to pass section floor.",
        evidence_ids={"real-001"},
    )


# ---------------------------------------------------------------------------
# User-clean rule tests: excessive_fallback (WARN)
# ---------------------------------------------------------------------------


def test_lint_warns_excessive_fallback() -> None:
    text = "\n".join([
        "## Section A",
        "",
        "*\u6682\u65e0\u6570\u636e\u3002*",
        "## Section B",
        "",
        "*\u6682\u65e0\u66f4\u591a\u6570\u636e\u3002*",
        "## Section C",
        "",
        "Real content with enough characters to pass the fifty character floor check easily.",
    ])
    results = lint_markdown_render_contract(text)
    assert any(r.rule == "excessive_fallback" for r in results)
    fb = next(r for r in results if r.rule == "excessive_fallback")
    assert fb.severity == LintSeverity.WARN


def test_lint_no_fallback_warning_when_below_threshold() -> None:
    text = "\n".join([
        "## A",
        "",
        "Content A with enough characters to pass the fifty character floor check.",
        "## B",
        "",
        "Content B with enough characters to pass the fifty character floor check.",
        "## C",
        "",
        "Content C with enough characters to pass the fifty character floor check.",
        "## D",
        "",
        "Content D with enough characters to pass the fifty character floor check.",
        "## E",
        "",
        "*\u6682\u65e0\u6570\u636e\u3002*",
    ])
    results = lint_markdown_render_contract(text)
    assert all(r.rule != "excessive_fallback" for r in results)


# ---------------------------------------------------------------------------
# User-clean rule tests: section_length_floor (WARN)
# ---------------------------------------------------------------------------


def test_lint_warns_short_section() -> None:
    text = "\n".join([
        "## Short",
        "",
        "Tiny.",
        "## Long Enough",
        "",
        "This section has plenty of content to pass the fifty character floor check easily.",
    ])
    results = lint_markdown_render_contract(text)
    assert any(r.rule == "section_length_floor" for r in results)
    sf = next(r for r in results if r.rule == "section_length_floor")
    assert sf.severity == LintSeverity.WARN
    assert "Short" in sf.message


# ---------------------------------------------------------------------------
# User-clean rule tests: duplicate_heading (ERROR)
# ---------------------------------------------------------------------------


def test_lint_detects_duplicate_heading() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        lint_markdown_render_contract(
            "## Same Title\n\nContent one with enough text.\n\n"
            "## Same Title\n\nContent two with enough text."
        )


# ---------------------------------------------------------------------------
# User-clean rule tests: table_header_mismatch (ERROR)
# ---------------------------------------------------------------------------


def test_lint_detects_table_header_mismatch() -> None:
    table = "## Data\n\n| A | B | C |\n|---|---|---|\n| 1 | 2 |\n"
    with pytest.raises(ValueError, match="table row"):
        lint_markdown_render_contract(table)


def test_lint_allows_well_formed_table() -> None:
    table = "\n".join([
        "## Data",
        "",
        "| A | B | C |",
        "|---|---|---|",
        "| 1 | 2 | 3 |",
        "| 4 | 5 | 6 |",
        "",
        "This table section has enough content to pass all checks easily.",
    ])
    lint_markdown_render_contract(table)


# ---------------------------------------------------------------------------
# User-clean rule tests: cjk_punctuation_mix (WARN)
# ---------------------------------------------------------------------------


def test_lint_warns_cjk_punctuation_mix() -> None:
    text = (
        "## Title\n\n"
        "\u8fd9\u662f\u6d4b\u8bd5,\u68c0\u67e5\u6807\u70b9\u6df7\u7528"
        "\u8fd9\u4e2a\u89c4\u5219\u662f\u5426\u6b63\u5e38\u5de5\u4f5c\u3002"
        "\u9700\u8981\u8db3\u591f\u957f\u7684\u5185\u5bb9\u6765\u907f\u514d"
        "\u89e6\u53d1\u5176\u4ed6\u8b66\u544a\u3002"
    )
    results = lint_markdown_render_contract(text)
    assert any(r.rule == "cjk_punctuation_mix" for r in results)
    cm = next(r for r in results if r.rule == "cjk_punctuation_mix")
    assert cm.severity == LintSeverity.WARN


def test_lint_no_cjk_warning_for_clean_text() -> None:
    text = (
        "## Title\n\n"
        "\u8fd9\u662f\u6d4b\u8bd5\uff0c\u68c0\u67e5\u6807\u70b9\u662f\u5426"
        "\u6b63\u786e\u4f7f\u7528\u4e86\u4e2d\u6587\u6807\u70b9\u3002"
        "\u9700\u8981\u8db3\u591f\u957f\u7684\u5185\u5bb9\u6765\u907f\u514d"
        "\u89e6\u53d1\u5176\u4ed6\u8b66\u544a\u3002"
    )
    results = lint_markdown_render_contract(text)
    assert all(r.rule != "cjk_punctuation_mix" for r in results)


# ---------------------------------------------------------------------------
# compute_fallback_ratio
# ---------------------------------------------------------------------------


def test_compute_fallback_ratio() -> None:
    text = "\n".join([
        "## A",
        "",
        "*\u6682\u65e0\u6570\u636e\u3002*",
        "## B",
        "",
        "Real content here.",
        "## C",
        "",
        "*\u6682\u65e0\u5176\u4ed6\u6570\u636e\u3002*",
    ])
    ratio, count, total = compute_fallback_ratio(text)
    assert total == 3
    assert count == 2
    assert abs(ratio - 2 / 3) < 0.01


def test_compute_fallback_ratio_parenthesized() -> None:
    text = "## A\n\n\uff08\u65e0\u6570\u636e\uff09\n\n## B\n\nReal content."
    ratio, count, total = compute_fallback_ratio(text)
    assert count == 1
    assert total == 2


# ---------------------------------------------------------------------------
# report_writer fallback_ratio hard gate
# ---------------------------------------------------------------------------


@patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
@patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
def test_write_v3_report_md_rejects_high_fallback_ratio(_mock_redact) -> None:
    report = _minimal_report(
        neutral_conclusion=(
            "\u5408\u540c\u501f\u6b3e\u5173\u7cfb\u6210\u7acb"
            "\u4e14\u8bc1\u636e\u94fe\u5b8c\u6574\uff0c"
            "\u6cd5\u9662\u5e94\u652f\u6301\u539f\u544a\u7684"
            "\u8bc9\u8bbc\u8bf7\u6c42\u3002"
        ),
        winning_move=(
            "\u5f55\u97f3\u8bc1\u636e\u662f\u5426\u88ab\u6cd5\u9662"
            "\u91c7\u4fe1\u5c06\u51b3\u5b9a\u6848\u4ef6\u8d70\u5411\u3002"
        ),
    )
    case_data = {"case_type": "civil_loan", "parties": {}}

    with TemporaryDirectory() as tmpdir:
        with pytest.raises(ValueError, match="fallback_ratio"):
            write_v3_report_md(Path(tmpdir), report, case_data, no_redact=True)


# ---------------------------------------------------------------------------
# Fallback ratio threshold boundary tests (Phase 1 transitional gate: 0.25)
# ---------------------------------------------------------------------------


@patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
@patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
@patch(
    "engines.report_generation.v3.report_writer.compute_fallback_ratio",
    return_value=(0.26, 2, 8),
)
def test_fallback_gate_blocks_ratio_above_0_25(_mock_ratio, _mock_redact) -> None:
    """Hard gate at 0.25 (Phase 1 transitional threshold) blocks 0.26."""
    report = _minimal_report(
        neutral_conclusion=(
            "\u5408\u540c\u501f\u6b3e\u5173\u7cfb\u6210\u7acb\u4e14\u8bc1\u636e\u94fe"
            "\u5b8c\u6574\uff0c\u6cd5\u9662\u5e94\u652f\u6301\u539f\u544a\u7684\u8bc9"
            "\u8bbc\u8bf7\u6c42\u3002"
        ),
        winning_move=(
            "\u8f6c\u8d26\u8bb0\u5f55\u548c\u501f\u6761\u662f\u5426\u88ab\u6cd5\u9662"
            "\u91c7\u4fe1\u5c06\u51b3\u5b9a\u6848\u4ef6\u8d70\u5411\u3002"
        ),
    )
    case_data = {"case_type": "civil_loan", "parties": {}}
    with TemporaryDirectory() as tmpdir:
        with pytest.raises(ValueError, match="fallback_ratio"):
            write_v3_report_md(Path(tmpdir), report, case_data, no_redact=True)


@patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
@patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
@patch(
    "engines.report_generation.v3.report_writer.compute_fallback_ratio",
    return_value=(0.24, 2, 8),
)
def test_fallback_gate_passes_ratio_below_0_25(_mock_ratio, _mock_redact) -> None:
    """Pipeline succeeds when fallback ratio is at or below transitional gate (0.25)."""
    report = _minimal_report(
        neutral_conclusion=(
            "\u5408\u540c\u501f\u6b3e\u5173\u7cfb\u6210\u7acb\u4e14\u8bc1\u636e\u94fe"
            "\u5b8c\u6574\uff0c\u6cd5\u9662\u5e94\u652f\u6301\u539f\u544a\u7684\u8bc9"
            "\u8bbc\u8bf7\u6c42\u3002"
        ),
        winning_move=(
            "\u8f6c\u8d26\u8bb0\u5f55\u548c\u501f\u6761\u662f\u5426\u88ab\u6cd5\u9662"
            "\u91c7\u4fe1\u5c06\u51b3\u5b9a\u6848\u4ef6\u8d70\u5411\u3002"
        ),
    )
    case_data = {"case_type": "civil_loan", "parties": {}}
    with TemporaryDirectory() as tmpdir:
        # Should not raise — ratio 0.24 ≤ 0.25
        result = write_v3_report_md(Path(tmpdir), report, case_data, no_redact=True)
        assert result.exists()
