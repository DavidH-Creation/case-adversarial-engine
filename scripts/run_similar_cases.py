"""
Standalone script to run similar-case search and insert results into existing DOCX report.

Usage:
    python scripts/run_similar_cases.py <case_yaml> <output_dir>

Example:
    python scripts/run_similar_cases.py cases/wang_v_chen_zhuang_2025.yaml outputs/20260401-090617
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import yaml

# Ensure project root on sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from docx import Document  # noqa: E402

from engines.report_generation.docx_generator import _render_similar_cases  # noqa: E402
from engines.shared.cli_adapter import ClaudeCLIClient  # noqa: E402
from engines.similar_case_search.keyword_extractor import KeywordExtractor  # noqa: E402
from engines.similar_case_search.local_search import LocalCaseSearcher  # noqa: E402
from engines.similar_case_search.relevance_ranker import RelevanceRanker  # noqa: E402


async def main(case_yaml: Path, output_dir: Path) -> None:
    # Load case data
    with open(case_yaml, "r", encoding="utf-8") as f:
        case_data: dict = yaml.safe_load(f)
    print(f"[1/4] Loaded case: {case_data.get('case_id', '?')}")

    # Initialize LLM client (ClaudeCLI, same as run_case.py)
    client = ClaudeCLIClient(timeout=600.0)

    # Stage 1: Extract keywords
    print("[2/4] Extracting keywords...")
    extractor = KeywordExtractor(llm_client=client, model="claude-sonnet-4-6")
    keywords = await extractor.extract(case_data)
    print(f"  案由: {keywords.cause_of_action}")
    print(f"  关键词: {', '.join(keywords.search_terms)}")

    # Stage 2: Local search
    print("[3/4] Searching local case index...")
    searcher = LocalCaseSearcher()
    candidates = searcher.search(keywords, max_results=20)
    print(f"  匹配到 {len(candidates)} 条候选案例")

    if not candidates:
        print("  No candidates found. Exiting.")
        return

    # Stage 3: Rank by relevance
    print("[4/4] Ranking by relevance...")
    ranker = RelevanceRanker(llm_client=client, model="claude-sonnet-4-6")
    ranked = await ranker.rank(case_data, candidates)
    similar_cases_data = [json.loads(rc.model_dump_json()) for rc in ranked[:10]]
    print(f"  排序完成，取 top {len(similar_cases_data)} 条")

    # Save raw results as JSON
    results_path = output_dir / "similar_cases.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(similar_cases_data, f, ensure_ascii=False, indent=2)
    print(f"\n  结果已保存: {results_path}")

    # Print summary
    print("\n=== 类案搜索结果 ===")
    for i, rc in enumerate(similar_cases_data, 1):
        case_info = rc.get("case", {})
        rel = rc.get("relevance", {})
        print(f"\n  {i}. {case_info.get('case_number', '?')}")
        print(f"     法院: {case_info.get('court', '?')}")
        print(f"     案由: {case_info.get('cause_of_action', '?')}")
        print(f"     相关性: {rel.get('overall', 0):.0%}")
        print(f"     摘要: {case_info.get('summary', '?')[:80]}")
        analysis = rc.get("analysis", "")
        if analysis:
            print(f"     分析: {analysis[:100]}")

    # Insert into existing DOCX report
    docx_path = output_dir / "对抗分析报告.docx"
    if docx_path.exists():
        print(f"\n[Insert] Opening existing report: {docx_path}")
        doc = Document(str(docx_path))
        _render_similar_cases(doc, similar_cases_data)
        doc.save(str(docx_path))
        print(f"[Insert] 类案检索参考 section inserted and saved to: {docx_path}")
    else:
        print(f"\n[Warning] DOCX not found: {docx_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    case_yaml = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    asyncio.run(main(case_yaml, output_dir))
