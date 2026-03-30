"""
AdmissibilityEvaluator 单元测试。
Unit tests for AdmissibilityEvaluator and simulate_exclusion.

测试策略：
- 不依赖真实 LLM；使用 stub LLM client 返回预定义 JSON
- 分层测试：模型字段 → schemas → prompts → 规则层逻辑 → 完整 evaluate() 流程 → simulate_exclusion
- 覆盖所有合约保证（见 evaluator.py 顶部 docstring）
"""
from __future__ import annotations

import json
from typing import Optional

import pytest

from engines.shared.models import (
    AccessDomain,
    AttackNode,
    BlockingCondition,
    BlockingConditionType,
    ConfidenceInterval,
    DecisionPath,
    DecisionPathTree,
    Evidence,
    EvidenceIndex,
    EvidenceStatus,
    EvidenceType,
    Issue,
    IssueStatus,
    IssueTree,
    IssueType,
    OptimalAttackChain,
)


# ---------------------------------------------------------------------------
# Task 1: Evidence 模型新字段测试
# ---------------------------------------------------------------------------


def test_evidence_has_admissibility_score_default():
    """Evidence 新增 admissibility_score 字段，默认 1.0。"""
    ev = _make_evidence("ev-001")
    assert ev.admissibility_score == 1.0


def test_evidence_has_admissibility_challenges_default():
    """Evidence 新增 admissibility_challenges 字段，默认空列表。"""
    ev = _make_evidence("ev-001")
    assert ev.admissibility_challenges == []


def test_evidence_has_exclusion_impact_default():
    """Evidence 新增 exclusion_impact 字段，默认 None。"""
    ev = _make_evidence("ev-001")
    assert ev.exclusion_impact is None


def test_evidence_admissibility_score_accepts_valid_range():
    """admissibility_score 接受 [0.0, 1.0] 之间的值。"""
    ev = _make_evidence("ev-001")
    ev2 = ev.model_copy(update={"admissibility_score": 0.0})
    ev3 = ev.model_copy(update={"admissibility_score": 0.5})
    assert ev2.admissibility_score == 0.0
    assert ev3.admissibility_score == 0.5


def test_evidence_admissibility_score_rejects_out_of_range():
    """admissibility_score 超出 [0.0, 1.0] 时 Pydantic 拒绝。"""
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        Evidence(
            evidence_id="ev-001",
            case_id="c-001",
            owner_party_id="p-001",
            title="test",
            source="src",
            summary="sum",
            evidence_type=EvidenceType.documentary,
            target_fact_ids=["f-001"],
            admissibility_score=1.5,  # 越界，应拒绝
        )


def test_evidence_admissibility_challenges_accepts_list():
    """admissibility_challenges 接受字符串列表。"""
    ev = _make_evidence("ev-001")
    ev2 = ev.model_copy(update={"admissibility_challenges": ["录音合法性存疑", "无公证"]})
    assert len(ev2.admissibility_challenges) == 2


# ---------------------------------------------------------------------------
# Task 2: schemas 测试
# ---------------------------------------------------------------------------

from engines.case_structuring.admissibility_evaluator.schemas import (
    AdmissibilityEvaluatorInput,
    ImpactReport,
    IssueImpact,
    LLMAdmissibilityItem,
    LLMAdmissibilityOutput,
    PathImpact,
    ChainImpact,
)


def test_evaluator_input_requires_case_id_and_evidence_index():
    """AdmissibilityEvaluatorInput 需要 case_id、run_id 和 evidence_index。"""
    index = EvidenceIndex(case_id="c-001", evidence=[])
    inp = AdmissibilityEvaluatorInput(case_id="c-001", run_id="r-001", evidence_index=index)
    assert inp.case_id == "c-001"
    assert inp.run_id == "r-001"


def test_llm_item_defaults():
    """LLMAdmissibilityItem 字段默认值正确。"""
    item = LLMAdmissibilityItem()
    assert item.evidence_id == ""
    assert item.admissibility_score == 1.0
    assert item.admissibility_challenges == []
    assert item.exclusion_impact is None


def test_llm_output_defaults():
    """LLMAdmissibilityOutput 默认 evidence_assessments 为空列表。"""
    out = LLMAdmissibilityOutput()
    assert out.evidence_assessments == []


