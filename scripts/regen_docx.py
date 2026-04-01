#!/usr/bin/env python3
"""Regenerate DOCX from existing report_v3.json (no re-analysis needed).

Usage:
    python scripts/regen_docx.py [output_dir]

    output_dir: path to output directory containing report_v3.json
                (default: outputs/20260401-090617)
"""

import json
import os
import sys
from pathlib import Path

# Windows UTF-8 fix
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent.parent))

from engines.report_generation.docx_generator import generate_docx_v3_report


def main() -> None:
    if len(sys.argv) > 1:
        out_dir = Path(sys.argv[1])
    else:
        out_dir = Path(__file__).parent.parent / "outputs" / "20260401-090617"

    if not out_dir.exists():
        print(f"ERROR: output directory not found: {out_dir}", file=sys.stderr)
        sys.exit(1)

    report_v3_path = out_dir / "report_v3.json"
    if not report_v3_path.exists():
        print(f"ERROR: report_v3.json not found in {out_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading report_v3.json from {out_dir} ...")
    report_v3 = json.loads(report_v3_path.read_text(encoding="utf-8"))

    # Load similar_cases.json if available (preferred over keyword variant)
    similar_cases: list | None = None
    for fname in ("similar_cases.json", "similar_cases_keyword.json"):
        sc_path = out_dir / fname
        if sc_path.exists():
            similar_cases = json.loads(sc_path.read_text(encoding="utf-8"))
            print(f"Loaded {len(similar_cases)} similar cases from {fname}")
            break

    print("Generating DOCX ...")
    dest = generate_docx_v3_report(
        output_dir=out_dir,
        report_v3=report_v3,
        similar_cases=similar_cases,
        filename="\u5bf9\u6297\u5206\u6790\u62a5\u544a_v3.docx",
    )
    print(f"Saved: {dest}")
    print(f"Size:  {dest.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
