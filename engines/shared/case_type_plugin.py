"""CaseTypePlugin Protocol + UnsupportedCaseTypeError.

Formalizes the PROMPT_REGISTRY pattern as a Python Protocol so that
case-type-specific prompt sources are expressed through a common interface.

Usage::

    from engines.shared.case_type_plugin import CaseTypePlugin, RegistryPlugin, UnsupportedCaseTypeError

    # Wrap an existing PROMPT_REGISTRY
    plugin = RegistryPlugin(PROMPT_REGISTRY)

    # Retrieve a user prompt string
    prompt = plugin.get_prompt("action_recommender", "civil_loan", context)

    # Unknown case types raise UnsupportedCaseTypeError (not KeyError)
    plugin.get_prompt("engine", "unknown", {})  # raises UnsupportedCaseTypeError
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class UnsupportedCaseTypeError(Exception):
    """Raised when a case type is not registered in a CaseTypePlugin."""

    def __init__(self, case_type: str, available: list[str] | None = None) -> None:
        self.case_type = case_type
        self.available = available or []
        if self.available:
            msg = (
                f"不支持的案由类型: '{case_type}'。"
                f"可用: {', '.join(self.available)}"
            )
        else:
            msg = f"不支持的案由类型: '{case_type}'"
        super().__init__(msg)


@runtime_checkable
class CaseTypePlugin(Protocol):
    """Protocol for case-type-specific prompt generation.

    Each simulation_run engine wraps its PROMPT_REGISTRY in a
    ``RegistryPlugin`` that satisfies this Protocol.
    """

    def get_prompt(self, engine_name: str, case_type: str, context: dict) -> str:
        """Build and return the user prompt for the given case type.

        Args:
            engine_name: Identifier of the calling engine (e.g. ``"action_recommender"``).
            case_type:   Case type key (e.g. ``"civil_loan"``).
            context:     Keyword arguments forwarded to the underlying
                         ``build_user_prompt`` callable.

        Returns:
            A non-empty prompt string.

        Raises:
            UnsupportedCaseTypeError: When *case_type* is not registered.
        """
        ...  # pragma: no cover


class RegistryPlugin:
    """``CaseTypePlugin`` implementation backed by a PROMPT_REGISTRY dict.

    Supports two registry-entry formats used across simulation_run engines:

    * **Module-based**: entry is a Python module with a
      ``build_user_prompt(**context)`` function.
    * **Dict-based**: entry is a ``dict`` with a ``"build_user"`` callable.

    Existing ``PROMPT_REGISTRY`` dicts remain unchanged; this class is a
    thin wrapper that adds Protocol compliance and raises
    ``UnsupportedCaseTypeError`` instead of ``KeyError`` for missing keys.
    """

    def __init__(self, registry: dict[str, Any]) -> None:
        self._registry = registry

    def get_prompt(self, engine_name: str, case_type: str, context: dict) -> str:
        """Return the built user prompt for the given case type.

        Raises:
            UnsupportedCaseTypeError: When *case_type* is not registered.
        """
        if case_type not in self._registry:
            raise UnsupportedCaseTypeError(case_type, list(self._registry.keys()))
        entry = self._registry[case_type]
        if isinstance(entry, dict):
            build_fn = entry["build_user"]
        else:
            build_fn = entry.build_user_prompt
        return build_fn(**context)
