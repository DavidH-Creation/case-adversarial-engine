"""
Unit 11 报告增强集成测试 — 测试 _write_md 中新增的四个 section。
Integration tests for report enhancement sections in _write_md and generate_docx_report.

验证:
- 行动优先级清单：exec_summary.top3_immediate_actions → 报告顶部显示
- 行动优先级清单：action_rec fallback → 从 action_rec 字段推导
- 风险热力图：ranked_issues → 表格包含 🟢🟡🔴 标注
- 调解区间：amount_report + decision_tree → 金额范围表
- 对方策略预警：defendant_strongest_defenses + attack_chain → 预警 section
- DOCX smoke: 新参数传入后不抛异常
"""

from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_result(*, with_summary: bool = True, with_defenses: bool = True):
    """Create a minimal AdversarialResult-like object for _write_md."""
    defenses = []
    if with_defenses:
        defenses = [
            SimpleNamespace(issue_id="issue-001", position="已还款", reasoning="有转账记录"),
            SimpleNamespace(issue_id="issue-002", position="借条无效", reasoning="签名存疑"),
        ]

    summary = None
    if with_summary:
        summary = SimpleNamespace(
            plaintiff_strongest_arguments=[
                SimpleNamespace(issue_id="issue-001", position="借条成立", reasoning="原件在手"),
            ],
            defendant_strongest_defenses=defenses,
            overall_assessment="原告证据较强。",
        )

    return SimpleNamespace(
        case_id="case-test-001",
        run_id="run-test-001",
        rounds=[],
        evidence_conflicts=[],
        missing_evidence_report=[],
        summary=summary,
    )


def _make_ranked_issues():
    """Create ranked issues with varying risk profiles."""
    return SimpleNamespace(
        issues=[
            SimpleNamespace(
                issue_id="issue-001",
                title="借贷关系成立",
                issue_type=SimpleNamespace(value="factual"),
                outcome_impact=SimpleNamespace(value="high"),
                opponent_attack_strength=SimpleNamespace(value="strong"),
                proponent_evidence_strength=SimpleNamespace(value="medium"),
                recommended_action=SimpleNamespace(value="supplement_evidence"),
            ),
            SimpleNamespace(
                issue_id="issue-002",
                title="还款事实",
                issue_type=SimpleNamespace(value="factual"),
                outcome_impact=SimpleNamespace(value="medium"),
                opponent_attack_strength=SimpleNamespace(value="weak"),
                proponent_evidence_strength=SimpleNamespace(value="strong"),
                recommended_action=SimpleNamespace(value="explain_in_trial"),
            ),
            SimpleNamespace(
                issue_id="issue-003",
                title="利息计算",
                issue_type=SimpleNamespace(value="legal"),
                outcome_impact=SimpleNamespace(value="low"),
                opponent_attack_strength=SimpleNamespace(value="medium"),
                proponent_evidence_strength=SimpleNamespace(value="medium"),
                recommended_action=SimpleNamespace(value="amend_claim"),
            ),
        ]
    )


def _make_attack_chain():
    """Create a minimal attack chain."""
    return SimpleNamespace(
        owner_party_id="party-d-001",
        top_attacks=[
            SimpleNamespace(
                attack_node_id="atk-001",
                target_issue_id="issue-001",
                attack_description="质疑借条真实性",
                success_conditions="借条鉴定不通过",
                supporting_evidence_ids=["ev-002"],
                counter_measure="申请司法鉴定",
                adversary_pivot_strategy="转向质疑转账用途",
            ),
            SimpleNamespace(
                attack_node_id="atk-002",
                target_issue_id="issue-002",
                attack_description="证明已还款",
                success_conditions="转账记录被认可",
                supporting_evidence_ids=["ev-003"],
                counter_measure="指出转账备注不明",
                adversary_pivot_strategy="提供更多还款证据",
            ),
        ],
        recommended_order=["atk-001", "atk-002"],
    )


