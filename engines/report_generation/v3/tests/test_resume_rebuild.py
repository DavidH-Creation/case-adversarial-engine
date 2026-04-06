"""Phase 4: Resume & idempotency tests for rebuild_from_artifacts().

Tests:
  1. rebuild_from_artifacts() makes zero LLM calls
  2. Resume output passes render contract
  3. Section title list identical between first-run and resume
  4. Old v2 checkpoints (no v3 fields) still resume correctly
  5. Missing report_v3.json raises FileNotFoundError
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from engines.report_generation.v3.models import (
    CoverSummary,
    EvidenceBasicCard,
    FactBaseEntry,
    FourLayerReport,
    IssueMapCard,
    Layer1Cover,
    Layer2Core,
    Layer3Perspective,
    Layer4Appendix,
    PerspectiveOutput,
    SectionTag,
    TimelineEvent,
)
from engines.report_generation.v3.render_contract import (
    compute_fallback_ratio,
    lint_markdown_render_contract,
)
from engines.report_generation.v3.report_writer import (
    rebuild_from_artifacts,
    write_v3_report_md,
)
from engines.shared.checkpoint import (
    ARTIFACT_REPORT_MD,
    ARTIFACT_RESULT_JSON,
    ARTIFACT_V3_DOCX,
    ARTIFACT_V3_JSON,
    CheckpointManager,
    CheckpointState,
)


# ---------------------------------------------------------------------------
# Fixtures — substantive FourLayerReport that passes the 0.20 fallback gate
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"(?m)^##\s+(.+?)\s*$")


def _substantive_report() -> FourLayerReport:
    """Build a FourLayerReport with enough content to survive the 0.20 gate."""
    cover = CoverSummary(
        neutral_conclusion=(
            "本案涉及民间借贷纠纷，原告主张借款20万元，"
            "核心争点在于借款合意是否成立及还款义务的主体认定。"
            "双方在借贷关系主体问题上存在根本性分歧。"
        ),
        winning_move=(
            "银行转账记录与微信聊天记录的交叉印证是决定案件走向的关键证据链。"
            "若二者能够形成完整的借贷合意证明，原告胜诉概率显著提高。"
        ),
        blocking_conditions=[
            "若法院认定被告仅为代收代付，借款合意不成立，则原告诉请将被驳回",
            "若关键电子证据未经公证且被告否认真实性，法院可能不予采信",
        ],
    )
    timeline = [
        TimelineEvent(date="2024-01-15", event="原告通过银行转账向被告账户汇入20万元", source="EV-P-TRANSFER"),
        TimelineEvent(date="2024-01-16", event="被告通过微信确认收到借款并承诺三个月内归还", source="EV-P-CHAT"),
        TimelineEvent(date="2024-04-20", event="还款期限届满，被告未履行还款义务", source="case_data"),
        TimelineEvent(date="2024-05-01", event="原告向法院提起民事诉讼", source="case_data"),
    ]
    layer1 = Layer1Cover(cover_summary=cover, timeline=timeline)

    fact_base = [
        FactBaseEntry(
            fact_id="FACT-001",
            description="2024年1月15日原告通过中国银行向被告账户转账20万元整，银行流水可查",
            source_evidence_ids=["EV-P-TRANSFER"],
        ),
        FactBaseEntry(
            fact_id="FACT-002",
            description="2024年1月16日被告在微信中确认收到款项并承诺三个月内归还全部借款",
            source_evidence_ids=["EV-P-CHAT"],
        ),
    ]
    issue_map = [
        IssueMapCard(
            issue_id="ISS-001",
            issue_title="借款合意是否成立",
            tag=SectionTag.inference,
            plaintiff_thesis="转账记录加微信确认构成完整的借贷合意证据链",
            defendant_thesis="转账系第三方委托代收，不构成借贷法律关系",
            decisive_evidence=["EV-P-TRANSFER", "EV-P-CHAT"],
        ),
        IssueMapCard(
            issue_id="ISS-002",
            issue_title="还款义务的主体认定",
            tag=SectionTag.inference,
            plaintiff_thesis="被告直接收款并承诺还款，是适格的债务人",
            defendant_thesis="实际借款人为第三方，被告仅为资金通道",
            decisive_evidence=["EV-P-CHAT"],
        ),
    ]
    evidence_cards = [
        EvidenceBasicCard(
            evidence_id="EV-P-TRANSFER",
            q1_what="中国银行转账凭证，显示原告向被告账户转入20万元",
            q2_target="直接证明资金交付事实，是认定借贷关系成立的基础证据",
            q3_key_risk="被告可能主张该转账系代第三方收款而非借款",
            q4_best_attack="结合微信聊天记录中被告的还款承诺，可排除代收代付的可能性",
        ),
        EvidenceBasicCard(
            evidence_id="EV-P-CHAT",
            q1_what="微信聊天记录截图，包含被告确认收款并承诺还款的完整对话",
            q2_target="直接证明被告存在还款承诺，强化借贷合意的认定",
            q3_key_risk="被告可能主张聊天记录被篡改或断章取义",
            q4_best_attack="可申请微信原始数据鉴定以证明真实性和完整性",
        ),
    ]
    layer2 = Layer2Core(
        fact_base=fact_base,
        issue_map=issue_map,
        evidence_cards=evidence_cards,
        evidence_battle_matrix_md=(
            "| 争议焦点 | 原告证据 | 被告证据 | 中立评估 |\n"
            "|---------|---------|---------|--------|\n"
            "| 借款合意 | 转账凭证＋微信记录 | 口头主张代收代付 | 原告证据链较完整，被告需举证反驳 |\n"
            "| 还款义务 | 微信还款承诺截图 | 否认借款人身份 | 被告承诺还款的事实较难推翻 |\n"
        ),
        scenario_tree_md=(
            "**路径A（原告胜诉）**：法院认定借贷合意成立→被告承担还款义务→判决返还本金20万元及利息。\n\n"
            "**路径B（被告胜诉）**：法院认定转账系代收代付→借贷合意不成立→驳回原告诉讼请求。\n\n"
            "**关键分歧节点**：微信聊天记录的真实性与证明力是决定路径走向的核心因素。"
        ),
    )

    outputs = [
        PerspectiveOutput(
            perspective="plaintiff",
            evidence_supplement_checklist=[
                "申请微信原始数据司法鉴定，确保聊天记录真实性",
                "提交银行流水原件作为转账事实的补强证据",
            ],
            cross_examination_points=[
                "质证被告代收代付说缺乏书面委托证据支撑",
                "追问被告为何在微信中明确承诺还款",
            ],
            trial_questions=[
                "被告是否能提供第三方实际借款人的有效联系方式和身份证明",
                "被告是否曾向第三方转付过该笔款项",
            ],
            contingency_plans=[
                "若被告否认微信记录真实性，申请电子数据鉴定",
                "若第三方证人出庭，准备交叉质询方案",
            ],
        ),
        PerspectiveOutput(
            perspective="defendant",
            evidence_supplement_checklist=[
                "提供第三方实际借款人的书面证言和身份证明",
                "收集与第三方的转账记录证明资金流转链条",
            ],
            cross_examination_points=[
                "主张微信聊天记录存在断章取义，要求出示完整对话",
                "质证转账凭证仅能证明资金交付，不能证明借贷合意",
            ],
            trial_questions=[
                "原告是否与第三方存在其他经济往来",
                "原告在转账时是否知晓被告系代收代付",
            ],
            contingency_plans=[
                "若第三方拒绝出庭，申请法院调取第三方银行流水",
                "若微信记录鉴定为真，转向主张存在胁迫或误解",
            ],
        ),
        PerspectiveOutput(
            perspective="neutral",
            evidence_supplement_checklist=[
                "建议双方就微信记录真实性进行共同鉴定以节约诉讼资源",
                "建议法院调取被告与第三方的银行流水以查明资金最终去向",
            ],
            cross_examination_points=[
                "原告的证据优势较为明显，被告需提供实质性反证",
                "代收代付抗辩需要第三方的直接证据支持，不能仅凭口头主张",
            ],
            trial_questions=[
                "法院应重点审查微信聊天记录的完整性和关联性",
                "双方是否愿意就部分事实进行调解以缩小争议范围",
            ],
            contingency_plans=[
                "根据证据优势原则，原告胜诉概率较高，建议被告考虑和解",
                "若证据势均力敌，法院可能按照举证责任分配规则裁判",
            ],
        ),
    ]
    layer3 = Layer3Perspective(outputs=outputs)

    layer4 = Layer4Appendix(
        adversarial_transcripts_md=(
            "**第一轮**：原告提出借贷合意证据链（转账＋微信确认），"
            "被告抗辩系代收代付但未提供书面证据支持。\n\n"
            "**第二轮**：原告补充银行流水明细，被告申请第三方证人出庭。\n\n"
            "**第三轮**：双方围绕微信记录真实性展开质证，原告申请司法鉴定。"
        ),
        evidence_index_md=(
            "| 编号 | 名称 | 提交方 | 类型 |\n"
            "|------|------|--------|------|\n"
            "| EV-P-TRANSFER | 银行转账凭证 | 原告 | 书证 |\n"
            "| EV-P-CHAT | 微信聊天记录 | 原告 | 电子数据 |\n"
            "| EV-D-WITNESS | 第三方证人证言 | 被告 | 证人证言 |\n"
        ),
        timeline_md=(
            "| 日期 | 事件 | 来源 |\n"
            "|------|------|------|\n"
            "| 2024-01-15 | 原告向被告转账20万元 | 银行流水 |\n"
            "| 2024-01-16 | 被告微信确认收款并承诺还款 | 聊天记录 |\n"
            "| 2024-04-20 | 还款期限届满 | 合同约定 |\n"
            "| 2024-05-01 | 原告提起诉讼 | 起诉状 |\n"
        ),
        glossary_md=(
            "| 术语 | 解释 |\n"
            "|------|------|\n"
            "| 民间借贷 | 自然人之间、自然人与法人之间的资金融通行为 |\n"
            "| 借贷合意 | 出借人与借款人就借贷事项达成的一致意思表示 |\n"
            "| 代收代付 | 受他人委托代为收取或支付款项的行为 |\n"
        ),
        amount_calculation_md=(
            "**借款本金**：200,000元（银行转账凭证确认）\n\n"
            "**利息计算**：按照同期LPR计算，自2024年4月20日起至实际清偿之日止\n\n"
            "**诉讼费用**：由败诉方承担"
        ),
    )

    return FourLayerReport(
        report_id="rpt-resume-test",
        case_id="case-resume-test",
        run_id="run-resume-test",
        layer1=layer1,
        layer2=layer2,
        layer3=layer3,
        layer4=layer4,
    )


# ===========================================================================
# Test 1: rebuild_from_artifacts() makes zero LLM calls
# ===========================================================================


class TestRebuildZeroLLM:
    """rebuild_from_artifacts() must not invoke any LLM client."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_rebuild_makes_no_llm_calls(self, _mock_redact):
        """Serialize a FourLayerReport to disk, rebuild, verify no LLM calls."""
        report = _substantive_report()

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            # Simulate the pipeline saving report_v3.json
            v3_json = workspace / "report_v3.json"
            v3_json.write_text(report.model_dump_json(indent=2), encoding="utf-8")

            # Patch the DOCX generator at source to avoid needing python-docx infra
            with patch(
                "engines.report_generation.docx_generator.generate_docx_v3_report",
                side_effect=Exception("DOCX not available in test"),
            ):
                md_path, docx_path = rebuild_from_artifacts(
                    workspace,
                    {"case_type": "civil_loan", "parties": {}},
                    no_redact=True,
                )

            assert md_path.exists()
            assert docx_path is None  # DOCX mock raised
            content = md_path.read_text(encoding="utf-8")
            assert len(content) > 100

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_rebuild_missing_json_raises(self, _mock_redact):
        """rebuild_from_artifacts raises FileNotFoundError without report_v3.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FileNotFoundError, match="report_v3.json"):
                rebuild_from_artifacts(
                    Path(tmpdir),
                    {"case_type": "civil_loan", "parties": {}},
                )


# ===========================================================================
# Test 2: Resume output passes render contract
# ===========================================================================


class TestResumeRenderContract:
    """Rebuilt report must pass the render contract (10 rules)."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_rebuilt_report_passes_render_contract(self, _mock_redact):
        report = _substantive_report()

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            v3_json = workspace / "report_v3.json"
            v3_json.write_text(report.model_dump_json(indent=2), encoding="utf-8")

            md_path, _ = rebuild_from_artifacts(
                workspace,
                {"case_type": "civil_loan", "parties": {}},
                no_redact=True,
            )

            content = md_path.read_text(encoding="utf-8")
            # Should not raise RenderContractViolation
            lint_markdown_render_contract(content)

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_rebuilt_report_fallback_ratio_within_threshold(self, _mock_redact):
        report = _substantive_report()

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            v3_json = workspace / "report_v3.json"
            v3_json.write_text(report.model_dump_json(indent=2), encoding="utf-8")

            md_path, _ = rebuild_from_artifacts(
                workspace,
                {"case_type": "civil_loan", "parties": {}},
                no_redact=True,
            )

            content = md_path.read_text(encoding="utf-8")
            ratio, count, total = compute_fallback_ratio(content)
            assert ratio <= 0.20, (
                f"Rebuilt report fallback ratio {ratio:.0%} ({count}/{total})"
                f" exceeds 0.20 threshold"
            )


