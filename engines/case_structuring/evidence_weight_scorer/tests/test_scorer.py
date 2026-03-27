"""
EvidenceWeightScorer 单元测试。
Unit tests for EvidenceWeightScorer (P1.5).

测试策略：
- 不依赖真实 LLM；使用 stub LLM client 返回预定义 JSON
- 分层测试：枚举/模型字段 → schemas → prompts → 规则层逻辑 → 完整 score() 流程
- 覆盖所有合约保证（见 spec P1.5 约束及验收标准）
"""
from __future__ import annotations

import json
from typing import Optional

import pytest

from engines.shared.models import (
    AccessDomain,
    AuthenticityRisk,
    Evidence,
    EvidenceIndex,
    EvidenceStatus,
    EvidenceType,
    ProbativeValue,
    RelevanceScore,
    Vulnerability,
)


# ---------------------------------------------------------------------------
# Task 1: 枚举与 Evidence 模型字段测试
# ---------------------------------------------------------------------------


def test_authenticity_risk_enum_values():
    """AuthenticityRisk 枚举包含三个合法值。"""
    assert AuthenticityRisk.high.value == "high"
    assert AuthenticityRisk.medium.value == "medium"
    assert AuthenticityRisk.low.value == "low"


def test_relevance_score_enum_values():
    """RelevanceScore 枚举包含三个合法值。"""
    assert RelevanceScore.strong.value == "strong"
    assert RelevanceScore.medium.value == "medium"
    assert RelevanceScore.weak.value == "weak"


def test_probative_value_enum_values():
    """ProbativeValue 枚举包含三个合法值。"""
    assert ProbativeValue.strong.value == "strong"
    assert ProbativeValue.medium.value == "medium"
    assert ProbativeValue.weak.value == "weak"


def test_vulnerability_enum_values():
    """Vulnerability 枚举包含三个合法值。"""
    assert Vulnerability.high.value == "high"
    assert Vulnerability.medium.value == "medium"
    assert Vulnerability.low.value == "low"


def test_evidence_has_weight_fields():
    """Evidence 模型具备四个权重字段，默认均为 None；evidence_weight_scored 默认 False。"""
    ev = Evidence(
        evidence_id="ev-001",
        case_id="c-001",
        owner_party_id="p-001",
        title="test",
        source="src",
        summary="sum",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=["f-001"],
    )
    assert ev.authenticity_risk is None
    assert ev.relevance_score is None
    assert ev.probative_value is None
    assert ev.vulnerability is None
    assert ev.evidence_weight_scored is False


def test_evidence_weight_fields_accept_enum_values():
    """Evidence 的权重字段接受对应枚举值。"""
    ev = Evidence(
        evidence_id="ev-001",
        case_id="c-001",
        owner_party_id="p-001",
        title="test",
        source="src",
        summary="sum",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=["f-001"],
        authenticity_risk=AuthenticityRisk.low,
        relevance_score=RelevanceScore.strong,
        probative_value=ProbativeValue.strong,
        vulnerability=Vulnerability.medium,
        evidence_weight_scored=True,
    )
    assert ev.authenticity_risk == AuthenticityRisk.low
    assert ev.relevance_score == RelevanceScore.strong
    assert ev.probative_value == ProbativeValue.strong
    assert ev.vulnerability == Vulnerability.medium
    assert ev.evidence_weight_scored is True


# ---------------------------------------------------------------------------
# Task 2: schemas 测试
# ---------------------------------------------------------------------------

from engines.case_structuring.evidence_weight_scorer.schemas import (
    EvidenceWeightScorerInput,
    LLMEvidenceWeightItem,
    LLMEvidenceWeightOutput,
)


def test_scorer_input_requires_case_id_and_evidence_index():
    """EvidenceWeightScorerInput 需要 case_id、run_id 和 evidence_index。"""
    index = EvidenceIndex(case_id="c-001", evidence=[])
    inp = EvidenceWeightScorerInput(case_id="c-001", run_id="r-001", evidence_index=index)
    assert inp.case_id == "c-001"
    assert inp.run_id == "r-001"
    assert inp.evidence_index == index


