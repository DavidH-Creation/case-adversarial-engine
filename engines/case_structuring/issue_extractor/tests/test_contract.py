"""
合同测试 — 使用 benchmark fixtures 验证 Issue Extractor 的输出结构。
Contract tests — validate Issue Extractor output structure against benchmark fixtures.

不验证 LLM 提取的具体内容（因输出会随模型调用变化），
仅验证结构性合同约束：
Only validates structural contract constraints (not LLM content, which varies per call):
1. 输出包含所有必填顶层字段 / Output has all required top-level keys
2. issue_id 全局唯一 / issue_ids are globally unique
3. issue_type 为合法枚举值 / issue_type is a valid enum value
4. parent_issue_id 无悬空引用 / No dangling parent_issue_id references
5. 核心 Issue 至少分配一个 Burden / Root issues have at least one Burden
6. 每个 Claim/Defense 都有争点映射 / Every Claim/Defense has an issue mapping
7. 每条 Issue 的 evidence_ids 引用输入中存在的证据 / evidence_ids reference known evidences
8. Burden 的 issue_id 引用实际存在的争点 / Burden issue_ids reference existing issues
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixture 路径 / Fixture paths
# ---------------------------------------------------------------------------

_FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent.parent / "benchmarks" / "fixtures"
)
_INPUT_FIXTURE = _FIXTURES_DIR / "issue_extractor_input.json"
_OUTPUT_FIXTURE = _FIXTURES_DIR / "issue_extractor_output.json"


def _load_fixture(path: Path) -> dict:
    """加载 fixture JSON 文件。Load fixture JSON file."""
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 合同测试套件 / Contract test suite
# ---------------------------------------------------------------------------


class TestContractFixtures:
    """基于 gold fixtures 的合同校验。Contract validation against gold fixtures."""

    @pytest.fixture(autouse=True)
    def load_fixtures(self):
        self.input_data = _load_fixture(_INPUT_FIXTURE)
        self.output_data = _load_fixture(_OUTPUT_FIXTURE)
        self.issues = self.output_data.get("issues", [])
        self.burdens = self.output_data.get("burdens", [])
        self.claim_mappings = self.output_data.get("claim_issue_mapping", [])
        self.defense_mappings = self.output_data.get("defense_issue_mapping", [])
        self.claims = self.input_data.get("claims", [])
        self.defenses = self.input_data.get("defenses", [])
        self.evidence = self.input_data.get("evidence", [])

    # ── 顶层结构 / Top-level structure ────────────────────────────────────────

    def test_output_has_required_top_level_keys(self):
        """输出 fixture 应包含所有必填顶层字段。"""
        required = {"case_id", "issues", "burdens", "claim_issue_mapping", "defense_issue_mapping"}
        missing = required - set(self.output_data.keys())
        assert not missing, f"缺少顶层字段 / Missing top-level keys: {missing}"

    def test_issues_non_empty(self):
        """issues 数组不能为空。"""
        assert len(self.issues) > 0, "issues array must not be empty"

    def test_burdens_non_empty(self):
        """burdens 数组不能为空。"""
        assert len(self.burdens) > 0, "burdens array must not be empty"

    # ── Issue 级别校验 / Issue-level validation ───────────────────────────────

    def test_all_issue_ids_unique(self):
        """所有 issue_id 在输出中唯一。All issue_ids must be globally unique."""
        ids = [i["issue_id"] for i in self.issues]
        assert len(ids) == len(set(ids)), f"存在重复的 issue_id: {ids}"

    def test_all_issues_have_required_fields(self):
        """每条 Issue 应包含 issue.schema.json 中的必填字段。"""
        required = {"issue_id", "case_id", "title", "issue_type", "fact_propositions"}
        for issue in self.issues:
            missing = required - set(issue.keys())
            assert not missing, (
                f"Issue {issue.get('issue_id', '?')} missing required fields: {missing}"
            )

    def test_issue_type_valid_enum(self):
        """issue_type 必须为合法枚举值。issue_type must be a valid enum value."""
        valid = {"factual", "legal", "procedural", "mixed"}
        for issue in self.issues:
            assert issue["issue_type"] in valid, (
                f"Issue {issue['issue_id']} has invalid issue_type: {issue['issue_type']}"
            )

    def test_issue_status_valid_enum(self):
        """issue status 如存在，必须为合法枚举值。"""
        valid = {"open", "resolved", "deferred"}
        for issue in self.issues:
            if "status" in issue:
                assert issue["status"] in valid, (
                    f"Issue {issue['issue_id']} has invalid status: {issue['status']}"
                )

    def test_no_dangling_parent_issue_id(self):
        """parent_issue_id 不得引用不存在的 issue_id。
        No parent_issue_id may reference a non-existent issue_id.
        """
        all_ids = {i["issue_id"] for i in self.issues}
        for issue in self.issues:
            parent = issue.get("parent_issue_id")
            if parent is not None:
                assert parent in all_ids, (
                    f"Issue {issue['issue_id']}: parent_issue_id '{parent}' not found in issues"
                )

    def test_fact_propositions_have_text(self):
        """每条 FactProposition 应包含 text 字段。"""
        for issue in self.issues:
            for fp in issue.get("fact_propositions", []):
                assert fp.get("text"), (
                    f"Issue {issue['issue_id']} has a fact_proposition without text"
                )

    # ── Burden 级别校验 / Burden-level validation ─────────────────────────────

    def test_root_issues_have_burdens(self):
        """核心争点（parent_issue_id 为 null）必须至少分配一个 Burden。
        Root issues (no parent) must have at least one Burden assigned.
        """
        burden_issue_ids = {b["issue_id"] for b in self.burdens}
        for issue in self.issues:
            if issue.get("parent_issue_id") is None:
                assert issue["issue_id"] in burden_issue_ids, (
                    f"Root issue {issue['issue_id']} has no assigned Burden"
                )

    def test_burden_issue_ids_reference_existing_issues(self):
        """Burden 的 issue_id 应引用输出中存在的争点。
        Burden issue_ids must reference issues that exist in the output.
        """
        all_issue_ids = {i["issue_id"] for i in self.issues}
        for burden in self.burdens:
            assert burden["issue_id"] in all_issue_ids, (
                f"Burden {burden['burden_id']} references unknown issue_id: {burden['issue_id']}"
            )

    # ── 映射完整性 / Mapping completeness ────────────────────────────────────

    def test_complete_claim_mapping(self):
        """每个 Claim 必须出现在 claim_issue_mapping 中。
        Every Claim must appear in claim_issue_mapping.
        """
        mapped_ids = {m["claim_id"] for m in self.claim_mappings}
        for claim in self.claims:
            cid = claim["claim_id"]
            assert cid in mapped_ids, f"Claim '{cid}' has no entry in claim_issue_mapping"

    def test_complete_defense_mapping(self):
        """每个 Defense 必须出现在 defense_issue_mapping 中。
        Every Defense must appear in defense_issue_mapping.
        """
        mapped_ids = {m["defense_id"] for m in self.defense_mappings}
        for defense in self.defenses:
            did = defense["defense_id"]
            assert did in mapped_ids, f"Defense '{did}' has no entry in defense_issue_mapping"

    def test_claim_mapping_issue_ids_non_empty(self):
        """claim_issue_mapping 中每个映射的 issue_ids 不能为空。"""
        for m in self.claim_mappings:
            assert m.get("issue_ids"), (
                f"claim_id '{m['claim_id']}' has empty issue_ids in claim_issue_mapping"
            )

    def test_defense_mapping_issue_ids_non_empty(self):
        """defense_issue_mapping 中每个映射的 issue_ids 不能为空。"""
        for m in self.defense_mappings:
            assert m.get("issue_ids"), (
                f"defense_id '{m['defense_id']}' has empty issue_ids in defense_issue_mapping"
            )

    # ── 引用完整性 / Reference integrity ─────────────────────────────────────

    def test_evidence_ids_reference_known_evidence(self):
        """Issue 的 evidence_ids 应引用输入中存在的证据。
        Issue evidence_ids must reference evidences present in the input.
        """
        known_ids = {e["evidence_id"] for e in self.evidence}
        for issue in self.issues:
            for eid in issue.get("evidence_ids", []):
                assert eid in known_ids, (
                    f"Issue {issue['issue_id']} references unknown evidence_id: '{eid}'"
                )

    def test_case_id_consistent(self):
        """所有 Issue 和 Burden 的 case_id 应与顶层输出的 case_id 一致。
        All issue and burden case_ids must match the top-level case_id.
        """
        expected = self.output_data.get("case_id")
        if not expected:
            return
        for issue in self.issues:
            assert issue["case_id"] == expected, (
                f"Issue {issue['issue_id']} case_id mismatch: {issue['case_id']} != {expected}"
            )
        for burden in self.burdens:
            assert burden["case_id"] == expected, (
                f"Burden {burden['burden_id']} case_id mismatch: {burden['case_id']} != {expected}"
            )
