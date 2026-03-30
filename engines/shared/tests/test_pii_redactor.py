"""
PII 脱敏模块测试
Tests for PII redaction module.
"""

from __future__ import annotations

import pytest

from engines.shared.pii_redactor import (
    _build_name_map,
    redact_bank_card,
    redact_id_card,
    redact_names,
    redact_phone,
    redact_text,
)


# ---------------------------------------------------------------------------
# 身份证号脱敏 / ID card redaction
# ---------------------------------------------------------------------------


class TestRedactIdCard:
    def test_valid_id_card_replaced(self):
        text = "身份证号为110101199003071234的当事人"
        assert redact_id_card(text) == "身份证号为***的当事人"

    def test_id_card_with_x_check_digit(self):
        text = "证件号码：32058219850312001X"
        assert redact_id_card(text) == "证件号码：***"

    def test_id_card_lowercase_x(self):
        text = "号码 44030619900815123x 已脱敏"
        assert redact_id_card(text) == "号码 *** 已脱敏"

    def test_multiple_id_cards(self):
        text = "原告110101199003071234与被告320582198503120018"
        result = redact_id_card(text)
        assert result == "原告***与被告***"

    def test_no_id_card_unchanged(self):
        text = "本案不涉及身份证号"
        assert redact_id_card(text) == text

    def test_short_number_not_matched(self):
        text = "案号12345678"
        assert redact_id_card(text) == text


# ---------------------------------------------------------------------------
# 手机号脱敏 / Phone number redaction
# ---------------------------------------------------------------------------


class TestRedactPhone:
    def test_valid_phone_redacted(self):
        text = "联系电话13812345678"
        assert redact_phone(text) == "联系电话138****5678"

    def test_phone_with_different_prefix(self):
        text = "号码 15900001111 已记录"
        assert redact_phone(text) == "号码 159****1111 已记录"

    def test_multiple_phones(self):
        text = "原告手机13812345678，被告手机15987654321"
        result = redact_phone(text)
        assert "138****5678" in result
        assert "159****4321" in result

    def test_no_phone_unchanged(self):
        text = "没有手机号码"
        assert redact_phone(text) == text

    def test_short_number_not_matched(self):
        text = "编号1381234"
        assert redact_phone(text) == text


# ---------------------------------------------------------------------------
# 银行卡号脱敏 / Bank card number redaction
# ---------------------------------------------------------------------------


class TestRedactBankCard:
    def test_16_digit_card(self):
        text = "卡号6222021234561234"
        assert redact_bank_card(text) == "卡号6222****1234"

    def test_19_digit_card(self):
        text = "银行卡6222021234561234567"
        assert redact_bank_card(text) == "银行卡6222****4567"

    def test_no_bank_card_unchanged(self):
        text = "不含银行卡信息"
        assert redact_bank_card(text) == text


# ---------------------------------------------------------------------------
# 姓名脱敏 / Name redaction
# ---------------------------------------------------------------------------


class TestRedactNames:
    def test_single_name_replaced(self):
        name_map = {"张三": "当事人A"}
        text = "原告张三提交了证据"
        assert redact_names(text, name_map) == "原告当事人A提交了证据"

    def test_multiple_names_replaced(self):
        name_map = {"张三": "当事人A", "李四": "当事人B"}
        text = "张三与李四签订合同"
        result = redact_names(text, name_map)
        assert result == "当事人A与当事人B签订合同"

    def test_long_name_priority(self):
        """长名应优先被替换，避免短名子串误匹配。"""
        name_map = {"王": "当事人A", "王小明": "当事人B"}
        text = "王小明提交了证据"
        result = redact_names(text, name_map)
        assert result == "当事人B提交了证据"

    def test_no_match_unchanged(self):
        name_map = {"张三": "当事人A"}
        text = "没有匹配的姓名"
        assert redact_names(text, name_map) == text


class TestBuildNameMap:
    def test_basic_mapping(self):
        result = _build_name_map(["张三", "李四"])
        assert result == {"张三": "当事人A", "李四": "当事人B"}

    def test_empty_names_skipped(self):
        result = _build_name_map(["张三", "", "李四"])
        assert result == {"张三": "当事人A", "李四": "当事人C"}

    def test_whitespace_stripped(self):
        result = _build_name_map(["  张三  "])
        assert result == {"张三": "当事人A"}


# ---------------------------------------------------------------------------
# 全量脱敏 / Full redaction
# ---------------------------------------------------------------------------


class TestRedactText:
    def test_happy_path_id_card(self):
        """包含身份证号的文本经脱敏后替换为 ***。"""
        text = "证件 110101199003071234 确认"
        result = redact_text(text)
        assert "***" in result
        assert "110101199003071234" not in result

    def test_happy_path_phone(self):
        """包含手机号的文本经脱敏后替换为 1XX****XXXX。"""
        text = "联系 13812345678"
        result = redact_text(text)
        assert "138****5678" in result

    def test_no_pii_unchanged(self):
        """无 PII 的文本经脱敏后不变。"""
        text = "本案事实清楚，证据确凿"
        assert redact_text(text) == text

    def test_multiple_pii_types(self):
        """同一文本中包含多种 PII 类型全部脱敏。"""
        text = "张三的身份证110101199003071234，手机13812345678，卡号6222021234561234"
        result = redact_text(text, party_names=["张三"])
        assert "110101199003071234" not in result
        assert "13812345678" not in result
        assert "6222021234561234" not in result
        assert "当事人A" in result
        assert "***" in result
        assert "138****5678" in result
        assert "6222****1234" in result

    def test_empty_text_returns_empty(self):
        assert redact_text("") == ""

    def test_none_party_names_ok(self):
        text = "证件 110101199003071234"
        result = redact_text(text, party_names=None)
        assert "***" in result

    def test_error_path_returns_original(self):
        """脱敏正则匹配异常时返回原文（不破坏报告生成）。

        We mock the redact function to simulate a regex error.
        """
        from unittest.mock import patch

        text = "some text"
        with patch(
            "engines.shared.pii_redactor.redact_id_card",
            side_effect=Exception("regex boom"),
        ):
            result = redact_text(text)
        assert result == text


# ---------------------------------------------------------------------------
# 免责声明模板 / Disclaimer templates
# ---------------------------------------------------------------------------


class TestDisclaimerTemplates:
    def test_md_disclaimer_contains_ai_notice(self):
        from engines.shared.disclaimer_templates import DISCLAIMER_MD

        assert "本报告由 AI 生成" in DISCLAIMER_MD

    def test_docx_disclaimer_contains_ai_notice(self):
        from engines.shared.disclaimer_templates import DISCLAIMER_DOCX_BODY

        assert "本报告由 AI 生成" in DISCLAIMER_DOCX_BODY

    def test_docx_title_is_disclaimer(self):
        from engines.shared.disclaimer_templates import DISCLAIMER_DOCX_TITLE

        assert DISCLAIMER_DOCX_TITLE == "免责声明"