def test_llm_item_defaults_to_empty_strings():
    """LLMEvidenceWeightItem 所有字段都有默认值（LLM 可能不输出完整字段）。"""
    item = LLMEvidenceWeightItem()
    assert item.evidence_id == ""
    assert item.authenticity_risk == ""
    assert item.relevance_score == ""
    assert item.probative_value == ""
    assert item.vulnerability == ""
    assert item.admissibility_notes is None


def test_llm_output_defaults_to_empty_list():
    """LLMEvidenceWeightOutput 默认 evidence_weights 为空列表。"""
    out = LLMEvidenceWeightOutput()
    assert out.evidence_weights == []


# ---------------------------------------------------------------------------
# Task 3: prompts 测试
# ---------------------------------------------------------------------------

from engines.case_structuring.evidence_weight_scorer.prompts import PROMPT_REGISTRY


def _make_evidence_index_for_prompt() -> EvidenceIndex:
    ev = Evidence(
        evidence_id="ev-001",
        case_id="c-001",
        owner_party_id="p-001",
        title="借款合同",
        source="合同原件",
        summary="载明借款金额10万元",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=["f-001"],
    )
    return EvidenceIndex(case_id="c-001", evidence=[ev])


def test_prompt_registry_has_civil_loan():
    """PROMPT_REGISTRY 包含 civil_loan 键及所需函数。"""
    assert "civil_loan" in PROMPT_REGISTRY
    assert "system" in PROMPT_REGISTRY["civil_loan"]
    assert "build_user" in PROMPT_REGISTRY["civil_loan"]


def test_system_prompt_mentions_four_dimensions():
    """system prompt 必须提到四个评分维度的字段名。"""
    system = PROMPT_REGISTRY["civil_loan"]["system"]
    assert "authenticity_risk" in system
    assert "relevance_score" in system
    assert "probative_value" in system
    assert "vulnerability" in system


def test_user_prompt_contains_evidence_id():
    """user prompt 包含待评分证据的 ID。"""
    build_user = PROMPT_REGISTRY["civil_loan"]["build_user"]
    prompt = build_user(evidence_index=_make_evidence_index_for_prompt())
    assert "ev-001" in prompt


def test_user_prompt_mentions_admissibility_notes():
    """user prompt 告知 LLM 高风险时须提供 admissibility_notes。"""
    build_user = PROMPT_REGISTRY["civil_loan"]["build_user"]
    prompt = build_user(evidence_index=_make_evidence_index_for_prompt())
    assert "admissibility_notes" in prompt


def test_user_prompt_contains_evidence_count():
    """user prompt 包含证据数量提示，供 LLM 校验输出数量。"""
    build_user = PROMPT_REGISTRY["civil_loan"]["build_user"]
    prompt = build_user(evidence_index=_make_evidence_index_for_prompt())
    assert "1" in prompt  # 1 条证据


# ---------------------------------------------------------------------------
# Task 4: scorer 主流程测试
# ---------------------------------------------------------------------------

from engines.case_structuring.evidence_weight_scorer.scorer import EvidenceWeightScorer


# --- Mock LLM 客户端 ---
class MockLLMClient:
    """返回预定义 JSON 响应的 mock LLM 客户端。"""

    def __init__(self, response: str, fail: bool = False) -> None:
        self._response = response
        self._fail = fail
        self.call_count = 0
        self.last_system: str | None = None
        self.last_user: str | None = None

    async def create_message(self, *, system: str, user: str, **kwargs) -> str:
        self.call_count += 1
        self.last_system = system
        self.last_user = user
        if self._fail:
            raise RuntimeError("模拟 LLM 调用失败")
        return self._response


# --- 测试辅助工厂 ---
def _make_evidence(
    evidence_id: str,
    admissibility_notes: Optional[str] = None,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        case_id="c-001",
        owner_party_id="p-001",
        title=f"证据 {evidence_id}",
        source="来源",
        summary="测试摘要",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=["f-001"],
        admissibility_notes=admissibility_notes,
    )


