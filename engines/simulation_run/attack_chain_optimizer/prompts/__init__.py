"""Prompt registry for attack_chain_optimizer."""
from .civil_loan import SYSTEM_PROMPT as _cl_sys, build_user_prompt as _cl_build
from .labor_dispute import SYSTEM_PROMPT as _ld_sys, build_user_prompt as _ld_build
from .real_estate import SYSTEM_PROMPT as _re_sys, build_user_prompt as _re_build

from engines.shared.case_type_plugin import RegistryPlugin

PROMPT_REGISTRY = {
    "civil_loan": {"system": _cl_sys, "build_user": _cl_build},
    "labor_dispute": {"system": _ld_sys, "build_user": _ld_build},
    "real_estate": {"system": _re_sys, "build_user": _re_build},
}

plugin = RegistryPlugin(PROMPT_REGISTRY)

__all__ = ["PROMPT_REGISTRY", "plugin"]
