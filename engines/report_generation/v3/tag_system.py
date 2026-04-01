"""
标注系统 / Tag system for V3 reports.

全文强制标注：「事实」「推断」「假设」「观点」「建议」
Every section/paragraph must carry one of these tags.
"""

from __future__ import annotations

from engines.report_generation.v3.models import SectionTag

# Tag display format: 「tag_value」
TAG_FORMAT = "「{tag}」"

# Mapping from StatementClass (existing enum) to SectionTag (v3 enum)
_STATEMENT_CLASS_TO_TAG = {
    "fact": SectionTag.fact,
    "inference": SectionTag.inference,
    "assumption": SectionTag.assumption,
    "opinion": SectionTag.opinion,
    "recommendation": SectionTag.recommendation,
}


def format_tag(tag: SectionTag) -> str:
    """Format a SectionTag for display: 「事实」."""
    return TAG_FORMAT.format(tag=tag.value)


def tag_line(text: str, tag: SectionTag) -> str:
    """Append a tag to a line of text."""
    return f"{text} {format_tag(tag)}"


def tag_section_header(title: str, tag: SectionTag) -> str:
    """Format a section header with tag: ## Title 「事实」."""
    return f"{title} {format_tag(tag)}"


def statement_class_to_tag(statement_class: str) -> SectionTag:
    """Convert an existing StatementClass string to a SectionTag.

    Falls back to SectionTag.inference for unknown values.
    """
    return _STATEMENT_CLASS_TO_TAG.get(
        statement_class.strip().lower(), SectionTag.inference
    )
