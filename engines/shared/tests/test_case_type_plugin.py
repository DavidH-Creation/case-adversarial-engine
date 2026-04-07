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
        self.plugin = RegistryPlugin(
            {
                "civil_loan": {
                    "system": "sys-prompt",
                    "build_user": lambda *, x: f"dict-prompt:{x}",
                },
            }
        )

    def test_happy_path_returns_string(self):
        result = self.plugin.get_prompt("attack_chain_optimizer", "civil_loan", {"x": "hello"})
        assert result == "dict-prompt:hello"

    def test_unregistered_raises_unsupported_case_type_error(self):
        with pytest.raises(UnsupportedCaseTypeError) as exc_info:
            self.plugin.get_prompt("attack_chain_optimizer", "labor_dispute", {})
        assert exc_info.value.case_type == "labor_dispute"


# ---------------------------------------------------------------------------
# RegistryPlugin — allowed_impact_targets (Unit 22 Phase C.5a)
# ---------------------------------------------------------------------------


class _ModuleWithVocab:
    """Module-style entry that declares an ALLOWED_IMPACT_TARGETS attribute."""

    ALLOWED_IMPACT_TARGETS: frozenset[str] = frozenset({"a", "b", "c"})

    def build_user_prompt(self, *, k: str = "x") -> str:
        return f"vocab-module:{k}"


class _ModuleWithoutVocab:
    """Module-style entry that omits ALLOWED_IMPACT_TARGETS."""

    def build_user_prompt(self, *, k: str = "x") -> str:
        return f"no-vocab-module:{k}"


class TestAllowedImpactTargets:
    """plugin.allowed_impact_targets(case_type) lookup behavior."""

    def test_module_based_returns_frozenset(self):
        plugin = RegistryPlugin({"civil_loan": _ModuleWithVocab()})
        result = plugin.allowed_impact_targets("civil_loan")
        assert isinstance(result, frozenset)
        assert result == frozenset({"a", "b", "c"})

    def test_dict_based_returns_frozenset(self):
        plugin = RegistryPlugin(
            {
                "civil_loan": {
                    "build_user": lambda *, k="x": f"dict:{k}",
                    "allowed_impact_targets": frozenset({"d", "e"}),
                }
            }
        )
        result = plugin.allowed_impact_targets("civil_loan")
        assert isinstance(result, frozenset)
        assert result == frozenset({"d", "e"})

    def test_dict_based_accepts_set_or_list_and_returns_frozenset(self):
        """The plugin must coerce set/list/tuple input to frozenset."""
        plugin = RegistryPlugin(
            {
                "civil_loan": {
                    "build_user": lambda: "x",
                    "allowed_impact_targets": ["x", "y", "x"],  # list with dup
                }
            }
        )
        result = plugin.allowed_impact_targets("civil_loan")
        assert result == frozenset({"x", "y"})

    def test_unregistered_raises_unsupported_case_type_error(self):
        plugin = RegistryPlugin({"civil_loan": _ModuleWithVocab()})
        with pytest.raises(UnsupportedCaseTypeError) as exc:
            plugin.allowed_impact_targets("criminal")
        assert exc.value.case_type == "criminal"
        assert "civil_loan" in exc.value.available

    def test_module_missing_constant_raises_value_error(self):
        plugin = RegistryPlugin({"civil_loan": _ModuleWithoutVocab()})
        with pytest.raises(ValueError, match="ALLOWED_IMPACT_TARGETS"):
            plugin.allowed_impact_targets("civil_loan")

    def test_dict_missing_key_raises_value_error(self):
        plugin = RegistryPlugin(
            {"civil_loan": {"build_user": lambda: "x"}}
        )
        with pytest.raises(ValueError, match="allowed_impact_targets"):
            plugin.allowed_impact_targets("civil_loan")


