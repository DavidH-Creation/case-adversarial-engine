#!/usr/bin/env python3
"""
Smoke-test script for Codex CLI subprocess integration.

Verifies that CodexCLIClient can successfully invoke `codex exec` via
subprocess with stdin-piped prompts (including Chinese text).

Usage:
    python scripts/test_codex_cli.py
    python scripts/test_codex_cli.py --model gpt-5.4
    python scripts/test_codex_cli.py --timeout 30

Exit codes:
    0 — all checks passed
    1 — one or more checks failed
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import sys
import time
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

from engines.shared.cli_adapter import CLICallError, CLINotFoundError, CodexCLIClient


def _print_result(name: str, passed: bool, detail: str = "") -> None:
    mark = "\u2713" if passed else "\u2717"
    suffix = f" — {detail}" if detail else ""
    print(f"  [{mark}] {name}{suffix}")


async def _run_checks(model: str | None, timeout: float) -> list[bool]:
    results: list[bool] = []

    # --- Check 0: codex binary exists ---
    codex_path = shutil.which("codex")
    ok = codex_path is not None
    _print_result("codex in PATH", ok, codex_path or "NOT FOUND")
    results.append(ok)
    if not ok:
        print("\n  FATAL: codex not in PATH, cannot continue.")
        return results

    # --- Check 1: CodexCLIClient with no model (uses codex config default) ---
    client = CodexCLIClient(timeout=timeout)
    try:
        t0 = time.monotonic()
        resp = await client.create_message(
            system="",
            user="Reply with exactly: CODEX_OK",
            model="claude-sonnet-4-6",  # intentionally wrong — should be ignored
        )
        elapsed = time.monotonic() - t0
        ok = "CODEX_OK" in resp.upper()
        _print_result(
            "No -m flag (codex config default)",
            ok,
            f"{elapsed:.1f}s, response={resp[:80]!r}",
        )
    except Exception as exc:
        _print_result("No -m flag (codex config default)", False, str(exc)[:120])
        ok = False
    results.append(ok)

    # --- Check 2: CodexCLIClient with explicit model ---
    if model:
        client2 = CodexCLIClient(timeout=timeout, model=model)
        try:
            t0 = time.monotonic()
            resp = await client2.create_message(system="", user="Reply with exactly: MODEL_OK")
            elapsed = time.monotonic() - t0
            ok = "MODEL_OK" in resp.upper()
            _print_result(
                f"Explicit -m {model}",
                ok,
                f"{elapsed:.1f}s, response={resp[:80]!r}",
            )
        except Exception as exc:
            _print_result(f"Explicit -m {model}", False, str(exc)[:120])
            ok = False
        results.append(ok)

    # --- Check 3: Chinese text round-trip ---
    try:
        t0 = time.monotonic()
        resp = await client.create_message(
            system="你是一个助手",
            user='用中文回复"收到"两个字',
        )
        elapsed = time.monotonic() - t0
        ok = len(resp) > 0
        _print_result(
            "Chinese text round-trip",
            ok,
            f"{elapsed:.1f}s, response={resp[:80]!r}",
        )
    except Exception as exc:
        _print_result("Chinese text round-trip", False, str(exc)[:120])
        ok = False
    results.append(ok)

    # --- Check 4: caller's model kwarg is ignored (not sent to codex) ---
    # Pass a Claude model name; should NOT cause an error since it's ignored
    client3 = CodexCLIClient(timeout=timeout)  # no _default_model
    try:
        resp = await client3.create_message(
            system="",
            user="Reply OK",
            model="claude-opus-4-6",  # should be ignored
        )
        ok = len(resp) > 0
        _print_result("Ignores caller model kwarg", ok, f"response={resp[:60]!r}")
    except Exception as exc:
        _print_result("Ignores caller model kwarg", False, str(exc)[:120])
        ok = False
    results.append(ok)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test Codex CLI integration")
    parser.add_argument(
        "--model", default=None, help="Explicit model to test with -m flag (e.g. gpt-5.4)"
    )
    parser.add_argument("--timeout", type=float, default=60.0, help="Timeout per call in seconds")
    args = parser.parse_args()

    print("Codex CLI integration smoke test\n")
    results = asyncio.run(_run_checks(args.model, args.timeout))

    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 40}")
    print(f"Results: {passed}/{total} passed")

    if all(results):
        print("All checks passed.")
        sys.exit(0)
    else:
        print("SOME CHECKS FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
