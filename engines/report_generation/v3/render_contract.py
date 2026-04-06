"""User-visible render contract checks for V3 reports.

Three format-clean rules (ERROR):
  - forbidden_tokens: internal IDs leaking into user-visible text
  - empty_major_section: ## heading with no body at all
  - placeholder_row: table row where every cell is a placeholder

Seven user-clean rules:
  - raw_json_leak: naked JSON (``{"`` / ``[{"``) in markdown  (ERROR)
  - orphan_citation: ``[src-xxx]`` not in evidence index       (ERROR)
  - excessive_fallback: fallback sections > 20 % of total      (WARN)
  - section_length_floor: core section body < 50 chars          (WARN)
  - duplicate_heading: same ``##`` title appears twice          (ERROR)
  - table_header_mismatch: data-row column count != header      (ERROR)
  - cjk_punctuation_mix: CJK text adjacent to ASCII punctuation (WARN)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class RenderContractViolation(ValueError):
    """Raised when user-visible report content violates the render contract."""


class LintSeverity(str, Enum):
    """Lint rule severity level."""

    ERROR = "error"
    WARN = "warn"


@dataclass
class LintResult:
    """Single lint rule result."""

    rule: str
    message: str
    severity: LintSeverity


# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

_FORBIDDEN_TOKEN_PATTERNS = [
    (re.compile(r"\bissue-[a-z0-9-]+\b", re.IGNORECASE), "issue-"),
    (re.compile(r"\bxexam-[a-z0-9-]+\b", re.IGNORECASE), "xexam-"),
    (re.compile(r"\bundefined\b", re.IGNORECASE), "undefined"),
    (re.compile(r"\bPATH-[A-Z0-9-]+\b"), "PATH-"),
    (re.compile(r"\bpath-[a-z0-9-]+\b", re.IGNORECASE), "path-"),
]

_PLACEHOLDER_CELLS = {"", "-", "\u2014", "\u2013"}

_HEADING_RE = re.compile(r"(?m)^##\s+(.+?)\s*$")
_RAW_JSON_RE = re.compile(r'\{"|\[\{"')
_CITATION_RE = re.compile(r"\[src-([^\]]+)\]")
_FALLBACK_BODY_RE = re.compile(
    r"\*(\u6682\u65e0.+[\u3002.]|No .+ available\.)\*"  # *暂无...。* | *No ... available.*
    r"|"
    r"\uff08\u65e0.+\uff09",  # （无...）
)
_CJK_RANGE = "\u4e00-\u9fff\u3400-\u4dbf"
_CJK_ASCII_PUNCT_RE = re.compile(
    rf"[{_CJK_RANGE}][,.:;!?]|[,.:;!?][{_CJK_RANGE}]"
)
_SECTION_LENGTH_FLOOR = 50
_MARKDOWN_SYNTAX_RE = re.compile(r"[#*_`>|~\-]")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def lint_markdown_render_contract(
    text: str,
    *,
    evidence_ids: set[str] | None = None,
) -> list[LintResult]:
    """Check user-visible Markdown against the render contract.

    Raises :class:`RenderContractViolation` when any ERROR-level rule fires.
    Returns the full list of results (ERRORs + WARNs).
    """
    results: list[LintResult] = []

    # Format-clean rules (ERROR)
    results.extend(_find_forbidden_tokens(text))
    results.extend(_find_empty_major_sections(text))
    results.extend(_find_placeholder_rows(text))

    # User-clean rules
    results.extend(_find_raw_json_leak(text))
    results.extend(_find_orphan_citations(text, evidence_ids))
    results.extend(_find_excessive_fallback(text))
    results.extend(_find_section_length_floor(text))
    results.extend(_find_duplicate_headings(text))
    results.extend(_find_table_header_mismatch(text))
    results.extend(_find_cjk_punctuation_mix(text))

    errors = [r for r in results if r.severity == LintSeverity.ERROR]
    if errors:
        msgs = "; ".join(r.message for r in errors)
        raise RenderContractViolation("render contract violation: " + msgs)

    return results


def compute_fallback_ratio(text: str) -> tuple[float, int, int]:
    """Compute the ratio of fallback sections to total ``##`` sections.

    Returns ``(ratio, fallback_count, total_sections)``.
    """
    sections = _extract_sections(text)
    if not sections:
        return 0.0, 0, 0
    fallback_count = sum(1 for _, body in sections if _is_fallback_body(body))
    return fallback_count / len(sections), fallback_count, len(sections)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_sections(text: str) -> list[tuple[str, str]]:
    """Extract ``(title, body)`` pairs for all ``##`` headings."""
    headings = list(_HEADING_RE.finditer(text))
    sections: list[tuple[str, str]] = []
    for i, m in enumerate(headings):
        title = m.group(1).strip()
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[start:end].strip()
        sections.append((title, body))
    return sections


def _is_fallback_body(body: str) -> bool:
    """Return True if section body is a fallback placeholder."""
    return bool(_FALLBACK_BODY_RE.fullmatch(body.strip()))


# ---------------------------------------------------------------------------
# Format-clean rules (ERROR)
# ---------------------------------------------------------------------------