class TestIssueImpactRankerPluginVocabulary:
    """The real issue_impact_ranker plugin must declare every case type's
    ALLOWED_IMPACT_TARGETS so that ranker construction never raises ValueError.
    """

    def test_all_three_case_types_declare_vocabulary(self):
        from engines.simulation_run.issue_impact_ranker.prompts import plugin

        for ct in ("civil_loan", "labor_dispute", "real_estate"):
            vocab = plugin.allowed_impact_targets(ct)
            assert isinstance(vocab, frozenset)
            assert vocab, f"{ct}: ALLOWED_IMPACT_TARGETS must be non-empty"
            # 'credibility' is the case-type-neutral pivot — every case type
            # must include it because issues that destroy a party's credibility
            # have cross-cutting impact.
            assert "credibility" in vocab, (
                f"{ct}: ALLOWED_IMPACT_TARGETS must include 'credibility'"
            )

    def test_civil_loan_vocabulary_matches_expected(self):
        from engines.simulation_run.issue_impact_ranker.prompts import plugin

        assert plugin.allowed_impact_targets("civil_loan") == frozenset(
            {"principal", "interest", "penalty", "attorney_fee", "credibility"}
        )


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
            assert "civil_loan" in p._registry, f"{p!r} missing civil_loan"

    def test_unsupported_case_type_from_plugin(self):
        """Unregistered case type raises UnsupportedCaseTypeError via any plugin."""
        from engines.simulation_run.action_recommender.prompts import plugin

        with pytest.raises(UnsupportedCaseTypeError):
            plugin.get_prompt("action_recommender", "criminal_law", {})


# ---------------------------------------------------------------------------
# Integration: Unit 14 (Q1=B) — remaining engines export `plugin`
# ---------------------------------------------------------------------------


class TestRemainingEnginePluginExports:
    """Engines outside ``simulation_run`` that also expose a ``CaseTypePlugin``.

    Adding new entries here is a forcing function: any engine listed below
    must satisfy the Protocol and have ``civil_loan`` registered. ``case_extractor``
    (uses single ``"generic"`` key) and ``document_assistance`` (uses 2D
    ``(doc_type, case_type)`` key) are intentionally NOT listed — they need
    a custom plugin design out of Unit 14 scope.
    """

    def test_admissibility_evaluator_exports_plugin(self):
        from engines.case_structuring.admissibility_evaluator.prompts import plugin

        assert isinstance(plugin, CaseTypePlugin)
        assert "civil_loan" in plugin._registry

    def test_evidence_indexer_exports_plugin(self):
        from engines.case_structuring.evidence_indexer.prompts import plugin

        assert isinstance(plugin, CaseTypePlugin)
        assert "civil_loan" in plugin._registry

    def test_evidence_weight_scorer_exports_plugin(self):
        from engines.case_structuring.evidence_weight_scorer.prompts import plugin

        assert isinstance(plugin, CaseTypePlugin)
        assert "civil_loan" in plugin._registry

    def test_issue_extractor_exports_plugin(self):
        from engines.case_structuring.issue_extractor.prompts import plugin

        assert isinstance(plugin, CaseTypePlugin)
        assert "civil_loan" in plugin._registry

    def test_adversarial_exports_plugin(self):
        from engines.adversarial.prompts import plugin

        assert isinstance(plugin, CaseTypePlugin)
        assert "civil_loan" in plugin._registry

    def test_interactive_followup_exports_plugin(self):
        from engines.interactive_followup.prompts import plugin

        assert isinstance(plugin, CaseTypePlugin)
        assert "civil_loan" in plugin._registry

    def test_pretrial_conference_exports_plugin(self):
        from engines.pretrial_conference.prompts import plugin

        assert isinstance(plugin, CaseTypePlugin)
        assert "civil_loan" in plugin._registry

    def test_procedure_setup_exports_plugin(self):
        from engines.procedure_setup.prompts import plugin

        assert isinstance(plugin, CaseTypePlugin)
        assert "civil_loan" in plugin._registry

    def test_report_generation_exports_plugin(self):
        from engines.report_generation.prompts import plugin

        assert isinstance(plugin, CaseTypePlugin)
        assert "civil_loan" in plugin._registry

    def test_simulation_run_root_exports_plugin(self):
        from engines.simulation_run.prompts import plugin

        assert isinstance(plugin, CaseTypePlugin)
        assert "civil_loan" in plugin._registry


