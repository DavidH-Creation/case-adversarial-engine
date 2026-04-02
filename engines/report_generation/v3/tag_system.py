"""
标注系统 / Tag system for V3 reports.

全文强制标注：「事实」「推断」「假设」「观点」「建议」
Every section/paragraph must carry one of these tags.

Also provides ID humanization utilities (humanize_id, humanize_text)
for converting internal IDs (issue-xxx-001, evidence-plaintiff-003, etc.)
to human-readable Chinese labels in report output.
"""

from __future__ import annotations

import re

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


# ---------------------------------------------------------------------------
# ID humanization
# ---------------------------------------------------------------------------

# ID patterns for humanization
# Issue IDs: issue-{slug}-{number} where slug may contain hyphens
_ISSUE_ID_RE = re.compile(r"issue-[a-z0-9]+(?:-[a-z0-9]+)*-(\d{3})")
_EVIDENCE_ID_RE = re.compile(r"evidence-(plaintiff|defendant)-(\d{3})")
# Fact IDs: FACT-NNN or fact-{slug}-NNN
_FACT_ID_RE = re.compile(r"FACT-(\d{3})")
_FACT_SLUG_RE = re.compile(r"fact-[a-z0-9]+(?:-[a-z0-9]+)*-(\d{3})")
_COND_ID_RE = re.compile(r"COND-(\d{3})")
# Attack node IDs: atk-NNN
_ATK_ID_RE = re.compile(r"atk-(\d{3})")
# Path IDs: path-A (letter) or path-NNN (number)
_PATH_LETTER_RE = re.compile(r"path-([A-E])")
_PATH_NUM_RE = re.compile(r"path-(\d{3})")
# Blocking condition IDs: bc-NNN or BC-NNN
_BC_ID_RE = re.compile(r"[Bb][Cc]-(\d{3})")
# Missing issue IDs: missing-issue-{slug}-NNN[-party-{role}-{name}]
_MISSING_ISSUE_RE = re.compile(r"missing-issue-[a-z0-9]+(?:-[a-z0-9]+)*-(\d{3})(?:-party-(?:plaintiff|defendant)-[a-z]+)?")
# Party IDs: party-{role}-{name}
_PARTY_ID_RE = re.compile(r"party-(plaintiff|defendant)-[a-z]+")

# Party label mapping
_PARTY_LABELS = {
    "plaintiff": "原告",
    "defendant": "被告",
}

# Internal field values that should be humanized
_FIELD_VALUE_MAP = {
    "supplement_evidence": "建议补强证据",
    "reassess": "建议重新评估",
    "proponent_strength=weak": "举证方举证较为薄弱",
    "proponent_strength=strong": "举证方举证较为充分",
    "proponent_strength=moderate": "举证方举证强度一般",
    "explain_in_trial": "建议庭审中解释说明",
    "cross_examine": "建议质证攻击",
    "principal": "本金",
    "interest": "利息",
    "litigation_cost": "诉讼费用",
}


def humanize_id(raw_id: str, context: dict[str, str] | None = None) -> str:
    """Convert internal IDs to human-readable form.

    Args:
        raw_id: The raw internal ID string
        context: Optional dict mapping raw IDs to human-readable titles.
                 Example: {"issue-xxx-001": "借贷关系是否成立",
                          "evidence-plaintiff-003": "银行转账电子回单"}

    Returns:
        Human-readable string. If ID is not recognized, returns raw_id unchanged.
    """
    # Try context lookup first (most accurate)
    if context and raw_id in context:
        return context[raw_id]

    # Issue ID pattern: issue-{slug}-{number}
    m = _ISSUE_ID_RE.match(raw_id)
    if m:
        num = int(m.group(1))
        title = context.get(raw_id, "") if context else ""
        if title:
            return f"争点{_chinese_numeral(num)}：{title}"
        return f"争点{_chinese_numeral(num)}"

    # Evidence ID pattern: evidence-{party}-{number}
    m = _EVIDENCE_ID_RE.match(raw_id)
    if m:
        party = _PARTY_LABELS.get(m.group(1), m.group(1))
        num = int(m.group(2))
        title = context.get(raw_id, "") if context else ""
        if title:
            return f"{party}证据{num}（{title}）"
        return f"{party}证据{num}"

    # Fact ID pattern: FACT-{number}
    m = _FACT_ID_RE.match(raw_id)
    if m:
        num = int(m.group(1))
        return f"事实{num}"

    # Fact slug pattern: fact-{slug}-{number}
    m = _FACT_SLUG_RE.match(raw_id)
    if m:
        # Extract the descriptive slug (between "fact-" and "-NNN")
        slug = raw_id[5 : -(len(m.group(1)) + 1)]  # strip "fact-" prefix and "-NNN" suffix
        return slug.replace("-", " ")

    # Conditional node pattern: COND-{number}
    m = _COND_ID_RE.match(raw_id)
    if m:
        num = int(m.group(1))
        return f"条件{num}"

    # Attack node ID: atk-NNN → 攻击点N
    m = _ATK_ID_RE.match(raw_id)
    if m:
        num = int(m.group(1))
        return f"攻击点{_chinese_numeral(num)}"

    # Path letter ID: path-A → 路径A
    m = _PATH_LETTER_RE.match(raw_id)
    if m:
        return f"路径{m.group(1)}"

    # Path number ID: path-NNN → 路径N
    m = _PATH_NUM_RE.match(raw_id)
    if m:
        num = int(m.group(1))
        return f"路径{_chinese_numeral(num)}"

    # Blocking condition: bc-NNN → 阻断条件N
    m = _BC_ID_RE.match(raw_id)
    if m:
        num = int(m.group(1))
        return f"阻断条件{_chinese_numeral(num)}"

    # Missing issue ID: missing-issue-slug-NNN-party-* → 证据缺口N
    m = _MISSING_ISSUE_RE.match(raw_id)
    if m:
        num = int(m.group(1))
        return f"证据缺口{_chinese_numeral(num)}"

    # Party ID pattern: party-{role}-{name}
    m = _PARTY_ID_RE.match(raw_id)
    if m:
        party = _PARTY_LABELS.get(m.group(1), m.group(1))
        return party

    return raw_id


