"""Prompt 模板注册表"""

from typing import Any

# 案由 → prompt 模块注册表
PROMPT_REGISTRY: dict[str, Any] = {}


def register_prompt(case_type: str, module: Any) -> None:
    """注册案由 prompt 模板模块"""
    PROMPT_REGISTRY[case_type] = module


# 自动注册内置 prompt 模块
from . import civil_loan as _civil_loan_module

register_prompt("civil_loan", _civil_loan_module)