def test_impact_report_fields():
    """ImpactReport 包含所有预期字段。"""
    report = ImpactReport(excluded_evidence_id="ev-001", case_id="c-001")
    assert report.excluded_evidence_id == "ev-001"
    assert report.case_id == "c-001"
    assert report.affected_issues == []
    assert report.affected_paths == []
    assert report.affected_chains == []
    assert report.overall_severity == "negligible"
    assert report.summary == ""


def test_issue_impact_defaults():
    """IssueImpact 默认值正确。"""
    ii = IssueImpact(issue_id="i-001")
    assert ii.loses_primary_evidence is False
    assert ii.remaining_evidence_ids == []
    assert ii.impact_severity == "negligible"


def test_path_impact_defaults():
    """PathImpact 默认值正确。"""
    pi = PathImpact(path_id="p-001")
    assert pi.becomes_nonviable is False
    assert pi.impact_description == ""


def test_chain_impact_defaults():
    """ChainImpact 默认值正确。"""
    ci = ChainImpact(chain_id="ch-001")
    assert ci.broken_attack_node_ids == []
    assert ci.owner_party_id == ""


# ---------------------------------------------------------------------------
# Task 3: prompts 测试
# ---------------------------------------------------------------------------

from engines.case_structuring.admissibility_evaluator.prompts import PROMPT_REGISTRY


def _make_evidence_index_for_prompt() -> EvidenceIndex:
    ev = Evidence(
        evidence_id="ev-001",
        case_id="c-001",
        owner_party_id="p-001",
        title="借款录音",
        source="手机录音",
        summary="被告口头承诺还款的录音",
        evidence_type=EvidenceType.audio_visual,
        target_fact_ids=["f-001"],
    )
    return EvidenceIndex(case_id="c-001", evidence=[ev])


def test_prompt_registry_has_civil_loan():
    """PROMPT_REGISTRY 包含 civil_loan 键及所需函数。"""
    assert "civil_loan" in PROMPT_REGISTRY
    assert "system" in PROMPT_REGISTRY["civil_loan"]
    assert "build_user" in PROMPT_REGISTRY["civil_loan"]


def test_system_prompt_mentions_key_concepts():
    """system prompt 提及可采性评分、质疑理由等关键概念。"""
    system = PROMPT_REGISTRY["civil_loan"]["system"]
    assert "admissibility_score" in system
    assert "admissibility_challenges" in system
    assert "exclusion_impact" in system


def test_system_prompt_mentions_audio_visual():
    """system prompt 特别提及录音/录屏证据的审查要点。"""
    system = PROMPT_REGISTRY["civil_loan"]["system"]
    assert "audio_visual" in system


def test_user_prompt_contains_evidence_id():
    """user prompt 包含待评估证据的 ID。"""
    build_user = PROMPT_REGISTRY["civil_loan"]["build_user"]
    prompt = build_user(evidence_index=_make_evidence_index_for_prompt())
    assert "ev-001" in prompt


def test_user_prompt_marks_audio_visual():
    """user prompt 对录音/录屏证据有特殊标注。"""
    build_user = PROMPT_REGISTRY["civil_loan"]["build_user"]
    prompt = build_user(evidence_index=_make_evidence_index_for_prompt())
    assert "录音" in prompt or "audio_visual" in prompt


def test_user_prompt_contains_evidence_count():
    """user prompt 包含证据数量提示。"""
    build_user = PROMPT_REGISTRY["civil_loan"]["build_user"]
    prompt = build_user(evidence_index=_make_evidence_index_for_prompt())
    assert "1" in prompt


# ---------------------------------------------------------------------------
# Task 4: AdmissibilityEvaluator 主流程测试
# ---------------------------------------------------------------------------

from engines.case_structuring.admissibility_evaluator.evaluator import AdmissibilityEvaluator


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


def _make_evidence(
    evidence_id: str,
    evidence_type: EvidenceType = EvidenceType.documentary,
    target_issue_ids: Optional[list[str]] = None,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        case_id="c-001",
        owner_party_id="p-001",
        title=f"证据 {evidence_id}",
        source="来源",
        summary="测试摘要",
        evidence_type=evidence_type,
        target_fact_ids=["f-001"],
        target_issue_ids=target_issue_ids or [],
    )