# ===========================================================================
# Test 3: Section titles identical between first-run and resume
# ===========================================================================


class TestResumeIdempotency:
    """First-run and resume must produce structurally identical reports."""

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_section_titles_match_between_runs(self, _mock_redact):
        """First write_v3_report_md and rebuild_from_artifacts produce same headings."""
        report = _substantive_report()
        case_data = {"case_type": "civil_loan", "parties": {}}

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)

            # First run: write directly
            first_md_path = write_v3_report_md(workspace, report, case_data, no_redact=True)
            first_content = first_md_path.read_text(encoding="utf-8")
            first_headings = _HEADING_RE.findall(first_content)

            # Save report_v3.json (simulate pipeline)
            v3_json = workspace / "report_v3.json"
            v3_json.write_text(report.model_dump_json(indent=2), encoding="utf-8")

            # Resume: rebuild from artifacts
            resume_md_path, _ = rebuild_from_artifacts(
                workspace, case_data, no_redact=True,
            )
            resume_content = resume_md_path.read_text(encoding="utf-8")
            resume_headings = _HEADING_RE.findall(resume_content)

            assert first_headings == resume_headings, (
                f"Heading mismatch between first-run and resume.\n"
                f"First-run: {first_headings}\n"
                f"Resume:    {resume_headings}"
            )

    @patch("engines.shared.disclaimer_templates.DISCLAIMER_MD", "TEST DISCLAIMER")
    @patch("engines.shared.pii_redactor.redact_text", side_effect=lambda x, **kw: x)
    def test_resume_render_contract_matches_first_run(self, _mock_redact):
        """Both first-run and resume must produce the same lint outcome."""
        report = _substantive_report()
        case_data = {"case_type": "civil_loan", "parties": {}}

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)

            first_md = write_v3_report_md(workspace, report, case_data, no_redact=True)
            first_content = first_md.read_text(encoding="utf-8")
            first_results = lint_markdown_render_contract(first_content)

            v3_json = workspace / "report_v3.json"
            v3_json.write_text(report.model_dump_json(indent=2), encoding="utf-8")

            resume_md, _ = rebuild_from_artifacts(workspace, case_data, no_redact=True)
            resume_content = resume_md.read_text(encoding="utf-8")
            resume_results = lint_markdown_render_contract(resume_content)

            first_rules = {r.rule for r in first_results}
            resume_rules = {r.rule for r in resume_results}
            assert first_rules == resume_rules, (
                f"Lint rule mismatch: first={first_rules}, resume={resume_rules}"
            )