# ---------------------------------------------------------------------------
# Integration: end-to-end behavioral verification of every exported plugin
#
# The TestRemainingEnginePluginExports class above only verifies *Protocol
# shape* (isinstance) and that "civil_loan" is a key. That is necessary but
# not sufficient — it would still pass even if the plugin's underlying
# registry were malformed (e.g., entries that are neither dict-with-build_user
# nor module-with-build_user_prompt). The two parameterized classes below
# close that gap by exercising actual plugin behavior on every engine listed.
# ---------------------------------------------------------------------------


def _import_engine_plugin(dotted_path: str):
    """Helper: import an engine's prompts.plugin by dotted package path."""
    import importlib

    module = importlib.import_module(dotted_path)
    return module.plugin


# All 16 engines that export `plugin = RegistryPlugin(PROMPT_REGISTRY)`.
# These all satisfy the Protocol *shape* (isinstance + has civil_loan key),
# so they all participate in the unsupported-case-type behavioral check.
ALL_PLUGIN_ENGINES: list[tuple[str, str]] = [
    # (engine_name, dotted_import_path)
    ("admissibility_evaluator", "engines.case_structuring.admissibility_evaluator.prompts"),
    ("evidence_indexer", "engines.case_structuring.evidence_indexer.prompts"),
    ("evidence_weight_scorer", "engines.case_structuring.evidence_weight_scorer.prompts"),
    ("issue_extractor", "engines.case_structuring.issue_extractor.prompts"),
    ("adversarial", "engines.adversarial.prompts"),
    ("interactive_followup", "engines.interactive_followup.prompts"),
    ("pretrial_conference", "engines.pretrial_conference.prompts"),
    ("procedure_setup", "engines.procedure_setup.prompts"),
    ("report_generation", "engines.report_generation.prompts"),
    ("simulation_run_root", "engines.simulation_run.prompts"),
    ("action_recommender", "engines.simulation_run.action_recommender.prompts"),
    ("attack_chain_optimizer", "engines.simulation_run.attack_chain_optimizer.prompts"),
    ("decision_path_tree", "engines.simulation_run.decision_path_tree.prompts"),
    ("defense_chain", "engines.simulation_run.defense_chain.prompts"),
    ("issue_impact_ranker", "engines.simulation_run.issue_impact_ranker.prompts"),
    ("issue_category_classifier", "engines.simulation_run.issue_category_classifier.prompts"),
]

# The subset of engines whose registry entries are FUNCTIONALLY DISPATCHABLE,
# i.e. each entry is either a dict with a callable ``build_user`` or a module
# whose top-level ``build_user_prompt`` is callable. Calling
# ``plugin.get_prompt(name, case_type, ctx)`` on one of these engines actually
# returns a built prompt string (does not raise AttributeError).
#
# The COMPLEMENT of this list — interface-only stubs whose prompt modules do
# NOT yet expose ``build_user_prompt`` — was discovered during the batch-4
# adversarial review. Those engines satisfy the Protocol *shape* (so they
# pass isinstance and the unsupported-case-type behavioral check) but their
# runners still bypass the plugin and access the prompt module directly. The
# plugin export on those engines is currently a forward-looking handle that
# completes once each runner migrates to ``plugin.get_prompt()`` and each
# prompt module conforms to the build_user_prompt convention. Tracked as
# Unit 14 follow-up work.
ENGINES_WITH_FUNCTIONAL_PLUGIN: list[tuple[str, str]] = [
    # Dict-based registries with callable build_user (admissibility/weight_scorer)
    ("admissibility_evaluator", "engines.case_structuring.admissibility_evaluator.prompts"),
    ("evidence_weight_scorer", "engines.case_structuring.evidence_weight_scorer.prompts"),
    # Module-based registries whose civil_loan/labor_dispute/real_estate modules
    # all expose build_user_prompt (the 6 simulation_run sub-engines)
    ("action_recommender", "engines.simulation_run.action_recommender.prompts"),
    ("attack_chain_optimizer", "engines.simulation_run.attack_chain_optimizer.prompts"),
    ("decision_path_tree", "engines.simulation_run.decision_path_tree.prompts"),
    ("defense_chain", "engines.simulation_run.defense_chain.prompts"),
    ("issue_impact_ranker", "engines.simulation_run.issue_impact_ranker.prompts"),
    ("issue_category_classifier", "engines.simulation_run.issue_category_classifier.prompts"),
    # Module-based registries newly completed in batch-4-followup
    ("evidence_indexer", "engines.case_structuring.evidence_indexer.prompts"),
    ("issue_extractor", "engines.case_structuring.issue_extractor.prompts"),
    ("report_generation", "engines.report_generation.prompts"),
    ("procedure_setup", "engines.procedure_setup.prompts"),
    ("interactive_followup", "engines.interactive_followup.prompts"),
    ("simulation_run_root", "engines.simulation_run.prompts"),
    ("pretrial_conference", "engines.pretrial_conference.prompts"),
    ("adversarial", "engines.adversarial.prompts"),
]