def _make_index(*evidence_ids: str, **kwargs) -> EvidenceIndex:
    return EvidenceIndex(
        case_id="c-001",
        evidence=[_make_evidence(eid, **kwargs) for eid in evidence_ids],
    )


def _make_input(*evidence_ids: str) -> AdmissibilityEvaluatorInput:
    return AdmissibilityEvaluatorInput(
        case_id="c-001",
        run_id="r-001",
        evidence_index=_make_index(*evidence_ids),
    )


def _llm_response(
    *evidence_ids: str,
    score: float = 0.9,
    challenges: Optional[list[str]] = None,
    exclusion_impact: Optional[str] = None,
) -> str:
    return json.dumps({
        "evidence_assessments": [
            {
                "evidence_id": eid,
                "admissibility_score": score,
                "admissibility_challenges": challenges or [],
                "exclusion_impact": exclusion_impact,
            }
            for eid in evidence_ids
        ]
    }, ensure_ascii=False)


def _make_evaluator(response: str, *, fail: bool = False) -> AdmissibilityEvaluator:
    return AdmissibilityEvaluator(
        llm_client=MockLLMClient(response, fail=fail),
        case_type="civil_loan",
        model="claude-test",
        temperature=0.0,
        max_retries=1,
    )


class TestSuccessfulEvaluation:
    """成功路径：三个可采性字段正确填充。"""

    @pytest.mark.asyncio
    async def test_admissibility_score_updated(self):
        """评估后，admissibility_score 被更新。"""
        result = await _make_evaluator(_llm_response("ev-001", score=0.7)).evaluate(
            _make_input("ev-001")
        )
        assert result.evidence[0].admissibility_score == 0.7

    @pytest.mark.asyncio
    async def test_admissibility_challenges_updated(self):
        """评估后，admissibility_challenges 被更新。"""
        result = await _make_evaluator(
            _llm_response("ev-001", score=0.3, challenges=["录音非法", "无公证"])
        ).evaluate(_make_input("ev-001"))
        assert result.evidence[0].admissibility_challenges == ["录音非法", "无公证"]

    @pytest.mark.asyncio
    async def test_exclusion_impact_updated(self):
        """评估后，exclusion_impact 被更新。"""
        result = await _make_evaluator(
            _llm_response("ev-001", exclusion_impact="失去关键证据")
        ).evaluate(_make_input("ev-001"))
        assert result.evidence[0].exclusion_impact == "失去关键证据"

    @pytest.mark.asyncio
    async def test_original_fields_unchanged(self):
        """评估后，原有字段（title, summary 等）不受影响。"""
        result = await _make_evaluator(_llm_response("ev-001")).evaluate(_make_input("ev-001"))
        ev = result.evidence[0]
        assert ev.title == "证据 ev-001"
        assert ev.case_id == "c-001"

    @pytest.mark.asyncio
    async def test_score_rounded_to_two_decimals(self):
        """admissibility_score 被四舍五入到两位小数。"""
        raw_resp = json.dumps({
            "evidence_assessments": [{
                "evidence_id": "ev-001",
                "admissibility_score": 0.8333333,
                "admissibility_challenges": [],
                "exclusion_impact": None,
            }]
        })
        result = await _make_evaluator(raw_resp).evaluate(_make_input("ev-001"))
        assert result.evidence[0].admissibility_score == 0.83

    @pytest.mark.asyncio
    async def test_multiple_evidence_all_evaluated(self):
        """多条证据全部被评估。"""
        response = _llm_response("ev-001", "ev-002", "ev-003", score=0.8)
        result = await _make_evaluator(response).evaluate(
            _make_input("ev-001", "ev-002", "ev-003")
        )
        assert all(ev.admissibility_score == 0.8 for ev in result.evidence)
        assert len(result.evidence) == 3

    @pytest.mark.asyncio
    async def test_case_id_preserved(self):
        """输出 EvidenceIndex 的 case_id 与输入一致。"""
        result = await _make_evaluator(_llm_response("ev-001")).evaluate(_make_input("ev-001"))
        assert result.case_id == "c-001"


