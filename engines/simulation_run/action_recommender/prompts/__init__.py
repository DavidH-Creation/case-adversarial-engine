"""行动建议策略层 prompt 模板注册表。
Action recommender strategic layer prompt template registry.
"""

from typing import Any

from engines.shared.case_type_plugin import RegistryPlugin

PROMPT_REGISTRY: dict[str, Any] = {}


def register_prompt(case_type: str, module: Any) -> None:
    PROMPT_REGISTRY[case_type] = module


from . import civil_loan as _civil_loan_module  # noqa: E402

register_prompt("civil_loan", _civil_loan_module)

from . import labor_dispute as _labor_dispute_module  # noqa: E402

register_prompt("labor_dispute", _labor_dispute_module)

from . import real_estate as _real_estate_module  # noqa: E402

register_prompt("real_estate", _real_estate_module)

plugin = RegistryPlugin(PROMPT_REGISTRY)