def _find_forbidden_tokens(text: str) -> list[LintResult]:
    labels: list[str] = []
    for pattern, label in _FORBIDDEN_TOKEN_PATTERNS:
        if pattern.search(text):
            labels.append(label)
    if labels:
        joined = "|".join(labels)
        return [
            LintResult(
                rule="forbidden_tokens",
                message=f"forbidden tokens present ({joined})",
                severity=LintSeverity.ERROR,
            )
        ]
    return []


def _find_empty_major_sections(text: str) -> list[LintResult]:
    results: list[LintResult] = []
    for title, body in _extract_sections(text):
        if not body:
            results.append(
                LintResult(
                    rule="empty_major_section",
                    message=f"empty major section: {title}",
                    severity=LintSeverity.ERROR,
                )
            )
    return results


def _find_placeholder_rows(text: str) -> list[LintResult]:
    results: list[LintResult] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if re.fullmatch(r"\|[\s:\-]+\|", stripped):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells and all(cell in _PLACEHOLDER_CELLS for cell in cells):
            results.append(
                LintResult(
                    rule="placeholder_row",
                    message=f"placeholder-only table row: {stripped}",
                    severity=LintSeverity.ERROR,
                )
            )
    return results


# ---------------------------------------------------------------------------
# User-clean rules
# ---------------------------------------------------------------------------


def _find_raw_json_leak(text: str) -> list[LintResult]:
    if _RAW_JSON_RE.search(text):
        return [
            LintResult(
                rule="raw_json_leak",
                message="raw JSON detected in markdown output",
                severity=LintSeverity.ERROR,
            )
        ]
    return []


def _find_orphan_citations(
    text: str,
    evidence_ids: set[str] | None,
) -> list[LintResult]:
    if evidence_ids is None:
        return []
    results: list[LintResult] = []
    seen: set[str] = set()
    for m in _CITATION_RE.finditer(text):
        ref = m.group(1)
        full_ref = f"src-{ref}"
        if full_ref in seen:
            continue
        seen.add(full_ref)
        if full_ref not in evidence_ids and ref not in evidence_ids:
            results.append(
                LintResult(
                    rule="orphan_citation",
                    message=f"orphan citation [src-{ref}] not found in evidence index",
                    severity=LintSeverity.ERROR,
                )
            )
    return results


def _find_excessive_fallback(text: str) -> list[LintResult]:
    ratio, count, total = compute_fallback_ratio(text)
    if total == 0 or ratio <= 0.20:
        return []
    return [
        LintResult(
            rule="excessive_fallback",
            message=f"fallback ratio {ratio:.0%} ({count}/{total} sections)",
            severity=LintSeverity.WARN,
        )
    ]


def _find_section_length_floor(text: str) -> list[LintResult]:
    results: list[LintResult] = []
    for title, body in _extract_sections(text):
        if not body or _is_fallback_body(body):
            continue  # covered by other rules
        clean = _MARKDOWN_SYNTAX_RE.sub("", body).strip()
        if 0 < len(clean) < _SECTION_LENGTH_FLOOR:
            results.append(
                LintResult(
                    rule="section_length_floor",
                    message=(
                        f"section '{title}' has only {len(clean)} chars"
                        f" (min {_SECTION_LENGTH_FLOOR})"
                    ),
                    severity=LintSeverity.WARN,
                )
            )
    return results


def _find_duplicate_headings(text: str) -> list[LintResult]:
    results: list[LintResult] = []
    seen: set[str] = set()
    for title, _ in _extract_sections(text):
        if title in seen:
            results.append(
                LintResult(
                    rule="duplicate_heading",
                    message=f"duplicate ## heading: {title}",
                    severity=LintSeverity.ERROR,
                )
            )
        seen.add(title)
    return results


def _find_table_header_mismatch(text: str) -> list[LintResult]:
    results: list[LintResult] = []
    in_table = False
    header_cols = 0

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            in_table = False
            continue

        # Separator detection (handles multi-column tables)
        inner = stripped.replace("|", "")
        if inner.strip() and all(c in " :-" for c in inner):
            continue

        cols = len([c.strip() for c in stripped.strip("|").split("|")])
        if not in_table:
            header_cols = cols
            in_table = True
        elif cols != header_cols:
            results.append(
                LintResult(
                    rule="table_header_mismatch",
                    message=(
                        f"table row has {cols} columns but header has"
                        f" {header_cols}: {stripped}"
                    ),
                    severity=LintSeverity.ERROR,
                )
            )
    return results


def _find_cjk_punctuation_mix(text: str) -> list[LintResult]:
    violations: list[str] = []
    for i, line in enumerate(text.splitlines(), 1):
        if _CJK_ASCII_PUNCT_RE.search(line):
            violations.append(f"line {i}")
    if violations:
        preview = ", ".join(violations[:5])
        if len(violations) > 5:
            preview += f" (+{len(violations) - 5} more)"
        return [
            LintResult(
                rule="cjk_punctuation_mix",
                message=f"CJK/ASCII punctuation mix on {preview}",
                severity=LintSeverity.WARN,
            )
        ]
    return []
