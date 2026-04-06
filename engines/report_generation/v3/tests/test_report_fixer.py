"""Tests for the ReportFixer — format fixes applied before lint."""

from __future__ import annotations

import pytest

from engines.report_generation.v3.render_contract import lint_markdown_render_contract
from engines.report_generation.v3.report_fixer import ReportFixer


class TestFixCjkPunctuation:
    def test_replaces_ascii_comma_after_cjk(self):
        fixer = ReportFixer()
        result = fixer.fix_cjk_punctuation("这是测试,检查。")
        assert "，" in result
        assert ",检" not in result

    def test_replaces_ascii_period_after_cjk(self):
        fixer = ReportFixer()
        result = fixer.fix_cjk_punctuation("测试.内容")
        assert "。" in result
        assert ".内" not in result

    def test_replaces_ascii_colon_after_cjk(self):
        fixer = ReportFixer()
        result = fixer.fix_cjk_punctuation("结论:如下")
        assert "：" in result
        assert ":如" not in result

    def test_no_change_for_clean_fullwidth_punctuation(self):
        fixer = ReportFixer()
        original = "这是测试，检查标点。"
        result = fixer.fix_cjk_punctuation(original)
        assert result == original

    def test_no_change_for_ascii_only_text(self):
        fixer = ReportFixer()
        original = "This is a test, check punctuation."
        result = fixer.fix_cjk_punctuation(original)
        assert result == original

    def test_fixed_content_passes_cjk_lint(self):
        fixer = ReportFixer()
        # Deliberately long content to avoid section_length_floor WARN
        md = (
            "## 证据分析\n\n"
            "这是测试,检查标点混用这个规则是否正常工作。"
            "需要足够长的内容来避免触发其他警告，这段文字超过五十个字符。\n"
        )
        fixed = fixer.fix_cjk_punctuation(md)
        results = lint_markdown_render_contract(fixed)
        assert not any(r.rule == "cjk_punctuation_mix" for r in results)


class TestFixDuplicateHeadings:
    def test_renames_second_duplicate_heading(self):
        fixer = ReportFixer()
        md = "## 证据分析\n\n内容一。\n\n## 证据分析\n\n内容二。\n"
        result = fixer.fix_duplicate_headings(md)
        assert "## 证据分析\n" in result
        assert "## 证据分析 (2)" in result

    def test_renames_third_duplicate_heading(self):
        fixer = ReportFixer()
        md = (
            "## 争点分析\n\n内容一。\n\n"
            "## 争点分析\n\n内容二。\n\n"
            "## 争点分析\n\n内容三。\n"
        )
        result = fixer.fix_duplicate_headings(md)
        assert "## 争点分析\n" in result  # first occurrence unchanged
        assert "## 争点分析 (2)" in result
        assert "## 争点分析 (3)" in result

    def test_no_change_for_unique_headings(self):
        fixer = ReportFixer()
        md = "## 争点分析\n\n内容。\n\n## 证据索引\n\n内容。\n"
        result = fixer.fix_duplicate_headings(md)
        assert result == md

    def test_fixed_content_passes_duplicate_heading_lint(self):
        fixer = ReportFixer()
        md = (
            "## 争点分析\n\n"
            "内容一的长度足够通过章节长度最低检查。内容需要超过五十个字符。\n\n"
            "## 争点分析\n\n"
            "内容二的长度足够通过章节长度最低检查。内容需要超过五十个字符。\n"
        )
        fixed = fixer.fix_duplicate_headings(md)
        # No duplicate_heading ERROR — lint would raise if present
        results = lint_markdown_render_contract(fixed)
        assert not any(r.rule == "duplicate_heading" for r in results)

    def test_only_affects_h2_headings(self):
        fixer = ReportFixer()
        # h1 and h3 duplicates should NOT be renamed
        md = "# 主标题\n\n内容。\n\n# 主标题\n\n内容。\n\n### 小节\n\n内容。\n\n### 小节\n\n内容。\n"
        result = fixer.fix_duplicate_headings(md)
        assert result == md


