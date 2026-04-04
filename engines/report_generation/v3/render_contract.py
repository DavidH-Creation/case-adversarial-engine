"""User-visible render contract checks for V3 reports."""

from __future__ import annotations

import re


class RenderContractViolation(ValueError):
    """Raised when user-visible report content violates the render contract."""


_FORBIDDEN_TOKEN_PATTERNS = [
    (re.compile(r"\bissue-[a-z0-9-]+\b", re.IGNORECASE), "issue-"),
    (re.compile(r"\bxexam-[a-z0-9-]+\b", re.IGNORECASE), "xexam-"),
    (re.compile(r"\bundefined\b", re.IGNORECASE), "undefined"),
    (re.compile(r"\bPATH-[A-Z0-9-]+\b"), "PATH-"),
    (re.compile(r"\bpath-[a-z0-9-]+\b", re.IGNORECASE), "path-"),
]

_PLACEHOLDER_CELLS = {"", "-", "—", "–"}


def lint_markdown_render_contract(text: str) -> None:
    """Raise when user-visible Markdown leaks internal tokens or unfinished sections."""
    violations: list[str] = []
    violations.extend(_find_forbidden_tokens(text))
    violations.extend(_find_empty_major_sections(text))
    violations.extend(_find_placeholder_rows(text))

    if violations:
        raise RenderContractViolation("render contract violation: " + "; ".join(violations))


def _find_forbidden_tokens(text: str) -> list[str]:
    labels: list[str] = []
    for pattern, label in _FORBIDDEN_TOKEN_PATTERNS:
        if pattern.search(text):
            labels.append(label)
    if labels:
        joined = "|".join(labels)
        return [f"forbidden tokens present ({joined})"]
    return []


def _find_empty_major_sections(text: str) -> list[str]:
    violations: list[str] = []
    headings = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", text))
    for index, match in enumerate(headings):
        section_title = match.group(1).strip()
        start = match.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = text[start:end].strip()
        if not body:
            violations.append(f"empty major section: {section_title}")
    return violations


def _find_placeholder_rows(text: str) -> list[str]:
    violations: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if re.fullmatch(r"\|[\s:\-]+\|", stripped):
            continue

        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells and all(cell in _PLACEHOLDER_CELLS for cell in cells):
            violations.append(f"placeholder-only table row: {line.strip()}")
    return violations