def _make_index(*evidence_ids: str) -> EvidenceIndex:
    return EvidenceIndex(
        case_id="c-001",
        evidence=[_make_evidence(eid) for eid in evidence_ids],
    )


def _make_input(*evidence_ids: str) -> EvidenceWeightScorerInput:
    return EvidenceWeightScorerInput(
        case_id="c-001",
        run_id="r-001",
        evidence_index=_make_index(*evidence_ids),
    )


def _llm_response(
    *evidence_ids: str,
    risk: str = "low",
    vuln: str = "low",
    notes: Optional[str] = None,
) -> str:
    """生成标准测试用 LLM 响应 JSON。"""
    return json.dumps({
        "evidence_weights": [
            {
                "evidence_id": eid,
                "authenticity_risk": risk,
                "relevance_score": "strong",
                "probative_value": "strong",
                "vulnerability": vuln,
                "admissibility_notes": notes,
            }
            for eid in evidence_ids
        ]
    }, ensure_ascii=False)


def _make_scorer(response: str, *, fail: bool = False) -> EvidenceWeightScorer:
    return EvidenceWeightScorer(
        llm_client=MockLLMClient(response, fail=fail),
        case_type="civil_loan",
        model="claude-test",
        temperature=0.0,
        max_retries=1,
    )


# ===========================================================================
# 合约测试：成功路径 — 四个字段被正确填充
# ===========================================================================


class TestSuccessfulScoring:
    """成功路径：四个权重字段正确填充。"""

    @pytest.mark.asyncio
    async def test_scored_evidence_has_all_four_fields(self):
        """成功评分后，evidence 的四个字段全部非 None。"""
        result = await _make_scorer(_llm_response("ev-001")).score(_make_input("ev-001"))
        ev = result.evidence[0]
        assert ev.authenticity_risk is not None
        assert ev.relevance_score is not None
        assert ev.probative_value is not None
        assert ev.vulnerability is not None

    @pytest.mark.asyncio
    async def test_evidence_weight_scored_flag_set_to_true(self):
        """成功评分后，evidence_weight_scored = True。"""
        result = await _make_scorer(_llm_response("ev-001")).score(_make_input("ev-001"))
        assert result.evidence[0].evidence_weight_scored is True

    @pytest.mark.asyncio
    async def test_correct_enum_values_assigned(self):
        """枚举值正确映射到 AuthenticityRisk 等类型。"""
        result = await _make_scorer(_llm_response("ev-001")).score(_make_input("ev-001"))
        ev = result.evidence[0]
        assert ev.authenticity_risk == AuthenticityRisk.low
        assert ev.relevance_score == RelevanceScore.strong
        assert ev.probative_value == ProbativeValue.strong
        assert ev.vulnerability == Vulnerability.low

    @pytest.mark.asyncio
    async def test_multiple_evidence_all_scored(self):
        """多条证据全部被评分。"""
        response = _llm_response("ev-001", "ev-002", "ev-003")
        result = await _make_scorer(response).score(_make_input("ev-001", "ev-002", "ev-003"))
        assert all(ev.evidence_weight_scored for ev in result.evidence)
        assert len(result.evidence) == 3

    @pytest.mark.asyncio
    async def test_original_fields_unchanged(self):
        """评分后原有字段（title, summary 等）不受影响。"""
        result = await _make_scorer(_llm_response("ev-001")).score(_make_input("ev-001"))
        ev = result.evidence[0]
        assert ev.title == "证据 ev-001"
        assert ev.case_id == "c-001"
        assert ev.owner_party_id == "p-001"

    @pytest.mark.asyncio
    async def test_case_id_preserved_in_output(self):
        """输出 EvidenceIndex 的 case_id 与输入一致。"""
        result = await _make_scorer(_llm_response("ev-001")).score(_make_input("ev-001"))
        assert result.case_id == "c-001"


# ===========================================================================
# 合约测试：admissibility_notes 强制要求
# ===========================================================================


