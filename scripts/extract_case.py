#!/usr/bin/env python3
"""
Extract structured case YAML from raw Chinese legal documents.

Usage:
    python scripts/extract_case.py complaint.txt defense.txt -o cases/new_case.yaml
    python scripts/extract_case.py docs/*.txt --model claude-opus-4-6
    python scripts/extract_case.py complaint.txt --case-id my-case-001
"""

from __future__ import annotations

import argparse
import asyncio
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

from engines.case_structuring.case_extractor import CaseExtractor
from engines.shared.cli_adapter import CLINotFoundError, ClaudeCLIClient
from engines.shared.model_selector import ModelSelector


async def main(
    input_files: list[str],
    output_path: str | None = None,
    model_override: str | None = None,
    model_config: str | None = None,
    case_id: str | None = None,
    validate_only: bool = False,
) -> None:
    # Read input files
    documents: list[tuple[str, str]] = []
    for fpath in input_files:
        p = Path(fpath)
        if not p.exists():
            print(f"[Error] File not found: {fpath}")
            sys.exit(1)
        text = p.read_text(encoding="utf-8")
        if not text.strip():
            print(f"[Warning] Empty file skipped: {fpath}")
            continue
        documents.append((p.name, text))

    if not documents:
        print("[Error] No non-empty input files provided")
        sys.exit(1)

    print(f"[Input] {len(documents)} document(s) loaded:")
    for fname, text in documents:
        print(f"  - {fname} ({len(text)} chars)")

    # Initialize model selector
    if model_config:
        selector = ModelSelector.from_yaml(model_config, model_override=model_override)
    else:
        _default_cfg = _PROJECT_ROOT / "config" / "model_tiers.yaml"
        if _default_cfg.exists():
            selector = ModelSelector.from_yaml(_default_cfg, model_override=model_override)
        else:
            selector = ModelSelector(model_override=model_override)

    model = selector.select("issue_extractor")  # balanced tier
    print(f"[Model] Using {model}")

    # Create LLM client and extractor
    claude = ClaudeCLIClient(timeout=600.0)
    extractor = CaseExtractor(llm_client=claude, model=model)

    print("[Extract] Running LLM extraction...")
    result = await extractor.extract(documents, case_id=case_id)

    # Validate
    errors = CaseExtractor.validate(result)
    if errors:
        print(f"\n[Validation] {len(errors)} issue(s) found:")
        for err in errors:
            print(f"  ⚠ {err}")
    else:
        print("[Validation] All pipeline requirements met ✓")

    if result.missing_fields:
        print(f"\n[Missing] Fields that need manual review:")
        for field in result.missing_fields:
            print(f"  - {field}")

    if validate_only:
        print("\n[Done] Validation-only mode, no output written.")
        return

    # Serialize to YAML
    yaml_str = CaseExtractor.to_yaml(result)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(yaml_str, encoding="utf-8")
        print(f"\n[Output] Written to {out}")
        print(f"[Next] Run: python scripts/run_case.py {out}")
    else:
        print("\n--- Extracted YAML ---")
        print(yaml_str)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract structured case YAML from raw legal documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/extract_case.py complaint.txt defense.txt -o cases/new_case.yaml\n"
            "  python scripts/extract_case.py docs/*.txt --model claude-opus-4-6\n"
            "  python scripts/extract_case.py complaint.txt --case-id my-case-001"
        ),
    )
    parser.add_argument(
        "input_files",
        nargs="+",
        help="Path(s) to raw legal document text files",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output YAML file path (default: print to stdout)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override LLM model (default: balanced tier from config)",
    )
    parser.add_argument(
        "--model-config",
        default=None,
        help="Path to model tier config YAML",
    )
    parser.add_argument(
        "--case-id",
        default=None,
        help="Override auto-generated case ID",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Extract and validate, but don't write output",
    )
    args = parser.parse_args()

    try:
        asyncio.run(
            main(
                args.input_files,
                output_path=args.output,
                model_override=args.model,
                model_config=args.model_config,
                case_id=args.case_id,
                validate_only=args.validate_only,
            )
        )
    except CLINotFoundError as e:
        print(f"\n[Error] CLI not available: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[Interrupted] User cancelled.")
        sys.exit(0)
