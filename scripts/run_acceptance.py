#!/usr/bin/env python3
"""
批量案件验收回放脚本 / Batch case acceptance runner.

Runs N pipeline executions per case YAML, computes three acceptance metrics:
  - consistency       : 争点一致性  (issue consistency across N runs, target ≥0.75)
  - citation_rate     : 证据引用率  (evidence_citations non-empty rate, target 1.0)
  - path_explainable  : 路径可解释性 (CaseOutcomePaths 4 paths all have real trigger_conditions)

Usage:
    python scripts/run_acceptance.py --case_type labor_dispute
    python scripts/run_acceptance.py --case_type real_estate --cases_dir cases/ --runs 3
    python scripts/run_acceptance.py --case_type labor_dispute --runs 1 --output-dir outputs/acceptance/
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# Windows UTF-8 guard
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_YAML_KEYS = [
    "case_id",
    "case_slug",
    "case_type",
    "parties",
    "materials",
    "claims",
    "defenses",
]

METRIC_THRESHOLDS = {
    "consistency": 0.75,
    "citation_rate": 1.0,
}

MIN_VALID_RUNS = 3  # Minimum successful runs for metrics to be meaningful


# ---------------------------------------------------------------------------
# YAML loading and validation
# ---------------------------------------------------------------------------


def load_and_validate_yaml(yaml_path: Path) -> tuple[dict | None, str | None]:
    """Load a case YAML file and validate required fields.

    Returns:
        (data, None) on success
        (None, error_reason) on failure
    """
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return None, f"invalid_yaml: {e}"
    except OSError as e:
        return None, f"file_error: {e}"

    if not isinstance(data, dict):
        return None, "yaml_not_dict"

    missing = [k for k in REQUIRED_YAML_KEYS if k not in data]
    if missing:
        return None, f"missing_keys:{','.join(missing)}"

    return data, None


# ---------------------------------------------------------------------------
# Metric computation (pure functions — no LLM)
# ---------------------------------------------------------------------------


def compute_metrics(run_results: list[dict]) -> dict:
    """Compute acceptance metrics from N pipeline run results.

    Args:
        run_results: List of dicts, each with:
            - "success"            : bool — whether this run completed without error
            - "issue_ids"          : list[str] — issue_ids present in this run's issue_tree
            - "evidence_citations" : list[list[str]] — one list per AgentOutput in the run
            - "outcome_paths"      : dict with keys win_path/lose_path/mediation_path/supplement_path,
                                     each having "trigger_conditions": list[str]
            - "error"              : str | None — error description if not successful

    Returns:
        dict with keys:
            consistency        float  [0.0–1.0]
            citation_rate      float  [0.0–1.0]
            path_explainable   bool
            passed             bool
            n_runs             int
            n_success          int
    """
    n_total = len(run_results)
    successful = [r for r in run_results if r.get("success", False)]
    n_success = len(successful)

    if n_success == 0:
        return {
            "consistency": 0.0,
            "citation_rate": 0.0,
            "path_explainable": False,
            "passed": False,
            "n_runs": n_total,
            "n_success": 0,
        }

    # --- 争点一致性 ---
    # For each unique issue_id, count how many runs it appears in.
    # consistency = max_count / n_success (i.e. the most stable issue's frequency).
    issue_counts: dict[str, int] = {}
    for r in successful:
        for iid in set(r.get("issue_ids", [])):
            issue_counts[iid] = issue_counts.get(iid, 0) + 1

    if issue_counts:
        consistency = max(issue_counts.values()) / n_success
    else:
        consistency = 0.0

    # --- 证据引用率 ---
    # Fraction of all AgentOutput slots across successful runs that have non-empty citations.
    total_outputs = 0
    cited_outputs = 0
    for r in successful:
        for citations in r.get("evidence_citations", []):
            total_outputs += 1
            if citations:
                cited_outputs += 1

    citation_rate = cited_outputs / total_outputs if total_outputs > 0 else 0.0

    # --- 路径可解释性 ---
    # Use the last successful run's outcome_paths.
    # All 4 paths must have trigger_conditions that is non-empty and not ["insufficient_data"].
    path_explainable = _check_path_explainability(successful)

    passed = (
        consistency >= METRIC_THRESHOLDS["consistency"]
        and citation_rate >= METRIC_THRESHOLDS["citation_rate"]
        and path_explainable
        and n_success >= min(MIN_VALID_RUNS, n_total)
    )

    return {
        "consistency": round(consistency, 4),
        "citation_rate": round(citation_rate, 4),
        "path_explainable": path_explainable,
        "passed": passed,
        "n_runs": n_total,
        "n_success": n_success,
    }


def _check_path_explainability(successful_runs: list[dict]) -> bool:
    """Return True if the last successful run's outcome_paths are all explainable."""
    for r in reversed(successful_runs):
        paths = r.get("outcome_paths")
        if not paths:
            continue
        for path_key in ("win_path", "lose_path", "mediation_path", "supplement_path"):
            tc = paths.get(path_key, {}).get("trigger_conditions", ["insufficient_data"])
            if not tc or tc == ["insufficient_data"]:
                return False
        return True
    # No run had outcome_paths
    return False


