"""
v2 multi-case acceptance test suite.

Tests use mock pipeline results to verify:
- YAML loading and validation logic
- Metric computation under the current mainline contract
- Batch report structure and status propagation
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

_PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.run_acceptance import (
    MIN_VALID_RUNS,
    REQUIRED_YAML_KEYS,
    compute_metrics,
    load_and_validate_yaml,
    run_acceptance,
    run_acceptance_for_case,
    write_report,
)


_VALID_YAML_CONTENT = {
    "case_id": "case-test-labor-001",
    "case_slug": "testlabor001",
    "case_type": "labor_dispute",
    "model": "claude-sonnet-4-6",
    "parties": {
        "plaintiff": {"party_id": "party-p", "name": "Plaintiff"},
        "defendant": {"party_id": "party-d", "name": "Defendant"},
    },
    "summary": [["plaintiff", "employment dispute"], ["defendant", "termination defense"]],
    "materials": {
        "plaintiff": [
            {
                "source_id": "src-p-001",
                "text": "Employment contract.",
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
                "text": "Company policy.",
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
            "claim_category": "wrongful_termination",
            "title": "Compensation",
            "claim_text": "Request statutory compensation.",
        }
    ],
    "defenses": [
        {
            "defense_id": "d-001",
            "defense_category": "lawful_termination",
            "against_claim_id": "c-001",
            "title": "Termination was lawful",
            "defense_text": "Termination followed company rules.",
        }
    ],
}


def _make_valid_run(
    issue_ids: list[str] | None = None,
    evidence_citations: list[list[str]] | None = None,
    *,
    branch_artifacts: dict | None = None,
    outcome_paths: dict | None = None,
) -> dict:
    if issue_ids is None:
        issue_ids = ["i-001", "i-002"]
    if evidence_citations is None:
        evidence_citations = [["src-p-001"], ["src-d-001"]]
    if branch_artifacts is None:
        branch_artifacts = {
            "report_present": True,
            "decision_tree_present": True,
            "explainable_path_count": 2,
        }
    if outcome_paths is None:
        outcome_paths = {}
    return {
        "success": True,
        "issue_ids": issue_ids,
        "evidence_citations": evidence_citations,
        "branch_artifacts": branch_artifacts,
        "outcome_paths": outcome_paths,
        "error": None,
    }


def _make_failed_run(error: str = "pipeline_timeout") -> dict:
    return {
        "success": False,
        "issue_ids": [],
        "evidence_citations": [],
        "branch_artifacts": None,
        "outcome_paths": None,
        "error": error,
    }


def _make_yaml_file(tmp_path: Path, content: dict, filename: str = "test_case.yaml") -> Path:
    path = tmp_path / filename
    path.write_text(yaml.dump(content, allow_unicode=True), encoding="utf-8")
    return path


class TestLoadAndValidateYaml:
    def test_valid_yaml_returns_data(self, tmp_path: Path) -> None:
        path = _make_yaml_file(tmp_path, _VALID_YAML_CONTENT)
        data, err = load_and_validate_yaml(path)
        assert err is None
        assert data is not None
        assert data["case_id"] == "case-test-labor-001"

    def test_missing_required_key_returns_error(self, tmp_path: Path) -> None:
        bad = dict(_VALID_YAML_CONTENT)
        del bad["claims"]
        path = _make_yaml_file(tmp_path, bad)
        data, err = load_and_validate_yaml(path)
        assert data is None
        assert "claims" in (err or "")

    def test_all_required_keys_must_be_present(self, tmp_path: Path) -> None:
        for key in REQUIRED_YAML_KEYS:
            bad = dict(_VALID_YAML_CONTENT)
            del bad[key]
            path = _make_yaml_file(tmp_path, bad, f"missing_{key}.yaml")
            data, err = load_and_validate_yaml(path)
            assert data is None
            assert err is not None

    def test_invalid_yaml_syntax_returns_error(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("case_id: [unclosed", encoding="utf-8")
        data, err = load_and_validate_yaml(path)
        assert data is None
        assert err is not None

    def test_nonexistent_file_returns_error(self, tmp_path: Path) -> None:
        path = tmp_path / "missing.yaml"
        data, err = load_and_validate_yaml(path)
        assert data is None
        assert err is not None

    def test_non_dict_yaml_returns_error(self, tmp_path: Path) -> None:
        path = tmp_path / "list.yaml"
        path.write_text("- item1\n- item2\n", encoding="utf-8")
        data, err = load_and_validate_yaml(path)
        assert data is None
        assert "not_dict" in (err or "")


class TestComputeMetrics:
    def test_empty_run_list_returns_zeros(self) -> None:
        metrics = compute_metrics([])
        assert metrics["consistency"] == 0.0
        assert metrics["citation_rate"] == 0.0
        assert metrics["path_explainable"] is False
        assert metrics["passed"] is False
        assert metrics["n_runs"] == 0
        assert metrics["n_success"] == 0

    def test_all_failed_runs_returns_zeros(self) -> None:
        metrics = compute_metrics([_make_failed_run() for _ in range(3)])
        assert metrics["consistency"] == 0.0
        assert metrics["n_success"] == 0
        assert metrics["passed"] is False

    def test_perfect_consistency_single_run(self) -> None:
        metrics = compute_metrics([_make_valid_run(issue_ids=["i-001", "i-002"])])
        assert metrics["consistency"] == 1.0
        assert metrics["n_success"] == 1

    def test_consistency_majority_same_issue_tree_meets_threshold(self) -> None:
        runs = [
            _make_valid_run(issue_ids=["i-001", "i-002"]),
            _make_valid_run(issue_ids=["i-001", "i-002"]),
            _make_valid_run(issue_ids=["i-001", "i-002"]),
            _make_valid_run(issue_ids=["i-001", "i-003"]),
        ]
        metrics = compute_metrics(runs)
        assert metrics["consistency"] == 0.75
        assert metrics["n_success"] == 4

    def test_consistency_reordered_issue_tree_fails(self) -> None:
        runs = [
            _make_valid_run(issue_ids=["i-001", "i-002", "i-003"]),
            _make_valid_run(issue_ids=["i-002", "i-001", "i-003"]),
            _make_valid_run(issue_ids=["i-001", "i-002", "i-003"]),
            _make_valid_run(issue_ids=["i-002", "i-001", "i-003"]),
        ]
        metrics = compute_metrics(runs)
        assert metrics["consistency"] == 0.5
        assert metrics["passed"] is False

    def test_consistency_stable_top_issue_but_drifted_tree_fails(self) -> None:
        runs = [
            _make_valid_run(issue_ids=["i-001", "i-002"]),
            _make_valid_run(issue_ids=["i-001", "i-003"]),
            _make_valid_run(issue_ids=["i-001", "i-004"]),
            _make_valid_run(issue_ids=["i-001", "i-005"]),
        ]
        metrics = compute_metrics(runs)
        assert metrics["consistency"] == 0.25
        assert metrics["passed"] is False

    def test_citation_rate_all_cited(self) -> None:
        runs = [
            _make_valid_run(evidence_citations=[["src-p-001"], ["src-d-001"]]),
            _make_valid_run(evidence_citations=[["src-p-001"], ["src-d-001"]]),
        ]
        metrics = compute_metrics(runs)
        assert metrics["citation_rate"] == 1.0

    def test_citation_rate_partial(self) -> None:
        runs = [
            _make_valid_run(evidence_citations=[["src-001"], []]),
            _make_valid_run(evidence_citations=[["src-001"], ["src-002"]]),
        ]
        metrics = compute_metrics(runs)
        assert metrics["citation_rate"] == pytest.approx(0.75)
        assert metrics["passed"] is False

    def test_citation_rate_no_outputs(self) -> None:
        metrics = compute_metrics([_make_valid_run(evidence_citations=[])])
        assert metrics["citation_rate"] == 0.0

    def test_path_explainable_uses_current_branch_artifacts(self) -> None:
        metrics = compute_metrics(
            [
                _make_valid_run(
                    branch_artifacts={
                        "report_present": True,
                        "decision_tree_present": True,
                        "explainable_path_count": 3,
                    }
                )
            ]
        )
        assert metrics["path_explainable"] is True

    def test_path_explainable_missing_report_fails(self) -> None:
        metrics = compute_metrics(
            [
                _make_valid_run(
                    branch_artifacts={
                        "report_present": False,
                        "decision_tree_present": True,
                        "explainable_path_count": 3,
                    }
                )
            ]
        )
        assert metrics["path_explainable"] is False

    def test_path_explainable_missing_decision_tree_fails(self) -> None:
        metrics = compute_metrics(
            [
                _make_valid_run(
                    branch_artifacts={
                        "report_present": True,
                        "decision_tree_present": False,
                        "explainable_path_count": 3,
                    }
                )
            ]
        )
        assert metrics["path_explainable"] is False

    def test_path_explainable_requires_explainable_branches(self) -> None:
        metrics = compute_metrics(
            [
                _make_valid_run(
                    branch_artifacts={
                        "report_present": True,
                        "decision_tree_present": True,
                        "explainable_path_count": 0,
                    }
                )
            ]
        )
        assert metrics["path_explainable"] is False

    def test_path_explainable_does_not_require_mediation_path(self) -> None:
        metrics = compute_metrics(
            [
                _make_valid_run(
                    branch_artifacts={
                        "report_present": True,
                        "decision_tree_present": True,
                        "explainable_path_count": 2,
                    },
                    outcome_paths={
                        "win_path": {"trigger_conditions": ["condition-a"]},
                        "lose_path": {"trigger_conditions": ["condition-b"]},
                        "supplement_path": {"trigger_conditions": ["condition-c"]},
                    },
                )
            ]
        )
        assert metrics["path_explainable"] is True

    def test_passed_requires_all_three_metrics(self) -> None:
        runs = [
            _make_valid_run(
                issue_ids=["i-001", "i-002"],
                evidence_citations=[["src-001"]],
                branch_artifacts={
                    "report_present": True,
                    "decision_tree_present": True,
                    "explainable_path_count": 2,
                },
            )
            for _ in range(MIN_VALID_RUNS)
        ]
        metrics = compute_metrics(runs)
        assert metrics["passed"] is True

    def test_n_runs_and_n_success_reported_correctly(self) -> None:
        metrics = compute_metrics([_make_valid_run(), _make_failed_run(), _make_valid_run()])
        assert metrics["n_runs"] == 3
        assert metrics["n_success"] == 2

    def test_metrics_are_floats_in_range(self) -> None:
        metrics = compute_metrics([_make_valid_run() for _ in range(3)])
        assert isinstance(metrics["consistency"], float)
        assert 0.0 <= metrics["consistency"] <= 1.0
        assert isinstance(metrics["citation_rate"], float)
        assert 0.0 <= metrics["citation_rate"] <= 1.0
        assert isinstance(metrics["path_explainable"], bool)


class TestRunAcceptanceForCase:
    def _make_runner(self, results: list[dict]):
        call_index = [0]

        def runner(yaml_path: Path, run_index: int, output_dir: Path) -> dict:
            idx = call_index[0]
            call_index[0] += 1
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
        path = _make_yaml_file(tmp_path, bad)
        result = run_acceptance_for_case(
            path,
            n_runs=2,
            base_output_dir=tmp_path / "runs",
            pipeline_runner=self._make_runner([_make_valid_run()]),
        )
        assert result["status"] == "skipped"

    def test_all_runs_successful_computes_metrics(self, tmp_path: Path) -> None:
        path = _make_yaml_file(tmp_path, _VALID_YAML_CONTENT)
        good_result = _make_valid_run(
            issue_ids=["i-001", "i-002"],
            evidence_citations=[["src-p-001"]],
            branch_artifacts={
                "report_present": True,
                "decision_tree_present": True,
                "explainable_path_count": 2,
            },
        )
        result = run_acceptance_for_case(
            path,
            n_runs=3,
            base_output_dir=tmp_path / "runs",
            pipeline_runner=self._make_runner([good_result] * 3),
        )
        assert result["status"] in ("passed", "failed")
        assert result["metrics"] is not None
        assert "consistency" in result["metrics"]
        assert "citation_rate" in result["metrics"]
        assert "path_explainable" in result["metrics"]

    def test_pipeline_failures_counted_in_runs(self, tmp_path: Path) -> None:
        path = _make_yaml_file(tmp_path, _VALID_YAML_CONTENT)
        mixed = [_make_valid_run(), _make_failed_run("pipeline_timeout"), _make_valid_run()]
        result = run_acceptance_for_case(
            path,
            n_runs=3,
            base_output_dir=tmp_path / "runs",
            pipeline_runner=self._make_runner(mixed),
        )
        assert len(result["runs"]) == 3
        assert result["runs"][1]["success"] is False
        assert result["runs"][1]["error"] == "pipeline_timeout"

    def test_result_has_required_keys(self, tmp_path: Path) -> None:
        path = _make_yaml_file(tmp_path, _VALID_YAML_CONTENT)
        result = run_acceptance_for_case(
            path,
            n_runs=1,
            base_output_dir=tmp_path / "runs",
            pipeline_runner=self._make_runner([_make_valid_run()]),
        )
        for key in ("case_id", "yaml_path", "status", "reason", "metrics", "runs"):
            assert key in result

    def test_case_id_matches_yaml(self, tmp_path: Path) -> None:
        path = _make_yaml_file(tmp_path, _VALID_YAML_CONTENT)
        result = run_acceptance_for_case(
            path,
            n_runs=1,
            base_output_dir=tmp_path / "runs",
            pipeline_runner=self._make_runner([_make_valid_run()]),
        )
        assert result["case_id"] == "case-test-labor-001"


class TestRunAcceptance:
    def _make_fixed_runner(self, issue_ids=None, evidence_citations=None):
        fixed = _make_valid_run(
            issue_ids=issue_ids or ["i-001"],
            evidence_citations=evidence_citations or [["src-001"]],
        )

        def runner(yaml_path, run_index, output_dir):
            return fixed

        return runner

    def _write_case_yaml(self, cases_dir: Path, case_type: str, idx: int) -> Path:
        content = dict(_VALID_YAML_CONTENT)
        content["case_id"] = f"case-{case_type}-test-{idx:03d}"
        content["case_slug"] = f"{case_type}test{idx:03d}"
        content["case_type"] = case_type
        path = cases_dir / f"{case_type}_{idx}.yaml"
        path.write_text(yaml.dump(content, allow_unicode=True), encoding="utf-8")
        return path

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
            assert key in report

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
        summary = report["summary"]
        assert summary["passed"] + summary["failed"] + summary["skipped"] == summary["total"]


class TestWriteReport:
    def test_write_report_writes_json(self, tmp_path: Path) -> None:
        report = {
            "generated_at": "2026-01-01T00:00:00Z",
            "case_type": "labor_dispute",
            "cases_dir": "cases",
            "n_runs_per_case": 3,
            "summary": {"total": 1, "passed": 1, "failed": 0, "skipped": 0, "all_passed": True},
            "thresholds": {"consistency": 0.75, "citation_rate": 1.0},
            "cases": [],
        }
        output = tmp_path / "report.json"
        written = write_report(report, output)
        assert written == output
        loaded = json.loads(output.read_text(encoding="utf-8"))
        assert loaded["summary"]["all_passed"] is True
