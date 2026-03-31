"""Tests for engines.shared.model_selector — ModelSelector + ModelTier."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from engines.shared.model_selector import (
    DEFAULT_TASK_TIERS,
    DEFAULT_TIER_MODELS,
    FALLBACK_TIER,
    ModelSelector,
    ModelTier,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def config_dir(tmp_path: Path) -> Path:
    d = tmp_path / "config"
    d.mkdir()
    return d


@pytest.fixture()
def default_config(config_dir: Path) -> Path:
    """Write a standard config YAML and return its path."""
    cfg = {
        "tiers": {
            "fast": "claude-haiku-4-5-20251001",
            "balanced": "claude-sonnet-4-6",
            "deep": "claude-opus-4-6",
        },
        "tasks": {
            "evidence_indexer": "fast",
            "plaintiff_agent": "balanced",
            "executive_summarizer": "deep",
        },
        "fallback_tier": "balanced",
    }
    p = config_dir / "model_tiers.yaml"
    p.write_text(yaml.dump(cfg), encoding="utf-8")
    return p


@pytest.fixture()
def custom_config(config_dir: Path) -> Path:
    """Write a custom config that remaps tasks to different tiers."""
    cfg = {
        "tiers": {
            "fast": "my-fast-model",
            "balanced": "my-balanced-model",
            "deep": "my-deep-model",
        },
        "tasks": {
            "evidence_indexer": "deep",
            "plaintiff_agent": "fast",
            "custom_task": "fast",
        },
        "fallback_tier": "fast",
    }
    p = config_dir / "custom_tiers.yaml"
    p.write_text(yaml.dump(cfg), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Happy path: hardcoded defaults
# ---------------------------------------------------------------------------


class TestDefaultSelector:
    """ModelSelector() with no arguments uses hardcoded defaults."""

    def test_fast_tier_task(self):
        sel = ModelSelector()
        assert sel.select("evidence_indexer") == DEFAULT_TIER_MODELS[ModelTier.fast]

    def test_balanced_tier_task(self):
        sel = ModelSelector()
        assert sel.select("plaintiff_agent") == DEFAULT_TIER_MODELS[ModelTier.balanced]

    def test_deep_tier_task(self):
        sel = ModelSelector()
        assert sel.select("executive_summarizer") == DEFAULT_TIER_MODELS[ModelTier.deep]

    def test_all_default_tasks_have_valid_tiers(self):
        sel = ModelSelector()
        for tag, tier in DEFAULT_TASK_TIERS.items():
            model = sel.select(tag)
            assert model == DEFAULT_TIER_MODELS[tier], (
                f"{tag}: expected {DEFAULT_TIER_MODELS[tier]}, got {model}"
            )

    def test_model_override_is_none(self):
        sel = ModelSelector()
        assert sel.model_override is None


# ---------------------------------------------------------------------------
# Happy path: model override (CLI --model)
# ---------------------------------------------------------------------------


class TestModelOverride:
    """When model_override is set, select() always returns it."""

    def test_override_returns_same_model_for_all_tasks(self):
        sel = ModelSelector(model_override="claude-opus-4-6")
        assert sel.select("evidence_indexer") == "claude-opus-4-6"
        assert sel.select("plaintiff_agent") == "claude-opus-4-6"
        assert sel.select("executive_summarizer") == "claude-opus-4-6"
        assert sel.select("unknown_task") == "claude-opus-4-6"

    def test_override_property(self):
        sel = ModelSelector(model_override="my-model")
        assert sel.model_override == "my-model"


# ---------------------------------------------------------------------------
# Happy path: YAML config loading
# ---------------------------------------------------------------------------


class TestFromYaml:
    """ModelSelector.from_yaml() loads config correctly."""

    def test_loads_standard_config(self, default_config: Path):
        sel = ModelSelector.from_yaml(default_config)
        assert sel.select("evidence_indexer") == "claude-haiku-4-5-20251001"
        assert sel.select("plaintiff_agent") == "claude-sonnet-4-6"
        assert sel.select("executive_summarizer") == "claude-opus-4-6"

    def test_custom_config_remaps_tasks(self, custom_config: Path):
        sel = ModelSelector.from_yaml(custom_config)
        assert sel.select("evidence_indexer") == "my-deep-model"
        assert sel.select("plaintiff_agent") == "my-fast-model"
        assert sel.select("custom_task") == "my-fast-model"

    def test_custom_config_fallback_tier(self, custom_config: Path):
        sel = ModelSelector.from_yaml(custom_config)
        # custom config has fallback_tier: fast → "my-fast-model"
        assert sel.select("totally_unknown_task") == "my-fast-model"

    def test_yaml_with_model_override(self, default_config: Path):
        sel = ModelSelector.from_yaml(default_config, model_override="override-model")
        assert sel.select("evidence_indexer") == "override-model"
        assert sel.select("executive_summarizer") == "override-model"
        assert sel.model_override == "override-model"

    def test_yaml_config_merges_with_defaults(self, config_dir: Path):
        """Config that only specifies a subset of tasks still has defaults for others."""
        cfg = {
            "tasks": {
                "evidence_indexer": "deep",
            },
        }
        p = config_dir / "partial.yaml"
        p.write_text(yaml.dump(cfg), encoding="utf-8")
        sel = ModelSelector.from_yaml(p)
        # evidence_indexer remapped to deep
        assert sel.select("evidence_indexer") == DEFAULT_TIER_MODELS[ModelTier.deep]
        # plaintiff_agent still uses default (balanced)
        assert sel.select("plaintiff_agent") == DEFAULT_TIER_MODELS[ModelTier.balanced]


# ---------------------------------------------------------------------------
# Edge case: config file missing
# ---------------------------------------------------------------------------


class TestConfigFileMissing:
    """Missing config file falls back to hardcoded defaults."""

    def test_nonexistent_path_uses_defaults(self, tmp_path: Path):
        sel = ModelSelector.from_yaml(tmp_path / "does_not_exist.yaml")
        assert sel.select("evidence_indexer") == DEFAULT_TIER_MODELS[ModelTier.fast]
        assert sel.select("plaintiff_agent") == DEFAULT_TIER_MODELS[ModelTier.balanced]

    def test_nonexistent_path_with_override(self, tmp_path: Path):
        sel = ModelSelector.from_yaml(tmp_path / "nope.yaml", model_override="x")
        assert sel.select("evidence_indexer") == "x"


# ---------------------------------------------------------------------------
# Edge case: unknown task tag → fallback tier
# ---------------------------------------------------------------------------


class TestUnknownTaskFallback:
    """Unknown task tags fall back to fallback_tier (default: balanced)."""

    def test_unknown_task_uses_balanced(self):
        sel = ModelSelector()
        assert sel.select("nonexistent_engine") == DEFAULT_TIER_MODELS[FALLBACK_TIER]

    def test_unknown_task_custom_fallback(self):
        sel = ModelSelector(fallback_tier=ModelTier.fast)
        assert sel.select("nonexistent_engine") == DEFAULT_TIER_MODELS[ModelTier.fast]

    def test_unknown_task_logs_warning(self, caplog):
        sel = ModelSelector()
        with caplog.at_level("WARNING"):
            sel.select("totally_new_engine")
        assert "Unknown task tag" in caplog.text
        assert "totally_new_engine" in caplog.text


# ---------------------------------------------------------------------------
# Edge case: invalid YAML content
# ---------------------------------------------------------------------------


class TestInvalidConfig:
    """Malformed or invalid config files degrade gracefully."""

    def test_non_dict_yaml_uses_defaults(self, config_dir: Path):
        p = config_dir / "bad.yaml"
        p.write_text("just a string", encoding="utf-8")
        sel = ModelSelector.from_yaml(p)
        assert sel.select("evidence_indexer") == DEFAULT_TIER_MODELS[ModelTier.fast]

    def test_unknown_tier_name_in_tiers_ignored(self, config_dir: Path):
        cfg = {"tiers": {"turbo": "some-model"}}
        p = config_dir / "unknown_tier.yaml"
        p.write_text(yaml.dump(cfg), encoding="utf-8")
        sel = ModelSelector.from_yaml(p)
        # Should still work with defaults
        assert sel.select("evidence_indexer") == DEFAULT_TIER_MODELS[ModelTier.fast]

    def test_unknown_tier_in_tasks_ignored(self, config_dir: Path):
        cfg = {"tasks": {"evidence_indexer": "turbo"}}
        p = config_dir / "bad_task_tier.yaml"
        p.write_text(yaml.dump(cfg), encoding="utf-8")
        sel = ModelSelector.from_yaml(p)
        # evidence_indexer still uses its default (fast) since "turbo" was ignored
        assert sel.select("evidence_indexer") == DEFAULT_TIER_MODELS[ModelTier.fast]

    def test_invalid_fallback_tier_uses_default(self, config_dir: Path):
        cfg = {"fallback_tier": "turbo"}
        p = config_dir / "bad_fallback.yaml"
        p.write_text(yaml.dump(cfg), encoding="utf-8")
        sel = ModelSelector.from_yaml(p)
        assert sel.select("unknown_task") == DEFAULT_TIER_MODELS[FALLBACK_TIER]

    def test_empty_yaml_uses_defaults(self, config_dir: Path):
        p = config_dir / "empty.yaml"
        p.write_text("", encoding="utf-8")
        sel = ModelSelector.from_yaml(p)
        # yaml.safe_load("") returns None → non-dict → defaults
        assert sel.select("evidence_indexer") == DEFAULT_TIER_MODELS[ModelTier.fast]


# ---------------------------------------------------------------------------
# ModelTier enum
# ---------------------------------------------------------------------------


class TestModelTier:
    """ModelTier enum has expected values."""

    def test_values(self):
        assert ModelTier.fast.value == "fast"
        assert ModelTier.balanced.value == "balanced"
        assert ModelTier.deep.value == "deep"

    def test_from_string(self):
        assert ModelTier("fast") == ModelTier.fast
        assert ModelTier("balanced") == ModelTier.balanced
        assert ModelTier("deep") == ModelTier.deep

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            ModelTier("turbo")
