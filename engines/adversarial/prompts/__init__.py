"""
对抗引擎 prompt 模块注册表。
Adversarial engine prompt module registry.
"""
from . import civil_loan
from . import labor_dispute
from . import real_estate

PROMPT_REGISTRY: dict[str, object] = {
    "civil_loan": civil_loan,
    "labor_dispute": labor_dispute,
    "real_estate": real_estate,
}

__all__ = ["PROMPT_REGISTRY"]