class TestLowScoreEnforcement:
    """规则层强制：低分证据必须有 admissibility_challenges。"""

    @pytest.mark.asyncio
    async def test_low_score_without_challenges_skips(self):
        """admissibility_score < 0.5 但无 challenges → 跳过（保持默认值）。"""
        response = json.dumps({
            "evidence_assessments": [{
                "evidence_id": "ev-001",
                "admissibility_score": 0.3,
                "admissibility_challenges": [],
                "exclusion_impact": None,
            }]
        })
        result = await _make_evaluator(response).evaluate(_make_input("ev-001"))
        assert result.evidence[0].admissibility_score == 1.0  # 默认值，未更新

    @pytest.mark.asyncio
    async def test_low_score_with_challenges_accepted(self):
        """admissibility_score < 0.5 且有 challenges → 正常更新。"""
        result = await _make_evaluator(
            _llm_response("ev-001", score=0.2, challenges=["录音非法"])
        ).evaluate(_make_input("ev-001"))
        assert result.evidence[0].admissibility_score == 0.2
        assert result.evidence[0].admissibility_challenges == ["录音非法"]

    @pytest.mark.asyncio
    async def test_score_exactly_05_without_challenges_accepted(self):
        """admissibility_score = 0.5（临界值，不触发强制）时无 challenges 也可接受。"""
        result = await _make_evaluator(
            _llm_response("ev-001", score=0.5)
        ).evaluate(_make_input("ev-001"))
        assert result.evidence[0].admissibility_score == 0.5

    @pytest.mark.asyncio
    async def test_low_score_blank_challenges_skips(self):
        """challenges 全为空白字符串视为空，也被跳过。"""
        response = json.dumps({
            "evidence_assessments": [{
                "evidence_id": "ev-001",
                "admissibility_score": 0.1,
                "admissibility_challenges": ["  ", ""],
                "exclusion_impact": None,
            }]
        })
        result = await _make_evaluator(response).evaluate(_make_input("ev-001"))
        assert result.evidence[0].admissibility_score == 1.0


class TestScoreRangeValidation:
    """规则层：score 越界时跳过。"""

    @pytest.mark.asyncio
    async def test_score_above_one_skips(self):
        """score > 1.0 → 跳过。"""
        response = json.dumps({
            "evidence_assessments": [{
                "evidence_id": "ev-001",
                "admissibility_score": 1.5,
                "admissibility_challenges": [],
                "exclusion_impact": None,
            }]
        })
        result = await _make_evaluator(response).evaluate(_make_input("ev-001"))
        assert result.evidence[0].admissibility_score == 1.0

    @pytest.mark.asyncio
    async def test_score_below_zero_skips(self):
        """score < 0.0 → 跳过。"""
        response = json.dumps({
            "evidence_assessments": [{
                "evidence_id": "ev-001",
                "admissibility_score": -0.1,
                "admissibility_challenges": [],
                "exclusion_impact": None,
            }]
        })
        result = await _make_evaluator(response).evaluate(_make_input("ev-001"))
        assert result.evidence[0].admissibility_score == 1.0

    @pytest.mark.asyncio
    async def test_unknown_evidence_id_ignored(self):
        """LLM 输出了未知 evidence_id → 忽略，已知证据正常处理。"""
        response = _llm_response("ev-GHOST", "ev-001", score=0.8)
        result = await _make_evaluator(response).evaluate(_make_input("ev-001"))
        assert result.evidence[0].admissibility_score == 0.8


