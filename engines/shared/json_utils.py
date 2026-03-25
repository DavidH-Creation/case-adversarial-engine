"""
共享 JSON 解析工具 / Shared JSON parsing utilities.

供四个引擎共用，避免重复实现。
Shared across all four engines to avoid duplication.
"""

from __future__ import annotations

import json
import re


def _extract_json_object(text: str) -> dict:
    """从 LLM 响应中提取 JSON 对象。
    Extract a JSON object from LLM response text.

    依次尝试：markdown 代码块 → 直接解析 → 大括号匹配。
    Tries in order: markdown code block → direct parse → brace extraction.
    """
    # markdown 代码块 / Markdown code block
    code_block_pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?\s*```"
    match = re.search(code_block_pattern, text)
    if match:
        candidate = match.group(1).strip()
        try:
            result = json.loads(candidate)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    # 直接解析 / Direct parse
    try:
        result = json.loads(text.strip())
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # 大括号提取 / Brace extraction
    brace_pattern = r"\{[\s\S]*\}"
    match = re.search(brace_pattern, text)
    if match:
        try:
            result = json.loads(match.group(0))
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"无法从 LLM 响应中解析 JSON 对象 / Cannot parse JSON object: {text[:200]}"
    )


def _extract_json_array(text: str) -> list[dict]:
    """从 LLM 响应中提取 JSON 数组。
    Extract a JSON array from LLM response text.

    依次尝试：markdown 代码块 → 直接解析 → 方括号匹配。
    Tries in order: markdown code block → direct parse → bracket extraction.
    """
    # 尝试提取 markdown 代码块中的 JSON / Try extracting from markdown code block
    code_block_pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?\s*```"
    match = re.search(code_block_pattern, text)
    if match:
        candidate = match.group(1).strip()
        try:
            result = json.loads(candidate)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    # 尝试直接解析整个文本 / Try parsing entire text directly
    try:
        result = json.loads(text.strip())
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # 尝试提取方括号包裹的内容 / Try extracting bracket-wrapped content
    bracket_pattern = r"\[[\s\S]*\]"
    match = re.search(bracket_pattern, text)
    if match:
        try:
            result = json.loads(match.group(0))
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法从 LLM 响应中解析 JSON 数组: {text[:200]}")
