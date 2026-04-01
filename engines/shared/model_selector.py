"""
Multi-model tiered strategy — select haiku/sonnet/opus by task complexity.
Multi-model tiered strategy — select haiku/sonnet/opus based on task complexity.

ModelSelector 根据 task tag 选择合适的模型，支持三层配置优先级：
ModelSelector picks the right model for each task tag, with three-level config priority:

    config.yaml > CLI --model override > hardcoded defaults

用法 / Usage::

    selector = ModelSelector()                          # 使用硬编码默认值
    selector = ModelSelector.from_yaml("config/model_tiers.yaml")  # 从配置加载
    selector = ModelSelector(model_override="claude-opus-4-6")     # CLI --model 覆盖全部

    model = selector.select("evidence_indexer")   # → "claude-haiku-4-5-20251001"
    model = selector.select("executive_summarizer")  # → "claude-opus-4-6"
"""

from __future__ import annotations

import logging
from enum import Enum
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)


class ModelTier(str, Enum):
    """模型分级 / Model tiers."""

    fast = "fast"  # haiku — lightweight tasks
    balanced = "balanced"  # sonnet — standard analysis
    deep = "deep"  # opus — complex reasoning


# ---------------------------------------------------------------------------
# Hardcoded defaults (used when no config file is provided)
# ---------------------------------------------------------------------------

DEFAULT_TIER_MODELS: dict[ModelTier, str] = {
    ModelTier.fast: "claude-haiku-4-5-20251001",
    ModelTier.balanced: "claude-sonnet-4-6",
    ModelTier.deep: "claude-opus-4-6",
}

DEFAULT_TASK_TIERS: dict[str, ModelTier] = {
    # fast — high volume, low complexity
    "evidence_indexer": ModelTier.fast,
    "issue_classifier": ModelTier.fast,
    "issue_category_classifier": ModelTier.fast,
    "hearing_order": ModelTier.fast,
    "keyword_extractor": ModelTier.fast,
    # balanced — core analysis
    "plaintiff_agent": ModelTier.balanced,
    "defendant_agent": ModelTier.balanced,
    "issue_impact_ranker": ModelTier.balanced,
    "defense_chain": ModelTier.balanced,
    "evidence_manager": ModelTier.balanced,
    "admissibility_evaluator": ModelTier.balanced,
    "issue_extractor": ModelTier.balanced,
    "decision_path_tree": ModelTier.balanced,
    "attack_chain_optimizer": ModelTier.balanced,
    "issue_dependency_graph": ModelTier.balanced,
    "relevance_ranker": ModelTier.balanced,
    # deep — complex reasoning
    "executive_summarizer": ModelTier.deep,
    "scenario_simulator": ModelTier.deep,
    "action_recommender": ModelTier.deep,
    "pretrial_conference": ModelTier.deep,
    "followup_responder": ModelTier.deep,
}

FALLBACK_TIER = ModelTier.balanced


class ModelSelector:
    """根据 task tag 选择 LLM 模型。
    Select LLM model based on task tag.

    Config priority: config file > model_override > hardcoded defaults.
    When model_override is set, ALL tasks use that single model (CLI --model behavior).

    Args:
        tier_models:    tier→model ID mapping (overrides DEFAULT_TIER_MODELS)
        task_tiers:     task_tag→tier mapping (overrides DEFAULT_TASK_TIERS)
        model_override: if set, select() always returns this model regardless of task tag
        fallback_tier:  tier used when task tag is not in task_tiers (default: balanced)
    """

    def __init__(
        self,
        *,
        tier_models: dict[ModelTier, str] | None = None,
        task_tiers: dict[str, ModelTier] | None = None,
        model_override: str | None = None,
        fallback_tier: ModelTier = FALLBACK_TIER,
    ) -> None:
        self._tier_models = tier_models or dict(DEFAULT_TIER_MODELS)
        self._task_tiers = task_tiers or dict(DEFAULT_TASK_TIERS)
        self._model_override = model_override
        self._fallback_tier = fallback_tier

    def select(self, task_tag: str) -> str:
        """返回适合该 task 的模型 ID。
        Return the model ID appropriate for the given task tag.

        If model_override is set, always returns that model.
        Otherwise looks up task_tag → tier → model ID.
        Unknown task tags fall back to fallback_tier.
        """
        if self._model_override:
            return self._model_override

        tier = self._task_tiers.get(task_tag, self._fallback_tier)
        model_id = self._tier_models.get(tier, DEFAULT_TIER_MODELS[self._fallback_tier])

        if task_tag not in self._task_tiers:
            _logger.warning(
                "Unknown task tag %r, falling back to %s tier (model=%s)",
                task_tag,
                self._fallback_tier.value,
                model_id,
            )

        return model_id

    @property
    def model_override(self) -> str | None:
        """Return the global model override, if set."""
        return self._model_override

    @classmethod
    def from_yaml(
        cls,
        config_path: str | Path,
        *,
        model_override: str | None = None,
    ) -> ModelSelector:
        """从 YAML 配置文件加载。
        Load from a YAML config file.

        Expected YAML structure::

            tiers:
              fast: claude-haiku-4-5-20251001
              balanced: claude-sonnet-4-6
              deep: claude-opus-4-6

            tasks:
              evidence_indexer: fast
              plaintiff_agent: balanced
              executive_summarizer: deep

            fallback_tier: balanced

        If the file does not exist, falls back to hardcoded defaults with a warning.

        Args:
            config_path:    path to YAML config file
            model_override: if set, select() always returns this model
        """
        import yaml  # noqa: PLC0415

        path = Path(config_path)
        if not path.exists():
            _logger.warning(
                "Model tier config not found at %s, using hardcoded defaults",
                path,
            )
            return cls(model_override=model_override)

        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            _logger.warning(
                "Invalid model tier config at %s (expected dict, got %s), using defaults",
                path,
                type(raw).__name__,
            )
            return cls(model_override=model_override)

        return cls._from_dict(raw, model_override=model_override)

    @classmethod
    def _from_dict(cls, raw: dict[str, Any], *, model_override: str | None = None) -> ModelSelector:
        """Parse a config dict into a ModelSelector."""
        tier_models: dict[ModelTier, str] = dict(DEFAULT_TIER_MODELS)
        if "tiers" in raw and isinstance(raw["tiers"], dict):
            for tier_name, model_id in raw["tiers"].items():
                try:
                    tier = ModelTier(tier_name)
                    tier_models[tier] = str(model_id)
                except ValueError:
                    _logger.warning("Unknown tier name %r in config, ignoring", tier_name)

        task_tiers: dict[str, ModelTier] = dict(DEFAULT_TASK_TIERS)
        if "tasks" in raw and isinstance(raw["tasks"], dict):
            for task_tag, tier_name in raw["tasks"].items():
                try:
                    task_tiers[str(task_tag)] = ModelTier(tier_name)
                except ValueError:
                    _logger.warning(
                        "Unknown tier %r for task %r in config, ignoring",
                        tier_name,
                        task_tag,
                    )

        fallback_tier = FALLBACK_TIER
        if "fallback_tier" in raw:
            try:
                fallback_tier = ModelTier(raw["fallback_tier"])
            except ValueError:
                _logger.warning(
                    "Unknown fallback_tier %r in config, using %s",
                    raw["fallback_tier"],
                    FALLBACK_TIER.value,
                )

        return cls(
            tier_models=tier_models,
            task_tiers=task_tiers,
            model_override=model_override,
            fallback_tier=fallback_tier,
        )