class TestAdmissibilityNotesEnforcement:
    """规则层强制：高风险证据必须有 admissibility_notes。"""

    @pytest.mark.asyncio
    async def test_high_authenticity_risk_without_notes_skips_scoring(self):
        """authenticity_risk=high 但无 admissibility_notes → 不更新该条证据权重字段。"""
        response = json.dumps({"evidence_weights": [{
            "evidence_id": "ev-001",
            "authenticity_risk": "high",
            "relevance_score": "strong",
            "probative_value": "strong",
            "vulnerability": "low",
            "admissibility_notes": None,
        }]})
        result = await _make_scorer(response).score(_make_input("ev-001"))
        ev = result.evidence[0]
        assert ev.evidence_weight_scored is False
        assert ev.authenticity_risk is None

    @pytest.mark.asyncio
    async def test_high_vulnerability_without_notes_skips_scoring(self):
        """vulnerability=high 但无 admissibility_notes → 不更新该条证据权重字段。"""
        response = json.dumps({"evidence_weights": [{
            "evidence_id": "ev-001",
            "authenticity_risk": "low",
            "relevance_score": "strong",
            "probative_value": "medium",
            "vulnerability": "high",
            "admissibility_notes": None,
        }]})
        result = await _make_scorer(response).score(_make_input("ev-001"))
        ev = result.evidence[0]
        assert ev.evidence_weight_scored is False

    @pytest.mark.asyncio
    async def test_high_risk_with_notes_updates_successfully(self):
        """authenticity_risk=high 且有 admissibility_notes → 正常更新。"""
        response = json.dumps({"evidence_weights": [{
            "evidence_id": "ev-001",
            "authenticity_risk": "high",
            "relevance_score": "strong",
            "probative_value": "strong",
            "vulnerability": "low",
            "admissibility_notes": "仅有复印件，建议申请原件核实",
        }]})
        result = await _make_scorer(response).score(_make_input("ev-001"))
        ev = result.evidence[0]
        assert ev.evidence_weight_scored is True
        assert ev.authenticity_risk == AuthenticityRisk.high
        assert ev.admissibility_notes == "仅有复印件，建议申请原件核实"

    @pytest.mark.asyncio
    async def test_high_vulnerability_with_notes_updates_successfully(self):
        """vulnerability=high 且有 admissibility_notes → 正常更新。"""
        response = json.dumps({"evidence_weights": [{
            "evidence_id": "ev-001",
            "authenticity_risk": "low",
            "relevance_score": "medium",
            "probative_value": "weak",
            "vulnerability": "high",
            "admissibility_notes": "证人证言存在前后矛盾，对方可能申请证人出庭",
        }]})
        result = await _make_scorer(response).score(_make_input("ev-001"))
        ev = result.evidence[0]
        assert ev.evidence_weight_scored is True
        assert ev.vulnerability == Vulnerability.high

    @pytest.mark.asyncio
    async def test_low_risk_without_notes_updates_successfully(self):
        """低风险时 admissibility_notes 为 None 也正常更新。"""
        result = await _make_scorer(_llm_response("ev-001")).score(_make_input("ev-001"))
        ev = result.evidence[0]
        assert ev.evidence_weight_scored is True

    @pytest.mark.asyncio
    async def test_both_high_with_notes_updates_successfully(self):
        """authenticity_risk=high 且 vulnerability=high，有 notes → 正常更新。"""
        response = json.dumps({"evidence_weights": [{
            "evidence_id": "ev-001",
            "authenticity_risk": "high",
            "relevance_score": "weak",
            "probative_value": "weak",
            "vulnerability": "high",
            "admissibility_notes": "存在多处矛盾，需进一步核实",
        }]})
        result = await _make_scorer(response).score(_make_input("ev-001"))
        ev = result.evidence[0]
        assert ev.evidence_weight_scored is True
        assert ev.authenticity_risk == AuthenticityRisk.high
        assert ev.vulnerability == Vulnerability.high

    @pytest.mark.asyncio
    async def test_admissibility_notes_from_llm_stored_on_evidence(self):
        """LLM 提供的 admissibility_notes 写入 Evidence.admissibility_notes 字段。"""
        notes = "此证据为复印件，请申请原件"
        response = json.dumps({"evidence_weights": [{
            "evidence_id": "ev-001",
            "authenticity_risk": "high",
            "relevance_score": "strong",
            "probative_value": "medium",
            "vulnerability": "low",
            "admissibility_notes": notes,
        }]})
        result = await _make_scorer(response).score(_make_input("ev-001"))
        assert result.evidence[0].admissibility_notes == notes


