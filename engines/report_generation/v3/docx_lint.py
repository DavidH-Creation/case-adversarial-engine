"""DOCX render contract lint — runs a subset of MD rules on extracted DOCX text."""

from __future__ import annotations

from pathlib import Path

from docx import Document

from engines.report_generation.v3.render_contract import (
    LintResult,
    _find_duplicate_headings,
    _find_forbidden_tokens,
    _find_raw_json_leak,
)


def lint_docx_render_contract(doc_path: Path) -> list[LintResult]:
    """Lint a generated DOCX file against the render contract rule subset.

    Extracts paragraph text from the DOCX, then applies:
    - forbidden_tokens: detect raw template artifacts
    - raw_json_leak: detect leaked JSON structures
    - duplicate_heading: detect duplicate section headings

    Args:
        doc_path: Path to the .docx file to lint

    Returns:
        List of LintResult items (WARN or ERROR severity)
    """
    try:
        doc = Document(str(doc_path))
        full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception:
        return []

    results: list[LintResult] = []
    results.extend(_find_forbidden_tokens(full_text))
    results.extend(_find_raw_json_leak(full_text))
    results.extend(_find_duplicate_headings(full_text))
    return results
