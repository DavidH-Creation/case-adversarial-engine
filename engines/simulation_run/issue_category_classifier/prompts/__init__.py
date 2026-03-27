"""
prompt 模板注册表。
Prompt template registry.
"""
from . import civil_loan

PROMPT_REGISTRY = {
    "civil_loan": civil_loan,
}