# ===========================================================================
# 合约测试：规则层过滤 — 无效枚举值
# ===========================================================================


class TestInvalidEnumFiltering:
    """规则层零容忍：非法枚举值的证据被跳过。"""

    @pytest.mark.asyncio
    async def test_invalid_authenticity_risk_skips_evidence(self):
        """非法 authenticity_risk 值（自由文本）的证据被跳过。"""
        response = json.dumps({"evidence_weights": [{
            "evidence_id": "ev-001",
            "authenticity_risk": "非常可疑",  # 非法枚举
            "relevance_score": "strong",
            "probative_value": "strong",
            "vulnerability": "low",
            "admissibility_notes": None,
        }]})
        result = await _make_scorer(response).score(_make_input("ev-001"))
        assert result.evidence[0].evidence_weight_scored is False

    @pytest.mark.asyncio
    async def test_invalid_relevance_score_skips_evidence(self):
        """非法 relevance_score 值的证据被跳过。"""
        response = json.dumps({"evidence_weights": [{
            "evidence_id": "ev-001",
            "authenticity_risk": "low",
            "relevance_score": "very_strong",  # 非法枚举
            "probative_value": "strong",
            "vulnerability": "low",
            "admissibility_notes": None,
        }]})
        result = await _make_scorer(response).score(_make_input("ev-001"))
        assert result.evidence[0].evidence_weight_scored is False

    @pytest.mark.asyncio
    async def test_empty_enum_string_skips_evidence(self):
        """空字符串枚举值的证据被跳过。"""
        response = json.dumps({"evidence_weights": [{
            "evidence_id": "ev-001",
            "authenticity_risk": "",  # 空值
            "relevance_score": "strong",
            "probative_value": "strong",
            "vulnerability": "low",
            "admissibility_notes": None,
        }]})
        result = await _make_scorer(response).score(_make_input("ev-001"))
        assert result.evidence[0].evidence_weight_scored is False

    @pytest.mark.asyncio
    async def test_high_risk_with_empty_string_notes_skips_scoring(self):
        """authenticity_risk=high 且 admissibility_notes 为空字符串（非 None）→ 同样被跳过。"""
        response = json.dumps({"evidence_weights": [{
            "evidence_id": "ev-001",
            "authenticity_risk": "high",
            "relevance_score": "strong",
            "probative_value": "strong",
            "vulnerability": "low",
            "admissibility_notes": "",  # 空字符串，等同于缺失
        }]})
        result = await _make_scorer(response).score(_make_input("ev-001"))
        assert result.evidence[0].evidence_weight_scored is False

    @pytest.mark.asyncio
    async def test_duplicate_evidence_id_in_llm_output_last_wins(self):
        """LLM 输出重复 evidence_id 时，最后一条覆盖前一条（last wins）。"""
        response = json.dumps({"evidence_weights": [
            {
                "evidence_id": "ev-001",
                "authenticity_risk": "high",
                "relevance_score": "strong",
                "probative_value": "strong",
                "vulnerability": "low",
                "admissibility_notes": "第一条（应被覆盖）",
            },
            {
                "evidence_id": "ev-001",  # 重复 ID，最后一条覆盖
                "authenticity_risk": "low",
                "relevance_score": "medium",
                "probative_value": "medium",
                "vulnerability": "low",
                "admissibility_notes": None,
            },
        ]})
        result = await _make_scorer(response).score(_make_input("ev-001"))
        ev = result.evidence[0]
        # 最后一条（low risk）覆盖第一条（high risk）
        assert ev.evidence_weight_scored is True
        assert ev.authenticity_risk == AuthenticityRisk.low

    @pytest.mark.asyncio
    async def test_unknown_evidence_id_in_llm_output_ignored(self):
        """LLM 输出了未知 evidence_id → 该条被忽略，已知证据正常处理。"""
        response = json.dumps({"evidence_weights": [
            {
                "evidence_id": "ev-GHOST",  # 不存在
                "authenticity_risk": "low",
                "relevance_score": "strong",
                "probative_value": "strong",
                "vulnerability": "low",
                "admissibility_notes": None,
            },
            {
                "evidence_id": "ev-001",  # 存在
                "authenticity_risk": "low",
                "relevance_score": "strong",
                "probative_value": "strong",
                "vulnerability": "low",
                "admissibility_notes": None,
            },
        ]})
        result = await _make_scorer(response).score(_make_input("ev-001"))
        assert result.evidence[0].evidence_weight_scored is True