def _make_amount_report():
    """Create a minimal amount report."""
    return SimpleNamespace(
        claim_calculation_table=[
            SimpleNamespace(
                claim_id="claim-001",
                claim_type=SimpleNamespace(value="principal"),
                claimed_amount=Decimal("100000"),
                calculated_amount=Decimal("80000"),
                delta=Decimal("20000"),
                delta_explanation="部分还款未扣除",
            ),
            SimpleNamespace(
                claim_id="claim-002",
                claim_type=SimpleNamespace(value="interest"),
                claimed_amount=Decimal("15000"),
                calculated_amount=Decimal("12000"),
                delta=Decimal("3000"),
                delta_explanation="利率计算差异",
            ),
        ],
    )


def _make_decision_tree():
    """Create a minimal decision tree with confidence intervals."""
    return SimpleNamespace(
        paths=[
            SimpleNamespace(
                path_id="path-001",
                trigger_condition="借条真实性认定",
                trigger_issue_ids=["issue-001"],
                key_evidence_ids=["ev-001"],
                possible_outcome="支持原告全额请求",
                confidence_interval=SimpleNamespace(lower=0.4, upper=0.7),
                path_notes="",
            ),
            SimpleNamespace(
                path_id="path-002",
                trigger_condition="还款事实认定",
                trigger_issue_ids=["issue-002"],
                key_evidence_ids=["ev-002"],
                possible_outcome="部分支持",
                confidence_interval=SimpleNamespace(lower=0.3, upper=0.6),
                path_notes="",
            ),
        ],
        blocking_conditions=[],
    )


def _make_exec_summary():
    return SimpleNamespace(
        top5_decisive_issues=["issue-001", "issue-002"],
        top3_immediate_actions=["补充借条原件公证", "申请银行流水调取", "准备利率计算说明"],
        top3_adversary_optimal_attacks=["atk-001"],
        current_most_stable_claim="请求偿还借款本金 8 万元",
        critical_evidence_gaps=["还款凭证"],
        adversary_attack_chain_id="chain-001",
        amount_report_id="amt-001",
    )


def _make_action_rec():
    return SimpleNamespace(
        evidence_supplement_priorities=["gap-001-还款凭证", "gap-002-利率依据"],
        recommended_claim_amendments=[
            SimpleNamespace(
                suggestion_id="amend-001",
                original_claim_id="claim-001",
                amendment_description="将本金请求调整为 80000 元",
                amendment_reason_issue_id="issue-001",
                amendment_reason_evidence_ids=[],
            ),
        ],
        claims_to_abandon=[
            SimpleNamespace(
                suggestion_id="abandon-001",
                claim_id="claim-003",
                abandon_reason="违约金请求缺乏合同依据",
                abandon_reason_issue_id="issue-003",
            ),
        ],
        trial_explanation_priorities=[],
    )


_CASE_DATA = {
    "case_id": "case-test-001",
    "case_type": "civil_loan",
    "parties": {
        "plaintiff": {"party_id": "party-p-001", "name": "张三"},
        "defendant": {"party_id": "party-d-001", "name": "李四"},
    },
    "summary": [["案件类型", "民间借贷"]],
}


# ---------------------------------------------------------------------------
# Test: _write_md sections
# ---------------------------------------------------------------------------