class TestEveryPluginRaisesUnsupportedOnUnknownCaseType:
    """Calling get_prompt(...) with an unknown case_type must raise
    ``UnsupportedCaseTypeError`` on EVERY exported plugin — not KeyError,
    not AttributeError, not silently return None.

    Catches the regression class where a future engine assigns
    ``plugin = PROMPT_REGISTRY`` (forgetting the RegistryPlugin wrapper) or
    refactors RegistryPlugin in a way that breaks the unsupported-error path.
    Applies to all 16 engines because the unsupported-case-type code path in
    RegistryPlugin short-circuits before touching the entry contents.
    """

    @pytest.mark.parametrize(("engine_name", "dotted_path"), ALL_PLUGIN_ENGINES)
    def test_unknown_case_type_raises_unsupported(self, engine_name: str, dotted_path: str):
        plugin = _import_engine_plugin(dotted_path)
        with pytest.raises(UnsupportedCaseTypeError) as exc_info:
            plugin.get_prompt(engine_name, "_nonexistent_case_type_xyz_", {})
        assert exc_info.value.case_type == "_nonexistent_case_type_xyz_"


class TestFunctionalPluginRegistryShape:
    """Structural integrity check for engines whose plugin is fully functional.

    Each entry in ``plugin._registry`` must be either:
      (a) a dict containing a callable ``build_user`` (dict-based pattern), OR
      (b) an object exposing a callable ``build_user_prompt`` attribute
          (module-based pattern).

    Catches the regression class where a future commit registers a malformed
    entry (a string, a module that lacks build_user_prompt, or a dict missing
    the build_user key). Without this test, such breakage would only surface
    at LLM call time in production.

    Parameterized over ENGINES_WITH_FUNCTIONAL_PLUGIN only — the 8 interface-
    only stubs are excluded by design (see ALL_PLUGIN_ENGINES docstring).
    """

    @pytest.mark.parametrize(("engine_name", "dotted_path"), ENGINES_WITH_FUNCTIONAL_PLUGIN)
    def test_every_registry_entry_is_dispatchable(
        self, engine_name: str, dotted_path: str
    ):
        plugin = _import_engine_plugin(dotted_path)
        registry = plugin._registry
        assert len(registry) > 0, f"{engine_name}: registry is empty"
        for case_type, entry in registry.items():
            if isinstance(entry, dict):
                assert "build_user" in entry, (
                    f"{engine_name}/{case_type}: dict entry missing 'build_user' key"
                )
                assert callable(entry["build_user"]), (
                    f"{engine_name}/{case_type}: dict entry 'build_user' is not callable"
                )
            else:
                assert hasattr(entry, "build_user_prompt"), (
                    f"{engine_name}/{case_type}: module-style entry missing build_user_prompt"
                )
                assert callable(entry.build_user_prompt), (
                    f"{engine_name}/{case_type}: build_user_prompt is not callable"
                )
