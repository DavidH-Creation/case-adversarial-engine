"""
对抗引擎 prompt 模块注册表。
Adversarial engine prompt module registry.
"""

from engines.shared.case_type_plugin import RegistryPlugin

from . import civil_loan
from . import labor_dispute
from . import real_estate

PROMPT_REGISTRY: dict[str, object] = {
    "civil_loan": civil_loan,
    "labor_dispute": labor_dispute,
    "real_estate": real_estate,
}

plugin = RegistryPlugin(PROMPT_REGISTRY)

__all__ = ["PROMPT_REGISTRY", "plugin"]
