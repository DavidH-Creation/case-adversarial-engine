"""
Unified engine configuration loader.
统一引擎配置加载器。

Loads ``config/engine_config.yaml`` (pipeline / report / interactive / rules)
alongside the existing ``config/model_tiers.yaml`` (model selection) and
exposes both through a single :class:`EngineConfig` dataclass.

Priority (highest → lowest):
  1. Caller-supplied overrides (CLI flags, constructor args)
  2. ``config/engine_config.yaml``
  3. Hardcoded defaults in this module

Usage::

    from engines.shared.config_loader import load_engine_config

    cfg = load_engine_config()                           # default path
    cfg = load_engine_config("custom/engine_config.yaml")  # explicit

    cfg.pipeline.max_retries      # 3
    cfg.pipeline.timeout_seconds  # 120.0
    cfg.report.redact_pii         # True
    cfg.rules.lpr_multiplier_cap  # 4.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path("config/engine_config.yaml")


# ---------------------------------------------------------------------------
# Typed config sections
# ---------------------------------------------------------------------------


@dataclass
class PipelineConfig:
    """Pipeline-level defaults for LLM calls."""

    max_retries: int = 3
    max_tokens: int = 4096
    temperature: float = 0.0
    timeout_seconds: float = 120.0
    output_dir: str = "outputs/"


@dataclass
class ReportConfig:
    """Report generation toggles."""

    include_disclaimer: bool = True
    redact_pii: bool = True


@dataclass
class InteractiveConfig:
    """Interactive followup session limits."""

    max_question_length: int = 2000
    max_session_turns: int = 20


@dataclass
class RulesConfig:
    """Deterministic rule thresholds (mirrors :class:`RuleThresholds`)."""

    prof_lender_min_cases: int = 3
    prof_lender_min_borrowers: int = 3
    prof_lender_max_span_months: int = 24
    false_litigation_ratio: float = 2.0
    lpr_multiplier_cap: float = 4.0


@dataclass
class EngineConfig:
    """Top-level engine configuration container."""

    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    report: ReportConfig = field(default_factory=ReportConfig)
    interactive: InteractiveConfig = field(default_factory=InteractiveConfig)
    rules: RulesConfig = field(default_factory=RulesConfig)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def _apply_section(target: Any, raw: dict) -> None:
    """Overwrite dataclass fields from a raw dict, ignoring unknown keys."""
    for key, value in raw.items():
        if hasattr(target, key):
            expected_type = type(getattr(target, key))
            try:
                setattr(target, key, expected_type(value))
            except (ValueError, TypeError):
                _logger.warning(
                    "Cannot cast config key %r value %r to %s, keeping default",
                    key,
                    value,
                    expected_type.__name__,
                )
        else:
            _logger.debug("Ignoring unknown config key %r", key)


def load_engine_config(
    config_path: str | Path | None = None,
    *,
    project_root: Path | None = None,
) -> EngineConfig:
    """Load engine configuration from YAML.

    Args:
        config_path:  Explicit path to engine_config.yaml.
                      When *None*, resolves ``config/engine_config.yaml``
                      relative to *project_root*.
        project_root: Repository root used to resolve default *config_path*.
                      Defaults to two directories above this file
                      (``engines/shared/`` → repo root).

    Returns:
        Fully-populated :class:`EngineConfig` (defaults for missing keys).
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent.parent

    path = Path(config_path) if config_path else project_root / _DEFAULT_CONFIG_PATH

    cfg = EngineConfig()

    if not path.exists():
        _logger.info(
            "Engine config not found at %s, using hardcoded defaults", path
        )
        return cfg

    try:
        import yaml  # noqa: PLC0415

        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        _logger.warning("Failed to parse %s, using hardcoded defaults", path, exc_info=True)
        return cfg

    if not isinstance(raw, dict):
        _logger.warning(
            "Expected dict in %s, got %s — using defaults", path, type(raw).__name__
        )
        return cfg

    section_map = {
        "pipeline": cfg.pipeline,
        "report": cfg.report,
        "interactive": cfg.interactive,
        "rules": cfg.rules,
    }

    for section_name, target in section_map.items():
        section_data = raw.get(section_name)
        if isinstance(section_data, dict):
            _apply_section(target, section_data)

    return cfg
