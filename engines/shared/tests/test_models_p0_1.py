"""
P0.1 数据模型单元测试 — 新增枚举和 Issue 扩展字段。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from engines.shared.models import (
    AttackStrength,
    EvidenceStrength,
    ImpactTarget,
    Issue,
    IssueType,
    OutcomeImpact,
    RecommendedAction,
)


class TestOutcomeImpact:
    """OutcomeImpact 枚举完整性。"""

    def test_values(self):
        assert {e.value for e in OutcomeImpact} == {"high", "medium", "low"}

    def test_string_coercion(self):
        assert OutcomeImpact("high") is OutcomeImpact.high


class TestImpactTarget:
    """ImpactTarget 枚举完整性。"""

    def test_values(self):
        expected = {"principal", "interest", "penalty", "attorney_fee", "credibility"}
        assert {e.value for e in ImpactTarget} == expected


class TestEvidenceStrength:
    def test_values(self):
        assert {e.value for e in EvidenceStrength} == {"strong", "medium", "weak"}


class TestAttackStrength:
    def test_values(self):
        assert {e.value for e in AttackStrength} == {"strong", "medium", "weak"}


class TestRecommendedAction:
    def test_values(self):
        expected = {
            "supplement_evidence",
            "amend_claim",
            "abandon",
            "explain_in_trial",
        }
        assert {e.value for e in RecommendedAction} == expected


def _minimal_issue(**overrides) -> Issue:
    """最小合法 Issue 工厂。"""
    defaults = dict(
        issue_id="i-001",
        case_id="case-001",
        title="借款合同是否成立",
        issue_type=IssueType.factual,
    )
    defaults.update(overrides)
    return Issue(**defaults)


class TestIssueP01Fields:
    """Issue P0.1 扩展字段。"""

    def test_defaults_are_none_and_empty(self):
        issue = _minimal_issue()
        assert issue.outcome_impact is None
        assert issue.impact_targets == []
        assert issue.proponent_evidence_strength is None
        assert issue.opponent_attack_strength is None
        assert issue.recommended_action is None
        assert issue.recommended_action_basis is None

    def test_all_fields_set_roundtrip(self):
        issue = _minimal_issue(
            outcome_impact=OutcomeImpact.high,
            impact_targets=["principal", "interest"],
            proponent_evidence_strength=EvidenceStrength.strong,
            opponent_attack_strength=AttackStrength.medium,
            recommended_action=RecommendedAction.supplement_evidence,
            recommended_action_basis="基于借款凭证 ev-001 评估，证据链不完整",
        )
        data = issue.model_dump()
        restored = Issue.model_validate(data)
        assert restored.outcome_impact == OutcomeImpact.high
        assert restored.impact_targets == ["principal", "interest"]
        assert restored.proponent_evidence_strength == EvidenceStrength.strong
        assert restored.opponent_attack_strength == AttackStrength.medium
        assert restored.recommended_action == RecommendedAction.supplement_evidence
        assert restored.recommended_action_basis == "基于借款凭证 ev-001 评估，证据链不完整"

    def test_existing_fields_unaffected(self):
        """P0.1 扩展不影响现有字段。"""
        issue = _minimal_issue(
            evidence_ids=["ev-001"],
            burden_ids=["burden-001"],
        )
        assert issue.evidence_ids == ["ev-001"]
        assert issue.burden_ids == ["burden-001"]

    def test_backward_compat_none_all_p01_fields(self):
        """旧数据（无 P0.1 字段）可正常反序列化。"""
        old_data = {
            "issue_id": "i-old",
            "case_id": "case-001",
            "title": "旧争点",
            "issue_type": "factual",
        }
        issue = Issue.model_validate(old_data)
        assert issue.outcome_impact is None
        assert issue.impact_targets == []


class TestImpactTargetsCoercion:
    """Unit 22 Phase C 回归：list[str] 字段对 str-Enum 的强制转换。

    Phase C 把 ``Issue.impact_targets`` 从 ``list[ImpactTarget]`` 弱化为
    ``list[str]``，目的是案由中立化。但 civil_loan 内部代码（fixtures、
    prompts、tests）仍然使用 ``ImpactTarget.principal`` 这种 enum 引用以获得
    自动补全和 IDE 跳转。这只在以下不变量成立时安全：

      Pydantic 在赋值时会把 str-Enum 实例 *降级* 成纯 str，使得后续
      ``isinstance(t, str)`` 为 True，``type(t) is str`` 为 True，且
      与其他 str 的 ``==`` 比较语义正确。

    如果未来有人加上 ``Annotated[list[str], AfterValidator(...)]`` 或类似
    的窄化装饰器破坏了这个降级，整个 Phase C 的"案由中立"承诺就会悄悄崩溃，
    civil_loan-内部代码会泄漏 ImpactTarget 实例到序列化层、ranker 过滤器
    （它做的是 ``str in frozenset[str]``），以及下游的 JSON 输出。

    这个测试类是该不变量的唯一守门人。
    """

    def test_str_enum_member_is_coerced_to_plain_str(self):
        """直接赋值 ImpactTarget 实例 → 字段实际存的是 str（不是 enum）。"""
        issue = _minimal_issue(impact_targets=[ImpactTarget.principal])
        assert issue.impact_targets == ["principal"]
        # 关键断言：实际类型是 str，不是 ImpactTarget
        for t in issue.impact_targets:
            assert type(t) is str, (
                f"Pydantic str-Enum coercion broken: got {type(t).__name__}, expected str. "
                f"Phase C contract requires Issue.impact_targets to flatten str-Enum members "
                f"to plain strings so the per-case-type filter and JSON serializer remain "
                f"case-type-neutral."
            )

    def test_mixed_enum_and_str_input(self):
        """混合 enum 和 str 输入 → 全部存为 str。"""
        issue = _minimal_issue(
            impact_targets=[
                ImpactTarget.principal,
                "interest",
                ImpactTarget.credibility,
            ]
        )
        assert issue.impact_targets == ["principal", "interest", "credibility"]
        for t in issue.impact_targets:
            assert type(t) is str

    def test_coerced_value_equals_enum_via_str_protocol(self):
        """str-Enum 协议保证：coerced str 与原始 enum 用 == 比较相等。"""
        issue = _minimal_issue(impact_targets=[ImpactTarget.principal])
        # str-Enum 的关键性质：member == "value" 为 True
        assert issue.impact_targets[0] == ImpactTarget.principal
        assert issue.impact_targets[0] == "principal"
        assert ImpactTarget.principal == "principal"

    def test_coerced_value_works_in_set_membership(self):
        """关键：coerced str 必须能与 ranker 的 frozenset[str] 词汇做 in 操作。

        如果 Pydantic 把它存成 ImpactTarget 实例，``ImpactTarget.principal in
        frozenset({"principal", ...})`` 在 Python 里仍然为 True（因为 hash
        基于 str），但反过来 ``"principal" in frozenset({ImpactTarget.principal})``
        也为 True — 即语义对，但**类型签名**就漂移了。我们要求字段实际值
        是 str 以避免类型层面的污染。
        """
        issue = _minimal_issue(impact_targets=[ImpactTarget.principal])
        allowed: frozenset[str] = frozenset(
            {"principal", "interest", "penalty", "attorney_fee", "credibility"}
        )
        assert all(t in allowed for t in issue.impact_targets)

    def test_serialization_emits_plain_strings(self):
        """``model_dump()`` 必须输出 list[str]，而不是嵌套 enum 字典或 IntEnum 数字。"""
        issue = _minimal_issue(
            impact_targets=[ImpactTarget.principal, ImpactTarget.interest]
        )
        dumped = issue.model_dump()
        assert dumped["impact_targets"] == ["principal", "interest"]
        # JSON 序列化也必须工作
        json_dumped = issue.model_dump_json()
        assert '"impact_targets":["principal","interest"]' in json_dumped

    def test_unknown_string_is_accepted_at_model_layer(self):
        """Phase C Q3 决定：Issue 模型层不做枚举校验，过滤在 ranker 层。

        这意味着 ``Issue(impact_targets=["NOT_A_REAL_TARGET"])`` 必须成功。
        如果未来有人在 Issue 上加 enum 校验装饰器，这个测试会失败并警示
        他们去读 Phase C 的 Q3 设计决策。
        """
        # 不应抛出 ValidationError
        issue = _minimal_issue(impact_targets=["NOT_A_REAL_TARGET"])
        assert issue.impact_targets == ["NOT_A_REAL_TARGET"]