class TestFixTableColumnMismatch:
    def test_pads_short_row_with_empty_cells(self):
        fixer = ReportFixer()
        md = "| A | B | C |\n|---|---|---|\n| 1 | 2 |\n"
        fixed = fixer.fix_table_column_mismatch(md)
        lines = fixed.strip().splitlines()
        data_row = lines[2]
        cells = [c.strip() for c in data_row.strip("|").split("|")]
        assert len(cells) == 3

    def test_truncates_long_row(self):
        fixer = ReportFixer()
        md = "| A | B |\n|---|---|\n| 1 | 2 | 3 |\n"
        fixed = fixer.fix_table_column_mismatch(md)
        lines = fixed.strip().splitlines()
        data_row = lines[2]
        cells = [c.strip() for c in data_row.strip("|").split("|")]
        assert len(cells) == 2

    def test_unchanged_for_well_formed_table(self):
        fixer = ReportFixer()
        md = "| A | B | C |\n|---|---|---|\n| 1 | 2 | 3 |\n"
        result = fixer.fix_table_column_mismatch(md)
        assert result == md

    def test_fixed_table_passes_lint(self):
        fixer = ReportFixer()
        md = (
            "## 数据表格\n\n"
            "| A | B | C |\n|---|---|---|\n| 1 | 2 |\n\n"
            "这个表格测试修复功能是否能够正确处理列数不匹配的情况，内容足够长。\n"
        )
        fixed = fixer.fix_table_column_mismatch(md)
        results = lint_markdown_render_contract(fixed)
        assert not any(r.rule == "table_header_mismatch" for r in results)

    def test_multiple_tables_fixed_independently(self):
        fixer = ReportFixer()
        md = (
            "| X | Y |\n|---|---|\n| 1 | 2 | 3 |\n"
            "\n"
            "| A | B | C |\n|---|---|---|\n| x | y |\n"
        )
        fixed = fixer.fix_table_column_mismatch(md)
        lines = fixed.strip().splitlines()
        # First table data row: truncated to 2 cols
        first_data = lines[2]
        first_cells = [c.strip() for c in first_data.strip("|").split("|")]
        assert len(first_cells) == 2
        # Second table data row: padded to 3 cols
        second_data = lines[6]
        second_cells = [c.strip() for c in second_data.strip("|").split("|")]
        assert len(second_cells) == 3


class TestApplyAll:
    def test_returns_tuple_of_str_and_list(self):
        fixer = ReportFixer()
        md = "## 标题\n\n内容。\n"
        result = fixer.apply_all(md)
        assert isinstance(result, tuple)
        assert len(result) == 2
        fixed_md, fix_log = result
        assert isinstance(fixed_md, str)
        assert isinstance(fix_log, list)

    def test_fix_log_records_cjk_fix(self):
        fixer = ReportFixer()
        md = "## 标题\n\n这是测试,检查标点是否被修复。内容足够长来避免其他警告触发。\n"
        _, fix_log = fixer.apply_all(md)
        assert any("cjk" in entry.lower() for entry in fix_log)

    def test_fix_log_records_duplicate_heading_fix(self):
        fixer = ReportFixer()
        md = "## 争点分析\n\n内容一。\n\n## 争点分析\n\n内容二。\n"
        _, fix_log = fixer.apply_all(md)
        assert any("duplicate" in entry.lower() for entry in fix_log)

    def test_fix_log_records_table_fix(self):
        fixer = ReportFixer()
        md = "## 标题\n\n| A | B | C |\n|---|---|---|\n| 1 | 2 |\n\n内容。\n"
        _, fix_log = fixer.apply_all(md)
        assert any("table" in entry.lower() for entry in fix_log)

    def test_empty_fix_log_for_clean_content(self):
        fixer = ReportFixer()
        md = "## 标题\n\n这是干净的内容，没有任何问题需要修复。\n"
        _, fix_log = fixer.apply_all(md)
        assert fix_log == []

    def test_apply_all_fixes_all_issues(self):
        fixer = ReportFixer()
        md = (
            "## 证据分析\n\n这是测试,检查标点。\n\n"
            "## 证据分析\n\n内容二。\n\n"
            "| A | B | C |\n|---|---|---|\n| 1 | 2 |\n"
        )
        fixed, fix_log = fixer.apply_all(md)
        assert len(fix_log) >= 2
        assert "## 证据分析 (2)" in fixed
        assert "，" in fixed  # CJK comma replaced
