"""
对抗引擎 prompt 模块注册表。
Adversarial engine prompt module registry.
"""
from . import civil_loan

PROMPT_REGISTRY: dict[str, object] = {
    "civil_loan": civil_loan,
}

__all__ = ["PROMPT_REGISTRY"]
