"""
PII 脱敏模块
PII Redaction module.

在报告输出层统一脱敏，不在中间层做。
Applied at the report output layer only, not in intermediate layers.

支持的 PII 类型 / Supported PII types:
- 中国身份证号（18位）/ Chinese ID card number (18 digits)
- 手机号（11位）/ Mobile phone number (11 digits)
- 银行卡号（16-19位）/ Bank card number (16-19 digits)
- 姓名（通过白名单替换为角色代号）/ Names (replaced via whitelist with role codes)
"""

from __future__ import annotations

import re
from typing import Sequence


# ---------------------------------------------------------------------------
# PII 正则模式 / PII regex patterns
# ---------------------------------------------------------------------------

# 中国身份证号: 6位地区码 + 8位出生日期 + 3位顺序码 + 1位校验码(数字或X)
_ID_CARD_RE = re.compile(
    r"(?<!\d)"  # 前面不是数字
    r"[1-9]\d{5}"  # 6位地区码
    r"(?:19|20)\d{2}"  # 出生年份
    r"(?:0[1-9]|1[0-2])"  # 月份
    r"(?:0[1-9]|[12]\d|3[01])"  # 日期
    r"\d{3}"  # 顺序码
    r"[\dXx]"  # 校验码
    r"(?!\d)"  # 后面不是数字
)

# 手机号: 1开头的11位数字
_PHONE_RE = re.compile(
    r"(?<!\d)"
    r"(1[3-9]\d)\d{4}(\d{4})"
    r"(?!\d)"
)

# 银行卡号: 16-19位数字
_BANK_CARD_RE = re.compile(
    r"(?<!\d)"
    r"(\d{4})\d{8,11}(\d{4})"
    r"(?!\d)"
)


# ---------------------------------------------------------------------------
# 姓名脱敏辅助 / Name redaction helpers
# ---------------------------------------------------------------------------

def _build_name_map(party_names: Sequence[str]) -> dict[str, str]:
    """从当事人姓名列表构建 姓名→角色代号 映射。

    Build name → role code mapping from party name list.
    Role codes are 当事人A, 当事人B, ... in order.
    """
    mapping: dict[str, str] = {}
    for idx, name in enumerate(party_names):
        name = name.strip()
        if name:
            code = f"当事人{chr(ord('A') + idx)}"
            mapping[name] = code
    return mapping


# ---------------------------------------------------------------------------
# 核心脱敏函数 / Core redaction functions
# ---------------------------------------------------------------------------

def redact_id_card(text: str) -> str:
    """将身份证号替换为 `***`。"""
    return _ID_CARD_RE.sub("***", text)


def redact_phone(text: str) -> str:
    """将手机号替换为 `1XX****XXXX` 格式（保留前3后4）。"""
    return _PHONE_RE.sub(r"\1****\2", text)


def redact_bank_card(text: str) -> str:
    """将银行卡号替换为 `XXXX****XXXX` 格式（保留前4后4）。"""
    return _BANK_CARD_RE.sub(r"\1****\2", text)


def redact_names(text: str, name_map: dict[str, str]) -> str:
    """将白名单中的姓名替换为角色代号。

    按姓名长度降序替换，避免短名被长名子串误匹配。
    """
    # 按长度降序排列，长名优先替换
    sorted_names = sorted(name_map.keys(), key=len, reverse=True)
    for name in sorted_names:
        if name in text:
            text = text.replace(name, name_map[name])
    return text


def redact_text(text: str, *, party_names: Sequence[str] | None = None) -> str:
    """对文本执行全量 PII 脱敏。

    Apply all PII redaction to text. Safe to call on any text —
    returns original text unchanged if no PII is found.
    If regex matching raises an unexpected error, returns original text
    to avoid breaking report generation.

    Args:
        text: 待脱敏文本 / Text to redact
        party_names: 当事人姓名白名单 / Party name whitelist for name redaction

    Returns:
        脱敏后文本 / Redacted text
    """
    if not text:
        return text

    try:
        result = redact_id_card(text)
        result = redact_phone(result)
        result = redact_bank_card(result)
        if party_names:
            name_map = _build_name_map(party_names)
            result = redact_names(result, name_map)
        return result
    except Exception:
        # 脱敏异常时返回原文，不破坏报告生成
        return text
