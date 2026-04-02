"""
Standalone script: keyword-matching similar case search + DOCX insertion.

No LLM calls - uses hardcoded keywords + local string matching only.

Usage:
    python scripts/insert_similar_cases.py [output_dir]

Default output_dir: outputs/20260330-123922  (relative to project root)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from docx import Document  # noqa: E402

from engines.report_generation.docx_generator import _render_similar_cases  # noqa: E402
from engines.similar_case_search.local_search import LocalCaseSearcher  # noqa: E402
from engines.similar_case_search.schemas import (  # noqa: E402
    CaseKeywords,
    RankedCase,
    RelevanceScore,
)

# ---------------------------------------------------------------------------
# Hardcoded keywords for 王某诉陈某、庄某民间借贷纠纷 (2025)
# ---------------------------------------------------------------------------
CASE_KEYWORDS = CaseKeywords(
    cause_of_action="民间借贷纠纷",
    legal_relations=["民间借贷", "债权债务", "借贷合意"],
    dispute_focuses=["借贷关系主体认定", "代收代付", "债务加入", "表见代理", "共同债务人"],
    relevant_statutes=["民法典第667条", "民法典第668条", "民间借贷司法解释"],
    search_terms=["民间借贷", "借款合意", "代收代付", "资金通道", "债务加入", "借贷主体"],
)


def score_to_relevance(raw_score: float, max_score: float) -> RelevanceScore:
    """Convert raw keyword-match score to a RelevanceScore."""
    ratio = min(raw_score / max(max_score, 1.0), 1.0)
    # Approximate sub-scores from overall ratio
    overall = round(0.3 + ratio * 0.6, 2)  # floor at 0.30, ceiling at 0.90
    return RelevanceScore(
        fact_similarity=round(overall * 0.85, 2),
        legal_relation_similarity=round(overall * 1.05, 2),
        dispute_focus_similarity=round(overall * 0.90, 2),
        judgment_reference_value=round(overall * 0.95, 2),
        overall=overall,
    )


def main(output_dir: Path) -> None:
    docx_path = output_dir / "对抗分析报告.docx"
    if not docx_path.exists():
        print(f"[ERROR] DOCX not found: {docx_path}")
        sys.exit(1)

    similar_json_path = output_dir / "similar_cases.json"

    # ------------------------------------------------------------------
    # Stage 1: Local keyword search (pure string matching, no LLM)
    # ------------------------------------------------------------------
    print("[1/3] Searching local case index...")
    searcher = LocalCaseSearcher()

    # Patch: LocalCaseSearcher.search() needs scored pairs; call internal logic
    entries = searcher._load_index()
    search_terms = CASE_KEYWORDS.search_terms + CASE_KEYWORDS.dispute_focuses

    scored: list[tuple[float, object]] = []
    for entry in entries:
        score = 0.0
        if entry.cause_of_action == CASE_KEYWORDS.cause_of_action:
            score += 3.0
        elif CASE_KEYWORDS.cause_of_action in entry.cause_of_action:
            score += 1.0
        elif entry.cause_of_action in CASE_KEYWORDS.cause_of_action:
            score += 1.0

        for term in search_terms:
            t = term.lower()
            if any(t in kw.lower() or kw.lower() in t for kw in entry.keywords):
                score += 2.0
            elif t in entry.summary.lower():
                score += 1.0

        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_raw_score = scored[0][0] if scored else 1.0
    candidates = scored[:20]
    print(f"  Found {len(candidates)} candidates (top score: {top_raw_score})")

    # ------------------------------------------------------------------
    # Stage 2: Build RankedCase objects (no LLM ranking, use score order)
    # ------------------------------------------------------------------
    print("[2/3] Building ranked results...")
    ranked: list[RankedCase] = []
    for raw_score, entry in candidates[:10]:
        rel = score_to_relevance(raw_score, top_raw_score)
        rc = RankedCase(case=entry, relevance=rel, analysis="")
        ranked.append(rc)
        print(f"  {entry.case_number[:30]:30s}  score={raw_score:.0f}  overall={rel.overall:.0%}")

    similar_cases_data = [json.loads(rc.model_dump_json()) for rc in ranked]

    # Save JSON
    with open(similar_json_path, "w", encoding="utf-8") as f:
        json.dump(similar_cases_data, f, ensure_ascii=False, indent=2)
    print(f"\n  Saved: {similar_json_path}")

    # ------------------------------------------------------------------
    # Stage 3: Insert into DOCX
    # ------------------------------------------------------------------
    print(f"[3/3] Inserting 类案检索参考 section into {docx_path.name}...")
    doc = Document(str(docx_path))

    # Check if section already exists
    has_section = any("类案检索参考" in p.text for p in doc.paragraphs)
    if has_section:
        print("  [WARNING] Section already exists in DOCX - appending anyway")

    _render_similar_cases(doc, similar_cases_data)
    doc.save(str(docx_path))
    print(f"  Done. DOCX saved: {docx_path}")

    print("\n=== 类案检索参考 ===")
    for i, rc in enumerate(similar_cases_data, 1):
        case = rc.get("case", {})
        rel = rc.get("relevance", {})
        print(f"  {i:2d}. {case.get('case_number', '?')}")
        print(f"      {case.get('court', '?')} | {case.get('cause_of_action', '?')}")
        print(f"      相关性: {rel.get('overall', 0):.0%}")
        print(f"      摘要: {case.get('summary', '')[:70]}")


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        out_dir = Path(sys.argv[1])
    else:
        # Default: most recent DOCX without similar cases
        out_dir = ROOT / "outputs" / "20260330-123922"

    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir

    print(f"Output dir: {out_dir}")
    main(out_dir)
