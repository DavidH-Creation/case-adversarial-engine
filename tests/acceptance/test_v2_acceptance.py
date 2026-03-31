"""
v2 多案型验收测试套件 / v2 Multi-case-type acceptance test suite.

Tests use mock LLM (no real LLM calls) to verify:
- YAML loading and validation logic
- Metric computation (consistency, citation_rate, path_explainable)
- Report JSON structure and field types
- Edge cases: invalid YAML, run failures, N=0 valid runs
- run_acceptance_for_case honours skipped/passed/failed status correctly
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.run_acceptance import (
    METRIC_THRESHOLDS,
    MIN_VALID_RUNS,
    REQUIRED_YAML_KEYS,
    compute_metrics,
    load_and_validate_yaml,
    run_acceptance,
    run_acceptance_for_case,
    write_report,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_VALID_YAML_CONTENT = {
    "case_id": "case-test-labor-001",
    "case_slug": "testlabor001",
    "case_type": "labor_dispute",
    "model": "claude-sonnet-4-6",
    "parties": {
        "plaintiff": {"party_id": "party-p", "name": "原告甲"},
        "defendant": {"party_id": "party-d", "name": "被告乙"},
    },
    "summary": [["原告", "甲"], ["被告", "乙"]],
    "materials": {
        "plaintiff": [
            {
                "source_id": "src-p-001",
                "text": "劳动合同原件。",
                "metadata": {
                    "document_type": "labor_contract",
                    "submitter": "plaintiff",
                    "status": "admitted_for_discussion",
                },
            }
        ],
        "defendant": [
            {
                "source_id": "src-d-001",
                "text": "公司规章制度。",
                "metadata": {
                    "document_type": "company_policy",
                    "submitter": "defendant",
                    "status": "admitted_for_discussion",
                },
            }
        ],
    },
    "claims": [
        {
            "claim_id": "c-001",
            "claim_category": "违法解除",
            "title": "支付赔偿金",
            "claim_text": "要求支付赔偿金。",
        }
    ],
    "defenses": [
        {
            "defense_id": "d-001",
            "defense_category": "合法解除",
            "against_claim_id": "c-001",
            "title": "解除合法",
            "defense_text": "依规章解除，合法。",
        }
    ],
}


def _make_valid_run(
    issue_ids: list[str] | None = None,
    evidence_citations: list[list[str]] | None = None,
    outcome_paths: dict | None = None,
) -> dict:
    """Build a successful run result dict."""
    if issue_ids is None:
        issue_ids = ["i-001", "i-002"]
    if evidence_citations is None:
        evidence_citations = [["src-p-001"], ["src-d-001"]]
    if outcome_paths is None:
        outcome_paths = {
            "win_path": {"trigger_conditions": ["原告举证充分"]},
            "lose_path": {"trigger_conditions": ["被告举证充分"]},
            "mediation_path": {"trigger_conditions": ["调解区间合理"]},
            "supplement_path": {"trigger_conditions": []},
        }
    return {
        "success": True,
        "issue_ids": issue_ids,
        "evidence_citations": evidence_citations,
        "outcome_paths": outcome_paths,
        "error": None,
    }


def _make_failed_run(error: str = "pipeline_timeout") -> dict:
    return {
        "success": False,
        "issue_ids": [],
        "evidence_citations": [],
        "outcome_paths": None,
        "error": error,
    }


def _make_yaml_file(tmp_path: Path, content: dict, filename: str = "test_case.yaml") -> Path:
    p = tmp_path / filename
    p.write_text(yaml.dump(content, allow_unicode=True), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# load_and_validate_yaml
# ---------------------------------------------------------------------------


class TestLoadAndValidateYaml:
    def test_valid_yaml_returns_data(self, tmp_path: Path) -> None:
        p = _make_yaml_file(tmp_path, _VALID_YAML_CONTENT)
        data, err = load_and_validate_yaml(p)
        assert err is None
        assert data is not None
        assert data["case_id"] == "case-test-labor-001"

    def test_missing_required_key_returns_error(self, tmp_path: Path) -> None:
        bad = dict(_VALID_YAML_CONTENT)
        del bad["claims"]
        p = _make_yaml_file(tmp_path, bad)
        data, err = load_and_validate_yaml(p)
        assert data is None
        assert err is not None
        assert "claims" in err

    def test_all_required_keys_must_be_present(self, tmp_path: Path) -> None:
        for key in REQUIRED_YAML_KEYS:
            bad = dict(_VALID_YAML_CONTENT)
            del bad[key]
            p = _make_yaml_file(tmp_path, bad, f"missing_{key}.yaml")
            data, err = load_and_validate_yaml(p)
            assert data is None, f"Expected failure when '{key}' is missing"
            assert err is not None

    def test_invalid_yaml_syntax_returns_error(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.yaml"
        p.write_text("case_id: [unclosed", encoding="utf-8")
        data, err = load_and_validate_yaml(p)
        assert data is None
        assert err is not None

    def test_nonexistent_file_returns_error(self, tmp_path: Path) -> None:
        p = tmp_path / "nonexistent.yaml"
        data, err = load_and_validate_yaml(p)
        assert data is None
        assert err is not None

    def test_non_dict_yaml_returns_error(self, tmp_path: Path) -> None:
        p = tmp_path / "list.yaml"
        p.write_text("- item1\n- item2\n", encoding="utf-8")
        data, err = load_and_validate_yaml(p)
        assert data is None
        assert "not_dict" in (err or "")


# ---------------------------------------------------------------------------
# compute_metrics
# ---------------------------------------------------------------------------


class TestComputeMetrics:
    def test_empty_run_list_returns_zeros(self) -> None:
        m = compute_metrics([])
        assert m["consistency"] == 0.0
        assert m["citation_rate"] == 0.0
        assert m["path_explainable"] is False
        assert m["passed"] is False
        assert m["n_runs"] == 0
        assert m["n_success"] == 0

    def test_all_failed_runs_returns_zeros(self) -> None:
        runs = [_make_failed_run() for _ in range(3)]
        m = compute_metrics(runs)
        assert m["n_success"] == 0
        assert m["consistency"] == 0.0
        assert m["passed"] is False

    def test_perfect_consistency_single_run(self) -> None:
        runs = [_make_valid_run(issue_ids=["i-001", "i-002"])]
        m = compute_metrics(runs)
        # With 1 run, max count = 1, n_success = 1 → consistency = 1.0
        assert m["consistency"] == 1.0
        assert m["n_success"] == 1

    def test_consistency_stable_issue_across_runs(self) -> None:
        # i-001 appears in all 4 runs, i-002 in 3, i-003 in 1
        runs = [
            _make_valid_run(issue_ids=["i-001", "i-002"]),
            _make_valid_run(issue_ids=["i-001", "i-002"]),
            _make_valid_run(issue_ids=["i-001", "i-002"]),
            _make_valid_run(issue_ids=["i-001", "i-003"]),
        ]
        m = compute_metrics(runs)
        # i-001 appears in 4/4 → consistency = 1.0
        assert m["consistency"] == 1.0
        assert m["n_success"] == 4

    def test_consistency_below_threshold_fails(self) -> None:
        # i-001 appears in 2/4 runs → consistency = 0.5 < 0.75
        runs = [
            _make_valid_run(issue_ids=["i-001"]),
            _make_valid_run(issue_ids=["i-001"]),
            _make_valid_run(issue_ids=["i-002"]),
            _make_valid_run(issue_ids=["i-002"]),
        ]
        m = compute_metrics(runs)
        assert m["consistency"] == 0.5
        assert m["passed"] is False

    def test_citation_rate_all_cited(self) -> None:
        runs = [
            _make_valid_run(evidence_citations=[["src-p-001"], ["src-d-001"]]),
            _make_valid_run(evidence_citations=[["src-p-001"], ["src-d-001"]]),
        ]
        m = compute_metrics(runs)
        assert m["citation_rate"] == 1.0

    def test_citation_rate_partial(self) -> None:
        # 1 out of 4 outputs has empty citations
        runs = [
            _make_valid_run(evidence_citations=[["src-001"], []]),
            _make_valid_run(evidence_citations=[["src-001"], ["src-002"]]),
        ]
        m = compute_metrics(runs)
        # 3 cited out of 4 total
        assert m["citation_rate"] == pytest.approx(0.75)
        assert m["passed"] is False  # citation_rate < 1.0

    def test_citation_rate_no_outputs(self) -> None:
        runs = [_make_valid_run(evidence_citations=[])]
        m = compute_metrics(runs)
        assert m["citation_rate"] == 0.0

    def test_path_explainable_all_paths_filled(self) -> None:
        runs = [
            _make_valid_run(
                outcome_paths={
                    "win_path": {"trigger_conditions": ["原告举证充分"]},
                    "lose_path": {"trigger_conditions": ["被告举证充分"]},
                    "mediation_path": {"trigger_conditions": ["价格合理"]},
                    "supplement_path": {"trigger_conditions": ["补充证据"]},
                }
            )
        ]
        m = compute_metrics(runs)
        assert m["path_explainable"] is True

    def test_path_explainable_insufficient_data_fails(self) -> None:
        runs = [
            _make_valid_run(
                outcome_paths={
                    "win_path": {"trigger_conditions": ["insufficient_data"]},
                    "lose_path": {"trigger_conditions": ["被告举证充分"]},
                    "mediation_path": {"trigger_conditions": ["价格合理"]},
                    "supplement_path": {"trigger_conditions": ["补充证据"]},
                }
            )
        ]
        m = compute_metrics(runs)
        assert m["path_explainable"] is False

    def test_path_explainable_empty_trigger_conditions_fails(self) -> None:
        runs = [
            _make_valid_run(
                outcome_paths={
                    "win_path": {"trigger_conditions": []},  # empty = not explainable
                    "lose_path": {"trigger_conditions": ["被告举证充分"]},
                    "mediation_path": {"trigger_conditions": ["价格合理"]},
                    "supplement_path": {"trigger_conditions": ["补充证据"]},
                }
            )
        ]
        m = compute_metrics(runs)
        assert m["path_explainable"] is False

    def test_path_explainable_no_outcome_paths_returns_false(self) -> None:
        runs = [_make_valid_run(outcome_paths=None)]
        m = compute_metrics(runs)
        assert m["path_explainable"] is False

    def test_path_explainable_uses_last_successful_run(self) -> None:
        # First run has bad paths, last has good paths
        runs = [
            _make_valid_run(
                outcome_paths={
                    "win_path": {"trigger_conditions": ["insufficient_data"]},
                    "lose_path": {"trigger_conditions": ["x"]},
                    "mediation_path": {"trigger_conditions": ["x"]},
                    "supplement_path": {"trigger_conditions": ["x"]},
                }
            ),
            _make_valid_run(
                outcome_paths={
                    "win_path": {"trigger_conditions": ["原告胜诉条件"]},
                    "lose_path": {"trigger_conditions": ["被告胜诉条件"]},
                    "mediation_path": {"trigger_conditions": ["调解条件"]},
                    "supplement_path": {"trigger_conditions": ["补证方向"]},
                }
            ),
        ]
        m = compute_metrics(runs)
        assert m["path_explainable"] is True

    def test_passed_requires_all_three_metrics(self) -> None:
        good_paths = {
            "win_path": {"trigger_conditions": ["条件A"]},
            "lose_path": {"trigger_conditions": ["条件B"]},
            "mediation_path": {"trigger_conditions": ["条件C"]},
            "supplement_path": {"trigger_conditions": ["条件D"]},
        }
        # All good
        runs = [
            _make_valid_run(
                issue_ids=["i-001"],
                evidence_citations=[["src-001"]],
                outcome_paths=good_paths,
            )
            for _ in range(MIN_VALID_RUNS)
        ]
        m = compute_metrics(runs)
        assert m["passed"] is True

    def test_n_runs_and_n_success_reported_correctly(self) -> None:
        runs = [
            _make_valid_run(),
            _make_failed_run(),
            _make_valid_run(),
        ]
        m = compute_metrics(runs)
        assert m["n_runs"] == 3
        assert m["n_success"] == 2

    def test_metrics_are_floats_in_range(self) -> None:
        runs = [_make_valid_run() for _ in range(3)]
        m = compute_metrics(runs)
        assert isinstance(m["consistency"], float)
        assert 0.0 <= m["consistency"] <= 1.0
        assert isinstance(m["citation_rate"], float)
        assert 0.0 <= m["citation_rate"] <= 1.0
        assert isinstance(m["path_explainable"], bool)


# ---------------------------------------------------------------------------
# run_acceptance_for_case  (mock pipeline_runner)
# ---------------------------------------------------------------------------


class TestRunAcceptanceForCase:
    def _make_runner(self, results: list[dict]):
        """Return a mock pipeline_runner that yields results in order."""
        call_idx = [0]

        def runner(yaml_path: Path, run_index: int, output_dir: Path) -> dict:
            idx = call_idx[0]
            call_idx[0] += 1
            return results[idx % len(results)]

        return runner

    def test_invalid_yaml_returns_skipped(self, tmp_path: Path) -> None:
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("not: a: valid yaml: [", encoding="utf-8")
        result = run_acceptance_for_case(
            bad_yaml,
            n_runs=3,
            base_output_dir=tmp_path / "runs",
            pipeline_runner=self._make_runner([_make_valid_run()]),
        )
        assert result["status"] == "skipped"
        assert result["metrics"] is None
        assert result["reason"] is not None

    def test_missing_required_field_returns_skipped(self, tmp_path: Path) -> None:
        bad = dict(_VALID_YAML_CONTENT)
        del bad["defenses"]
        p = _make_yaml_file(tmp_path, bad)
        result = run_acceptance_for_case(
            p,
            n_runs=2,
            base_output_dir=tmp_path / "runs",
            pipeline_runner=self._make_runner([_make_valid_run()]),
        )
        assert result["status"] == "skipped"

    def test_all_runs_successful_computes_metrics(self, tmp_path: Path) -> None:
        p = _make_yaml_file(tmp_path, _VALID_YAML_CONTENT)
        good_result = _make_valid_run(
            issue_ids=["i-001"],
            evidence_citations=[["src-p-001"]],
            outcome_paths={
                "win_path": {"trigger_conditions": ["A"]},
                "lose_path": {"trigger_conditions": ["B"]},
                "mediation_path": {"trigger_conditions": ["C"]},
                "supplement_path": {"trigger_conditions": ["D"]},
            },
        )
        runner = self._make_runner([good_result] * 3)
        result = run_acceptance_for_case(
            p, n_runs=3, base_output_dir=tmp_path / "runs", pipeline_runner=runner
        )
        assert result["status"] in ("passed", "failed")  # depends on MIN_VALID_RUNS
        assert result["metrics"] is not None
        assert "consistency" in result["metrics"]
        assert "citation_rate" in result["metrics"]
        assert "path_explainable" in result["metrics"]

    def test_pipeline_failures_counted_in_runs(self, tmp_path: Path) -> None:
        p = _make_yaml_file(tmp_path, _VALID_YAML_CONTENT)
        mixed = [_make_valid_run(), _make_failed_run("pipeline_timeout"), _make_valid_run()]
        runner = self._make_runner(mixed)
        result = run_acceptance_for_case(
            p, n_runs=3, base_output_dir=tmp_path / "runs", pipeline_runner=runner
        )
        assert len(result["runs"]) == 3
        assert result["runs"][1]["success"] is False
        assert result["runs"][1]["error"] == "pipeline_timeout"

    def test_result_has_required_keys(self, tmp_path: Path) -> None:
        p = _make_yaml_file(tmp_path, _VALID_YAML_CONTENT)
        result = run_acceptance_for_case(
            p,
            n_runs=1,
            base_output_dir=tmp_path / "runs",
            pipeline_runner=self._make_runner([_make_valid_run()]),
        )
        for key in ("case_id", "yaml_path", "status", "reason", "metrics", "runs"):
            assert key in result, f"Missing key: {key}"

    def test_case_id_matches_yaml(self, tmp_path: Path) -> None:
        p = _make_yaml_file(tmp_path, _VALID_YAML_CONTENT)
        result = run_acceptance_for_case(
            p,
            n_runs=1,
            base_output_dir=tmp_path / "runs",
            pipeline_runner=self._make_runner([_make_valid_run()]),
        )
        assert result["case_id"] == "case-test-labor-001"


# ---------------------------------------------------------------------------
# run_acceptance (batch)
# ---------------------------------------------------------------------------


class TestRunAcceptance:
    def _make_fixed_runner(self, issue_ids=None, evidence_citations=None, outcome_paths=None):
        """Return a pipeline_runner that always returns a fixed successful result."""
        _good_paths = {
            "win_path": {"trigger_conditions": ["原告胜诉"]},
            "lose_path": {"trigger_conditions": ["被告胜诉"]},
            "mediation_path": {"trigger_conditions": ["调解"]},
            "supplement_path": {"trigger_conditions": ["补证"]},
        }
        fixed = _make_valid_run(
            issue_ids=issue_ids or ["i-001"],
            evidence_citations=evidence_citations or [["src-001"]],
            outcome_paths=outcome_paths or _good_paths,
        )

        def runner(yaml_path, run_index, output_dir):
            return fixed

        return runner

    def _write_case_yaml(self, cases_dir: Path, case_type: str, idx: int) -> Path:
        content = dict(_VALID_YAML_CONTENT)
        content["case_id"] = f"case-{case_type}-test-{idx:03d}"
        content["case_slug"] = f"{case_type}test{idx:03d}"
        content["case_type"] = case_type
        p = cases_dir / f"{case_type}_{idx}.yaml"
        p.write_text(yaml.dump(content, allow_unicode=True), encoding="utf-8")
        return p

    def test_no_matching_yamls_returns_empty_report(self, tmp_path: Path) -> None:
        cases_dir = tmp_path / "cases"
        cases_dir.mkdir()
        report = run_acceptance(
            case_type="labor_dispute",
            cases_dir=cases_dir,
            n_runs=1,
            pipeline_runner=self._make_fixed_runner(),
            output_dir=tmp_path / "out",
        )
        assert report["summary"]["total"] == 0
        assert report["summary"]["passed"] == 0
        assert report["summary"]["all_passed"] is False

    def test_matching_yamls_found_by_filename_prefix(self, tmp_path: Path) -> None:
        cases_dir = tmp_path / "cases"
        cases_dir.mkdir()
        self._write_case_yaml(cases_dir, "labor_dispute", 1)
        self._write_case_yaml(cases_dir, "labor_dispute", 2)
        # This one should not match
        self._write_case_yaml(cases_dir, "real_estate", 1)

        report = run_acceptance(
            case_type="labor_dispute",
            cases_dir=cases_dir,
            n_runs=1,
            pipeline_runner=self._make_fixed_runner(),
            output_dir=tmp_path / "out",
        )
        assert report["summary"]["total"] == 2
        assert report["case_type"] == "labor_dispute"

    def test_report_has_required_top_level_keys(self, tmp_path: Path) -> None:
        cases_dir = tmp_path / "cases"
        cases_dir.mkdir()
        self._write_case_yaml(cases_dir, "labor_dispute", 1)

        report = run_acceptance(
            case_type="labor_dispute",
            cases_dir=cases_dir,
            n_runs=1,
            pipeline_runner=self._make_fixed_runner(),
            output_dir=tmp_path / "out",
        )
        for key in (
            "generated_at",
            "case_type",
            "cases_dir",
            "n_runs_per_case",
            "summary",
            "thresholds",
            "cases",
        ):
            assert key in report, f"Missing top-level key: {key}"

    def test_report_summary_counts_are_consistent(self, tmp_path: Path) -> None:
        cases_dir = tmp_path / "cases"
        cases_dir.mkdir()
        self._write_case_yaml(cases_dir, "real_estate", 1)
        self._write_case_yaml(cases_dir, "real_estate", 2)
        self._write_case_yaml(cases_dir, "real_estate", 3)

        report = run_acceptance(
            case_type="real_estate",
            cases_dir=cases_dir,
            n_runs=1,
            pipeline_runner=self._make_fixed_runner(),
            output_dir=tmp_path / "out",
        )
        s = report["summary"]
        assert s["passed"] + s["failed"] + s["skipped"] == s["total"]

    def test_skipped_case_counted_separately(self, tmp_path: Path) -> None:
        cases_dir = tmp_path / "cases"
        cases_dir.mkdir()
        # Write a valid case
        self._write_case_yaml(cases_dir, "labor_dispute", 1)
        # Write an invalid case (missing required key)
        bad_content = dict(_VALID_YAML_CONTENT)
        del bad_content["claims"]
        bad_content["case_type"] = "labor_dispute"
        p = cases_dir / "labor_dispute_2.yaml"
        p.write_text(yaml.dump(bad_content, allow_unicode=True), encoding="utf-8")

        report = run_acceptance(
            case_type="labor_dispute",
            cases_dir=cases_dir,
            n_runs=1,
            pipeline_runner=self._make_fixed_runner(),
            output_dir=tmp_path / "out",
        )
        assert report["summary"]["skipped"] == 1
        assert report["summary"]["total"] == 2

    def test_thresholds_included_in_report(self, tmp_path: Path) -> None:
        cases_dir = tmp_path / "cases"
        cases_dir.mkdir()
        report = run_acceptance(
            case_type="labor_dispute",
            cases_dir=cases_dir,
            n_runs=1,
            pipeline_runner=self._make_fixed_runner(),
            output_dir=tmp_path / "out",
        )
        assert report["thresholds"]["consistency"] == METRIC_THRESHOLDS["consistency"]
        assert report["thresholds"]["citation_rate"] == METRIC_THRESHOLDS["citation_rate"]


# ---------------------------------------------------------------------------
# write_report
# ---------------------------------------------------------------------------


class TestWriteReport:
    def _sample_report(self) -> dict:
        return {
            "generated_at": "2026-03-31T00:00:00+00:00",
            "case_type": "labor_dispute",
            "cases_dir": "cases/",
            "n_runs_per_case": 3,
            "summary": {"total": 2, "passed": 2, "failed": 0, "skipped": 0, "all_passed": True},
            "thresholds": METRIC_THRESHOLDS,
            "cases": [],
        }

    def test_report_written_to_specified_path(self, tmp_path: Path) -> None:
        report = self._sample_report()
        out_path = tmp_path / "my_report.json"
        result_path = write_report(report, out_path)
        assert result_path == out_path
        assert out_path.exists()

    def test_report_is_valid_json(self, tmp_path: Path) -> None:
        report = self._sample_report()
        out_path = tmp_path / "report.json"
        write_report(report, out_path)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert data["case_type"] == "labor_dispute"

    def test_report_default_path_contains_date(self, tmp_path: Path) -> None:
        import scripts.run_acceptance as ra_mod

        original_root = ra_mod._PROJECT_ROOT
        try:
            # Patch PROJECT_ROOT to write into tmp_path
            ra_mod._PROJECT_ROOT = tmp_path
            report = self._sample_report()
            out_path = write_report(report)
            assert "report_" in out_path.name
            assert out_path.suffix == ".json"
        finally:
            ra_mod._PROJECT_ROOT = original_root

    def test_report_preserves_unicode(self, tmp_path: Path) -> None:
        report = self._sample_report()
        report["cases"] = [{"case_id": "案件-001", "status": "passed"}]
        out_path = tmp_path / "report.json"
        write_report(report, out_path)
        raw = out_path.read_text(encoding="utf-8")
        assert "案件-001" in raw


# ---------------------------------------------------------------------------
# Real case YAML files (smoke test — validates all 6 YAML files parse cleanly)
# ---------------------------------------------------------------------------


class TestCaseYamlFiles:
    """Verify that all 6 newly created case YAML files are valid."""

    _EXPECTED_CASES = [
        ("labor_dispute_1.yaml", "labor_dispute"),
        ("labor_dispute_2.yaml", "labor_dispute"),
        ("labor_dispute_3.yaml", "labor_dispute"),
        ("real_estate_1.yaml", "real_estate"),
        ("real_estate_2.yaml", "real_estate"),
        ("real_estate_3.yaml", "real_estate"),
    ]

    @pytest.mark.parametrize("filename,expected_type", _EXPECTED_CASES)
    def test_yaml_file_is_valid(self, filename: str, expected_type: str) -> None:
        yaml_path = _PROJECT_ROOT / "cases" / filename
        assert yaml_path.exists(), f"Missing case file: {yaml_path}"
        data, err = load_and_validate_yaml(yaml_path)
        assert err is None, f"{filename} failed validation: {err}"
        assert data is not None
        assert data["case_type"] == expected_type, (
            f"{filename}: expected case_type='{expected_type}', got '{data.get('case_type')}'"
        )

    @pytest.mark.parametrize("filename,_", _EXPECTED_CASES)
    def test_yaml_has_at_least_one_claim_and_defense(self, filename: str, _: str) -> None:
        yaml_path = _PROJECT_ROOT / "cases" / filename
        data, _ = load_and_validate_yaml(yaml_path)
        assert data is not None
        assert len(data["claims"]) >= 1, f"{filename}: must have at least 1 claim"
        assert len(data["defenses"]) >= 1, f"{filename}: must have at least 1 defense"

    @pytest.mark.parametrize("filename,_", _EXPECTED_CASES)
    def test_yaml_has_both_plaintiff_and_defendant_materials(self, filename: str, _: str) -> None:
        yaml_path = _PROJECT_ROOT / "cases" / filename
        data, _ = load_and_validate_yaml(yaml_path)
        assert data is not None
        materials = data.get("materials", {})
        assert "plaintiff" in materials, f"{filename}: missing plaintiff materials"
        assert "defendant" in materials, f"{filename}: missing defendant materials"
        assert len(materials["plaintiff"]) >= 1
        assert len(materials["defendant"]) >= 1
