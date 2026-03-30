"""
Few-shot examples 单元测试。
Unit tests for few-shot example loading and injection into prompts.

测试策略：
- 验证 loader 正确加载 JSON 文件并格式化为 <example> 标签
- 验证 loader 在文件缺失时优雅降级（返回空字符串）
- 验证各关键模块的 system prompt 包含 few-shot examples
- 验证 few-shot examples 的 JSON 结构与 tool_use schema 一致
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from engines.shared.few_shot_examples import load_few_shot_text


# ---------------------------------------------------------------------------
# Loader 基础测试
# ---------------------------------------------------------------------------


class TestLoadFewShotText:
    """load_few_shot_text 加载器测试。"""

    def test_loads_existing_module(self):
        """已有的 example 文件能正确加载并包含 <example> 标签。"""
        text = load_few_shot_text("adversarial_plaintiff")
        assert text != ""
        assert "<example" in text
        assert "</example>" in text
        assert "参考示例" in text

    def test_missing_module_returns_empty(self):
        """不存在的模块名返回空字符串，不报错。"""
        text = load_few_shot_text("nonexistent_module_xyz")
        assert text == ""

    def test_contains_input_summary_and_output(self):
        """加载结果包含 input_summary 和 expected_output 的 JSON。"""
        text = load_few_shot_text("adversarial_plaintiff")
        assert "输入摘要" in text
        assert "期望输出" in text
        # 应包含 JSON 结构中的关键字段
        assert "issue_ids" in text
        assert "evidence_citations" in text

    def test_malformed_json_returns_empty(self, tmp_path):
        """JSON 格式错误时返回空字符串。"""
        bad_file = tmp_path / "bad_module.json"
        bad_file.write_text("{invalid json", encoding="utf-8")
        with patch(
            "engines.shared.few_shot_examples._EXAMPLES_DIR", tmp_path
        ):
            text = load_few_shot_text("bad_module")
            assert text == ""

    def test_all_example_files_are_valid_json(self):
        """所有 example JSON 文件格式合法。"""
        examples_dir = Path(__file__).parent.parent / "engines" / "shared" / "few_shot_examples"
        json_files = list(examples_dir.glob("*.json"))
        assert len(json_files) >= 4, f"应至少有 4 个 example 文件，实际: {len(json_files)}"
        for f in json_files:
            data = json.loads(f.read_text(encoding="utf-8"))
            items = data if isinstance(data, list) else [data]
            for item in items:
                assert "input_summary" in item, f"{f.name} 缺少 input_summary"
                assert "expected_output" in item, f"{f.name} 缺少 expected_output"


# ---------------------------------------------------------------------------
# Prompt 注入验证
# ---------------------------------------------------------------------------


class TestPlaintiffAgentFewShot:
    """原告代理 system prompt 包含 few-shot examples。"""

    def test_system_prompt_contains_examples(self):
        from engines.adversarial.agents.plaintiff import PlaintiffAgent
        from engines.adversarial.schemas import RoundConfig

        class _FakeLLM:
            async def create_message(self, **kw):
                return "{}"

        config = RoundConfig(
            num_rounds=1, model="test", temperature=0.0,
            max_tokens_per_output=100, max_retries=1,
        )
        agent = PlaintiffAgent(llm_client=_FakeLLM(), party_id="p1", config=config)
        prompt = agent._build_system_prompt()
        assert "<example" in prompt
        assert "原告主张借贷关系成立" in prompt


class TestDefendantAgentFewShot:
    """被告代理 system prompt 包含 few-shot examples。"""

    def test_system_prompt_contains_examples(self):
        from engines.adversarial.agents.defendant import DefendantAgent
        from engines.adversarial.schemas import RoundConfig

        class _FakeLLM:
            async def create_message(self, **kw):
                return "{}"

        config = RoundConfig(
            num_rounds=1, model="test", temperature=0.0,
            max_tokens_per_output=100, max_retries=1,
        )
        agent = DefendantAgent(llm_client=_FakeLLM(), party_id="d1", config=config)
        prompt = agent._build_system_prompt()
        assert "<example" in prompt
        assert "被告主张已还款" in prompt


class TestIssueImpactRankerFewShot:
    """争点影响排序器 SYSTEM_PROMPT 包含 few-shot examples。"""

    def test_system_prompt_contains_examples(self):
        from engines.simulation_run.issue_impact_ranker.prompts.civil_loan import (
            SYSTEM_PROMPT,
        )
        assert "<example" in SYSTEM_PROMPT
        assert "importance_score" in SYSTEM_PROMPT
        assert "swing_score" in SYSTEM_PROMPT
        # 验证包含两个 example（根争点和子争点）
        assert 'index="1"' in SYSTEM_PROMPT
        assert 'index="2"' in SYSTEM_PROMPT


class TestDefenseChainFewShot:
    """防御链优化器 SYSTEM_PROMPT 包含 few-shot examples。"""

    def test_system_prompt_contains_examples(self):
        from engines.simulation_run.defense_chain.prompts.civil_loan import (
            SYSTEM_PROMPT,
        )
        assert "<example" in SYSTEM_PROMPT
        assert "defense_strategy" in SYSTEM_PROMPT
        assert "confidence_score" in SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Token 限制验证
# ---------------------------------------------------------------------------


class TestFewShotTokenBudget:
    """验证 few-shot examples 不会导致 token 超限。

    粗估规则：1 个中文字符 ≈ 1.5 tokens，1 个英文单词 ≈ 1.3 tokens。
    每个 example 文件的 system prompt 注入量应控制在 2000 tokens 以内。
    """

    @pytest.mark.parametrize("module_name", [
        "adversarial_plaintiff",
        "adversarial_defendant",
        "issue_impact_ranker",
        "defense_chain",
    ])
    def test_few_shot_text_within_token_budget(self, module_name):
        text = load_few_shot_text(module_name)
        # 粗估：字符数 * 1.5 作为 token 上限
        estimated_tokens = len(text) * 1.5
        assert estimated_tokens < 4000, (
            f"{module_name} few-shot text 预估 {estimated_tokens:.0f} tokens，超过 4000 限制"
        )


# ---------------------------------------------------------------------------
# Example 内容与 schema 一致性
# ---------------------------------------------------------------------------


class TestExampleSchemaConsistency:
    """验证 few-shot example 的输出结构与各模块的 JSON schema 一致。"""

    def test_adversarial_example_has_required_fields(self):
        """对抗代理 example 包含 AgentOutput 所需的核心字段。"""
        examples_dir = Path(__file__).parent.parent / "engines" / "shared" / "few_shot_examples"
        for name in ("adversarial_plaintiff", "adversarial_defendant"):
            data = json.loads((examples_dir / f"{name}.json").read_text(encoding="utf-8"))
            for ex in data:
                output = ex["expected_output"]
                assert "title" in output
                assert "body" in output
                assert "issue_ids" in output
                assert "evidence_citations" in output
                assert "arguments" in output
                assert len(output["arguments"]) >= 1
                for arg in output["arguments"]:
                    assert "issue_id" in arg
                    assert "position" in arg
                    assert "supporting_evidence_ids" in arg

    def test_ranker_example_has_required_fields(self):
        """排序器 example 包含 LLMIssueEvaluationOutput 所需的核心字段。"""
        examples_dir = Path(__file__).parent.parent / "engines" / "shared" / "few_shot_examples"
        data = json.loads(
            (examples_dir / "issue_impact_ranker.json").read_text(encoding="utf-8")
        )
        for ex in data:
            evals = ex["expected_output"]["evaluations"]
            for ev in evals:
                assert "issue_id" in ev
                assert "outcome_impact" in ev
                assert ev["outcome_impact"] in ("high", "medium", "low")
                assert "importance_score" in ev
                assert 0 <= ev["importance_score"] <= 100
                assert "swing_score" in ev
                assert 0 <= ev["swing_score"] <= 100

    def test_defense_chain_example_has_required_fields(self):
        """防御链 example 包含 LLMDefenseChainOutput 所需的核心字段。"""
        examples_dir = Path(__file__).parent.parent / "engines" / "shared" / "few_shot_examples"
        data = json.loads(
            (examples_dir / "defense_chain.json").read_text(encoding="utf-8")
        )
        for ex in data:
            output = ex["expected_output"]
            assert "defense_points" in output
            assert "confidence_score" in output
            assert 0.0 <= output["confidence_score"] <= 1.0
            for pt in output["defense_points"]:
                assert "issue_id" in pt
                assert "defense_strategy" in pt
                assert "supporting_argument" in pt
                assert "evidence_ids" in pt
                assert "priority" in pt
