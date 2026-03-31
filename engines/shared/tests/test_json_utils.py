"""
json_utils 单元测试 / Unit tests for json_utils.

覆盖：
- _repair_json_string 关键场景
- _extract_json_object 截断恢复路径（open_braces > 0）
- _extract_json_array 正常路径

Tests cover:
- _repair_json_string key scenarios
- _extract_json_object truncation-recovery path (open_braces > 0)
- _extract_json_array happy path
"""

from __future__ import annotations

import pytest

from engines.shared.json_utils import (
    _extract_json_array,
    _extract_json_object,
    _repair_json_string,
)


# ---------------------------------------------------------------------------
# _repair_json_string
# ---------------------------------------------------------------------------


class TestRepairJsonString:
    """_repair_json_string 的关键场景。"""

    def test_valid_json_unchanged(self) -> None:
        """纯净的 JSON 字符串经过修复后应保持不变。"""
        raw = '{"key": "value", "num": 42}'
        assert _repair_json_string(raw) == raw

    def test_escapes_unescaped_quote_inside_string_value(self) -> None:
        """字符串值内的未转义双引号应被修复，使整体可被 json.loads 解析。"""
        import json

        # Build a raw string that has an unescaped internal quote
        # e.g.  {"note": "he said "hello" to me"}
        raw = '{"note": "he said "hello" to me"}'
        repaired = _repair_json_string(raw)
        # After repair it must be parseable
        result = json.loads(repaired)
        assert "note" in result

    def test_empty_string_unchanged(self) -> None:
        """空字符串输入应返回空字符串。"""
        assert _repair_json_string("") == ""

    def test_no_string_values(self) -> None:
        """没有字符串值的 JSON（只有数字）应保持不变。"""
        raw = '{"a": 1, "b": 2}'
        assert _repair_json_string(raw) == raw

    def test_nested_json_unchanged(self) -> None:
        """嵌套结构不破坏正常 JSON。"""
        import json

        raw = '{"outer": {"inner": "value"}, "arr": [1, 2]}'
        repaired = _repair_json_string(raw)
        assert json.loads(repaired) == json.loads(raw)

    def test_escaped_backslash_not_double_escaped(self) -> None:
        """已正确转义的引号不应被二次转义。"""
        import json

        raw = r'{"key": "say \" hello"}'
        repaired = _repair_json_string(raw)
        # The \" inside is already escaped — result must still be parseable
        result = json.loads(repaired)
        assert "key" in result


# ---------------------------------------------------------------------------
# _extract_json_object — 截断恢复路径 / Truncation recovery
# ---------------------------------------------------------------------------


class TestExtractJsonObjectTruncation:
    """截断恢复路径：LLM 因 max_tokens 被截断导致 JSON 不完整时，引擎能恢复。"""

    def test_truncated_after_value(self) -> None:
        """最外层 brace 未闭合的片段能恢复出已有的键值。"""
        truncated = '{"title": "测试标题", "score": 95'
        result = _extract_json_object(truncated)
        assert result["title"] == "测试标题"
        assert result["score"] == 95

    def test_truncated_mid_key(self) -> None:
        """中途截断在键名后（无值）时也能恢复至少前一个完整键值对。"""
        truncated = '{"a": 1, "b": 2, "incomplet'
        result = _extract_json_object(truncated)
        assert result["a"] == 1
        assert result["b"] == 2

    def test_truncated_nested_object(self) -> None:
        """嵌套结构的截断也能恢复外层已完成的字段。"""
        truncated = '{"outer": 42, "inner": {"x": 1'
        result = _extract_json_object(truncated)
        # outer is complete and recoverable
        assert result["outer"] == 42

    def test_nested_array_truncated(self) -> None:
        """含数组的 JSON 被截断时能恢复已有内容。"""
        truncated = '{"items": [1, 2, 3'
        result = _extract_json_object(truncated)
        assert "items" in result

    def test_complete_json_still_parses(self) -> None:
        """完整 JSON 经截断恢复路径仍能正确解析。"""
        complete = '{"key": "val", "num": 7}'
        result = _extract_json_object(complete)
        assert result == {"key": "val", "num": 7}

    def test_no_json_raises_value_error(self) -> None:
        """完全无 JSON 内容时应抛 ValueError。"""
        with pytest.raises(ValueError, match="无法从 LLM 响应中解析"):
            _extract_json_object("没有任何 JSON 结构的纯文本")

    def test_markdown_code_block_extraction(self) -> None:
        """从 markdown 代码块中提取 JSON 对象。"""
        text = '结果如下：\n```json\n{"status": "ok"}\n```'
        result = _extract_json_object(text)
        assert result == {"status": "ok"}

    def test_surrounding_text_extraction(self) -> None:
        """含前后文时能提取内嵌 JSON 对象。"""
        text = '分析完毕。{"verdict": "supported"}结束。'
        result = _extract_json_object(text)
        assert result["verdict"] == "supported"


# ---------------------------------------------------------------------------
# _extract_json_array — 基本路径
# ---------------------------------------------------------------------------


class TestExtractJsonArray:
    """_extract_json_array 基本路径。"""

    def test_direct_array(self) -> None:
        result = _extract_json_array('[{"id": "a"}, {"id": "b"}]')
        assert len(result) == 2
        assert result[0]["id"] == "a"

    def test_array_in_markdown_code_block(self) -> None:
        text = '```json\n[{"x": 1}]\n```'
        result = _extract_json_array(text)
        assert result == [{"x": 1}]

    def test_array_with_surrounding_text(self) -> None:
        text = '前缀文字 [{"k": "v"}] 后缀'
        result = _extract_json_array(text)
        assert result[0]["k"] == "v"

    def test_no_array_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            _extract_json_array("no array here")
