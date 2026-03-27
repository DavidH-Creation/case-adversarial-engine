"""争点影响排序 prompt 模板注册表。
Issue impact ranking prompt template registry.
"""
from typing import Any

PROMPT_REGISTRY: dict[str, Any] = {}


def register_prompt(case_type: str, module: Any) -> None:
    PROMPT_REGISTRY[case_type] = module


from . import civil_loan as _civil_loan_module  # noqa: E402
register_prompt("civil_loan", _civil_loan_module)