class TestLLMFailureHandling:
    """LLM 失败时：返回原始 EvidenceIndex，不抛异常。"""

    @pytest.mark.asyncio
    async def test_llm_failure_returns_original_unchanged(self):
        """LLM 抛出异常时返回原始 EvidenceIndex。"""
        result = await _make_evaluator("", fail=True).evaluate(_make_input("ev-001"))
        assert result.evidence[0].admissibility_score == 1.0
        assert result.evidence[0].admissibility_challenges == []

    @pytest.mark.asyncio
    async def test_llm_invalid_json_returns_original(self):
        """LLM 返回非法 JSON 时返回原始 EvidenceIndex。"""
        result = await _make_evaluator("这不是 JSON").evaluate(_make_input("ev-001"))
        assert result.evidence[0].admissibility_score == 1.0

    @pytest.mark.asyncio
    async def test_empty_evidence_list_no_llm_call(self):
        """空证据列表时不调用 LLM。"""
        inp = AdmissibilityEvaluatorInput(
            case_id="c-001",
            run_id="r-001",
            evidence_index=EvidenceIndex(case_id="c-001", evidence=[]),
        )
        mock = MockLLMClient(_llm_response())
        evaluator = AdmissibilityEvaluator(
            llm_client=mock,
            case_type="civil_loan",
            model="claude-test",
            temperature=0.0,
            max_retries=0,
        )
        result = await evaluator.evaluate(inp)
        assert result.evidence == []
        assert mock.call_count == 0

    @pytest.mark.asyncio
    async def test_llm_failure_retries(self):
        """max_retries=2 时 LLM 连续失败后返回原始索引，call_count=3。"""
        mock = MockLLMClient("", fail=True)
        evaluator = AdmissibilityEvaluator(
            llm_client=mock,
            case_type="civil_loan",
            model="claude-test",
            temperature=0.0,
            max_retries=2,
        )
        result = await evaluator.evaluate(_make_input("ev-001"))
        assert result.evidence[0].admissibility_score == 1.0
        assert mock.call_count == 3


class TestConstructorValidation:
    """构造时校验案件类型。"""

    def test_unsupported_case_type_raises(self):
        """不支持的案件类型在构造时抛出 ValueError。"""
        with pytest.raises(ValueError, match="不支持的案件类型"):
            AdmissibilityEvaluator(
                llm_client=MockLLMClient(""),
                case_type="criminal",
                model="claude-test",
                temperature=0.0,
                max_retries=0,
            )

    def test_civil_loan_case_type_accepted(self):
        """civil_loan 案件类型正常构造。"""
        ev = AdmissibilityEvaluator(
            llm_client=MockLLMClient(""),
            case_type="civil_loan",
            model="claude-test",
            temperature=0.0,
            max_retries=0,
        )
        assert ev is not None


class TestPromptContent:
    """prompt 内容测试——确认关键信息传入 LLM。"""

    @pytest.mark.asyncio
    async def test_prompt_contains_evidence_ids(self):
        """user prompt 包含待评估的证据 ID。"""
        mock = MockLLMClient(_llm_response("ev-999", score=0.8))
        evaluator = AdmissibilityEvaluator(
            llm_client=mock,
            case_type="civil_loan",
            model="claude-test",
            temperature=0.0,
            max_retries=0,
        )
        await evaluator.evaluate(_make_input("ev-999"))
        assert "ev-999" in mock.last_user

    @pytest.mark.asyncio
    async def test_system_prompt_passed_to_llm(self):
        """system prompt 非空并传递给 LLM。"""
        mock = MockLLMClient(_llm_response("ev-001", score=0.9))
        evaluator = AdmissibilityEvaluator(
            llm_client=mock,
            case_type="civil_loan",
            model="claude-test",
            temperature=0.0,
            max_retries=0,
        )
        await evaluator.evaluate(_make_input("ev-001"))
        assert mock.last_system
        assert "admissibility_score" in mock.last_system


# ---------------------------------------------------------------------------
# Task 5: simulate_exclusion 测试
# ---------------------------------------------------------------------------

from engines.case_structuring.admissibility_evaluator.propagation import simulate_exclusion


def _make_issue_tree(
    issue_id: str = "i-001",
    evidence_ids: Optional[list[str]] = None,
) -> IssueTree:
    issue = Issue(
        issue_id=issue_id,
        case_id="c-001",
        title=f"争点 {issue_id}",
        issue_type=IssueType.factual,
        status=IssueStatus.open,
        evidence_ids=evidence_ids or [],
    )
    return IssueTree(case_id="c-001", issues=[issue])


def _make_decision_path_tree(
    path_id: str = "path-001",
    admissibility_gate: Optional[list[str]] = None,
    key_evidence_ids: Optional[list[str]] = None,
    fallback_path_id: Optional[str] = None,
) -> DecisionPathTree:
    path = DecisionPath(
        path_id=path_id,
        trigger_condition="测试触发条件",
        possible_outcome="测试结果",
        admissibility_gate=admissibility_gate or [],
        key_evidence_ids=key_evidence_ids or [],
        fallback_path_id=fallback_path_id,
    )
    return DecisionPathTree(
        tree_id="tree-001",
        case_id="c-001",
        run_id="r-001",
        paths=[path],
    )


