"""Prompt 模板注册表"""

from typing import Any

from engines.shared.case_type_plugin import RegistryPlugin

# 案由 → prompt 模块注册表
PROMPT_REGISTRY: dict[str, Any] = {}


def register_prompt(case_type: str, module: Any) -> None:
    """注册案由 prompt 模板模块"""
    PROMPT_REGISTRY[case_type] = module


# 自动注册内置 prompt 模块
from . import civil_loan as _civil_loan_module  # noqa: E402
from . import labor_dispute as _labor_dispute_module  # noqa: E402
from . import real_estate as _real_estate_module  # noqa: E402

register_prompt("civil_loan", _civil_loan_module)
register_prompt("labor_dispute", _labor_dispute_module)
register_prompt("real_estate", _real_estate_module)

plugin = RegistryPlugin(PROMPT_REGISTRY)
