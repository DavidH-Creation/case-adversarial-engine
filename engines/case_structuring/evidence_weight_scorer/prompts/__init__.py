"""Prompt registry for evidence_weight_scorer."""
from .civil_loan import SYSTEM_PROMPT, build_user_prompt

PROMPT_REGISTRY = {
    "civil_loan": {"system": SYSTEM_PROMPT, "build_user": build_user_prompt},
}

__all__ = ["PROMPT_REGISTRY"]
