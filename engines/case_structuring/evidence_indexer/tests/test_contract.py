"""
合同测试 — 使用 benchmark fixtures 验证 Evidence Indexer 的输出结构。

不验证 LLM 提取的具体内容（因输出会随模型调用变化），
仅验证结构性合同约束：
1. 每条 Evidence 符合 JSON Schema
2. 每条 Evidence 状态为 private / owner_private
3. target_fact_ids 非空
4. evidence_id 全局唯一
5. 每个输入 source_id 至少映射到一条输出 Evidence
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixture 路径
# ---------------------------------------------------------------------------

_FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent.parent / "benchmarks" / "fixtures"
)
_INPUT_FIXTURE = _FIXTURES_DIR / "evidence_indexer_input.json"
_OUTPUT_FIXTURE = _FIXTURES_DIR / "evidence_indexer_output.json"


def _load_fixture(path: Path) -> dict:
    """加载 fixture JSON 文件。"""
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestContractFixtures:
    """基于 gold fixtures 的合同校验。"""

    @pytest.fixture(autouse=True)
    def load_fixtures(self):
        self.input_data = _load_fixture(_INPUT_FIXTURE)
        self.output_data = _load_fixture(_OUTPUT_FIXTURE)
        self.evidences = self.output_data.get("evidences", [])
        self.raw_materials = self.input_data.get("raw_materials", [])

    def test_output_has_evidences(self):
        """输出 fixture 应包含 evidences 数组。"""
        assert "evidences" in self.output_data
        assert len(self.evidences) > 0

    def test_evidence_count_matches_materials(self):
        """证据数量应 >= 原始材料数量（每条材料至少一条证据）。"""
        assert len(self.evidences) >= len(self.raw_materials)

    def test_all_evidence_ids_unique(self):
        """所有 evidence_id 在输出中唯一。"""
        ids = [e["evidence_id"] for e in self.evidences]
        assert len(ids) == len(set(ids)), f"存在重复的 evidence_id: {ids}"

    def test_all_evidence_status_private(self):
        """初始状态必须为 private。"""
        for e in self.evidences:
            assert e["status"] == "private", (
                f"Evidence {e['evidence_id']} status={e['status']}, expected 'private'"
            )

    def test_all_evidence_access_domain_owner_private(self):
        """初始 access_domain 必须为 owner_private。"""
        for e in self.evidences:
            assert e["access_domain"] == "owner_private", (
                f"Evidence {e['evidence_id']} access_domain={e['access_domain']}"
            )

    def test_all_evidence_have_target_facts(self):
        """每条 Evidence 的 target_fact_ids 不能为空。"""
        for e in self.evidences:
            facts = e.get("target_fact_ids", [])
            assert len(facts) >= 1, f"Evidence {e['evidence_id']} has empty target_fact_ids"

    def test_all_evidence_submitted_by_null(self):
        """初始 submitted_by_party_id 必须为 null。"""
        for e in self.evidences:
            assert e.get("submitted_by_party_id") is None, (
                f"Evidence {e['evidence_id']} submitted_by_party_id should be null"
            )

    def test_all_evidence_challenged_by_empty(self):
        """初始 challenged_by_party_ids 必须为空数组。"""
        for e in self.evidences:
            assert e.get("challenged_by_party_ids") == [], (
                f"Evidence {e['evidence_id']} challenged_by_party_ids should be []"
            )

    def test_source_coverage(self):
        """每个输入 source_id 应至少被一条 Evidence 的 source 引用。"""
        input_source_ids = {m["source_id"] for m in self.raw_materials}
        output_sources = {e["source"] for e in self.evidences}
        missing = input_source_ids - output_sources
        assert not missing, f"以下 source_id 未被任何 Evidence 引用: {missing}"

    def test_case_id_consistent(self):
        """所有 Evidence 的 case_id 应与输入一致。"""
        expected_case_id = self.input_data.get("case_id")
        if expected_case_id:
            for e in self.evidences:
                assert e["case_id"] == expected_case_id

    def test_evidence_type_valid(self):
        """evidence_type 必须为合法枚举值。"""
        valid_types = {
            "documentary",
            "physical",
            "witness_statement",
            "electronic_data",
            "expert_opinion",
            "audio_visual",
            "other",
        }
        for e in self.evidences:
            assert e["evidence_type"] in valid_types, (
                f"Evidence {e['evidence_id']} has invalid type: {e['evidence_type']}"
            )

    def test_required_fields_present(self):
        """输出 fixture 中每条 Evidence 应包含所有必填字段。"""
        required = {
            "evidence_id",
            "case_id",
            "owner_party_id",
            "title",
            "source",
            "summary",
            "evidence_type",
            "target_fact_ids",
            "target_issue_ids",
            "access_domain",
            "status",
            "submitted_by_party_id",
            "challenged_by_party_ids",
            "admissibility_notes",
        }
        for e in self.evidences:
            missing = required - set(e.keys())
            assert not missing, f"Evidence {e.get('evidence_id', '?')} missing fields: {missing}"
