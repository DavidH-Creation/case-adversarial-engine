"""
共享 JSON 解析工具 / Shared JSON parsing utilities.

供四个引擎共用，避免重复实现。
Shared across all four engines to avoid duplication.
"""

from __future__ import annotations

import json
import re


def _repair_json_string(text: str) -> str:
    """简单修复 LLM 生成的 JSON 中的常见问题。
    Simple repair for common LLM JSON formatting issues.

    仅处理 JSON 字符串值内未转义双引号的情况。
    Only handles unescaped double quotes inside JSON string values.
    """
    # 将字符串值内的未转义双引号替换为中文引号（避免破坏 JSON 结构）
    # Replace unescaped double quotes inside string values with Chinese quotes
    # Strategy: find string values and escape internal quotes
    result = []
    i = 0
    in_string = False
    prev_char = ""
    while i < len(text):
        c = text[i]
        if c == '"' and prev_char != "\\":
            if not in_string:
                in_string = True
                result.append(c)
            else:
                # Could be end of string or unescaped quote inside string
                # Peek ahead to see if this looks like a valid JSON delimiter
                # (followed by : , ] } whitespace)
                j = i + 1
                while j < len(text) and text[j] in " \t\r\n":
                    j += 1
                next_meaningful = text[j] if j < len(text) else ""
                if next_meaningful in (": ", ":", ",", "]", "}", ""):
                    in_string = False
                    result.append(c)
                else:
                    # Unescaped quote inside string - escape it
                    result.append('\\"')
        else:
            result.append(c)
        prev_char = c
        i += 1
    return "".join(result)


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
            try:
                result = json.loads(_repair_json_string(candidate))
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
            try:
                result = json.loads(_repair_json_string(match.group(0)))
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass

    # 截断恢复 / Truncation recovery: LLM may hit max_tokens, leaving incomplete JSON
    # Find the first '{' and try closing unclosed brackets/braces
    first_brace = text.find("{")
    if first_brace >= 0:
        fragment = text[first_brace:]
        # Remove trailing incomplete string (cut at last complete value)
        # Then close all unclosed brackets/braces
        open_braces = fragment.count("{") - fragment.count("}")
        open_brackets = fragment.count("[") - fragment.count("]")
        if open_braces > 0 or open_brackets > 0:
            # Trim trailing incomplete tokens (partial strings, keys)
            # Find last comma or colon, truncate after it, then close
            for trim_pat in (r',\s*"[^"]*$', r',\s*$', r':\s*"[^"]*$', r':\s*$'):
                trimmed = re.sub(trim_pat, "", fragment)
                if trimmed != fragment:
                    fragment = trimmed
                    break
            closing = "]" * max(0, open_brackets) + "}" * max(0, open_braces)
            candidate = fragment + closing
            try:
                result = json.loads(candidate)
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
            # 尝试修复后再解析 / Try with repair
            try:
                result = json.loads(_repair_json_string(candidate))
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
            # 尝试修复后再解析 / Try with repair
            try:
                result = json.loads(_repair_json_string(match.group(0)))
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

    raise ValueError(f"无法从 LLM 响应中解析 JSON 数组: {text[:200]}")
