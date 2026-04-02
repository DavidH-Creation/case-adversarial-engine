from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from docx import Document

from engines.report_generation.docx_generator import generate_docx_report


_EMPTY_RESULT: dict = {
    "case_id": "case-smoke-001",
    "run_id": "run-smoke-001",
    "rounds": [],
    "evidence_conflicts": [],
    "summary": None,
    "missing_evidence_report": [],
}

_EMPTY_CASE_DATA: dict = {
    "parties": {},
    "summary": [],
    "model": "",
}


def _read_docx_text(path: Path) -> str:
    doc = Document(path)
    parts: list[str] = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return "\n".join(parts)


class TestDocxGeneratorSmoke:
    def test_minimal_data_no_exception(self, tmp_path: Path) -> None:
        dest = generate_docx_report(
            output_dir=tmp_path,
            case_data=_EMPTY_CASE_DATA,
            result=_EMPTY_RESULT,
        )
        assert dest.exists()
        assert dest.stat().st_size > 0
        assert dest.suffix == ".docx"

    def test_output_in_correct_directory(self, tmp_path: Path) -> None:
        dest = generate_docx_report(
            output_dir=tmp_path,
            case_data=_EMPTY_CASE_DATA,
            result=_EMPTY_RESULT,
        )
        assert dest.parent == tmp_path

    def test_custom_filename(self, tmp_path: Path) -> None:
        dest = generate_docx_report(
            output_dir=tmp_path,
            case_data=_EMPTY_CASE_DATA,
            result=_EMPTY_RESULT,
            filename="custom_report.docx",
        )
        assert dest.name == "custom_report.docx"
        assert dest.exists()

    def test_full_data_no_exception(self, tmp_path: Path) -> None:
        case_data = {
            "parties": {
                "plaintiff": {"party_id": "party-p-001", "name": "Alice"},
                "defendant": {"party_id": "party-d-001", "name": "Bob"},
            },
            "summary": [
                ["Case Type", "Civil Loan Dispute"],
                ["Amount", "100,000"],
            ],
            "model": "claude-sonnet-4-6",
        }

        result = {
            "case_id": "case-smoke-002",
            "run_id": "run-smoke-002",
            "rounds": [
                {
                    "round_number": 1,
                    "phase": "claim",
                    "outputs": [
                        {
                            "agent_role_code": "plaintiff_agent",
                            "title": "Plaintiff position",
                            "body": "The defendant failed to repay the loan.",
                            "issue_ids": ["issue-001"],
                            "evidence_citations": ["ev-001"],
                            "risk_flags": [
                                {"flag_id": "own-weakness-001", "description": "Date is blurry"}
                            ],
                        },
                        {
                            "agent_role_code": "defendant_agent",
                            "title": "Defendant response",
                            "body": "The loan was already repaid.",
                            "issue_ids": ["issue-001"],
                            "evidence_citations": ["ev-002"],
                            "risk_flags": [],
                        },
                    ],
                }
            ],
            "evidence_conflicts": [
                {
                    "issue_id": "issue-001",
                    "conflict_description": "The parties dispute whether repayment happened.",
                }
            ],
            "summary": {
                "overall_assessment": "The plaintiff currently has the stronger documentary record.",
                "plaintiff_strongest_arguments": [
                    {
                        "issue_id": "issue-001",
                        "position": "The IOU is valid",
                        "reasoning": "The original is available",
                    }
                ],
                "defendant_strongest_defenses": [
                    {
                        "issue_id": "issue-001",
                        "position": "The debt was repaid",
                        "reasoning": "There is a transfer record",
                    }
                ],
                "unresolved_issues": [
                    {
                        "issue_id": "issue-001",
                        "issue_title": "Repayment dispute",
                        "why_unresolved": "The transfer note is ambiguous",
                    }
                ],
            },
            "missing_evidence_report": [
                {
                    "issue_id": "issue-001",
                    "missing_for_party_id": "party-d-001",
                    "description": "Repayment proof is incomplete",
                }
            ],
        }

        exec_summary = {
            "top5_decisive_issues": ["issue-001"],
            "current_most_stable_claim": "Repayment of principal in the amount of 100,000",
            "top3_immediate_actions": ["Authenticate the IOU", "Request bank records"],
            "critical_evidence_gaps": ["Repayment proof"],
            "top3_adversary_optimal_attacks": ["Challenge the IOU authenticity"],
        }

        issue = SimpleNamespace(
            issue_id="issue-001",
            title="Repayment dispute",
            issue_type=SimpleNamespace(value="factual"),
        )
        issue_tree = SimpleNamespace(issues=[issue])

        dest = generate_docx_report(
            output_dir=tmp_path,
            case_data=case_data,
            result=result,
            issue_tree=issue_tree,
            exec_summary=exec_summary,
            filename="full_report.docx",
        )

        assert dest.exists()
        assert dest.stat().st_size > 0


class TestDocxGeneratorProbabilityFree:
    def test_decision_tree_uses_path_ranking_without_probability_labels(
        self, tmp_path: Path
    ) -> None:
        dest = generate_docx_report(
            output_dir=tmp_path,
            case_data=_EMPTY_CASE_DATA,
            result=_EMPTY_RESULT,
            decision_tree={
                "paths": [
                    {
                        "path_id": "path-001",
                        "trigger_condition": "Trigger one",
                        "trigger_issue_ids": ["ISS-001"],
                        "key_evidence_ids": ["EV-001"],
                        "possible_outcome": "Outcome one",
                        "probability": 0.95,
                        "probability_rationale": "legacy only",
                        "party_favored": "plaintiff",
                    },
                    {
                        "path_id": "path-002",
                        "trigger_condition": "Trigger two",
                        "trigger_issue_ids": ["ISS-002"],
                        "key_evidence_ids": ["EV-002"],
                        "possible_outcome": "Outcome two",
                        "probability": 0.10,
                        "probability_rationale": "legacy only",
                        "party_favored": "defendant",
                    },
                ],
                "most_likely_path": "path-001",
                "plaintiff_best_path": "path-001",
                "defendant_best_path": "path-002",
                "path_ranking": [
                    {"path_id": "path-002", "probability": 0.10, "party_favored": "defendant"},
                    {"path_id": "path-001", "probability": 0.95, "party_favored": "plaintiff"},
                ],
                "blocking_conditions": [],
            },
            amount_report={
                "claim_calculation_table": [
                    {
                        "claim_id": "CLM-001",
                        "claimed_amount": "100000",
                        "calculated_amount": "80000",
                    }
                ],
                "consistency_check_result": {
                    "verdict_block_active": False,
                    "unresolved_conflicts": [],
                },
            },
        )

        content = _read_docx_text(dest)

        assert "调解区间评估" not in content
        assert "路径概率比较" not in content
        assert "可能性：" not in content
        assert "概率依据" not in content
        assert content.index("Outcome two") < content.index("Outcome one")
