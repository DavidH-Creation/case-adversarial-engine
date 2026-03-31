"""
文书辅助引擎提示注册表。
Document assistance engine prompt registry.

PROMPT_REGISTRY 使用二维键 (doc_type, case_type) → (system_prompt, build_user_prompt_fn)。
PROMPT_REGISTRY uses 2D key (doc_type, case_type) → (system_prompt, build_user_prompt_fn).

支持的组合 / Supported combinations:
- ("pleading",   "civil_loan")
- ("defense",    "civil_loan")
- ("cross_exam", "civil_loan")
- ("pleading",   "labor_dispute")
- ("defense",    "labor_dispute")
- ("cross_exam", "labor_dispute")
- ("pleading",   "real_estate")
- ("defense",    "real_estate")
- ("cross_exam", "real_estate")
"""

from __future__ import annotations

from typing import Callable

from .civil_loan_pleading import (
    SYSTEM_PROMPT as _CL_PL_SYS,
    build_user_prompt as _CL_PL_BUILD,
)
from .civil_loan_defense import (
    SYSTEM_PROMPT as _CL_DF_SYS,
    build_user_prompt as _CL_DF_BUILD,
)
from .civil_loan_cross_exam import (
    SYSTEM_PROMPT as _CL_XE_SYS,
    build_user_prompt as _CL_XE_BUILD,
)
from .labor_dispute_pleading import (
    SYSTEM_PROMPT as _LD_PL_SYS,
    build_user_prompt as _LD_PL_BUILD,
)
from .labor_dispute_defense import (
    SYSTEM_PROMPT as _LD_DF_SYS,
    build_user_prompt as _LD_DF_BUILD,
)
from .labor_dispute_cross_exam import (
    SYSTEM_PROMPT as _LD_XE_SYS,
    build_user_prompt as _LD_XE_BUILD,
)
from .real_estate_pleading import (
    SYSTEM_PROMPT as _RE_PL_SYS,
    build_user_prompt as _RE_PL_BUILD,
)
from .real_estate_defense import (
    SYSTEM_PROMPT as _RE_DF_SYS,
    build_user_prompt as _RE_DF_BUILD,
)
from .real_estate_cross_exam import (
    SYSTEM_PROMPT as _RE_XE_SYS,
    build_user_prompt as _RE_XE_BUILD,
)

# (doc_type, case_type) → (system_prompt, build_user_prompt)
PROMPT_REGISTRY: dict[tuple[str, str], tuple[str, Callable]] = {
    ("pleading",   "civil_loan"):     (_CL_PL_SYS, _CL_PL_BUILD),
    ("defense",    "civil_loan"):     (_CL_DF_SYS, _CL_DF_BUILD),
    ("cross_exam", "civil_loan"):     (_CL_XE_SYS, _CL_XE_BUILD),
    ("pleading",   "labor_dispute"):  (_LD_PL_SYS, _LD_PL_BUILD),
    ("defense",    "labor_dispute"):  (_LD_DF_SYS, _LD_DF_BUILD),
    ("cross_exam", "labor_dispute"):  (_LD_XE_SYS, _LD_XE_BUILD),
    ("pleading",   "real_estate"):    (_RE_PL_SYS, _RE_PL_BUILD),
    ("defense",    "real_estate"):    (_RE_DF_SYS, _RE_DF_BUILD),
    ("cross_exam", "real_estate"):    (_RE_XE_SYS, _RE_XE_BUILD),
}

__all__ = ["PROMPT_REGISTRY"]
