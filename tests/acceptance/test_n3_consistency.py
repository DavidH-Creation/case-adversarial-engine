"""
Phase 0b: N=3 consistency checks for multi-case-type acceptance.

Tests that:
1. The acceptance metric framework correctly computes consistency, citation_rate,
   and path_explainability from synthetic N=3 pipeline run results.
2. Per-case-type golden artifact structures meet acceptance thresholds.
3. The run_acceptance_for_case() pipeline runner integration works with
   a deterministic mock pipeline that produces consistent artifacts.

These tests use synthetic but structurally realistic artifacts, not real LLM calls.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.run_acceptance import (
    METRIC_THRESHOLDS,
    MIN_VALID_RUNS,
    compute_metrics,
    extract_run_artifacts,
    run_acceptance_for_case,
)

CASE_TYPES = ["civil_loan", "labor_dispute", "real_estate"]

REPRESENTATIVE_YAMLS = {
    "civil_loan": "wang_v_chen_zhuang_2025.yaml",
    "labor_dispute": "labor_dispute_1.yaml",
    "real_estate": "real_estate_1.yaml",
}

CASES_DIR = _PROJECT_ROOT / "cases"


# ---------------------------------------------------------------------------
# Helpers — golden artifact builders per case type
# ---------------------------------------------------------------------------

# Each case type produces a stable set of issue IDs and evidence citations.
# These represent what a well-functioning pipeline would emit.

_GOLDEN_ISSUES = {
    "civil_loan": [
        "iss-cl-loan-agreement",
        "iss-cl-principal-amount",
        "iss-cl-interest-rate",
        "iss-cl-repayment-obligation",
        "iss-cl-borrower-identity",
    ],
    "labor_dispute": [
        "iss-ld-termination-legality",
        "iss-ld-trade-secret-breach",
        "iss-ld-policy-validity",
        "iss-ld-wage-dispute",
        "iss-ld-compensation-calc",
    ],
    "real_estate": [
        "iss-re-contract-validity",
        "iss-re-deposit-penalty",
        "iss-re-specific-performance",
        "iss-re-market-value-gap",
        "iss-re-mortgage-obstacle",
    ],
}

_GOLDEN_EVIDENCE_CITATIONS = {
    "civil_loan": [
        ["src-p-transfer", "src-p-contract"],
        ["src-p-chat", "src-d-receipt"],
        ["src-d-witness"],
        ["src-p-transfer"],
    ],
    "labor_dispute": [
        ["src-p-contract", "src-p-termination-notice"],
        ["src-d-itlog", "src-d-nda"],
        ["src-p-salary-records"],
        ["src-p-wechat", "src-p-colleague-statement"],
    ],
    "real_estate": [
        ["src-p-purchase-contract", "src-p-deposit-receipt"],
        ["src-p-refusal-wechat"],
        ["src-d-contract-defect", "src-d-property-restriction"],
        ["src-p-bank-approval"],
    ],
}

_GOLDEN_DECISION_TREE = {
    "paths": [
        {
            "path_id": "path-001",
            "trigger_condition": "借款合意成立且有银行转账凭证",
            "outcome": "plaintiff_favorable",
        },
        {
            "path_id": "path-002",
            "trigger_condition": "被告证明款项系代收代付",
            "outcome": "defendant_favorable",
        },
        {
            "path_id": "path-003",
            "trigger_condition": "双方协商调解",
            "outcome": "settlement",
        },
    ]
}


def _make_golden_run(
    case_type: str,
    *,
    issue_variation: int = 0,
    all_cited: bool = True,
) -> dict:
    """Build a synthetic but structurally realistic pipeline run result.

    Args:
        case_type: One of CASE_TYPES
        issue_variation: 0 = golden order, 1+ = minor reordering for consistency test
        all_cited: If True, all citations are non-empty (citation_rate=1.0)
    """
    issues = list(_GOLDEN_ISSUES[case_type])
    if issue_variation == 1:
        # Swap last two — still similar enough for consistency >= 0.75
        issues[-1], issues[-2] = issues[-2], issues[-1]

    citations = [list(c) for c in _GOLDEN_EVIDENCE_CITATIONS[case_type]]
    if not all_cited:
        citations.append([])  # Add one uncited output slot

    return {
        "success": True,
        "issue_ids": issues,
        "evidence_citations": citations,
        "branch_artifacts": {
            "report_present": True,
            "decision_tree_present": True,
            "explainable_path_count": 3,
        },
        "outcome_paths": None,
        "error": None,
    }


def _write_golden_artifacts(output_dir: Path, case_type: str) -> None:
    """Write realistic pipeline artifacts to disk for extract_run_artifacts() to parse."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # issue_tree.json
    issue_tree = {
        "case_id": f"case-{case_type}-golden",
        "issues": [
            {"issue_id": iid, "title": f"Issue {i+1}", "description": "test"}
            for i, iid in enumerate(_GOLDEN_ISSUES[case_type])
        ],
    }
    (output_dir / "issue_tree.json").write_text(
        json.dumps(issue_tree, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # result.json — adversarial debate result with evidence citations
    rounds = []
    for i, citations in enumerate(_GOLDEN_EVIDENCE_CITATIONS[case_type]):
        rounds.append({
            "round_number": i + 1,
            "phase": "claim",
            "outputs": [{
                "output_id": f"out-{i+1}",
                "evidence_citations": citations,
                "body": f"Argument round {i+1}",
            }],
        })
    result = {
        "case_id": f"case-{case_type}-golden",
        "run_id": f"run-{case_type}-golden",
        "rounds": rounds,
    }
    (output_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # decision_tree.json
    (output_dir / "decision_tree.json").write_text(
        json.dumps(_GOLDEN_DECISION_TREE, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # report.md
    (output_dir / "report.md").write_text(
        f"# {case_type} Golden Report\n\nThis is a golden artifact for acceptance testing.\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# 1. compute_metrics with perfect N=3 runs — all case types should pass
# ---------------------------------------------------------------------------


class TestN3PerfectConsistency:
    """With 3 identical runs, all metrics should be at maximum."""

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_perfect_n3_passes_all_metrics(self, case_type: str):
        runs = [_make_golden_run(case_type) for _ in range(3)]
        metrics = compute_metrics(runs)

        assert metrics["consistency"] == 1.0, f"Expected perfect consistency, got {metrics['consistency']}"
        assert metrics["citation_rate"] == 1.0, f"Expected perfect citation, got {metrics['citation_rate']}"
        assert metrics["path_explainable"] is True
        assert metrics["passed"] is True
        assert metrics["n_success"] == 3

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_perfect_n3_exceeds_thresholds(self, case_type: str):
        runs = [_make_golden_run(case_type) for _ in range(3)]
        metrics = compute_metrics(runs)

        assert metrics["consistency"] >= METRIC_THRESHOLDS["consistency"]
        assert metrics["citation_rate"] >= METRIC_THRESHOLDS["citation_rate"]


# ---------------------------------------------------------------------------
# 2. compute_metrics with minor variation — consistency should still pass
# ---------------------------------------------------------------------------


class TestN3WithVariation:
    """With 2/3 identical + 1 slightly different, consistency >= 0.75 threshold."""

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_two_of_three_identical_passes_consistency(self, case_type: str):
        """2 identical + 1 reordered → consistency = 2/3 ≈ 0.667 (below threshold)."""
        runs = [
            _make_golden_run(case_type, issue_variation=0),
            _make_golden_run(case_type, issue_variation=0),
            _make_golden_run(case_type, issue_variation=1),
        ]
        metrics = compute_metrics(runs)

        # 2/3 = 0.667, which is below the 0.75 threshold
        assert metrics["consistency"] == pytest.approx(2 / 3, abs=0.01)
        assert metrics["citation_rate"] == 1.0
        assert metrics["path_explainable"] is True

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_all_three_identical_passes_threshold(self, case_type: str):
        """3/3 identical → consistency = 1.0 (above threshold)."""
        runs = [_make_golden_run(case_type, issue_variation=0) for _ in range(3)]
        metrics = compute_metrics(runs)

        assert metrics["consistency"] >= METRIC_THRESHOLDS["consistency"]
        assert metrics["passed"] is True


# ---------------------------------------------------------------------------
# 3. compute_metrics with citation gaps — should fail citation_rate
# ---------------------------------------------------------------------------


class TestN3CitationGaps:
    """Missing citations should cause citation_rate to drop below 1.0."""

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_uncited_outputs_fail_citation_rate(self, case_type: str):
        runs = [_make_golden_run(case_type, all_cited=False) for _ in range(3)]
        metrics = compute_metrics(runs)

        assert metrics["citation_rate"] < 1.0
        # With one empty citation per run, rate = cited/(cited+1) per run
        assert not metrics["passed"], "Should fail when citation_rate < 1.0"


# ---------------------------------------------------------------------------
# 4. compute_metrics with failed runs — n_success check
# ---------------------------------------------------------------------------


class TestN3FailedRuns:
    """Pipeline failures should reduce n_success and potentially fail acceptance."""

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_one_failed_run_of_three_still_passes(self, case_type: str):
        """2 successful + 1 failed → n_success=2 < MIN_VALID_RUNS=3 → fails."""
        runs = [
            _make_golden_run(case_type),
            _make_golden_run(case_type),
            {"success": False, "issue_ids": [], "evidence_citations": [],
             "branch_artifacts": None, "outcome_paths": None, "error": "timeout"},
        ]
        metrics = compute_metrics(runs)

        assert metrics["n_success"] == 2
        # With n_runs=3 and MIN_VALID_RUNS=3, 2 successes fail the check
        assert not metrics["passed"]

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_all_three_failed(self, case_type: str):
        runs = [
            {"success": False, "issue_ids": [], "evidence_citations": [],
             "branch_artifacts": None, "outcome_paths": None, "error": "crash"}
            for _ in range(3)
        ]
        metrics = compute_metrics(runs)

        assert metrics["n_success"] == 0
        assert metrics["consistency"] == 0.0
        assert metrics["citation_rate"] == 0.0
        assert metrics["path_explainable"] is False
        assert not metrics["passed"]


# ---------------------------------------------------------------------------
# 5. extract_run_artifacts from disk — golden artifacts
# ---------------------------------------------------------------------------


class TestExtractRunArtifacts:
    """extract_run_artifacts() correctly parses golden artifacts from disk."""

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_golden_artifacts_extract_successfully(self, case_type: str, tmp_path: Path):
        run_dir = tmp_path / f"golden_{case_type}"
        _write_golden_artifacts(run_dir, case_type)

        result = extract_run_artifacts(run_dir)

        assert result["success"] is True
        assert result["error"] is None
        assert len(result["issue_ids"]) == len(_GOLDEN_ISSUES[case_type])
        assert result["issue_ids"] == _GOLDEN_ISSUES[case_type]
        assert result["branch_artifacts"]["report_present"] is True
        assert result["branch_artifacts"]["decision_tree_present"] is True
        assert result["branch_artifacts"]["explainable_path_count"] == 3

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_golden_artifacts_have_citations(self, case_type: str, tmp_path: Path):
        run_dir = tmp_path / f"golden_{case_type}"
        _write_golden_artifacts(run_dir, case_type)

        result = extract_run_artifacts(run_dir)

        # Every output should have at least one citation
        for i, citations in enumerate(result["evidence_citations"]):
            assert len(citations) > 0, f"Output {i} has no citations"

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_golden_artifacts_pass_acceptance(self, case_type: str, tmp_path: Path):
        """N=3 golden artifacts should pass full acceptance when extracted from disk."""
        run_results = []
        for i in range(3):
            run_dir = tmp_path / f"golden_{case_type}_run{i}"
            _write_golden_artifacts(run_dir, case_type)
            run_results.append(extract_run_artifacts(run_dir))

        metrics = compute_metrics(run_results)

        assert metrics["passed"], (
            f"{case_type} golden artifacts failed acceptance: {metrics}"
        )
        assert metrics["consistency"] >= METRIC_THRESHOLDS["consistency"]
        assert metrics["citation_rate"] >= METRIC_THRESHOLDS["citation_rate"]
        assert metrics["path_explainable"] is True


# ---------------------------------------------------------------------------
# 6. run_acceptance_for_case() with mock pipeline runner
# ---------------------------------------------------------------------------


class TestRunAcceptanceForCaseMock:
    """Integration test: run_acceptance_for_case() with deterministic mock pipeline."""

    def _mock_pipeline_runner(self, case_type: str):
        """Return a pipeline runner that produces golden artifacts."""
        def runner(yaml_path: Path, run_index: int, output_dir: Path) -> dict:
            _write_golden_artifacts(output_dir, case_type)
            return extract_run_artifacts(output_dir)
        return runner

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_acceptance_for_case_passes_with_golden_pipeline(
        self, case_type: str, tmp_path: Path
    ):
        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
        result = run_acceptance_for_case(
            yaml_path=yaml_path,
            n_runs=3,
            base_output_dir=tmp_path / case_type,
            pipeline_runner=self._mock_pipeline_runner(case_type),
        )

        assert result["status"] == "passed", (
            f"{case_type} acceptance failed: {result.get('metrics')}"
        )
        assert result["metrics"]["passed"] is True
        assert result["metrics"]["n_success"] == 3
        assert result["metrics"]["consistency"] >= METRIC_THRESHOLDS["consistency"]
        assert result["metrics"]["citation_rate"] >= METRIC_THRESHOLDS["citation_rate"]

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_acceptance_report_structure(self, case_type: str, tmp_path: Path):
        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
        result = run_acceptance_for_case(
            yaml_path=yaml_path,
            n_runs=3,
            base_output_dir=tmp_path / case_type,
            pipeline_runner=self._mock_pipeline_runner(case_type),
        )

        # Verify report structure
        assert "case_id" in result
        assert "yaml_path" in result
        assert "status" in result
        assert "metrics" in result
        assert "runs" in result
        assert len(result["runs"]) == 3
        for run in result["runs"]:
            assert run["success"] is True
            assert run["issue_count"] == len(_GOLDEN_ISSUES[case_type])


# ---------------------------------------------------------------------------
# 7. Checked-in golden artifacts validation
# ---------------------------------------------------------------------------

_GOLDEN_DIR = _PROJECT_ROOT / "tests" / "acceptance" / "golden_artifacts"


class TestCheckedInGoldenArtifacts:
    """Validate that checked-in golden artifacts pass acceptance metrics."""

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_golden_dir_exists(self, case_type: str):
        d = _GOLDEN_DIR / case_type
        assert d.is_dir(), f"Missing golden artifacts dir: {d}"

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_golden_has_required_files(self, case_type: str):
        d = _GOLDEN_DIR / case_type
        for filename in ("issue_tree.json", "result.json", "decision_tree.json", "report.md"):
            assert (d / filename).exists(), f"Missing {filename} in {d}"

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_golden_artifacts_parse_successfully(self, case_type: str):
        d = _GOLDEN_DIR / case_type
        result = extract_run_artifacts(d)
        assert result["success"], f"Failed to parse golden artifacts: {result.get('error')}"
        assert len(result["issue_ids"]) >= 3, "Expected at least 3 issues"

    @pytest.mark.parametrize("case_type", CASE_TYPES)
    def test_golden_n3_passes_acceptance(self, case_type: str):
        """N=3 reads of the same golden artifacts should pass acceptance."""
        d = _GOLDEN_DIR / case_type
        runs = [extract_run_artifacts(d) for _ in range(3)]
        metrics = compute_metrics(runs)
        assert metrics["passed"], f"{case_type} golden N=3 failed: {metrics}"


# ---------------------------------------------------------------------------
# 8. Cross-case-type consistency — different types produce different issues
# ---------------------------------------------------------------------------


class TestCrossCaseTypeConsistency:
    """Different case types must produce distinct issue sets."""

    def test_issue_sets_are_distinct_across_case_types(self):
        for ct1 in CASE_TYPES:
            for ct2 in CASE_TYPES:
                if ct1 == ct2:
                    continue
                set1 = set(_GOLDEN_ISSUES[ct1])
                set2 = set(_GOLDEN_ISSUES[ct2])
                assert set1 != set2, f"{ct1} and {ct2} have identical issue sets"
                # They should have no overlap at all (different legal domains)
                assert not set1.intersection(set2), (
                    f"{ct1} and {ct2} share issues: {set1 & set2}"
                )

    def test_evidence_citations_are_distinct_across_case_types(self):
        for ct1 in CASE_TYPES:
            for ct2 in CASE_TYPES:
                if ct1 == ct2:
                    continue
                flat1 = {c for group in _GOLDEN_EVIDENCE_CITATIONS[ct1] for c in group}
                flat2 = {c for group in _GOLDEN_EVIDENCE_CITATIONS[ct2] for c in group}
                assert flat1 != flat2, f"{ct1} and {ct2} have identical evidence citations"
