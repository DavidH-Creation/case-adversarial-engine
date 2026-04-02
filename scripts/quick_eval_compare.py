#!/usr/bin/env python3
"""
Lightweight eval comparison: bigram matching vs LLM-as-judge for issue extraction.

Uses Claude CLI (Sonnet) to extract legal issues from case summaries, then scores
against gold_issue_tree.json with both bigram Jaccard and LLM-as-judge matching.

Cases: civil-loan-001, 002, 003, 004, 015 (hardest 5)

Usage:
    python scripts/quick_eval_compare.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Windows UTF-8 guard
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

_PROJECT_ROOT = Path(__file__).parent.parent
BENCHMARKS_DIR = _PROJECT_ROOT / "benchmarks" / "civil_loans"

HARD_CASES = ["civil-loan-001", "civil-loan-002", "civil-loan-003", "civil-loan-004", "civil-loan-015"]
EXTRACT_MODEL = "claude-sonnet-4-6"
JUDGE_MODEL = "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# Claude CLI subprocess helper
# ---------------------------------------------------------------------------

def _run_claude(prompt: str, model: str, timeout: int = 120) -> str:
    """Invoke claude CLI with --print and return stdout."""
    claude_bin = shutil.which("claude")
    if not claude_bin:
        raise RuntimeError("claude CLI not found in PATH")

    cmd = [claude_bin, "--print", "--output-format", "text", "--model", model]
    if sys.platform == "win32" and claude_bin.lower().endswith((".cmd", ".bat")):
        cmd = ["cmd", "/c"] + cmd

    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"claude CLI exited {result.returncode}: {result.stderr[:300]}"
        )
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Issue extraction
# ---------------------------------------------------------------------------

# All Chinese stored as Unicode escapes so the source file is ASCII-safe.
# At runtime Python resolves \uXXXX to the actual characters.

# \u4f60\u662f\u4e2d\u56fd\u6c11\u4e8b\u8bc9\u8ba3\u6cd5\u5f8b\u4e13\u5bb6 = 你是中国民事诉讼法律专家
# \u3010 = 【  \u3011 = 】
_EXTRACT_PROMPT = (
    "\u4f60\u662f\u4e2d\u56fd\u6c11\u4e8b\u8bc9\u8ba3\u6cd5\u5f8b\u4e13\u5bb6\u3002"
    "\u8bf7\u9605\u8bfb\u4ee5\u4e0b\u6848\u4ef6\u4fe1\u606f\uff0c"
    "\u63d0\u53d6\u672c\u6848\u7684\u4e3b\u8981\u6cd5\u5f8b\u4e89\u70b9\uff083\uff5e8\u4e2a\uff09\u3002"
    "\n\n\u3010\u6848\u4ef6\u6807\u9898\u3011{title}"
    "\n\n\u3010\u6848\u4ef6\u63cf\u8ff0\u3011{description}"
    "\n\n\u53ea\u8f93\u51fa JSON\uff0c\u683c\u5f0f\uff1a"
    '\n{{"issues": [{{"title": "\u4e89\u70b91"}}, {{"title": "\u4e89\u70b92"}}]}}'
    "\n\n\u8981\u6c42\uff1a\u6bcf\u4e2a\u4e89\u70b9 15\uff5e40 \u5b57\uff0c"
    "\u91cd\u70b9\u6355\u6349\u4e8b\u5b9e\u4e89\u70b9\u548c\u6cd5\u5f8b\u9002\u7528\u4e89\u70b9\u3002"
)


def extract_issues(manifest: dict) -> list[str]:
    """Extract issue titles from case manifest via Claude CLI."""
    prompt = _EXTRACT_PROMPT.format(
        title=manifest.get("title", ""),
        description=manifest.get("description", ""),
    )
    raw = _run_claude(prompt, model=EXTRACT_MODEL)

    # Strip markdown code fences if present
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    json_text = m.group(1) if m else raw

    try:
        data = json.loads(json_text)
        return [i["title"] for i in data.get("issues", [])]
    except (json.JSONDecodeError, KeyError):
        # Broaden: find outermost { ... }
        m2 = re.search(r"(\{.*\})", raw, re.DOTALL)
        if m2:
            try:
                data = json.loads(m2.group(1))
                return [i["title"] for i in data.get("issues", [])]
            except Exception:
                pass
        print(f"  WARNING: failed to parse JSON: {raw[:200]}")
        return []


# ---------------------------------------------------------------------------
# Bigram matching
# ---------------------------------------------------------------------------

def _bigram_jaccard(a: str, b: str) -> float:
    bg_a = {a[i:i + 2] for i in range(len(a) - 1)}
    bg_b = {b[i:i + 2] for i in range(len(b) - 1)}
    if not bg_a and not bg_b:
        return 1.0
    return len(bg_a & bg_b) / len(bg_a | bg_b)


def _bigram_match(query: str, candidates: list[str], threshold: float = 0.25) -> bool:
    if not candidates:
        return False
    return max(_bigram_jaccard(query.lower(), c.lower()) for c in candidates) >= threshold


# ---------------------------------------------------------------------------
# LLM-as-judge matching
# ---------------------------------------------------------------------------

# Common Chinese function words excluded from keyword pre-filter.
# \u7684=\u7684 \u662f=\u662f  etc. — kept as escapes for ASCII safety
_STOP = set(
    "\u7684\u662f\u5426\u4e3a\u5728\u4e0e\u4e4b\u5176\u7b49"
    "\u4e86\u800c\u4f46\u548c\u6216\u56e0\u7531\u5bf9\u4e8e"
    "\u4e2d\u6709\u88ab\u6240\u4ee5\u5f97\u4e0d\u4e5f\u5c06"
)

# \u4ee5\u4e0b... = 以下两个法律争点描述是否指向同一个争议焦点？只回答 YES 或 NO，不要其他文字。
_JUDGE_PROMPT = (
    "\u4ee5\u4e0b\u4e24\u4e2a\u6cd5\u5f8b\u4e89\u70b9\u63cf\u8ff0"
    "\u662f\u5426\u6307\u5411\u540c\u4e00\u4e2a\u4e89\u8bae\u7126\u70b9\uff1f"
    "\u53ea\u56de\u7b54 YES \u6216 NO\uff0c\u4e0d\u8981\u5176\u4ed6\u6587\u5b57\u3002"
    "\n\u4e89\u70b9A: {a}\n\u4e89\u70b9B: {b}"
)


def _content_chars(text: str) -> set[str]:
    """CJK content characters, excluding stop words."""
    return {c for c in text if "\u4e00" <= c <= "\u9fff" and c not in _STOP}


def _llm_judge(a: str, b: str) -> bool:
    """Ask Claude Haiku whether two issue descriptions are semantically equivalent."""
    prompt = _JUDGE_PROMPT.format(a=a, b=b)
    try:
        ans = _run_claude(prompt, model=JUDGE_MODEL, timeout=60)
        return "YES" in ans.strip().upper()
    except Exception:
        return False


_LLM_TOP_K = 2  # LLM judge: check only top-K bigram-similar candidates per query


def _llm_match(query: str, candidates: list[str]) -> bool:
    """Semantic match: check top-K bigram candidates via LLM judge.

    Limits calls to _LLM_TOP_K per query (vs O(n*m) brute-force), making the
    comparison tractable while still catching paraphrases bigram misses.
    """
    if not candidates:
        return False
    ranked = sorted(candidates, key=lambda c: _bigram_jaccard(query, c), reverse=True)
    for c in ranked[:_LLM_TOP_K]:
        if _llm_judge(query, c):
            return True
    return False


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _f1(p: float, r: float) -> float:
    return 2 * p * r / (p + r) if (p + r) else 0.0


def score(extracted: list[str], gold: list[str], use_llm: bool) -> dict:
    """Compute precision, recall, F1 for extracted vs gold issue titles."""
    match_fn = _llm_match if use_llm else (lambda q, cs: _bigram_match(q, cs))
    recall_hits = sum(1 for g in gold if match_fn(g, extracted))
    precision_hits = sum(1 for e in extracted if match_fn(e, gold))
    recall = recall_hits / len(gold) if gold else 1.0
    precision = precision_hits / len(extracted) if extracted else 0.0
    return {
        "recall": round(recall, 3),
        "precision": round(precision, 3),
        "f1": round(_f1(precision, recall), 3),
        "recall_hits": recall_hits,
        "precision_hits": precision_hits,
        "gold_count": len(gold),
        "extracted_count": len(extracted),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("\nQuick Eval: Bigram vs LLM-as-Judge | Issue Extraction Accuracy")
    print(f"Extract: {EXTRACT_MODEL}  |  Judge: {JUDGE_MODEL}")
    print("=" * 72)

    rows: list[dict] = []

    for case_id in HARD_CASES:
        case_dir = BENCHMARKS_DIR / case_id
        if not case_dir.exists():
            print(f"SKIP {case_id}: directory not found")
            continue

        manifest = json.loads((case_dir / "case_manifest.json").read_text(encoding="utf-8"))
        gold_raw = json.loads((case_dir / "gold_issue_tree.json").read_text(encoding="utf-8"))
        gold = [i["title"] for i in gold_raw.get("issues", [])]

        title_short = manifest.get("title", "")[:55]
        print(f"\n[{case_id}] {title_short}")
        print(f"  Gold ({len(gold)}): {[t[:25] for t in gold]}")

        print("  Extracting issues via Sonnet...")
        try:
            ext = extract_issues(manifest)
        except Exception as exc:
            print(f"  ERROR extracting: {exc}")
            continue
        print(f"  Extracted ({len(ext)}): {[t[:25] for t in ext]}")

        bg = score(ext, gold, use_llm=False)

        max_calls = (len(gold) + len(ext)) * _LLM_TOP_K
        print(f"  LLM judge (top-{_LLM_TOP_K} per query, ≤{max_calls} calls)...")
        lj = score(ext, gold, use_llm=True)

        print(f"  Bigram:    R={bg['recall']:.1%}  P={bg['precision']:.1%}  F1={bg['f1']:.1%}")
        print(f"  LLM-judge: R={lj['recall']:.1%}  P={lj['precision']:.1%}  F1={lj['f1']:.1%}")

        rows.append({"case_id": case_id, "gold": len(gold), "ext": len(ext), "bg": bg, "lj": lj})

    if not rows:
        print("\nNo results — exiting.")
        return

    # Summary comparison table
    W = 72
    print(f"\n{'=' * W}")
    print("COMPARISON TABLE — Issue Extraction (Bigram vs LLM-as-Judge)")
    print(f"{'=' * W}")
    print(f"{'Case':<20}  {'--- Bigram ---':^28}  {'--- LLM-Judge ---':^28}")
    print(f"{'':20}  {'Recall':>8} {'Prec':>8} {'F1':>8}  {'Recall':>8} {'Prec':>8} {'F1':>8}")
    print("-" * W)

    bg_f1s, lj_f1s = [], []
    for r in rows:
        b, l = r["bg"], r["lj"]
        bg_f1s.append(b["f1"])
        lj_f1s.append(l["f1"])
        print(
            f"{r['case_id']:<20}  "
            f"{b['recall']:>8.1%} {b['precision']:>8.1%} {b['f1']:>8.1%}  "
            f"{l['recall']:>8.1%} {l['precision']:>8.1%} {l['f1']:>8.1%}"
        )

    print("-" * W)
    avg_b = sum(bg_f1s) / len(bg_f1s)
    avg_l = sum(lj_f1s) / len(lj_f1s)
    print(f"{'AVERAGE':<20}  {'':>8} {'':>8} {avg_b:>8.1%}  {'':>8} {'':>8} {avg_l:>8.1%}")

    delta = avg_l - avg_b
    sign = "+" if delta >= 0 else ""
    if delta > 0.02:
        verdict = "LLM-judge improves over bigram"
    elif delta < -0.02:
        verdict = "Bigram beats LLM-judge"
    else:
        verdict = "Methods are comparable (delta < 2pp)"
    print(f"\nLLM-judge vs Bigram avg F1: {sign}{delta:.1%}  ({verdict})")


if __name__ == "__main__":
    main()
