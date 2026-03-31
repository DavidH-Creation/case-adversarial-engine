"""Unit tests for CaseTypePlugin Protocol and RegistryPlugin.

Test scenarios (per Unit 11 spec):
- Happy path: RegistryPlugin.get_prompt returns non-empty string for registered case type
- Edge case: unregistered case type raises UnsupportedCaseTypeError, not KeyError
- Protocol compliance: RegistryPlugin satisfies CaseTypePlugin Protocol
- Integration: all 6 simulation_run prompt __init__ modules export a `plugin`
"""
from __future__ import annotations

import pytest

from engines.shared.case_type_plugin import (
    CaseTypePlugin,
    RegistryPlugin,
    UnsupportedCaseTypeError,
)


# ---------------------------------------------------------------------------
# UnsupportedCaseTypeError
# ---------------------------------------------------------------------------

class TestUnsupportedCaseTypeError:
    def test_message_contains_case_type(self):
        err = UnsupportedCaseTypeError("criminal")
        assert "criminal" in str(err)

    def test_message_lists_available_when_provided(self):
        err = UnsupportedCaseTypeError("criminal", ["civil_loan", "labor_dispute"])
        assert "civil_loan" in str(err)
        assert "labor_dispute" in str(err)

    def test_attributes(self):
        err = UnsupportedCaseTypeError("foo", ["a", "b"])
        assert err.case_type == "foo"
        assert err.available == ["a", "b"]

    def test_empty_available(self):
        err = UnsupportedCaseTypeError("foo")
        assert err.available == []
        assert "foo" in str(err)

    def test_is_exception(self):
        assert isinstance(UnsupportedCaseTypeError("x"), Exception)


# ---------------------------------------------------------------------------
# RegistryPlugin — Protocol compliance
# ---------------------------------------------------------------------------

class TestRegistryPluginProtocol:
    def test_is_case_type_plugin(self):
        plugin = RegistryPlugin({})
        assert isinstance(plugin, CaseTypePlugin)

    def test_empty_registry_raises_on_any_case_type(self):
        plugin = RegistryPlugin({})
        with pytest.raises(UnsupportedCaseTypeError):
            plugin.get_prompt("engine", "civil_loan", {})


# ---------------------------------------------------------------------------
# RegistryPlugin — module-based registry
# ---------------------------------------------------------------------------

class FakeModule:
    """Simulates a module-based PROMPT_REGISTRY entry."""

    def build_user_prompt(self, *, key: str = "default") -> str:
        return f"module-prompt:{key}"


class TestRegistryPluginModuleBased:
    def setup_method(self):
        self.plugin = RegistryPlugin({"civil_loan": FakeModule()})

    def test_happy_path_returns_string(self):
        result = self.plugin.get_prompt("action_recommender", "civil_loan", {"key": "test"})
        assert isinstance(result, str)
        assert result == "module-prompt:test"

    def test_unregistered_raises_unsupported_not_key_error(self):
        with pytest.raises(UnsupportedCaseTypeError) as exc_info:
            self.plugin.get_prompt("action_recommender", "labor_dispute", {})
        assert exc_info.value.case_type == "labor_dispute"
        assert "civil_loan" in exc_info.value.available

    def test_does_not_raise_key_error(self):
        """UnsupportedCaseTypeError should be raised, never KeyError."""
        with pytest.raises(UnsupportedCaseTypeError):
            self.plugin.get_prompt("engine", "unknown", {})
        # Verify KeyError is NOT raised (it would propagate if not caught)
        try:
            self.plugin.get_prompt("engine", "unknown", {})
        except UnsupportedCaseTypeError:
            pass
        except KeyError:
            pytest.fail("KeyError leaked — should be UnsupportedCaseTypeError")


# ---------------------------------------------------------------------------
# RegistryPlugin — dict-based registry
# ---------------------------------------------------------------------------

class TestRegistryPluginDictBased:
    def setup_method(self):
        self.plugin = RegistryPlugin({
            "civil_loan": {
                "system": "sys-prompt",
                "build_user": lambda *, x: f"dict-prompt:{x}",
            },
        })

    def test_happy_path_returns_string(self):
        result = self.plugin.get_prompt("attack_chain_optimizer", "civil_loan", {"x": "hello"})
        assert result == "dict-prompt:hello"

    def test_unregistered_raises_unsupported_case_type_error(self):
        with pytest.raises(UnsupportedCaseTypeError) as exc_info:
            self.plugin.get_prompt("attack_chain_optimizer", "labor_dispute", {})
        assert exc_info.value.case_type == "labor_dispute"


# ---------------------------------------------------------------------------
# Integration: all 6 simulation_run prompt modules export `plugin`
# ---------------------------------------------------------------------------

class TestSimulationRunPluginExports:
    """Each simulation_run sub-engine must export a `plugin: CaseTypePlugin`."""

    def test_action_recommender_exports_plugin(self):
        from engines.simulation_run.action_recommender.prompts import plugin
        assert isinstance(plugin, CaseTypePlugin)

    def test_attack_chain_optimizer_exports_plugin(self):
        from engines.simulation_run.attack_chain_optimizer.prompts import plugin
        assert isinstance(plugin, CaseTypePlugin)

    def test_decision_path_tree_exports_plugin(self):
        from engines.simulation_run.decision_path_tree.prompts import plugin
        assert isinstance(plugin, CaseTypePlugin)

    def test_defense_chain_exports_plugin(self):
        from engines.simulation_run.defense_chain.prompts import plugin
        assert isinstance(plugin, CaseTypePlugin)

    def test_issue_impact_ranker_exports_plugin(self):
        from engines.simulation_run.issue_impact_ranker.prompts import plugin
        assert isinstance(plugin, CaseTypePlugin)

    def test_issue_category_classifier_exports_plugin(self):
        from engines.simulation_run.issue_category_classifier.prompts import plugin
        assert isinstance(plugin, CaseTypePlugin)

    def test_all_plugins_contain_civil_loan(self):
        """civil_loan must be registered in all 6 engines."""
        from engines.simulation_run.action_recommender.prompts import plugin as p1
        from engines.simulation_run.attack_chain_optimizer.prompts import plugin as p2
        from engines.simulation_run.decision_path_tree.prompts import plugin as p3
        from engines.simulation_run.defense_chain.prompts import plugin as p4
        from engines.simulation_run.issue_impact_ranker.prompts import plugin as p5
        from engines.simulation_run.issue_category_classifier.prompts import plugin as p6

        for p in (p1, p2, p3, p4, p5, p6):
            assert "civil_loan" in p._registry, (
                f"{p!r} missing civil_loan"
            )

    def test_unsupported_case_type_from_plugin(self):
        """Unregistered case type raises UnsupportedCaseTypeError via any plugin."""
        from engines.simulation_run.action_recommender.prompts import plugin

        with pytest.raises(UnsupportedCaseTypeError):
            plugin.get_prompt("action_recommender", "criminal_law", {})