def humanize_field_value(raw_value: str) -> str:
    """Convert internal field enum values to natural language.

    Args:
        raw_value: The raw field value string

    Returns:
        Human-readable string.
    """
    return _FIELD_VALUE_MAP.get(raw_value, raw_value)


def humanize_text(text: str, context: dict[str, str] | None = None) -> str:
    """Replace all internal IDs and field values in a text string.

    Scans text for known ID patterns and replaces them with human-readable form.
    Also removes [来源:对抗分析] markers.

    Args:
        text: The raw text potentially containing internal IDs
        context: Optional dict mapping raw IDs to human-readable titles

    Returns:
        Text with IDs replaced by human-readable equivalents.
    """
    # Remove [来源:对抗分析] markers
    result = re.sub(r"\[来源:对抗分析\]\s*", "", text)

    # Replace issue IDs (hyphenated slugs like issue-loan-agreement-validity-001)
    def _replace_issue(m: re.Match[str]) -> str:
        return humanize_id(m.group(0), context)
    result = re.sub(r"issue-[a-z0-9]+(?:-[a-z0-9]+)*-\d{3}", _replace_issue, result)

    # Replace evidence IDs
    def _replace_evidence(m: re.Match[str]) -> str:
        return humanize_id(m.group(0), context)
    result = re.sub(r"evidence-(?:plaintiff|defendant)-\d{3}", _replace_evidence, result)

    # Replace FACT IDs (both FACT-NNN and fact-slug-NNN forms)
    def _replace_fact(m: re.Match[str]) -> str:
        return humanize_id(m.group(0), context)
    result = re.sub(r"FACT-\d{3}", _replace_fact, result)
    result = re.sub(r"fact-[a-z0-9]+(?:-[a-z0-9]+)*-\d{3}", _replace_fact, result)

    # Replace atk IDs
    result = re.sub(r"atk-\d{3}", lambda m: humanize_id(m.group(0), context), result)

    # Replace path IDs (letter and number forms)
    result = re.sub(r"path-[A-E]", lambda m: humanize_id(m.group(0), context), result)
    result = re.sub(r"path-\d{3}", lambda m: humanize_id(m.group(0), context), result)

    # Replace blocking condition IDs
    result = re.sub(r"[Bb][Cc]-\d{3}", lambda m: humanize_id(m.group(0), context), result)

    # Replace missing-issue IDs
    result = re.sub(
        r"missing-issue-[a-z0-9]+(?:-[a-z0-9]+)*-\d{3}(?:-party-(?:plaintiff|defendant)-[a-z]+)?",
        lambda m: humanize_id(m.group(0), context),
        result,
    )

    # Replace party IDs (party-plaintiff-wang → 原告方)
    def _replace_party(m: re.Match[str]) -> str:
        return humanize_id(m.group(0), context)
    result = re.sub(r"party-(?:plaintiff|defendant)-[a-z]+", _replace_party, result)

    # Replace internal field values
    for raw, human in _FIELD_VALUE_MAP.items():
        result = result.replace(raw, human)

    # Remove model class names + internal report IDs (e.g. "AmountCalculationReport amount-report-xxx")
    result = re.sub(r"\s*AmountCalculationReport\s+amount-report-[a-f0-9]+", "", result)
    # Remove delta=0 style internal metadata
    result = re.sub(r"（delta=\d+）", "", result)
    # Clean up issue-NNN short references in prose (e.g. "issue-003")
    result = re.sub(r"issue-(\d{3})", lambda m: f"争点{_chinese_numeral(int(m.group(1)))}", result)
    # Remove run-id patterns (e.g. "run-abc12345")
    result = re.sub(r"run-[a-f0-9]{8,}", "", result)

    return result


def build_humanize_context(issue_tree=None, evidence_index=None) -> dict[str, str]:
    """Build a context dict for humanize_id from issue tree and evidence index.

    Args:
        issue_tree: IssueTree with .issues list
        evidence_index: EvidenceIndex with .evidence list

    Returns:
        Dict mapping raw IDs to titles
    """
    ctx: dict[str, str] = {}

    if issue_tree:
        for issue in issue_tree.issues:
            ctx[issue.issue_id] = issue.title

    if evidence_index:
        for ev in evidence_index.evidence:
            ctx[ev.evidence_id] = ev.title

    return ctx


def _chinese_numeral(n: int) -> str:
    """Convert small integer to Chinese numeral string for display."""
    _NUMERALS = "零一二三四五六七八九十"
    if 1 <= n <= 10:
        return _NUMERALS[n]
    if 11 <= n <= 19:
        return f"十{_NUMERALS[n - 10]}" if n > 10 else "十"
    # Fallback for larger numbers
    return str(n)
