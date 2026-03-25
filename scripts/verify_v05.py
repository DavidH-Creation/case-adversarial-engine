"""
v0.5 自动化验收脚本。
Automated acceptance verification script for v0.5.

从 benchmarks/acceptance/v0_5_pass_criteria.json 读取版本元数据，
按 plans/current_plan.md 中描述的通过条件逐项检查。
Reads version metadata from v0_5_pass_criteria.json and checks all
pass conditions described in plans/current_plan.md.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# 颜色输出 / ANSI color output
# ---------------------------------------------------------------------------
_GREEN = "\033[32m"
_RED   = "\033[31m"
_RESET = "\033[0m"
_BOLD  = "\033[1m"


def _pass(msg: str) -> str:
    return f"{_GREEN}PASS{_RESET} {msg}"


def _fail(msg: str) -> str:
    return f"{_RED}FAIL{_RESET} {msg}"


# ---------------------------------------------------------------------------
# 个别检查 / Individual checks
# ---------------------------------------------------------------------------

def check_core_docs_exist() -> list[tuple[bool, str]]:
    """6 个核心文档全部存在。"""
    required = [
        "docs/00_north_star.md",
        "docs/01_product_roadmap.md",
        "docs/02_architecture.md",
        "docs/03_case_object_model.md",
        "docs/04_eval_and_acceptance.md",
        "plans/current_plan.md",
    ]
    results = []
    for rel in required:
        p = ROOT / rel
        ok = p.exists()
        results.append((ok, f"Core doc exists: {rel}"))
    return results


def check_current_plan_targets_v05() -> list[tuple[bool, str]]:
    """current_plan.md 当前目标为 v0.5。"""
    p = ROOT / "plans" / "current_plan.md"
    if not p.exists():
        return [(False, "current_plan.md not found")]
    text = p.read_text(encoding="utf-8")
    ok = "v0.5" in text and ("当前目标" in text or "current" in text.lower())
    return [(ok, "current_plan.md targets v0.5")]


def check_case_object_model_complete() -> list[tuple[bool, str]]:
    """docs/03_case_object_model.md 定义完整核心对象。"""
    p = ROOT / "docs" / "03_case_object_model.md"
    if not p.exists():
        return [(False, "03_case_object_model.md not found")]
    text = p.read_text(encoding="utf-8")
    required_objects = [
        "Party",
        "Claim",
        "Defense",
        "Issue",
        "Evidence",
        "Burden",
        "ProcedureState",
        "AgentOutput",
    ]
    results = []
    for obj in required_objects:
        ok = obj in text
        results.append((ok, f"Core object defined in docs/03: {obj}"))
    return results


def check_hard_fail_defined() -> list[tuple[bool, str]]:
    """docs/04_eval_and_acceptance.md 明确 hard fail 条件。"""
    p = ROOT / "docs" / "04_eval_and_acceptance.md"
    if not p.exists():
        return [(False, "04_eval_and_acceptance.md not found")]
    text = p.read_text(encoding="utf-8")
    # Must contain hard fail / Hard Fail keywords
    ok = bool(re.search(r"[Hh]ard [Ff]ail|HARD_FAIL|hard_fail", text))
    return [(ok, "04_eval_and_acceptance.md defines hard fail conditions")]


def check_hard_fail_json_conditions() -> list[tuple[bool, str]]:
    """v0_5_pass_criteria.json 的 hard_fail_conditions 至少 6 条。"""
    criteria_path = ROOT / "benchmarks" / "acceptance" / "v0_5_pass_criteria.json"
    if not criteria_path.exists():
        return [(False, "v0_5_pass_criteria.json not found")]
    data = json.loads(criteria_path.read_text(encoding="utf-8"))
    conditions = data.get("hard_fail_conditions", [])
    ok = len(conditions) >= 6
    return [(ok, f"v0_5_pass_criteria.json has {len(conditions)} hard_fail_conditions (need >=6)")]


def check_acceptance_criteria_version() -> list[tuple[bool, str]]:
    """v0_5_pass_criteria.json 版本字段为 v0.5。"""
    criteria_path = ROOT / "benchmarks" / "acceptance" / "v0_5_pass_criteria.json"
    if not criteria_path.exists():
        return [(False, "v0_5_pass_criteria.json not found")]
    data = json.loads(criteria_path.read_text(encoding="utf-8"))
    ok = data.get("version") == "v0.5"
    return [(ok, f"v0_5_pass_criteria.json version = {data.get('version')!r} (need 'v0.5')")]


def check_engineering_skeleton() -> list[tuple[bool, str]]:
    """最小工程骨架目录全部存在。"""
    required_dirs = [
        "schemas",
        "schemas/case",
        "schemas/procedure",
        "schemas/reporting",
        "engines",
        "engines/case_structuring",
        "engines/procedure_setup",
        "engines/simulation_run",
        "engines/report_generation",
        "engines/interactive_followup",
        "engines/shared",
        "benchmarks",
        "benchmarks/fixtures",
        "benchmarks/acceptance",
        "tests",
        "tests/integration",
        ".bulwark",
        ".bulwark/tasks",
        ".bulwark/policies",
    ]
    results = []
    for rel in required_dirs:
        p = ROOT / rel
        ok = p.is_dir()
        results.append((ok, f"Directory exists: {rel}/"))
    return results


def check_bulwark_tasks_exist() -> list[tuple[bool, str]]:
    """.bulwark/tasks/ 至少有 1 个 task contract 文件。"""
    tasks_dir = ROOT / ".bulwark" / "tasks"
    if not tasks_dir.exists():
        return [(False, ".bulwark/tasks/ directory not found")]
    task_files = list(tasks_dir.glob("*.yaml"))
    ok = len(task_files) >= 1
    return [(ok, f".bulwark/tasks/ has {len(task_files)} task contract(s) (need >=1)")]


def check_acceptance_json_parseable() -> list[tuple[bool, str]]:
    """v0_5_pass_criteria.json 可被正常解析（格式合法）。"""
    criteria_path = ROOT / "benchmarks" / "acceptance" / "v0_5_pass_criteria.json"
    if not criteria_path.exists():
        return [(False, "v0_5_pass_criteria.json not found")]
    try:
        json.loads(criteria_path.read_text(encoding="utf-8"))
        return [(True, "v0_5_pass_criteria.json is valid JSON")]
    except json.JSONDecodeError as exc:
        return [(False, f"v0_5_pass_criteria.json is NOT valid JSON: {exc}")]


# ---------------------------------------------------------------------------
# 主程序 / Main
# ---------------------------------------------------------------------------

def run_all_checks() -> int:
    """Run all checks and print results. Returns exit code (0=pass, 1=fail)."""
    check_groups = [
        ("Core documents", check_core_docs_exist),
        ("Current plan target", check_current_plan_targets_v05),
        ("Case object model completeness", check_case_object_model_complete),
        ("Hard fail definition", check_hard_fail_defined),
        ("Acceptance criteria JSON", check_acceptance_json_parseable),
        ("Acceptance criteria version", check_acceptance_criteria_version),
        ("Hard fail conditions (>=6)", check_hard_fail_json_conditions),
        ("Engineering skeleton", check_engineering_skeleton),
        ("Bulwark task contracts", check_bulwark_tasks_exist),
    ]

    all_results: list[tuple[bool, str]] = []

    print(f"\n{_BOLD}=== v0.5 Acceptance Verification ==={_RESET}\n")
    for group_name, check_fn in check_groups:
        print(f"{_BOLD}{group_name}{_RESET}")
        results = check_fn()
        for ok, msg in results:
            print(f"  {_pass(msg) if ok else _fail(msg)}")
            all_results.append((ok, msg))
        print()

    passed = sum(1 for ok, _ in all_results if ok)
    total  = len(all_results)
    failed = total - passed

    if failed == 0:
        print(f"{_GREEN}{_BOLD}ALL {total} CHECKS PASSED{_RESET}")
        return 0
    else:
        print(f"{_RED}{_BOLD}FAILED {failed}/{total} CHECKS{_RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_checks())
