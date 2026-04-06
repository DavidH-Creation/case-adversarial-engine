"""
Case extractor prompt registry.
案件提取 prompt 注册表。

Prompt modules register via register_prompt(). Each module must expose:
  - SYSTEM_PROMPT: str
  - EXTRACTION_PROMPT: str (with {documents} placeholder)
  - format_documents(texts: list[tuple[str, str]]) -> str
"""

from __future__ import annotations

from typing import Any

PROMPT_REGISTRY: dict[str, Any] = {}


def register_prompt(name: str, module: Any) -> None:
    """Register an extraction prompt module."""
    PROMPT_REGISTRY[name] = module


# Auto-register built-in prompts
from . import generic as _generic_module

register_prompt("generic", _generic_module)
