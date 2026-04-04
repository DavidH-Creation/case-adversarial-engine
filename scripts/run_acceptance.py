#!/usr/bin/env python3
"""
Batch case acceptance runner.

Runs N pipeline executions per case YAML and computes three mainline metrics:
- consistency: ordered issue-tree stability across runs
- citation_rate: non-empty evidence citation rate
- path_explainable: current branch/report artifacts are present and explainable
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
from typing import Callable

import yaml

# Windows UTF-8 guard
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))


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

MIN_VALID_RUNS = 3


def load_and_validate_yaml(yaml_path: Path) -> tuple[dict | None, str | None]:
    """Load a case YAML file and validate required fields."""
    try:
        with open(yaml_path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        return None, f"invalid_yaml: {exc}"
    except OSError as exc:
        return None, f"file_error: {exc}"

    if not isinstance(data, dict):
        return None, "yaml_not_dict"

    missing = [key for key in REQUIRED_YAML_KEYS if key not in data]
    if missing:
        return None, f"missing_keys:{','.join(missing)}"

    return data, None


def compute_metrics(run_results: list[dict]) -> dict:
    """Compute acceptance metrics from pipeline run results."""
    n_total = len(run_results)
    successful = [result for result in run_results if result.get("success", False)]
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

    consistency = _compute_issue_tree_stability(successful)
    citation_rate = _compute_citation_rate(successful)
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


def _compute_issue_tree_stability(successful_runs: list[dict], *, top_k: int = 5) -> float:
    """Measure stability using the most common ordered top-k issue sequence."""
    ordered_sequences = [
        tuple(run.get("issue_ids", [])[:top_k])
        for run in successful_runs
        if run.get("issue_ids")
    ]
    if not ordered_sequences:
        return 0.0

    most_common_count = Counter(ordered_sequences).most_common(1)[0][1]
    return most_common_count / len(successful_runs)


def _compute_citation_rate(successful_runs: list[dict]) -> float:
    """Measure how often output slots have non-empty evidence citations."""
    total_outputs = 0
    cited_outputs = 0

    for run in successful_runs:
        for citations in run.get("evidence_citations", []):
            total_outputs += 1
            if citations:
                cited_outputs += 1

    return cited_outputs / total_outputs if total_outputs > 0 else 0.0


def _check_path_explainability(successful_runs: list[dict]) -> bool:
    """Return True when current explainability artifacts satisfy the mainline contract."""
    for run in reversed(successful_runs):
        branch_artifacts = run.get("branch_artifacts")
        if branch_artifacts is not None:
            return (
                bool(branch_artifacts.get("report_present"))
                and bool(branch_artifacts.get("decision_tree_present"))
                and int(branch_artifacts.get("explainable_path_count", 0)) > 0
            )

        # Legacy fallback for older artifacts that still expose outcome_paths.
        paths = run.get("outcome_paths")
        if not paths:
            continue

        required_keys = ("win_path", "lose_path", "supplement_path")
        for path_key in required_keys:
            trigger_conditions = paths.get(path_key, {}).get(
                "trigger_conditions", ["insufficient_data"]
            )
            if not trigger_conditions or trigger_conditions == ["insufficient_data"]:
                return False
        return True

    return False


def extract_run_artifacts(output_dir: Path) -> dict:
    """Parse pipeline outputs for one run."""
    try:
        issue_ids: list[str] = []
        issue_tree_path = output_dir / "issue_tree.json"
        if issue_tree_path.exists():
            issue_tree = json.loads(issue_tree_path.read_text(encoding="utf-8"))
            issue_ids = [issue["issue_id"] for issue in issue_tree.get("issues", [])]

        evidence_citations: list[list[str]] = []
        result_path = output_dir / "result.json"
        if result_path.exists():
            result_data = json.loads(result_path.read_text(encoding="utf-8"))
            for round_data in result_data.get("rounds", []):
                for output in round_data.get("outputs", []):
                    evidence_citations.append(output.get("evidence_citations", []))

        outcome_paths: dict | None = None
        explainable_path_count = 0
        decision_tree_path = output_dir / "decision_tree.json"
        if decision_tree_path.exists():
            outcome_paths, explainable_path_count = _extract_decision_tree_artifacts(
                decision_tree_path,
                output_dir,
            )

        return {
            "success": True,
            "issue_ids": issue_ids,
            "evidence_citations": evidence_citations,
            "branch_artifacts": {
                "report_present": (output_dir / "report.md").exists(),
                "decision_tree_present": decision_tree_path.exists(),
                "explainable_path_count": explainable_path_count,
            },
            "outcome_paths": outcome_paths,
            "error": None,
        }
    except Exception as exc:
        return {
            "success": False,
            "issue_ids": [],
            "evidence_citations": [],
            "branch_artifacts": None,
            "outcome_paths": None,
            "error": str(exc),
        }


def _extract_decision_tree_artifacts(
    decision_tree_path: Path, output_dir: Path
) -> tuple[dict | None, int]:
    """Return legacy outcome paths plus current explainable-branch count."""
    from engines.report_generation.mediation_range import compute_mediation_range
    from engines.report_generation.outcome_paths import build_case_outcome_paths

    decision_tree_data = json.loads(decision_tree_path.read_text(encoding="utf-8"))
    explainable_path_count = sum(
        1
        for path in decision_tree_data.get("paths", [])
        if str(path.get("trigger_condition", "")).strip()
        and str(path.get("trigger_condition", "")).strip() != "insufficient_data"
    )

    amount_report = None
    amount_report_path = output_dir / "amount_report.json"
    if amount_report_path.exists():
        try:
            from engines.case_structuring.amount_calculator import AmountCalculationReport

            amount_report_data = json.loads(amount_report_path.read_text(encoding="utf-8"))
            amount_report = AmountCalculationReport.model_validate(amount_report_data)
        except Exception:
            amount_report = None

    mediation_range = compute_mediation_range(amount_report) if amount_report else None

    class _DictWrapper:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def __getattr__(self, key: str):
            return self._payload.get(key)

    outcome_paths = build_case_outcome_paths(_DictWrapper(decision_tree_data), mediation_range, None)
    return json.loads(outcome_paths.model_dump_json()), explainable_path_count


def _default_pipeline_runner(yaml_path: Path, run_index: int, output_dir: Path) -> dict:
    """Run the full pipeline via subprocess and return extracted artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(_PROJECT_ROOT / "scripts" / "run_case.py"),
        str(yaml_path),
        "--output-dir",
        str(output_dir),
        "--skip-pretrial",
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
        )
        if completed.returncode != 0:
            return {
                "success": False,
                "issue_ids": [],
                "evidence_citations": [],
                "branch_artifacts": None,
                "outcome_paths": None,
                "error": f"subprocess_exit_{completed.returncode}: {completed.stderr[-500:]}",
            }
        return extract_run_artifacts(output_dir)
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "issue_ids": [],
            "evidence_citations": [],
            "branch_artifacts": None,
            "outcome_paths": None,
            "error": "pipeline_timeout",
        }
    except Exception as exc:
        return {
            "success": False,
            "issue_ids": [],
            "evidence_citations": [],
            "branch_artifacts": None,
            "outcome_paths": None,
            "error": str(exc),
        }


