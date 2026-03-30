#!/usr/bin/env python3
"""
Scenario Engine what-if analysis CLI.

Usage:
    python scripts/run_scenario.py --baseline outputs/<run>/ --change-set changes.yaml
    python scripts/run_scenario.py --baseline outputs/v3/ --change-set scenarios/remove_evidence.yaml --model claude-sonnet-4-6

Output:
    outputs/<run>/scenario_<id>/diff_summary.json
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
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
sys.path.insert(0, str(_PROJECT_ROOT))

from engines.shared.cli_adapter import CLINotFoundError, ClaudeCLIClient  # noqa: E402
from engines.simulation_run.simulator import (  # noqa: E402
    load_baseline,
    parse_change_set,
    run_whatif,
)

DEFAULT_MODEL = "claude-sonnet-4-6"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scenario Engine what-if analysis — "
        "apply a change set to a baseline run and generate a diff summary.",
    )
    parser.add_argument(
        "--baseline",
        required=True,
        help="Path to baseline run output directory (e.g. outputs/v3/)",
    )
    parser.add_argument(
        "--change-set",
        required=True,
        help="Path to change_set YAML file",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"LLM model name (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--case-type",
        default="civil_loan",
        help="Case type / prompt profile (default: civil_loan)",
    )
    parser.add_argument(
        "--workspace-id",
        default="workspace-default",
        help="Workspace ID (default: workspace-default)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser


async def _main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # Logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    baseline = Path(args.baseline)
    change_set = Path(args.change_set)

    # Validate inputs exist before constructing LLM client
    print(f"\n[Scenario Engine] what-if analysis")
    print(f"  Baseline: {baseline}")
    print(f"  Change set: {change_set}")
    print(f"  Model: {args.model}")

    # Pre-validate: load baseline and change_set to fail fast
    issue_tree, evidence_index, baseline_run_id = load_baseline(baseline)
    print(f"  \u2713 Loaded baseline: {len(issue_tree.issues)} issues, "
          f"{len(evidence_index.evidence)} evidence items")

    scenario_id, change_items = parse_change_set(change_set)
    print(f"  \u2713 Parsed change set: scenario={scenario_id}, "
          f"{len(change_items)} changes")

    # Build LLM client
    try:
        llm_client = ClaudeCLIClient(timeout=300.0)
    except CLINotFoundError:
        print("\n[Error] Claude CLI not found. Install claude CLI or set PATH.")
        sys.exit(1)

    # Run what-if analysis
    print(f"\n[Step 1] Running scenario simulation...")
    result = await run_whatif(
        baseline_dir=baseline,
        change_set_path=change_set,
        llm_client=llm_client,
        case_type=args.case_type,
        model=args.model,
        workspace_id=args.workspace_id,
    )

    # Report result
    scenario = result.scenario
    if scenario.status.value == "failed":
        print(f"\n[Result] Simulation FAILED for scenario {scenario.scenario_id}")
        sys.exit(1)

    print(f"\n[Result] Simulation completed")
    print(f"  Scenario ID: {scenario.scenario_id}")
    print(f"  Status: {scenario.status.value}")
    print(f"  Affected issues: {len(scenario.affected_issue_ids)}")
    for iid in scenario.affected_issue_ids:
        print(f"    - {iid}")
    print(f"  Diff entries: {len(scenario.diff_summary)}")
    for entry in scenario.diff_summary:
        print(f"    [{entry.direction.value}] {entry.issue_id}: "
              f"{entry.impact_description[:80]}")

    out_path = baseline / f"scenario_{scenario.scenario_id}" / "diff_summary.json"
    print(f"\n  Output: {out_path}")


if __name__ == "__main__":
    asyncio.run(_main())
