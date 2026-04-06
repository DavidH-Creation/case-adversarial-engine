"""
Tests for engines/shared/config_loader.py

Covers:
  - Default values when no config file exists
  - Loading from a valid YAML file
  - Partial YAML (missing sections) falls back to defaults
  - Unknown keys are silently ignored
  - Invalid YAML content falls back to defaults
  - Type coercion for numeric/boolean values
  - Explicit config_path overrides project_root resolution
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from engines.shared.config_loader import (
    EngineConfig,
    InteractiveConfig,
    PipelineConfig,
    ReportConfig,
    RulesConfig,
    load_engine_config,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_yaml(path: Path, data: dict) -> Path:
    path.write_text(yaml.dump(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Defaults (no config file)
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_returns_engine_config_when_no_file(self, tmp_path: Path):
        cfg = load_engine_config(config_path=tmp_path / "nonexistent.yaml")
        assert isinstance(cfg, EngineConfig)

    def test_pipeline_defaults(self, tmp_path: Path):
        cfg = load_engine_config(config_path=tmp_path / "missing.yaml")
        assert cfg.pipeline.max_retries == 3
        assert cfg.pipeline.max_tokens == 4096
        assert cfg.pipeline.temperature == 0.0
        assert cfg.pipeline.timeout_seconds == 120.0
        assert cfg.pipeline.output_dir == "outputs/"

    def test_report_defaults(self, tmp_path: Path):
        cfg = load_engine_config(config_path=tmp_path / "missing.yaml")
        assert cfg.report.include_disclaimer is True
        assert cfg.report.redact_pii is True

    def test_interactive_defaults(self, tmp_path: Path):
        cfg = load_engine_config(config_path=tmp_path / "missing.yaml")
        assert cfg.interactive.max_question_length == 2000
        assert cfg.interactive.max_session_turns == 20

    def test_rules_defaults(self, tmp_path: Path):
        cfg = load_engine_config(config_path=tmp_path / "missing.yaml")
        assert cfg.rules.prof_lender_min_cases == 3
        assert cfg.rules.prof_lender_min_borrowers == 3
        assert cfg.rules.prof_lender_max_span_months == 24
        assert cfg.rules.false_litigation_ratio == 2.0
        assert cfg.rules.lpr_multiplier_cap == 4.0


# ---------------------------------------------------------------------------
# Full YAML load
# ---------------------------------------------------------------------------


class TestFullLoad:
    def test_all_sections_loaded(self, tmp_path: Path):
        data = {
            "pipeline": {
                "max_retries": 5,
                "max_tokens": 8192,
                "temperature": 0.7,
                "timeout_seconds": 300.0,
                "output_dir": "custom_out/",
            },
            "report": {"include_disclaimer": False, "redact_pii": False},
            "interactive": {"max_question_length": 5000, "max_session_turns": 50},
            "rules": {
                "prof_lender_min_cases": 10,
                "prof_lender_min_borrowers": 5,
                "prof_lender_max_span_months": 36,
                "false_litigation_ratio": 3.0,
                "lpr_multiplier_cap": 6.0,
            },
        }
        cfg_path = _write_yaml(tmp_path / "engine_config.yaml", data)
        cfg = load_engine_config(cfg_path)

        assert cfg.pipeline.max_retries == 5
        assert cfg.pipeline.max_tokens == 8192
        assert cfg.pipeline.temperature == 0.7
        assert cfg.pipeline.timeout_seconds == 300.0
        assert cfg.pipeline.output_dir == "custom_out/"
        assert cfg.report.include_disclaimer is False
        assert cfg.report.redact_pii is False
        assert cfg.interactive.max_question_length == 5000
        assert cfg.interactive.max_session_turns == 50
        assert cfg.rules.prof_lender_min_cases == 10
        assert cfg.rules.lpr_multiplier_cap == 6.0


# ---------------------------------------------------------------------------
# Partial YAML
# ---------------------------------------------------------------------------


class TestPartialLoad:
    def test_missing_section_uses_defaults(self, tmp_path: Path):
        """YAML with only pipeline section — other sections keep defaults."""
        data = {"pipeline": {"max_retries": 7}}
        cfg_path = _write_yaml(tmp_path / "engine_config.yaml", data)
        cfg = load_engine_config(cfg_path)

        assert cfg.pipeline.max_retries == 7
        assert cfg.pipeline.max_tokens == 4096  # default
        assert cfg.report.redact_pii is True  # default
        assert cfg.interactive.max_question_length == 2000  # default

    def test_empty_yaml_uses_defaults(self, tmp_path: Path):
        cfg_path = tmp_path / "engine_config.yaml"
        cfg_path.write_text("", encoding="utf-8")
        cfg = load_engine_config(cfg_path)
        assert cfg.pipeline.max_retries == 3

    def test_yaml_with_only_unknown_keys(self, tmp_path: Path):
        data = {"pipeline": {"unknown_key": 999, "max_retries": 2}}
        cfg_path = _write_yaml(tmp_path / "engine_config.yaml", data)
        cfg = load_engine_config(cfg_path)

        assert cfg.pipeline.max_retries == 2
        assert not hasattr(cfg.pipeline, "unknown_key")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_non_dict_yaml_falls_back_to_defaults(self, tmp_path: Path):
        cfg_path = tmp_path / "engine_config.yaml"
        cfg_path.write_text("just a string\n", encoding="utf-8")
        cfg = load_engine_config(cfg_path)
        assert cfg.pipeline.max_retries == 3

    def test_invalid_yaml_falls_back_to_defaults(self, tmp_path: Path):
        cfg_path = tmp_path / "engine_config.yaml"
        cfg_path.write_text("{{{{invalid yaml", encoding="utf-8")
        cfg = load_engine_config(cfg_path)
        assert cfg.pipeline.max_retries == 3

    def test_project_root_resolution(self, tmp_path: Path):
        """When config_path is None, resolves relative to project_root."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        data = {"pipeline": {"max_retries": 42}}
        _write_yaml(config_dir / "engine_config.yaml", data)
        cfg = load_engine_config(project_root=tmp_path)
        assert cfg.pipeline.max_retries == 42

    def test_type_coercion_int_from_string(self, tmp_path: Path):
        """YAML may parse '5' as int already, but test explicit coercion."""
        data = {"pipeline": {"max_retries": 5, "temperature": 0.5}}
        cfg_path = _write_yaml(tmp_path / "engine_config.yaml", data)
        cfg = load_engine_config(cfg_path)
        assert isinstance(cfg.pipeline.max_retries, int)
        assert isinstance(cfg.pipeline.temperature, float)

    def test_section_with_non_dict_value_ignored(self, tmp_path: Path):
        """If a section is a list or scalar, it's silently skipped."""
        data = {"pipeline": "not a dict", "report": {"redact_pii": False}}
        cfg_path = _write_yaml(tmp_path / "engine_config.yaml", data)
        cfg = load_engine_config(cfg_path)
        assert cfg.pipeline.max_retries == 3  # default, not overridden
        assert cfg.report.redact_pii is False  # loaded


# ---------------------------------------------------------------------------
# Dataclass construction
# ---------------------------------------------------------------------------


class TestDataclasses:
    def test_engine_config_default_construction(self):
        cfg = EngineConfig()
        assert isinstance(cfg.pipeline, PipelineConfig)
        assert isinstance(cfg.report, ReportConfig)
        assert isinstance(cfg.interactive, InteractiveConfig)
        assert isinstance(cfg.rules, RulesConfig)

    def test_pipeline_config_fields(self):
        pc = PipelineConfig(max_retries=10, timeout_seconds=60.0)
        assert pc.max_retries == 10
        assert pc.timeout_seconds == 60.0
        assert pc.max_tokens == 4096  # default

    def test_rules_config_fields(self):
        rc = RulesConfig(lpr_multiplier_cap=8.0)
        assert rc.lpr_multiplier_cap == 8.0
        assert rc.prof_lender_min_cases == 3  # default
