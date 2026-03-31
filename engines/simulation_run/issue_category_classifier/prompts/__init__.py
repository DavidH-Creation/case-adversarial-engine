"""
prompt 模板注册表。
Prompt template registry.
"""
from . import civil_loan, labor_dispute, real_estate

from engines.shared.case_type_plugin import RegistryPlugin

PROMPT_REGISTRY = {
    "civil_loan": civil_loan,
    "labor_dispute": labor_dispute,
    "real_estate": real_estate,
}

plugin = RegistryPlugin(PROMPT_REGISTRY)