def run_acceptance_for_case(
    yaml_path: Path,
    n_runs: int,
    base_output_dir: Path,
    pipeline_runner: Callable[[Path, int, Path], dict] | None = None,
) -> dict:
    """Run acceptance evaluation for a single case YAML."""
    runner = pipeline_runner or _default_pipeline_runner

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
    for run_index in range(n_runs):
        run_dir = base_output_dir / f"{case_slug}_run{run_index + 1}"
        print(f"    Run {run_index + 1}/{n_runs}...", end="", flush=True)
        result = runner(yaml_path, run_index, run_dir)
        run_results.append(result)
        status_symbol = "[OK]" if result["success"] else "[FAIL]"
        print(f" {status_symbol}")
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
                "run_index": index + 1,
                "success": result["success"],
                "error": result.get("error"),
                "issue_count": len(result.get("issue_ids", [])),
            }
            for index, result in enumerate(run_results)
        ],
    }


def run_acceptance(
    case_type: str,
    cases_dir: Path,
    n_runs: int = 5,
    *,
    pipeline_runner: Callable[[Path, int, Path], dict] | None = None,
    output_dir: Path | None = None,
) -> dict:
    """Run acceptance evaluation for all matching case YAMLs."""
    all_yamls = sorted(cases_dir.glob("*.yaml"))
    matching = [path for path in all_yamls if _yaml_matches_case_type(path, case_type)]

    if not matching:
        print(f"  [Warning] No YAML files found for case_type='{case_type}' in {cases_dir}")

    if output_dir is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        output_dir = _PROJECT_ROOT / "outputs" / "acceptance" / f"{case_type}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    case_results: list[dict] = []
    for yaml_path in matching:
        case_dir = output_dir / yaml_path.stem
        case_results.append(
            run_acceptance_for_case(
                yaml_path,
                n_runs,
                case_dir,
                pipeline_runner=pipeline_runner,
            )
        )

    passed = sum(1 for result in case_results if result["status"] == "passed")
    failed = sum(1 for result in case_results if result["status"] == "failed")
    skipped = sum(1 for result in case_results if result["status"] == "skipped")

    return {
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


def _yaml_matches_case_type(yaml_path: Path, case_type: str) -> bool:
    """Return True if a YAML file matches the requested case type."""
    if yaml_path.stem.startswith(case_type):
        return True

    try:
        with open(yaml_path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        return data.get("case_type") == case_type
    except Exception:
        return False


def write_report(report: dict, report_path: Path | None = None) -> Path:
    """Write the acceptance report JSON to disk."""
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch case acceptance runner.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/run_acceptance.py --case_type labor_dispute\n"
            "  python scripts/run_acceptance.py --case_type real_estate --runs 3\n"
            "  python scripts/run_acceptance.py --case_type civil_loan --cases_dir cases/ --runs 1\n"
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
        help="Override the report JSON output path",
    )
    args = parser.parse_args()

    report = run_acceptance(
        case_type=args.case_type,
        cases_dir=Path(args.cases_dir),
        n_runs=args.runs,
        output_dir=Path(args.output_dir) if args.output_dir else None,
    )
    path = write_report(report, Path(args.report_path) if args.report_path else None)
    print(f"\nAcceptance report written to: {path}")
    summary = report["summary"]
    print(
        "Summary: "
        f"total={summary['total']} "
        f"passed={summary['passed']} "
        f"failed={summary['failed']} "
        f"skipped={summary['skipped']}"
    )


if __name__ == "__main__":
    main()