# ===========================================================================
# 合约测试：LLM 失败降级
# ===========================================================================


class TestLLMFailureHandling:
    """LLM 失败时：返回原始 EvidenceIndex，不抛异常。"""

    @pytest.mark.asyncio
    async def test_llm_failure_returns_original_index_unchanged(self):
        """LLM 抛出异常时返回原始 EvidenceIndex，不抛异常。"""
        result = await _make_scorer("", fail=True).score(_make_input("ev-001"))
        assert result.evidence[0].evidence_weight_scored is False
        assert result.evidence[0].authenticity_risk is None

    @pytest.mark.asyncio
    async def test_llm_invalid_json_returns_original_index(self):
        """LLM 返回非法 JSON 时返回原始 EvidenceIndex。"""
        result = await _make_scorer("这不是 JSON").score(_make_input("ev-001"))
        assert result.evidence[0].evidence_weight_scored is False

    @pytest.mark.asyncio
    async def test_llm_failure_retries_then_returns_original(self):
        """max_retries=2 时 LLM 连续失败 3 次（1 次初始 + 2 次重试）后返回原始索引。"""
        mock = MockLLMClient("", fail=True)
        scorer = EvidenceWeightScorer(
            llm_client=mock,
            case_type="civil_loan",
            model="claude-test",
            temperature=0.0,
            max_retries=2,
        )
        result = await scorer.score(_make_input("ev-001"))
        assert result.evidence[0].evidence_weight_scored is False
        assert mock.call_count == 3  # 1 初始 + 2 重试

    @pytest.mark.asyncio
    async def test_empty_evidence_list_no_llm_call(self):
        """空证据列表时不调用 LLM，直接返回空 EvidenceIndex。"""
        inp = EvidenceWeightScorerInput(
            case_id="c-001",
            run_id="r-001",
            evidence_index=EvidenceIndex(case_id="c-001", evidence=[]),
        )
        mock = MockLLMClient(_llm_response())
        scorer = EvidenceWeightScorer(
            llm_client=mock,
            case_type="civil_loan",
            model="claude-test",
            temperature=0.0,
            max_retries=0,
        )
        result = await scorer.score(inp)
        assert result.evidence == []
        assert mock.call_count == 0

    @pytest.mark.asyncio
    async def test_llm_empty_response_returns_original(self):
        """LLM 返回空字符串时返回原始 EvidenceIndex。"""
        result = await _make_scorer("").score(_make_input("ev-001"))
        assert result.evidence[0].evidence_weight_scored is False


# ===========================================================================
# 合约测试：混合有效/无效条目
# ===========================================================================


