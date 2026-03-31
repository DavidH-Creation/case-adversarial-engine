"""
prompt 模板注册表。
Prompt template registry.
"""
from . import civil_loan, labor_dispute, real_estate

PROMPT_REGISTRY = {
    "civil_loan": civil_loan,
    "labor_dispute": labor_dispute,
    "real_estate": real_estate,
}
