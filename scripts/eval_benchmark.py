#!/usr/bin/env python3
"""
金标基准评测脚本 / Gold benchmark evaluation script.

对 benchmarks/civil_loans/<case_id>/ 下的金标案件运行证据索引器 + 争点抽取器，
将引擎输出与金标 JSON 文件对比，计算 Recall / Precision / F1 指标。

Run EvidenceIndexer + IssueExtractor against gold-annotated civil loan cases,
compare engine output to gold_evidence_index.json / gold_issue_tree.json,
and report Recall / Precision / F1 metrics.

Usage:
    python scripts/eval_benchmark.py --cases civil-loan-002 civil-loan-001
    python scripts/eval_benchmark.py --all          # run all 20 cases
    python scripts/eval_benchmark.py --hard         # run hardest 5 cases
    python scripts/eval_benchmark.py --cases civil-loan-002 --model claude-sonnet-4-6
    python scripts/eval_benchmark.py --hard --matcher llm-judge  # semantic matching via LLM
    python scripts/eval_benchmark.py --hard --match-only --matcher llm-judge  # re-score cached output
    python scripts/eval_benchmark.py --hard --compare-matchers  # bigram vs llm-judge on same engine output
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Windows UTF-8 guard
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from engines.case_structuring.evidence_indexer.indexer import EvidenceIndexer
from engines.case_structuring.evidence_indexer.schemas import RawMaterial
from engines.case_structuring.issue_extractor.extractor import IssueExtractor
from engines.shared.cli_adapter import ClaudeCLIClient, CLINotFoundError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BENCHMARKS_DIR = _PROJECT_ROOT / "benchmarks" / "civil_loans"

HARD_CASES = [
    "civil-loan-002",
    "civil-loan-001",
    "civil-loan-015",
    "civil-loan-003",
    "civil-loan-004",
]

DEFAULT_MODEL = "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# Similarity helpers
# ---------------------------------------------------------------------------


def _char_jaccard(a: str, b: str) -> float:
    """Character-level Jaccard similarity between two strings."""
    set_a = set(a)
    set_b = set(b)
    if not set_a and not set_b:
        return 1.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


def _bigram_jaccard(a: str, b: str) -> float:
    """Bigram Jaccard similarity — more sensitive than character-level."""
    bigrams_a = {a[i : i + 2] for i in range(len(a) - 1)}
    bigrams_b = {b[i : i + 2] for i in range(len(b) - 1)}
    if not bigrams_a and not bigrams_b:
        return 1.0
    intersection = len(bigrams_a & bigrams_b)
    union = len(bigrams_a | bigrams_b)
    return intersection / union if union else 0.0


def _best_match(query: str, candidates: list[str], threshold: float = 0.25) -> float:
    """Return the best bigram Jaccard score between query and any candidate."""
    if not candidates:
        return 0.0
    return max(_bigram_jaccard(query.lower(), c.lower()) for c in candidates)


def _compute_f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


# ---------------------------------------------------------------------------
# LLM-as-judge matching
# ---------------------------------------------------------------------------

_JUDGE_MODEL = "claude-haiku-4-5-20251001"
_LLM_TOP_K = 2

# Common Chinese stop/function characters — excluded from keyword pre-filter
_STOP_CHARS = set("的是否为在与之其等了而但和或因由对于中有被所以得不也将")


def _extract_content_chars(text: str) -> set[str]:
    """Extract meaningful CJK characters, filtering stop chars and punctuation."""
    return {c for c in text if "\u4e00" <= c <= "\u9fff" and c not in _STOP_CHARS}


def _has_keyword_overlap(a: str, b: str, min_overlap: int = 2) -> bool:
    """Quick pre-filter: skip LLM call if texts share fewer than min_overlap content chars."""
    chars_a = _extract_content_chars(a)
    chars_b = _extract_content_chars(b)
    return len(chars_a & chars_b) >= min_overlap


def _get_judge_client():
    """Return the resolved path to the claude CLI binary for LLM-judge calls."""
    import shutil

    resolved = shutil.which("claude")
    if not resolved:
        raise CLINotFoundError("claude CLI not found — needed for --matcher llm-judge")
    return resolved


def _llm_judge_match(a: str, b: str, claude_bin: str) -> bool:
    """Call claude CLI (sync subprocess) to judge semantic equivalence of two legal issues."""
    import subprocess

    prompt = (
        f"以下两个法律争点描述是否指向同一个争议焦点？只回答 YES 或 NO。\n争点A: {a}\n争点B: {b}"
    )
    cmd = [claude_bin, "--print", "--output-format", "text", "--model", _JUDGE_MODEL]
    if sys.platform == "win32" and claude_bin.lower().endswith((".cmd", ".bat")):
        cmd = ["cmd", "/c"] + cmd
    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=60,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return False
    return "YES" in result.stdout.strip().upper()


def _best_match_llm(query: str, candidates: list[str], client) -> bool:
    """Check if query semantically matches any candidate (keyword pre-filter + LLM judge)."""
    for c in candidates:
        if not _has_keyword_overlap(query, c):
            continue
        if _llm_judge_match(query, c, client):
            return True
    # Fallback: if keyword filter skipped all candidates, try the best bigram candidate
    if candidates:
        best_idx = max(range(len(candidates)), key=lambda i: _bigram_jaccard(query, candidates[i]))
        if _llm_judge_match(query, candidates[best_idx], client):
            return True
    return False


def _collect_candidate_pairs(
    left: list[str],
    right: list[str],
    *,
    threshold: float,
    matcher: str,
    judge_client=None,
) -> list[tuple[float, int, int]]:
    """Return candidate one-to-one pairs as (score, left_idx, right_idx)."""
    pairs: list[tuple[float, int, int]] = []
    if not left or not right:
        return pairs

    if matcher == "llm-judge" and judge_client is not None:
        for left_idx, left_text in enumerate(left):
            ranked = sorted(
                (
                    (_bigram_jaccard(left_text, right_text), right_idx, right_text)
                    for right_idx, right_text in enumerate(right)
                ),
                reverse=True,
            )
            for rank, (score, right_idx, right_text) in enumerate(ranked[:_LLM_TOP_K]):
                if rank > 0 and not _has_keyword_overlap(left_text, right_text):
                    continue
                if _llm_judge_match(left_text, right_text, judge_client):
                    pairs.append((score, left_idx, right_idx))
        return pairs

    for left_idx, left_text in enumerate(left):
        for right_idx, right_text in enumerate(right):
            score = _bigram_jaccard(left_text.lower(), right_text.lower())
            if score >= threshold:
                pairs.append((score, left_idx, right_idx))
    return pairs


def _count_one_to_one_matches(
    left: list[str],
    right: list[str],
    *,
    threshold: float = 0.25,
    matcher: str = "bigram",
    judge_client=None,
) -> int:
    """Greedy one-to-one matching avoids overcounting broad labels."""
    pairs = _collect_candidate_pairs(
        left,
        right,
        threshold=threshold,
        matcher=matcher,
        judge_client=judge_client,
    )
    pairs.sort(reverse=True)

    matched_left: set[int] = set()
    matched_right: set[int] = set()
    hits = 0

    for _score, left_idx, right_idx in pairs:
        if left_idx in matched_left or right_idx in matched_right:
            continue
        matched_left.add(left_idx)
        matched_right.add(right_idx)
        hits += 1

    return hits


# ---------------------------------------------------------------------------
# Gold data loaders
# ---------------------------------------------------------------------------


def load_gold_evidence(case_dir: Path) -> list[dict]:
    path = case_dir / "gold_evidence_index.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("evidence", [])


def load_gold_issues(case_dir: Path) -> list[dict]:
    path = case_dir / "gold_issue_tree.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("issues", [])


def load_manifest(case_dir: Path) -> dict:
    return json.loads((case_dir / "case_manifest.json").read_text(encoding="utf-8"))


def save_engine_output(case_dir: Path, evidence_dicts: list[dict], issue_dicts: list[dict]) -> None:
    """Persist engine output for later --match-only re-evaluation."""
    out = {"evidence": evidence_dicts, "issues": issue_dicts}
    (case_dir / "engine_output.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_engine_output(case_dir: Path) -> tuple[list[dict], list[dict]] | None:
    """Load previously saved engine output. Returns None if not found."""
    path = case_dir / "engine_output.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("evidence", []), data.get("issues", [])


# ---------------------------------------------------------------------------
# Input construction from case description
# ---------------------------------------------------------------------------


def build_raw_materials(manifest: dict) -> list[RawMaterial]:
    """Build a single RawMaterial from the case description (裁判要旨)."""
    description = manifest.get("description", "")
    title = manifest.get("title", manifest["case_id"])
    text = f"【案件标题】{title}\n\n【裁判要旨】{description}"
    return [
        RawMaterial(
            source_id="src-case-abstract",
            text=text,
            metadata={
                "document_type": "case_abstract",
                "submitter": "court",
                "status": "admitted_for_discussion",
            },
        )
    ]


def build_synthetic_claims(manifest: dict) -> list[dict]:
    """Derive minimal claim + defense dicts from the case description."""
    case_id = manifest["case_id"]
    parties = manifest.get("parties", [])
    plaintiff = next((p for p in parties if p["side"] == "plaintiff"), None)
    defendants = [p for p in parties if p["side"] == "defendant"]

    plaintiff_id = plaintiff["party_id"] if plaintiff else f"party-{case_id}-001"
    defendant_id = defendants[0]["party_id"] if defendants else f"party-{case_id}-002"

    claims = [
        {
            "claim_id": f"claim-{case_id}-eval-001",
            "case_id": case_id,
            "party_id": plaintiff_id,
            "title": "原告主张",
            "description": manifest.get("description", "")[:300],
            "legal_basis": "民法典",
            "related_evidence_ids": [],
        }
    ]
    defenses = [
        {
            "defense_id": f"defense-{case_id}-eval-001",
            "case_id": case_id,
            "party_id": defendant_id,
            "title": "被告抗辩",
            "description": manifest.get("description", "")[:300],
            "legal_basis": "",
            "related_evidence_ids": [],
        }
    ]
    return claims, defenses


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------


def compute_evidence_metrics(
    extracted: list,
    gold: list[dict],
    threshold: float = 0.25,
    matcher: str = "bigram",
    judge_client=None,
) -> dict:
    """Compare extracted Evidence objects to gold evidence dicts."""
    gold_titles = [e.get("title", "") for e in gold]
    gold_summaries = [e.get("summary", "") for e in gold]
    gold_texts = [f"{t} {s}" for t, s in zip(gold_titles, gold_summaries)]

    ext_titles = [getattr(e, "title", "") or "" for e in extracted]
    ext_summaries = [getattr(e, "summary", "") or "" for e in extracted]
    ext_texts = [f"{t} {s}" for t, s in zip(ext_titles, ext_summaries)]

    hits = _count_one_to_one_matches(
        gold_texts,
        ext_texts,
        threshold=threshold,
        matcher=matcher,
        judge_client=judge_client,
    )

    recall = hits / len(gold_texts) if gold_texts else 1.0
    precision = hits / len(ext_texts) if ext_texts else 0.0

    return {
        "gold_count": len(gold),
        "extracted_count": len(extracted),
        "recall": round(recall, 3),
        "precision": round(precision, 3),
        "f1": round(_compute_f1(precision, recall), 3),
        "recall_hits": hits,
        "precision_hits": hits,
    }


def compute_issue_metrics(
    extracted_issues: list[dict],
    gold: list[dict],
    threshold: float = 0.25,
    matcher: str = "bigram",
    judge_client=None,
) -> dict:
    """Compare extracted IssueTree issues to gold issue dicts."""
    gold_titles = [i.get("title", "") for i in gold]

    # IssueTree stores issues as pydantic objects with .title
    ext_titles = []
    for issue in extracted_issues:
        if hasattr(issue, "title"):
            ext_titles.append(issue.title or "")
        elif isinstance(issue, dict):
            ext_titles.append(issue.get("title", ""))
        else:
            ext_titles.append(str(issue))

    hits = _count_one_to_one_matches(
        gold_titles,
        ext_titles,
        threshold=threshold,
        matcher=matcher,
        judge_client=judge_client,
    )

    recall = hits / len(gold_titles) if gold_titles else 1.0
    precision = hits / len(ext_titles) if ext_titles else 0.0

    return {
        "gold_count": len(gold),
        "extracted_count": len(ext_titles),
        "recall": round(recall, 3),
        "precision": round(precision, 3),
        "f1": round(_compute_f1(precision, recall), 3),
        "recall_hits": hits,
        "precision_hits": hits,
    }


def _aggregate_results(results: list[dict]) -> dict:
    ev_f1s = [r.get("evidence_metrics", {}).get("f1", 0) for r in results]
    iss_f1s = [r.get("issue_metrics", {}).get("f1", 0) for r in results]
    return {
        "avg_evidence_f1": round(sum(ev_f1s) / len(ev_f1s), 3) if ev_f1s else 0.0,
        "avg_issue_f1": round(sum(iss_f1s) / len(iss_f1s), 3) if iss_f1s else 0.0,
    }


def _print_summary(title: str, results: list[dict]) -> None:
    print(f"\n{'='*60}")
    print(title)
    print(f"{'='*60}")
    print(f"{'Case':<20} {'Ev-R':>6} {'Ev-P':>6} {'Ev-F1':>7} {'Iss-R':>6} {'Iss-P':>6} {'Iss-F1':>7}")
    print("-" * 65)

    for result in results:
        ev = result.get("evidence_metrics", {})
        iss = result.get("issue_metrics", {})
        print(
            f"{result['case_id']:<20} "
            f"{ev.get('recall', 0):>6.1%} {ev.get('precision', 0):>6.1%} {ev.get('f1', 0):>7.1%} "
            f"{iss.get('recall', 0):>6.1%} {iss.get('precision', 0):>6.1%} {iss.get('f1', 0):>7.1%}"
        )

    aggregate = _aggregate_results(results)
    print("-" * 65)
    print(
        f"{'AVERAGE':<20} {'':>6} {'':>6} {aggregate['avg_evidence_f1']:>7.1%} "
        f"{'':>6} {'':>6} {aggregate['avg_issue_f1']:>7.1%}"
    )


def _print_comparison_table(bigram_results: list[dict], llm_results: list[dict]) -> None:
    print("\nCOMPARISON TABLE")
    print("=" * 80)
    print(
        f"{'Case':<20} {'Bg-Iss-F1':>10} {'LLM-Iss-F1':>10} {'Delta':>8} "
        f"{'Bg-Ev-F1':>10} {'LLM-Ev-F1':>10}"
    )
    print("-" * 80)

    llm_by_case = {result["case_id"]: result for result in llm_results}
    for bigram in bigram_results:
        llm = llm_by_case.get(bigram["case_id"], {})
        bg_issue = bigram.get("issue_metrics", {}).get("f1", 0)
        llm_issue = llm.get("issue_metrics", {}).get("f1", 0)
        bg_evidence = bigram.get("evidence_metrics", {}).get("f1", 0)
        llm_evidence = llm.get("evidence_metrics", {}).get("f1", 0)
        delta = llm_issue - bg_issue
        print(
            f"{bigram['case_id']:<20} {bg_issue:>10.1%} {llm_issue:>10.1%} {delta:>+8.1%} "
            f"{bg_evidence:>10.1%} {llm_evidence:>10.1%}"
        )


# ---------------------------------------------------------------------------
# Single-case evaluation
# ---------------------------------------------------------------------------


async def eval_case(
    case_id: str,
    model: str,
    verbose: bool = True,
    matcher: str = "bigram",
    judge_client=None,
    match_only: bool = False,
) -> dict:
    """Run EvidenceIndexer + IssueExtractor on a single benchmark case.

    When match_only=True, skip engine calls and load saved engine_output.json
    to re-evaluate with a different matcher.
    """
    case_dir = BENCHMARKS_DIR / case_id
    if not case_dir.exists():
        raise FileNotFoundError(f"Case directory not found: {case_dir}")

    manifest = load_manifest(case_dir)
    gold_evidence = load_gold_evidence(case_dir)
    gold_issues = load_gold_issues(case_dir)

    if verbose:
        print(f"\n{'=' * 60}")
        print(f"[{case_id}] {manifest.get('title', '')}")
        print(f"  Gold: {len(gold_evidence)} evidence, {len(gold_issues)} issues")

    result: dict = {
        "case_id": case_id,
        "title": manifest.get("title", ""),
        "gold_evidence_count": len(gold_evidence),
        "gold_issue_count": len(gold_issues),
        "error": None,
    }

    # --match-only path: load cached engine output
    if match_only:
        saved = load_engine_output(case_dir)
        if saved is None:
            result["error"] = "No saved engine_output.json — run without --match-only first"
            if verbose:
                print(f"  SKIP: {result['error']}")
            return result

        saved_evidence, saved_issues = saved
        if verbose:
            print(
                f"  [match-only] Loaded {len(saved_evidence)} evidence, {len(saved_issues)} issues from cache"
            )

        from types import SimpleNamespace

        ev_metrics = compute_evidence_metrics(
            [SimpleNamespace(**d) for d in saved_evidence],
            gold_evidence,
            matcher=matcher,
            judge_client=judge_client,
        )
        result["evidence_metrics"] = ev_metrics

        issue_metrics = compute_issue_metrics(
            saved_issues,
            gold_issues,
            matcher=matcher,
            judge_client=judge_client,
        )
        result["issue_metrics"] = issue_metrics

        if verbose:
            print(
                f"  Evidence  Recall={ev_metrics['recall']:.1%}  Precision={ev_metrics['precision']:.1%}  F1={ev_metrics['f1']:.1%}"
            )
            print(
                f"  Issues    Recall={issue_metrics['recall']:.1%}  Precision={issue_metrics['precision']:.1%}  F1={issue_metrics['f1']:.1%}"
            )
            print(f"  Gold issues:      {[i.get('title', '') for i in gold_issues]}")
            print(f"  Extracted issues: {[i.get('title', '') for i in saved_issues]}")
        return result

    # Full engine run path
    llm_client = ClaudeCLIClient(timeout=300.0)

    # --- Phase 1: Evidence Indexing ---
    if verbose:
        print(f"  [Phase 1] Running EvidenceIndexer...")

    materials = build_raw_materials(manifest)
    indexer = EvidenceIndexer(llm_client=llm_client, model=model)

    try:
        party_id = (
            manifest["parties"][0]["party_id"]
            if manifest.get("parties")
            else f"party-{case_id}-001"
        )
        extracted_evidence = await indexer.index(
            materials=materials,
            case_id=case_id,
            owner_party_id=party_id,
            case_slug=case_id,
        )
        ev_metrics = compute_evidence_metrics(
            extracted_evidence,
            gold_evidence,
            matcher=matcher,
            judge_client=judge_client,
        )
        result["evidence_metrics"] = ev_metrics
        if verbose:
            print(f"  [Phase 1] Extracted {len(extracted_evidence)} evidence items")
            print(
                f"           Recall={ev_metrics['recall']:.1%}  Precision={ev_metrics['precision']:.1%}  F1={ev_metrics['f1']:.1%}"
            )
    except Exception as exc:
        result["evidence_error"] = str(exc)
        extracted_evidence = []
        if verbose:
            print(f"  [Phase 1] ERROR: {exc}")

    # --- Phase 2: Issue Extraction ---
    if verbose:
        print(f"  [Phase 2] Running IssueExtractor...")

    claims, defenses = build_synthetic_claims(manifest)
    evidence_dicts = [
        {
            "evidence_id": getattr(e, "evidence_id", f"ev-{i}"),
            "title": getattr(e, "title", ""),
            "summary": getattr(e, "summary", ""),
            "evidence_type": str(getattr(e, "evidence_type", "")),
            "source": getattr(e, "source", ""),
        }
        for i, e in enumerate(extracted_evidence)
    ]

    extractor = IssueExtractor(llm_client=llm_client, model=model)
    try:
        issue_tree = await extractor.extract(
            claims=claims,
            defenses=defenses,
            evidence=evidence_dicts,
            case_id=case_id,
            case_slug=case_id,
        )
        extracted_issues = issue_tree.issues if hasattr(issue_tree, "issues") else []
        issue_metrics = compute_issue_metrics(
            extracted_issues,
            gold_issues,
            matcher=matcher,
            judge_client=judge_client,
        )
        result["issue_metrics"] = issue_metrics
        if verbose:
            print(f"  [Phase 2] Extracted {len(extracted_issues)} issues")
            print(
                f"           Recall={issue_metrics['recall']:.1%}  Precision={issue_metrics['precision']:.1%}  F1={issue_metrics['f1']:.1%}"
            )
            # Show extracted vs gold titles
            print(f"  Gold issues:      {[i.get('title', '') for i in gold_issues]}")
            ext_titles = [getattr(i, "title", "") for i in extracted_issues]
            print(f"  Extracted issues: {ext_titles}")
    except Exception as exc:
        result["issue_error"] = str(exc)
        extracted_issues = []
        if verbose:
            print(f"  [Phase 2] ERROR: {exc}")

    # Save engine output for future --match-only runs
    issue_save = []
    for iss in extracted_issues:
        if hasattr(iss, "title"):
            issue_save.append({"title": iss.title or ""})
        elif isinstance(iss, dict):
            issue_save.append({"title": iss.get("title", "")})
        else:
            issue_save.append({"title": str(iss)})
    save_engine_output(case_dir, evidence_dicts, issue_save)
    if verbose:
        print(f"  [Saved] engine_output.json → {case_dir}")

    return result


async def _run_matcher(
    cases: list[str],
    *,
    model: str,
    verbose: bool,
    matcher: str,
    judge_client=None,
    match_only: bool = False,
) -> dict:
    results = []
    for case_id in cases:
        try:
            result = await eval_case(
                case_id,
                model=model,
                verbose=verbose,
                matcher=matcher,
                judge_client=judge_client,
                match_only=match_only,
            )
            results.append(result)
        except FileNotFoundError as exc:
            print(f"  SKIP: {exc}")
        except CLINotFoundError:
            raise

    return {
        "matcher": matcher,
        "match_only": match_only,
        "results": results,
        "aggregate": _aggregate_results(results),
    }


async def run_matcher_comparison(
    cases: list[str],
    *,
    model: str,
    verbose: bool = True,
    match_only: bool = False,
) -> dict[str, dict]:
    """Run bigram and llm-judge against the same extracted engine output."""
    bigram = await _run_matcher(
        cases,
        model=model,
        verbose=verbose,
        matcher="bigram",
        match_only=match_only,
    )
    llm_judge = await _run_matcher(
        cases,
        model=model,
        verbose=verbose,
        matcher="llm-judge",
        judge_client=_get_judge_client(),
        match_only=True,
    )
    return {"bigram": bigram, "llm-judge": llm_judge}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate engine against gold benchmark cases")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--cases", nargs="+", metavar="CASE_ID", help="Specific case IDs to evaluate"
    )
    group.add_argument("--hard", action="store_true", help="Evaluate hardest 5 cases")
    group.add_argument("--all", action="store_true", help="Evaluate all 20 cases")
    parser.add_argument(
        "--model", default=DEFAULT_MODEL, help=f"Model name (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=_PROJECT_ROOT / "outputs" / "benchmark_eval"
    )
    parser.add_argument(
        "--matcher",
        choices=["bigram", "llm-judge"],
        default="bigram",
        help="Matching algorithm: bigram (fast, literal) or llm-judge (semantic, uses API)",
    )
    parser.add_argument(
        "--compare-matchers",
        action="store_true",
        help="Run bigram and llm-judge side-by-side on the same engine outputs",
    )
    parser.add_argument(
        "--match-only",
        action="store_true",
        help="Skip engine runs; re-evaluate saved engine_output.json with chosen --matcher",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress per-case verbose output")
    args = parser.parse_args()

    # Determine which cases to run
    if args.hard:
        cases = HARD_CASES
    elif args.all:
        cases = sorted(
            d.name
            for d in BENCHMARKS_DIR.iterdir()
            if d.is_dir() and d.name.startswith("civil-loan-")
        )
    elif args.cases:
        cases = args.cases
    else:
        cases = HARD_CASES  # default: hard 5


    print(f"\nBenchmark Evaluation — {len(cases)} cases")
    print(f"Model: {args.model}")
    if args.compare_matchers:
        mode_suffix = "cached re-score only" if args.match_only else "engine run + cached re-score"
        print(f"Mode: compare-matchers ({mode_suffix})")
    else:
        print(f"Matcher: {args.matcher}" + (" (match-only)" if args.match_only else ""))
    print(f"Cases: {', '.join(cases)}")

    try:
        if args.compare_matchers:
            comparison = await run_matcher_comparison(
                cases,
                model=args.model,
                verbose=not args.quiet,
                match_only=args.match_only,
            )
        else:
            judge_client = _get_judge_client() if args.matcher == "llm-judge" else None
            single = await _run_matcher(
                cases,
                model=args.model,
                verbose=not args.quiet,
                matcher=args.matcher,
                judge_client=judge_client,
                match_only=args.match_only,
            )
    except CLINotFoundError:
        print("\nERROR: claude CLI not found in PATH.")
        print("Make sure Claude Code CLI is installed and authenticated.")
        sys.exit(1)

    # Save output
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = args.output_dir / f"eval_{ts}.json"
    if args.compare_matchers:
        _print_summary("SUMMARY — BIGRAM", comparison["bigram"]["results"])
        _print_summary("SUMMARY — LLM-JUDGE", comparison["llm-judge"]["results"])
        _print_comparison_table(comparison["bigram"]["results"], comparison["llm-judge"]["results"])
        out_data = {
            "timestamp": ts,
            "model": args.model,
            "mode": "compare-matchers",
            "cases": cases,
            "bigram": comparison["bigram"],
            "llm_judge": comparison["llm-judge"],
        }
    else:
        _print_summary("SUMMARY", single["results"])
        out_data = {
            "timestamp": ts,
            "model": args.model,
            "mode": "single-matcher",
            "matcher": args.matcher,
            "cases": cases,
            "results": single["results"],
            "aggregate": single["aggregate"],
        }
    out_path.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
