"""
docx_generator 冒烟测试 / Smoke tests for docx_generator.generate_docx_report.

验证：
- 调用不抛异常
- 输出 .docx 文件确实产出且非空
- 传入最小空数据集（all-empty dicts）仍能完成
- 传入完整数据集（含 parties/summary/rounds/exec_summary 等）仍能完成
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from engines.report_generation.docx_generator import generate_docx_report


# ---------------------------------------------------------------------------
# 最小空数据集 / Minimal empty dataset
# ---------------------------------------------------------------------------

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


class TestDocxGeneratorSmoke:
    """冒烟测试 — 验证 generate_docx_report 调用不抛异常、输出文件产出。"""

    def test_minimal_data_no_exception(self, tmp_path: Path) -> None:
        """最小空数据集：不抛异常，文件产出。"""
        dest = generate_docx_report(
            output_dir=tmp_path,
            case_data=_EMPTY_CASE_DATA,
            result=_EMPTY_RESULT,
        )
        assert dest.exists(), f"输出文件不存在: {dest}"
        assert dest.stat().st_size > 0, "输出文件为空"
        assert dest.suffix == ".docx"

    def test_output_in_correct_directory(self, tmp_path: Path) -> None:
        """输出文件位于 output_dir 内。"""
        dest = generate_docx_report(
            output_dir=tmp_path,
            case_data=_EMPTY_CASE_DATA,
            result=_EMPTY_RESULT,
        )
        assert dest.parent == tmp_path

    def test_custom_filename(self, tmp_path: Path) -> None:
        """自定义文件名被尊重。"""
        dest = generate_docx_report(
            output_dir=tmp_path,
            case_data=_EMPTY_CASE_DATA,
            result=_EMPTY_RESULT,
            filename="custom_report.docx",
        )
        assert dest.name == "custom_report.docx"
        assert dest.exists()

    def test_full_data_no_exception(self, tmp_path: Path) -> None:
        """完整数据集（含三轮对抗、证据冲突、执行摘要等）不抛异常，文件产出。"""
        case_data = {
            "parties": {
                "plaintiff": {"party_id": "party-p-001", "name": "张三"},
                "defendant": {"party_id": "party-d-001", "name": "李四"},
            },
            "summary": [
                ["案件类型", "民间借贷纠纷"],
                ["争议金额", "100,000 元"],
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
                            "title": "原告主张",
                            "body": "被告未归还借款 10 万元。",
                            "issue_ids": ["issue-001"],
                            "evidence_citations": ["ev-001"],
                            "risk_flags": [
                                {
                                    "flag_id": "own-weakness-001",
                                    "description": "借条日期模糊",
                                }
                            ],
                        },
                        {
                            "agent_role_code": "defendant_agent",
                            "title": "被告抗辩",
                            "body": "借款已于 2025 年 1 月偿还。",
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
                    "conflict_description": "双方就还款事实存在直接矛盾。",
                }
            ],
            "summary": {
                "overall_assessment": "原告证据较强。",
                "plaintiff_strongest_arguments": [
                    {
                        "issue_id": "issue-001",
                        "position": "借条成立",
                        "reasoning": "原件在手",
                    }
                ],
                "defendant_strongest_defenses": [
                    {
                        "issue_id": "issue-001",
                        "position": "已还款",
                        "reasoning": "有转账记录",
                    }
                ],
                "unresolved_issues": [
                    {
                        "issue_id": "issue-001",
                        "issue_title": "还款争点",
                        "why_unresolved": "转账备注不明",
                    }
                ],
            },
            "missing_evidence_report": [
                {
                    "issue_id": "issue-001",
                    "missing_for_party_id": "party-d-001",
                    "description": "还款凭证不完整",
                }
            ],
        }

        exec_summary = {
            "top5_decisive_issues": ["issue-001"],
            "current_most_stable_claim": "请求偿还借款本金 10 万元",
            "top3_immediate_actions": ["补充借条原件公证", "申请银行流水调取"],
            "critical_evidence_gaps": ["还款凭证"],
            "top3_adversary_optimal_attacks": ["质疑借条真实性"],
        }

        # 构造最小 IssueTree 对象
        issue = SimpleNamespace(
            issue_id="issue-001",
            title="还款争点",
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

        assert dest.exists(), f"输出文件不存在: {dest}"
        assert dest.stat().st_size > 0, "输出文件为空"