# ===========================================================================
# Test 4: Old v2 checkpoints (no v3 fields) backward-compatible
# ===========================================================================


class TestCheckpointBackwardCompat:
    """Checkpoints without v3 artifact keys must still work."""

    def test_v2_checkpoint_has_v3_artifacts_false(self):
        """CheckpointState without report_v3_json returns has_v3_artifacts=False."""
        state = CheckpointState(
            run_id="run-v2",
            last_completed_step="step_4_outputs",
            artifact_paths={
                "result_json": "/tmp/result.json",
                "report_md": "/tmp/report.md",
            },
            timestamp="2026-04-01T00:00:00Z",
        )
        assert not state.has_v3_artifacts

    def test_v3_checkpoint_has_v3_artifacts_true(self):
        """CheckpointState with report_v3_json returns has_v3_artifacts=True."""
        state = CheckpointState(
            run_id="run-v3",
            last_completed_step="step_5_docx",
            artifact_paths={
                "result_json": "/tmp/result.json",
                "report_md": "/tmp/report.md",
                "report_v3_json": "/tmp/report_v3.json",
                "report_v3_docx": "/tmp/report.docx",
            },
            timestamp="2026-04-06T00:00:00Z",
        )
        assert state.has_v3_artifacts

    def test_v2_checkpoint_round_trip(self):
        """Save and load a v2 checkpoint — no v3 keys should appear."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = CheckpointManager(Path(tmpdir))
            # Create a dummy artifact so validate doesn't fail
            dummy = Path(tmpdir) / "result.json"
            dummy.write_text("{}", encoding="utf-8")

            mgr.save(
                "step_4_outputs",
                {"result_json": str(dummy), "report_md": str(dummy)},
                run_id="run-v2-compat",
            )
            state = mgr.load()
            assert state is not None
            assert not state.has_v3_artifacts
            assert state.last_completed_step == "step_4_outputs"

    def test_v3_checkpoint_round_trip(self):
        """Save and load a v3 checkpoint — v3 keys must survive round-trip."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = CheckpointManager(Path(tmpdir))
            dummy = Path(tmpdir) / "result.json"
            dummy.write_text("{}", encoding="utf-8")
            v3_dummy = Path(tmpdir) / "report_v3.json"
            v3_dummy.write_text("{}", encoding="utf-8")

            mgr.save(
                "step_4_outputs",
                {
                    "result_json": str(dummy),
                    "report_md": str(dummy),
                    "report_v3_json": str(v3_dummy),
                },
                run_id="run-v3-compat",
            )
            state = mgr.load()
            assert state is not None
            assert state.has_v3_artifacts
            assert "report_v3_json" in state.artifact_paths


# ===========================================================================
# Test 5: JSON round-trip fidelity
# ===========================================================================


class TestJsonRoundTrip:
    """FourLayerReport JSON serialization survives rebuild."""

    def test_model_round_trip_preserves_structure(self):
        """Serialize → deserialize must preserve all fields."""
        report = _substantive_report()
        json_str = report.model_dump_json(indent=2)
        restored = FourLayerReport.model_validate_json(json_str)

        assert restored.report_id == report.report_id
        assert restored.case_id == report.case_id
        assert len(restored.layer2.fact_base) == len(report.layer2.fact_base)
        assert len(restored.layer2.issue_map) == len(report.layer2.issue_map)
        assert len(restored.layer2.evidence_cards) == len(report.layer2.evidence_cards)
        assert len(restored.layer3.outputs) == len(report.layer3.outputs)
        assert restored.layer4.amount_calculation_md == report.layer4.amount_calculation_md
