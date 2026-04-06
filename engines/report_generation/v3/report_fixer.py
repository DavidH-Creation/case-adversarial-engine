"""Auto-fixer for common render-contract violations.

Applied before lint in the report pipeline.  Performs only format corrections —
no semantic changes to the content.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Character maps
# ---------------------------------------------------------------------------

_CJK_RANGE = "\u4e00-\u9fff\u3400-\u4dbf"

# ASCII punctuation → full-width equivalents used in Chinese text
_ASCII_TO_FULLWIDTH: dict[str, str] = {
    ",": "\uff0c",  # ，
    ".": "\u3002",  # 。
    ":": "\uff1a",  # ：
    ";": "\uff1b",  # ；
    "!": "\uff01",  # ！
    "?": "\uff1f",  # ？
}

# Pattern: CJK char followed by ASCII punctuation
_CJK_THEN_ASCII = re.compile(rf"([{_CJK_RANGE}])([,.:;!?])")
# Pattern: ASCII punctuation followed by CJK char
_ASCII_THEN_CJK = re.compile(rf"([,.:;!?])([{_CJK_RANGE}])")

# Only h2 headings — matches the lint rule's scope
_H2_RE = re.compile(r"(?m)^(##)\s+(.+?)\s*$")


class ReportFixer:
    """Apply format-level fixes to Markdown before running lint.

    Does not alter semantics — only corrects structural and typographic issues
    that the render contract lint rules would flag.
    """

    # ------------------------------------------------------------------
    # Individual fix methods
    # ------------------------------------------------------------------

    def fix_cjk_punctuation(self, md: str) -> str:
        """Replace ASCII punctuation immediately adjacent to CJK chars with full-width equivalents.

        Handles both ``CJK + ASCII`` and ``ASCII + CJK`` adjacency.
        Two passes are needed because a single replacement may expose new adjacency.
        """

        def _after_cjk(m: re.Match) -> str:
            return m.group(1) + _ASCII_TO_FULLWIDTH[m.group(2)]

        def _before_cjk(m: re.Match) -> str:
            return _ASCII_TO_FULLWIDTH[m.group(1)] + m.group(2)

        # Pass 1: CJK followed by ASCII punct
        md = _CJK_THEN_ASCII.sub(_after_cjk, md)
        # Pass 2: ASCII punct followed by CJK (handles leading-punct cases)
        md = _ASCII_THEN_CJK.sub(_before_cjk, md)
        return md

    def fix_duplicate_headings(self, md: str) -> str:
        """Append a numeric suffix to duplicate ``##`` headings.

        The first occurrence keeps its original title.  Subsequent duplicates
        become ``## Title (2)``, ``## Title (3)``, etc.
        Only ``##`` (h2) headings are processed — matching the lint rule scope.
        """
        seen: dict[str, int] = {}

        def _renumber(m: re.Match) -> str:
            level = m.group(1)  # "##"
            title = m.group(2)
            key = title
            if key in seen:
                seen[key] += 1
                return f"{level} {title} ({seen[key]})"
            seen[key] = 1
            return m.group(0)  # first occurrence unchanged

        return _H2_RE.sub(_renumber, md)

    def fix_table_column_mismatch(self, md: str) -> str:
        """Normalise table data rows so they match the header column count.

        Short rows are padded with empty cells; long rows are truncated.
        Separator lines (``|---|---|``) are left untouched.
        """
        ends_with_newline = md.endswith("\n")
        lines = md.splitlines()
        result: list[str] = []
        in_table = False
        header_cols = 0

        for line in lines:
            stripped = line.strip()
            if not stripped.startswith("|"):
                in_table = False
                result.append(line)
                continue

            # Separator line detection (e.g. |---|:--|---:|)
            inner = stripped.replace("|", "")
            if inner.strip() and all(c in " :-" for c in inner):
                result.append(line)
                continue

            cells = [c.strip() for c in stripped.strip("|").split("|")]

            if not in_table:
                header_cols = len(cells)
                in_table = True
                result.append(line)
            elif len(cells) != header_cols:
                if len(cells) < header_cols:
                    cells.extend([""] * (header_cols - len(cells)))
                else:
                    cells = cells[:header_cols]
                result.append("| " + " | ".join(cells) + " |")
            else:
                result.append(line)

        joined = "\n".join(result)
        if ends_with_newline:
            joined += "\n"
        return joined

    # ------------------------------------------------------------------
    # Composite entry point
    # ------------------------------------------------------------------

    def apply_all(self, md: str) -> tuple[str, list[str]]:
        """Apply all fixes in sequence.

        Returns ``(fixed_md, fix_log)`` where ``fix_log`` is a list of
        human-readable strings describing each fix that was applied.
        An empty list means no changes were made.
        """
        fix_log: list[str] = []

        fixed = self.fix_cjk_punctuation(md)
        if fixed != md:
            fix_log.append("cjk_punctuation: replaced ASCII punctuation adjacent to CJK characters")
        md = fixed

        fixed = self.fix_duplicate_headings(md)
        if fixed != md:
            fix_log.append("duplicate_headings: renamed duplicate ## headings with numeric suffixes")
        md = fixed

        fixed = self.fix_table_column_mismatch(md)
        if fixed != md:
            fix_log.append("table_column_mismatch: adjusted table row column counts to match header")
        md = fixed

        return md, fix_log