class TestMixedValidInvalid:
    """混合有效/无效条目时，只有有效的被标记 scored=True。"""

    @pytest.mark.asyncio
    async def test_partial_success_only_valid_evidence_scored(self):
        """部分证据有效、部分枚举非法时，只有有效的被标记 scored=True。"""
        response = json.dumps({"evidence_weights": [
            {
                "evidence_id": "ev-001",
                "authenticity_risk": "low",
                "relevance_score": "strong",
                "probative_value": "strong",
                "vulnerability": "low",
                "admissibility_notes": None,
            },  # 有效
            {
                "evidence_id": "ev-002",
                "authenticity_risk": "高风险",  # 非法枚举
                "relevance_score": "strong",
                "probative_value": "strong",
                "vulnerability": "low",
                "admissibility_notes": None,
            },  # 非法枚举 → 跳过
        ]})
        result = await _make_scorer(response).score(_make_input("ev-001", "ev-002"))
        ev1 = next(e for e in result.evidence if e.evidence_id == "ev-001")
        ev2 = next(e for e in result.evidence if e.evidence_id == "ev-002")
        assert ev1.evidence_weight_scored is True
        assert ev2.evidence_weight_scored is False

    @pytest.mark.asyncio
    async def test_one_high_risk_missing_notes_one_valid(self):
        """一条高风险缺 notes（跳过），一条正常（更新）。"""
        response = json.dumps({"evidence_weights": [
            {
                "evidence_id": "ev-001",
                "authenticity_risk": "high",
                "relevance_score": "strong",
                "probative_value": "strong",
                "vulnerability": "low",
                "admissibility_notes": None,  # 缺失 → 跳过
            },
            {
                "evidence_id": "ev-002",
                "authenticity_risk": "low",
                "relevance_score": "medium",
                "probative_value": "medium",
                "vulnerability": "low",
                "admissibility_notes": None,  # 低风险，无需 notes
            },
        ]})
        result = await _make_scorer(response).score(_make_input("ev-001", "ev-002"))
        ev1 = next(e for e in result.evidence if e.evidence_id == "ev-001")
        ev2 = next(e for e in result.evidence if e.evidence_id == "ev-002")
        assert ev1.evidence_weight_scored is False
        assert ev2.evidence_weight_scored is True


# ===========================================================================
# 合约测试：构造校验
# ===========================================================================


class TestConstructorValidation:
    """构造时校验案件类型。"""

    def test_unsupported_case_type_raises(self):
        """不支持的案件类型在构造时抛出 ValueError。"""
        with pytest.raises(ValueError, match="不支持的案件类型"):
            EvidenceWeightScorer(
                llm_client=MockLLMClient(""),
                case_type="unsupported_type",
                model="claude-test",
                temperature=0.0,
                max_retries=0,
            )

    def test_civil_loan_case_type_accepted(self):
        """civil_loan 案件类型正常构造，不抛异常。"""
        scorer = EvidenceWeightScorer(
            llm_client=MockLLMClient(""),
            case_type="civil_loan",
            model="claude-test",
            temperature=0.0,
            max_retries=0,
        )
        assert scorer is not None


# ===========================================================================
# 合约测试：prompt 内容
# ===========================================================================


class TestPromptContent:
    """prompt 内容测试——确认关键信息传入 LLM。"""

    @pytest.mark.asyncio
    async def test_prompt_contains_evidence_ids(self):
        """user prompt 包含待评分的证据 ID。"""
        mock = MockLLMClient(_llm_response("ev-999"))
        scorer = EvidenceWeightScorer(
            llm_client=mock,
            case_type="civil_loan",
            model="claude-test",
            temperature=0.0,
            max_retries=0,
        )
        await scorer.score(_make_input("ev-999"))
        assert "ev-999" in mock.last_user

    @pytest.mark.asyncio
    async def test_system_prompt_passed_to_llm(self):
        """system prompt 非空并传递给 LLM。"""
        mock = MockLLMClient(_llm_response("ev-001"))
        scorer = EvidenceWeightScorer(
            llm_client=mock,
            case_type="civil_loan",
            model="claude-test",
            temperature=0.0,
            max_retries=0,
        )
        await scorer.score(_make_input("ev-001"))
        assert mock.last_system  # 非空
        assert "authenticity_risk" in mock.last_system