class TestWriteMdActionPriorityList:
    """行动优先级清单 section 测试。"""

    def _write(self, *, exec_summary=None, action_rec=None) -> str:
        """Call _write_md and return content."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
        from scripts.run_case import _write_md

        result = _make_result(with_summary=False)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            _write_md(
                out,
                result,
                SimpleNamespace(issues=[]),
                _CASE_DATA,
                exec_summary=exec_summary,
                action_rec=action_rec,
                no_redact=True,
            )
            return (out / "report.md").read_text(encoding="utf-8")

    def test_from_exec_summary(self) -> None:
        """exec_summary.top3_immediate_actions → 显示在报告顶部。"""
        content = self._write(exec_summary=_make_exec_summary())
        assert "你现在最该做的 3 件事" in content
        assert "补充借条原件公证" in content
        assert "申请银行流水调取" in content

    def test_from_action_rec_fallback(self) -> None:
        """无 exec_summary 时 → 从 action_rec 推导。"""
        content = self._write(action_rec=_make_action_rec())
        assert "你现在最该做的 3 件事" in content
        assert "补强证据" in content

    def test_no_data_no_section(self) -> None:
        """无数据 → 不显示 section。"""
        content = self._write()
        assert "你现在最该做的 3 件事" not in content


class TestWriteMdRiskHeatmap:
    """风险热力图 section 测试。"""

    def _write(self, *, ranked_issues=None) -> str:
        from scripts.run_case import _write_md

        result = _make_result(with_summary=False)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            _write_md(
                out,
                result,
                SimpleNamespace(issues=[]),
                _CASE_DATA,
                ranked_issues=ranked_issues,
                no_redact=True,
            )
            return (out / "report.md").read_text(encoding="utf-8")

    def test_heatmap_with_data(self) -> None:
        """ranked_issues → 显示热力图表格。"""
        content = self._write(ranked_issues=_make_ranked_issues())
        assert "风险热力图" in content
        assert "🔴" in content  # high impact + strong attack = unfavorable
        assert "🟢" in content  # medium impact + weak attack + strong evidence = favorable
        assert "🟡" in content  # low impact + medium attack = neutral

    def test_no_ranked_issues_no_section(self) -> None:
        """无 ranked_issues → 不显示。"""
        content = self._write()
        assert "风险热力图" not in content


class TestWriteMdMediationRange:
    """调解区间 section 测试。"""

    def _write(self, *, amount_report=None, decision_tree=None) -> str:
        from scripts.run_case import _write_md

        result = _make_result(with_summary=False)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            _write_md(
                out,
                result,
                SimpleNamespace(issues=[]),
                _CASE_DATA,
                amount_report=amount_report,
                decision_tree=decision_tree,
                no_redact=True,
            )
            return (out / "report.md").read_text(encoding="utf-8")

    def test_mediation_range_with_data(self) -> None:
        """amount_report + decision_tree → 显示调解区间。"""
        content = self._write(
            amount_report=_make_amount_report(),
            decision_tree=_make_decision_tree(),
        )
        assert "调解区间评估" in content
        assert "建议调解点" in content
        assert "诉请总额" in content

    def test_no_amount_report_no_section(self) -> None:
        """无 amount_report → 不显示。"""
        content = self._write()
        assert "调解区间评估" not in content


class TestWriteMdOpponentStrategy:
    """对方策略预警 section 测试。"""

    def _write(self, *, with_defenses=True, attack_chain=None) -> str:
        from scripts.run_case import _write_md

        result = _make_result(with_summary=True, with_defenses=with_defenses)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            _write_md(
                out,
                result,
                SimpleNamespace(issues=[]),
                _CASE_DATA,
                attack_chain=attack_chain,
                no_redact=True,
            )
            return (out / "report.md").read_text(encoding="utf-8")

    def test_defenses_with_attack_chain(self) -> None:
        """defendant_strongest_defenses + attack_chain → 完整预警 section。"""
        content = self._write(attack_chain=_make_attack_chain())
        assert "对方策略预警" in content
        assert "被告核心抗辩及应对建议" in content
        assert "已还款" in content
        assert "应对建议" in content
        assert "对方最优攻击路径预警" in content
        assert "质疑借条真实性" in content

    def test_defenses_only(self) -> None:
        """仅有 defenses, 无 attack_chain → 显示抗辩部分。"""
        content = self._write(attack_chain=None)
        assert "对方策略预警" in content
        assert "已还款" in content

    def test_attack_chain_only(self) -> None:
        """无 defenses, 仅有 attack_chain → 显示攻击路径。"""
        content = self._write(with_defenses=False, attack_chain=_make_attack_chain())
        assert "对方策略预警" in content
        assert "对方最优攻击路径预警" in content

    def test_no_data_no_section(self) -> None:
        """无 defenses 且无 attack_chain → 不显示。"""
        result = _make_result(with_summary=False)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            from scripts.run_case import _write_md

            _write_md(
                out,
                result,
                SimpleNamespace(issues=[]),
                _CASE_DATA,
                no_redact=True,
            )
            content = (out / "report.md").read_text(encoding="utf-8")
        assert "对方策略预警" not in content


# ---------------------------------------------------------------------------
# Test: DOCX smoke with new parameters
# ---------------------------------------------------------------------------


class TestDocxSmokeEnhancements:
    """DOCX 生成器接受新参数后仍然不抛异常。"""

    def test_all_new_params_no_exception(self, tmp_path: Path) -> None:
        """传入所有新参数 → DOCX 生成成功。"""
        import json
        from engines.report_generation.docx_generator import generate_docx_report

        case_data = _CASE_DATA.copy()
        case_data["model"] = "claude-sonnet-4-6"

        result = {
            "case_id": "case-test-001",
            "run_id": "run-test-001",
            "rounds": [],
            "evidence_conflicts": [],
            "summary": {
                "overall_assessment": "原告证据较强。",
                "plaintiff_strongest_arguments": [
                    {"issue_id": "issue-001", "position": "借条成立", "reasoning": "原件在手"},
                ],
                "defendant_strongest_defenses": [
                    {"issue_id": "issue-001", "position": "已还款", "reasoning": "有转账记录"},
                ],
            },
            "missing_evidence_report": [],
        }

        exec_summary = {
            "top5_decisive_issues": ["issue-001"],
            "top3_immediate_actions": ["补充借条原件公证", "申请银行流水调取"],
            "current_most_stable_claim": "请求偿还借款本金 8 万元",
            "critical_evidence_gaps": ["还款凭证"],
            "top3_adversary_optimal_attacks": ["atk-001"],
        }

        amount_report = {
            "claim_calculation_table": [
                {"claimed_amount": "100000", "calculated_amount": "80000"},
            ],
            "consistency_check_result": {
                "verdict_block_active": False,
                "unresolved_conflicts": [],
            },
        }

        decision_tree = {
            "paths": [
                {
                    "path_id": "path-001",
                    "trigger_condition": "借条真实性认定",
                    "trigger_issue_ids": ["issue-001"],
                    "key_evidence_ids": ["ev-001"],
                    "possible_outcome": "支持原告",
                    "confidence_interval": {"lower": 0.4, "upper": 0.7},
                    "probability": 0.6,
                    "party_favored": "plaintiff",
                },
            ],
            "blocking_conditions": [],
        }

        attack_chain = {
            "owner_party_id": "party-d-001",
            "top_attacks": [
                {
                    "attack_node_id": "atk-001",
                    "target_issue_id": "issue-001",
                    "attack_description": "质疑借条真实性",
                    "success_conditions": "借条鉴定不通过",
                    "supporting_evidence_ids": ["ev-002"],
                    "counter_measure": "申请司法鉴定",
                    "adversary_pivot_strategy": "转向质疑转账用途",
                },
            ],
            "recommended_order": ["atk-001"],
        }

        issue = SimpleNamespace(
            issue_id="issue-001",
            title="借贷关系成立",
            issue_type=SimpleNamespace(value="factual"),
        )
        issue_tree = SimpleNamespace(issues=[issue])

        dest = generate_docx_report(
            output_dir=tmp_path,
            case_data=case_data,
            result=result,
            issue_tree=issue_tree,
            ranked_issues=_make_ranked_issues(),
            decision_tree=decision_tree,
            attack_chain=attack_chain,
            exec_summary=exec_summary,
            amount_report=amount_report,
            action_rec=_make_action_rec(),
        )

        assert dest.exists()
        assert dest.stat().st_size > 0
        assert dest.suffix == ".docx"

    def test_empty_new_params_no_exception(self, tmp_path: Path) -> None:
        """新参数全部为 None → 仍然不抛异常。"""
        from engines.report_generation.docx_generator import generate_docx_report

        dest = generate_docx_report(
            output_dir=tmp_path,
            case_data={"parties": {}, "summary": [], "model": ""},
            result={
                "case_id": "c",
                "run_id": "r",
                "rounds": [],
                "evidence_conflicts": [],
                "summary": None,
                "missing_evidence_report": [],
            },
            ranked_issues=None,
            action_rec=None,
        )
        assert dest.exists()
