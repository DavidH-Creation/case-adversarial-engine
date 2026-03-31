#!/usr/bin/env python3
"""
案件文本 → YAML 提取工具
Case text → YAML extraction CLI

从起诉书、案情摘要或裁判文书文本中自动提取案件结构化信息，
输出兼容 cases/ schema 的 YAML 文件。

Automatically extracts structured case information from complaint text,
case summaries, or judgment documents, outputting YAML compatible with
the cases/ schema.

Usage:
    # 从标准输入读取
    echo "原告老王诉被告小陈借款20万元..." | python scripts/extract_case_yaml.py

    # 从文件读取
    python scripts/extract_case_yaml.py --input my_complaint.txt

    # 指定输出文件
    python scripts/extract_case_yaml.py --input complaint.txt --output cases/new_case.yaml

    # 指定案件 slug
    python scripts/extract_case_yaml.py --input complaint.txt --slug wang-v-li-2025

    # 指定模型
    python scripts/extract_case_yaml.py --input complaint.txt --model claude-opus-4-6
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

# 确保项目根目录在 sys.path
# Ensure project root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from engines.case_extraction import CaseExtractor  # noqa: E402

logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="从法律文本提取案件 YAML（Extract case YAML from legal text）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input", "-i",
        metavar="FILE",
        help="输入文件路径（默认从 stdin 读取）/ Input file path (default: stdin)",
    )
    parser.add_argument(
        "--output", "-o",
        metavar="FILE",
        help="输出 YAML 文件路径（默认输出到 stdout）/ Output YAML file path (default: stdout)",
    )
    parser.add_argument(
        "--slug",
        default="",
        help="案件标识符，用于生成 case_id / Case identifier for case_id generation",
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        help="LLM 模型名称（默认 claude-sonnet-4-6）/ LLM model name",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细日志 / Show verbose logs",
    )
    return parser.parse_args()


def _read_input(input_path: str | None) -> str:
    if input_path:
        path = Path(input_path)
        if not path.exists():
            print(f"错误：输入文件不存在 / Error: Input file not found: {input_path}", file=sys.stderr)
            sys.exit(1)
        return path.read_text(encoding="utf-8")
    else:
        if sys.stdin.isatty():
            print(
                "请输入案件文本（输入完成后按 Ctrl+D / Ctrl+Z+Enter 结束）：\n"
                "Please enter case text (press Ctrl+D / Ctrl+Z+Enter when done):\n",
                file=sys.stderr,
            )
        return sys.stdin.read()


async def _run(args: argparse.Namespace) -> int:
    # 读取输入文本 / Read input text
    text = _read_input(args.input)
    if not text.strip():
        print("错误：输入文本为空 / Error: Input text is empty", file=sys.stderr)
        return 1

    # 初始化 LLM 客户端 / Initialize LLM client
    try:
        from engines.shared.models import AnthropicSDKClient
        llm_client = AnthropicSDKClient()
    except Exception as exc:
        print(
            f"错误：无法初始化 LLM 客户端 / Error: Cannot initialize LLM client: {exc}\n"
            "请检查 ANTHROPIC_API_KEY 环境变量。\n"
            "Please check the ANTHROPIC_API_KEY environment variable.",
            file=sys.stderr,
        )
        return 1

    extractor = CaseExtractor(llm_client, model=args.model)

    print("正在提取案件信息... / Extracting case information...", file=sys.stderr)

    try:
        result = await extractor.extract(text)
    except ValueError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"LLM 调用失败 / LLM call failed: {exc}", file=sys.stderr)
        return 1

    yaml_str = extractor.to_yaml(result, case_slug=args.slug)

    # 输出结果 / Output result
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(yaml_str, encoding="utf-8")
        print(f"已保存到 / Saved to: {out_path}", file=sys.stderr)

        # 打印摘要 / Print summary
        _print_summary(result)
    else:
        print(yaml_str)

    return 0


def _print_summary(result) -> None:
    """打印提取摘要到 stderr。Print extraction summary to stderr."""
    unknown_count = len(result.unknown_fields)
    print("\n--- 提取摘要 / Extraction Summary ---", file=sys.stderr)
    print(f"案件类型 / Case type:  {result.case_type}", file=sys.stderr)
    print(f"原告 / Plaintiff:      {result.plaintiff.name}", file=sys.stderr)
    defendants_str = ", ".join(d.name for d in result.defendants)
    print(f"被告 / Defendants:     {defendants_str}", file=sys.stderr)
    print(f"诉讼请求数 / Claims:   {len(result.claims)}", file=sys.stderr)
    print(f"证据数 / Evidence:     {len(result.evidence_list)}", file=sys.stderr)
    if result.disputed_amount.is_ambiguous:
        print(
            f"争议金额 / Amount:     ambiguous — {result.disputed_amount.amounts}",
            file=sys.stderr,
        )
    else:
        print(
            f"争议金额 / Amount:     {result.disputed_amount.amounts}",
            file=sys.stderr,
        )
    if unknown_count:
        print(
            f"待确认字段 / TODO fields ({unknown_count}): {', '.join(result.unknown_fields)}",
            file=sys.stderr,
        )
    print("-------------------------------------", file=sys.stderr)


def main() -> None:
    args = _parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    exit_code = asyncio.run(_run(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