# ---------------------------------------------------------------------------
# Artifact extraction from pipeline output directory
# ---------------------------------------------------------------------------


def extract_run_artifacts(output_dir: Path) -> dict:
    """Parse pipeline output files from a single run directory.

    Reads result.json, issue_tree.json, and decision_tree.json to produce
    the run result dict expected by compute_metrics().

    Returns a run result dict with success=True on success, success=False on error.
    """
    try:
        # --- issue_ids from issue_tree.json ---
        issue_ids: list[str] = []
        it_path = output_dir / "issue_tree.json"
        if it_path.exists():
            it_data = json.loads(it_path.read_text(encoding="utf-8"))
            issue_ids = [iss["issue_id"] for iss in it_data.get("issues", [])]

        # --- evidence_citations from result.json ---
        evidence_citations: list[list[str]] = []
        result_path = output_dir / "result.json"
        if result_path.exists():
            result_data = json.loads(result_path.read_text(encoding="utf-8"))
            for rnd in result_data.get("rounds", []):
                for output in rnd.get("outputs", []):
                    evidence_citations.append(output.get("evidence_citations", []))

        # --- outcome_paths from decision_tree.json ---
        # Build CaseOutcomePaths using the outcome_paths module.
        outcome_paths: dict | None = None
        dt_path = output_dir / "decision_tree.json"
        if dt_path.exists():
            from engines.report_generation.outcome_paths import build_case_outcome_paths
            from engines.report_generation.mediation_range import compute_mediation_range

            dt_data = json.loads(dt_path.read_text(encoding="utf-8"))

            # Load amount_report for mediation range (optional)
            amount_report = None
            ar_path = output_dir / "amount_report.json"
            if ar_path.exists():
                try:
                    from engines.case_structuring.amount_calculator import AmountCalculationReport

                    ar_data = json.loads(ar_path.read_text(encoding="utf-8"))
                    amount_report = AmountCalculationReport.model_validate(ar_data)
                except Exception:
                    pass

            mediation_range = compute_mediation_range(amount_report) if amount_report else None

            # Wrap dt_data as a simple object for build_case_outcome_paths
            class _DictWrapper:
                def __init__(self, d: dict) -> None:
                    self._d = d

                def __getattr__(self, key: str):
                    return self._d.get(key)

            dt_obj = _DictWrapper(dt_data)
            cop = build_case_outcome_paths(dt_obj, mediation_range, None)
            outcome_paths = json.loads(cop.model_dump_json())

        return {
            "success": True,
            "issue_ids": issue_ids,
            "evidence_citations": evidence_citations,
            "outcome_paths": outcome_paths,
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "issue_ids": [],
            "evidence_citations": [],
            "outcome_paths": None,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Pipeline runner (default: subprocess)
# ---------------------------------------------------------------------------


def _default_pipeline_runner(
    yaml_path: Path,
    run_index: int,
    output_dir: Path,
) -> dict:
    """Run the full pipeline via subprocess and return extracted artifacts.

    Args:
        yaml_path   : Path to the case YAML file.
        run_index   : 0-based run index (for logging).
        output_dir  : Directory to write pipeline outputs into.

    Returns:
        Run result dict for compute_metrics().
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(_PROJECT_ROOT / "scripts" / "run_case.py"),
        str(yaml_path),
        "--output-dir",
        str(output_dir),
        "--skip-pretrial",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
        )
        if proc.returncode != 0:
            return {
                "success": False,
                "issue_ids": [],
                "evidence_citations": [],
                "outcome_paths": None,
                "error": f"subprocess_exit_{proc.returncode}: {proc.stderr[-500:]}",
            }
        return extract_run_artifacts(output_dir)
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "issue_ids": [],
            "evidence_citations": [],
            "outcome_paths": None,
            "error": "pipeline_timeout",
        }
    except Exception as e:
        return {
            "success": False,
            "issue_ids": [],
            "evidence_citations": [],
            "outcome_paths": None,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Per-case acceptance run
# ---------------------------------------------------------------------------


def run_acceptance_for_case(
    yaml_path: Path,
    n_runs: int,
    base_output_dir: Path,
    pipeline_runner: Callable[[Path, int, Path], dict] | None = None,
) -> dict:
    """Run acceptance evaluation for a single case YAML.

    Args:
        yaml_path       : Path to the case YAML file.
        n_runs          : Number of pipeline runs to execute.
        base_output_dir : Directory under which per-run subdirs are created.
        pipeline_runner : Optional override for the pipeline execution function.
                          Signature: (yaml_path, run_index, output_dir) -> run_result_dict
                          Defaults to _default_pipeline_runner.

    Returns:
        Case result dict with keys:
            case_id   str
            yaml_path str
            status    "passed" | "failed" | "skipped"
            reason    str | None   (set when status == "skipped")
            metrics   dict | None  (set when status != "skipped")
            runs      list[dict]   per-run results
    """
    runner = pipeline_runner or _default_pipeline_runner

    # Validate YAML
    data, error = load_and_validate_yaml(yaml_path)
    if data is None:
        return {
            "case_id": yaml_path.stem,
            "yaml_path": str(yaml_path),
            "status": "skipped",
            "reason": f"invalid_yaml: {error}",
            "metrics": None,
            "runs": [],
        }

    case_id = data.get("case_id", yaml_path.stem)
    case_slug = data.get("case_slug", yaml_path.stem)
    run_results: list[dict] = []

    print(f"\n  Case: {case_id} ({yaml_path.name})")
    for i in range(n_runs):
        run_dir = base_output_dir / f"{case_slug}_run{i + 1}"
        print(f"    Run {i + 1}/{n_runs}...", end="", flush=True)
        result = runner(yaml_path, i, run_dir)
        run_results.append(result)
        status_sym = "✓" if result["success"] else "✗"
        print(f" {status_sym}")
        if not result["success"]:
            print(f"      Error: {result.get('error', 'unknown')}")

    metrics = compute_metrics(run_results)
    overall_status = "passed" if metrics["passed"] else "failed"

    return {
        "case_id": case_id,
        "yaml_path": str(yaml_path),
        "status": overall_status,
        "reason": None,
        "metrics": metrics,
        "runs": [
            {
                "run_index": i + 1,
                "success": r["success"],
                "error": r.get("error"),
                "issue_count": len(r.get("issue_ids", [])),
            }
            for i, r in enumerate(run_results)
        ],
    }


# ---------------------------------------------------------------------------
# Batch acceptance run
# ---------------------------------------------------------------------------


def run_acceptance(
    case_type: str,
    cases_dir: Path,
    n_runs: int = 5,
    *,
    pipeline_runner: Callable[[Path, int, Path], dict] | None = None,
    output_dir: Path | None = None,
) -> dict:
    """Run acceptance evaluation for all case YAMLs of a given case_type.

    Args:
        case_type       : e.g. "labor_dispute" or "real_estate"
        cases_dir       : Directory containing case YAML files.
        n_runs          : Number of runs per case (default 5).
        pipeline_runner : Optional pipeline runner override (for testing).
        output_dir      : Where to write intermediate run outputs.

    Returns:
        Acceptance report dict.
    """
    # Find matching YAML files
    all_yamls = sorted(cases_dir.glob("*.yaml"))
    matching = [p for p in all_yamls if _yaml_matches_case_type(p, case_type)]

    if not matching:
        print(f"  [Warning] No YAML files found for case_type='{case_type}' in {cases_dir}")

    # Intermediate output dir
    if output_dir is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        output_dir = _PROJECT_ROOT / "outputs" / "acceptance" / f"{case_type}_{ts}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run each case
    case_results: list[dict] = []
    for yaml_path in matching:
        case_dir = output_dir / yaml_path.stem
        case_result = run_acceptance_for_case(
            yaml_path, n_runs, case_dir, pipeline_runner=pipeline_runner
        )
        case_results.append(case_result)

    # Aggregate summary
    passed = sum(1 for r in case_results if r["status"] == "passed")
    failed = sum(1 for r in case_results if r["status"] == "failed")
    skipped = sum(1 for r in case_results if r["status"] == "skipped")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_type": case_type,
        "cases_dir": str(cases_dir),
        "n_runs_per_case": n_runs,
        "summary": {
            "total": len(case_results),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "all_passed": passed == len(matching) and len(matching) > 0,
        },
        "thresholds": METRIC_THRESHOLDS,
        "cases": case_results,
    }
    return report


def _yaml_matches_case_type(yaml_path: Path, case_type: str) -> bool:
    """Return True if the YAML file's case_type matches the requested type.

    Checks both the filename prefix and the case_type field inside the YAML.
    """
    # Fast check: filename prefix (e.g. labor_dispute_1.yaml)
    if yaml_path.stem.startswith(case_type):
        return True

    # Slow check: read YAML and inspect case_type field
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("case_type") == case_type
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Report output
# ---------------------------------------------------------------------------


def write_report(report: dict, report_path: Path | None = None) -> Path:
    """Write the acceptance report JSON to disk.

    Args:
        report      : Report dict from run_acceptance().
        report_path : Override path. Defaults to outputs/acceptance/report_YYYYMMDD.json

    Returns:
        Path to written report file.
    """
    if report_path is None:
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        report_dir = _PROJECT_ROOT / "outputs" / "acceptance"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"report_{today}.json"

    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch case acceptance runner — runs N pipeline executions per case and computes acceptance metrics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/run_acceptance.py --case_type labor_dispute\n"
            "  python scripts/run_acceptance.py --case_type real_estate --runs 3\n"
            "  python scripts/run_acceptance.py --case_type labor_dispute --cases_dir cases/ --runs 1\n"
        ),
    )
    parser.add_argument(
        "--case_type",
        required=True,
        help="Case type to filter (e.g. labor_dispute, real_estate, civil_loan)",
    )
    parser.add_argument(
        "--cases_dir",
        default="cases",
        help="Directory containing case YAML files (default: cases/)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Number of pipeline runs per case (default: 5)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Override the intermediate output directory for pipeline runs",
    )
    parser.add_argument(
        "--report-path",
        default=None,
        help="Override the report JSON output path (default: outputs/acceptance/report_YYYYMMDD.json)",
    )
    args = parser.parse_args()

    cases_dir = Path(args.cases_dir)
    if not cases_dir.is_absolute():
        cases_dir = _PROJECT_ROOT / cases_dir

    output_dir = Path(args.output_dir) if args.output_dir else None
    report_path = Path(args.report_path) if args.report_path else None

    print(f"\n{'=' * 60}")
    print(f"Acceptance Run")
    print(f"  case_type : {args.case_type}")
    print(f"  cases_dir : {cases_dir}")
    print(f"  runs      : {args.runs}")
    print(f"{'=' * 60}")

    report = run_acceptance(
        case_type=args.case_type,
        cases_dir=cases_dir,
        n_runs=args.runs,
        output_dir=output_dir,
    )

    out_path = write_report(report, report_path)

    summary = report["summary"]
    print(f"\n{'=' * 60}")
    print(f"Acceptance Report")
    print(f"  Total cases : {summary['total']}")
    print(f"  Passed      : {summary['passed']}")
    print(f"  Failed      : {summary['failed']}")
    print(f"  Skipped     : {summary['skipped']}")
    print(f"  All passed  : {summary['all_passed']}")
    print(f"\nReport written to: {out_path}")
    print(f"{'=' * 60}\n")

    # Exit with non-zero code if any case failed
    if not summary["all_passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