def _make_attack_chain(
    chain_id: str = "chain-001",
    supporting_evidence_ids: Optional[list[str]] = None,
) -> OptimalAttackChain:
    node = AttackNode(
        attack_node_id="node-001",
        target_issue_id="i-001",
        attack_description="测试攻击点",
        supporting_evidence_ids=supporting_evidence_ids or ["ev-001"],
    )
    return OptimalAttackChain(
        chain_id=chain_id,
        case_id="c-001",
        run_id="r-001",
        owner_party_id="plaintiff",
        top_attacks=[node],
        recommended_order=["node-001"],
    )


class TestSimulateExclusion:
    """simulate_exclusion 规则层测试。"""

    def test_unknown_evidence_id_returns_empty_report(self):
        """不存在的证据 ID 返回空报告。"""
        index = _make_index("ev-001")
        report = simulate_exclusion("ev-GHOST", index)
        assert report.overall_severity == "negligible"
        assert report.affected_issues == []
        assert report.affected_paths == []
        assert report.affected_chains == []

    def test_no_artifacts_returns_negligible(self):
        """无争点树、路径树、攻击链时，整体影响为 negligible。"""
        index = _make_index("ev-001")
        report = simulate_exclusion("ev-001", index)
        assert report.overall_severity == "negligible"

    def test_issue_with_single_evidence_is_case_breaking(self):
        """争点仅有该证据时，排除后 severity=case_breaking。"""
        index = _make_index("ev-001")
        issue_tree = _make_issue_tree("i-001", evidence_ids=["ev-001"])
        report = simulate_exclusion("ev-001", index, issue_tree=issue_tree)
        assert len(report.affected_issues) == 1
        ii = report.affected_issues[0]
        assert ii.loses_primary_evidence is True
        assert ii.remaining_evidence_ids == []
        assert ii.impact_severity == "case_breaking"
        assert report.overall_severity == "case_breaking"

    def test_issue_with_multiple_evidence_is_significant(self):
        """争点有多份证据时，排除其中最强证据后 severity=significant。"""
        index = EvidenceIndex(
            case_id="c-001",
            evidence=[
                _make_evidence("ev-001"),
                _make_evidence("ev-002"),
            ],
        )
        issue_tree = _make_issue_tree("i-001", evidence_ids=["ev-001", "ev-002"])
        report = simulate_exclusion("ev-001", index, issue_tree=issue_tree)
        ii = report.affected_issues[0]
        assert "ev-002" in ii.remaining_evidence_ids
        assert ii.impact_severity in ("significant", "manageable")

    def test_issue_not_dependent_on_evidence_not_affected(self):
        """争点不依赖该证据时，不出现在 affected_issues 中。"""
        index = _make_index("ev-001", "ev-002")
        issue_tree = _make_issue_tree("i-001", evidence_ids=["ev-002"])  # 不依赖 ev-001
        report = simulate_exclusion("ev-001", index, issue_tree=issue_tree)
        assert report.affected_issues == []

    def test_path_in_admissibility_gate_becomes_nonviable(self):
        """证据在 admissibility_gate 中时，路径变为不可行。"""
        index = _make_index("ev-001")
        dpt = _make_decision_path_tree("path-001", admissibility_gate=["ev-001"])
        report = simulate_exclusion("ev-001", index, decision_path_tree=dpt)
        assert len(report.affected_paths) == 1
        assert report.affected_paths[0].becomes_nonviable is True
        assert report.overall_severity in ("significant", "case_breaking")

    def test_path_in_key_evidence_not_nonviable(self):
        """证据仅在 key_evidence_ids 中时，路径不设为不可行。"""
        index = _make_index("ev-001")
        dpt = _make_decision_path_tree("path-001", key_evidence_ids=["ev-001"])
        report = simulate_exclusion("ev-001", index, decision_path_tree=dpt)
        assert len(report.affected_paths) == 1
        assert report.affected_paths[0].becomes_nonviable is False

    def test_path_not_dependent_not_affected(self):
        """路径不依赖该证据时不出现在 affected_paths 中。"""
        index = _make_index("ev-001")
        dpt = _make_decision_path_tree("path-001", admissibility_gate=["ev-002"])
        report = simulate_exclusion("ev-001", index, decision_path_tree=dpt)
        assert report.affected_paths == []

    def test_attack_chain_node_broken_when_evidence_excluded(self):
        """攻击节点依赖该证据时，节点出现在 broken_attack_node_ids 中。"""
        index = _make_index("ev-001")
        chain = _make_attack_chain("chain-001", supporting_evidence_ids=["ev-001"])
        report = simulate_exclusion("ev-001", index, attack_chains=[chain])
        assert len(report.affected_chains) == 1
        assert "node-001" in report.affected_chains[0].broken_attack_node_ids

    def test_attack_chain_not_affected_when_evidence_not_used(self):
        """攻击节点不使用该证据时，攻击链不受影响。"""
        index = _make_index("ev-001")
        chain = _make_attack_chain("chain-001", supporting_evidence_ids=["ev-002"])
        report = simulate_exclusion("ev-001", index, attack_chains=[chain])
        assert report.affected_chains == []

    def test_two_nonviable_paths_escalates_to_case_breaking(self):
        """两条或以上路径不可行时，overall_severity 升为 case_breaking。"""
        index = _make_index("ev-001")
        path1 = DecisionPath(
            path_id="path-001",
            trigger_condition="条件A",
            possible_outcome="结果A",
            admissibility_gate=["ev-001"],
        )
        path2 = DecisionPath(
            path_id="path-002",
            trigger_condition="条件B",
            possible_outcome="结果B",
            admissibility_gate=["ev-001"],
        )
        dpt = DecisionPathTree(
            tree_id="tree-001",
            case_id="c-001",
            run_id="r-001",
            paths=[path1, path2],
        )
        report = simulate_exclusion("ev-001", index, decision_path_tree=dpt)
        assert report.overall_severity == "case_breaking"

    def test_summary_is_non_empty_when_impacts_exist(self):
        """有影响时 summary 非空。"""
        index = _make_index("ev-001")
        issue_tree = _make_issue_tree("i-001", evidence_ids=["ev-001"])
        report = simulate_exclusion("ev-001", index, issue_tree=issue_tree)
        assert report.summary != ""
        assert "ev-001" in report.summary

    def test_excluded_evidence_id_and_case_id_in_report(self):
        """ImpactReport 包含 excluded_evidence_id 和 case_id。"""
        index = _make_index("ev-001")
        report = simulate_exclusion("ev-001", index)
        assert report.excluded_evidence_id == "ev-001"
        assert report.case_id == "c-001"

    def test_evidence_with_admissibility_score_zero_is_excluded(self):
        """admissibility_score=0 的证据为最弱，排除时为 primary evidence。"""
        # 构建两份证据：ev-001 score=0.0，ev-002 score=1.0
        ev1 = _make_evidence("ev-001")
        ev1 = ev1.model_copy(update={"admissibility_score": 0.0})
        ev2 = _make_evidence("ev-002")
        ev2 = ev2.model_copy(update={"admissibility_score": 1.0})
        index = EvidenceIndex(case_id="c-001", evidence=[ev1, ev2])
        issue_tree = _make_issue_tree("i-001", evidence_ids=["ev-001", "ev-002"])
        report = simulate_exclusion("ev-001", index, issue_tree=issue_tree)
        # ev-001 score 最低，不是 primary（ev-002 score 更高）
        ii = report.affected_issues[0]
        assert ii.loses_primary_evidence is False  # ev-002 仍是主力

    def test_all_artifacts_combined(self):
        """同时传入争点树、路径树、攻击链时，三层均分析。"""
        index = _make_index("ev-001")
        issue_tree = _make_issue_tree("i-001", evidence_ids=["ev-001"])
        dpt = _make_decision_path_tree("path-001", admissibility_gate=["ev-001"])
        chain = _make_attack_chain("chain-001", supporting_evidence_ids=["ev-001"])
        report = simulate_exclusion(
            "ev-001", index,
            issue_tree=issue_tree,
            decision_path_tree=dpt,
            attack_chains=[chain],
        )
        assert len(report.affected_issues) == 1
        assert len(report.affected_paths) == 1
        assert len(report.affected_chains) == 1
