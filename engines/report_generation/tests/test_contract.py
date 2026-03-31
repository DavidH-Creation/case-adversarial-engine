"""
合同测试 — 使用 benchmark fixtures 验证 Report Generator 的输出结构。
Contract tests — validate Report Generator output structure against benchmark fixtures.

仅验证结构性合约约束（不验证 LLM 内容）：
Only validates structural contract constraints (not LLM content):
1. 报告包含所有必填顶层字段 / Report has all required top-level fields
2. sections 非空 / sections is non-empty
3. 每个章节有 linked_output_ids / Each section has linked_output_ids
4. 每条结论有 supporting_evidence_ids（citation_completeness）
5. statement_class 为合法枚举值 / statement_class is a valid enum value
6. summary ≤ 500 字 / summary ≤ 500 characters
7. section_index 唯一且连续 / section_index is unique
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixture 路径 / Fixture paths
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "benchmarks" / "fixtures"
_OUTPUT_FIXTURE = _FIXTURES_DIR / "report_artifact_example.json"


def _load_fixture(path: Path) -> dict:
    """加载 fixture JSON 文件 / Load fixture JSON file."""
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 合同测试套件 / Contract test suite
# ---------------------------------------------------------------------------


class TestReportContractFixtures:
    """基于 gold fixtures 的报告合约校验 / Contract validation against gold fixtures."""

    @pytest.fixture(autouse=True)
    def load_fixtures(self):
        self.report = _load_fixture(_OUTPUT_FIXTURE)
        self.sections = self.report.get("sections", [])
        all_conclusions = []
        for sec in self.sections:
            all_conclusions.extend(sec.get("key_conclusions", []))
        self.all_conclusions = all_conclusions

    # ── 顶层结构 / Top-level structure ────────────────────────────────────────

    def test_output_has_required_top_level_keys(self):
        """报告必须包含所有必填顶层字段。"""
        required = {"report_id", "case_id", "run_id", "title", "summary", "sections"}
        missing = required - set(self.report.keys())
        assert not missing, f"缺少顶层字段 / Missing top-level keys: {missing}"

    def test_sections_non_empty(self):
        """sections 数组不能为空。"""
        assert len(self.sections) > 0, "sections array must not be empty"

    def test_summary_length_under_500(self):
        """summary ≤ 500 字。"""
        summary = self.report.get("summary", "")
        assert len(summary) <= 500, (
            f"summary 超过 500 字 ({len(summary)}) / Summary exceeds 500 chars"
        )

    # ── 章节级别校验 / Section-level validation ──────────────────────────────

    def test_sections_have_required_fields(self):
        """每个章节应包含必填字段。"""
        required = {"section_id", "section_index", "title", "body", "linked_evidence_ids"}
        for sec in self.sections:
            missing = required - set(sec.keys())
            assert not missing, f"Section {sec.get('section_id', '?')} missing fields: {missing}"

    def test_section_indices_unique(self):
        """section_index 在报告中唯一。"""
        indices = [sec.get("section_index") for sec in self.sections]
        assert len(indices) == len(set(indices)), f"存在重复的 section_index: {indices}"

    def test_sections_have_linked_output_ids(self):
        """每个章节必须有 linked_output_ids（推演回连）。"""
        for sec in self.sections:
            assert sec.get("linked_output_ids"), (
                f"Section {sec.get('section_id', '?')} has empty linked_output_ids"
            )

    # ── 结论级别校验 / Conclusion-level validation ───────────────────────────

    def test_all_conclusions_have_supporting_evidence(self):
        """每条关键结论必须有至少一个 supporting_evidence_ids（citation_completeness=100%）。"""
        for concl in self.all_conclusions:
            assert concl.get("supporting_evidence_ids"), (
                f"Conclusion {concl.get('conclusion_id', '?')} has empty supporting_evidence_ids"
            )

    def test_statement_class_valid_enum(self):
        """statement_class 必须为合法枚举值。"""
        valid = {"fact", "inference", "assumption"}
        for concl in self.all_conclusions:
            sc = concl.get("statement_class")
            assert sc in valid, (
                f"Conclusion {concl.get('conclusion_id', '?')} has invalid statement_class: {sc!r}"
            )

    def test_conclusions_have_required_fields(self):
        """每条结论应包含必填字段。"""
        required = {"conclusion_id", "text", "statement_class", "supporting_evidence_ids"}
        for concl in self.all_conclusions:
            missing = required - set(concl.keys())
            assert not missing, (
                f"Conclusion {concl.get('conclusion_id', '?')} missing fields: {missing}"
            )
