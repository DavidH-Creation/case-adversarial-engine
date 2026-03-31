"""
房屋买卖合同纠纷（real_estate）案件类型的防御链优化 LLM 提示模板。
LLM prompt templates for real estate sale contract dispute case type defense chain optimization.

指导 LLM 为原告方生成针对每个争点的最优防御策略链。
"""
from __future__ import annotations

from engines.shared.few_shot_examples import load_few_shot_text
from engines.shared.models import EvidenceIndex, Issue

_BASE_SYSTEM_PROMPT = """\
你是一名专业的中国房屋买卖合同纠纷案件法律顾问，负责为原告方生成最优防御策略链。

你的任务是针对每个争点，生成原告方的防御论点，并按优先级排序，形成完整的庭审防御链。

## 输出格式（严格 JSON）

```json
{
  "defense_points": [
    {
      "issue_id": "争点 ID（必须与输入 issue_id 完全一致）",
      "defense_strategy": "防御策略摘要（1-2 句话，聚焦核心主张）",
      "supporting_argument": "详细支撑论证（引用具体事实和法律依据）",
      "evidence_ids": ["支持该论点的证据 ID 列表"],
      "priority": 1
    }
  ],
  "confidence_score": 0.85,
  "strategic_summary": "整体防御策略摘要（2-3 句话）"
}
```

## 约束条件

1. issue_id 必须与输入中的 issue_id 完全一致，不得自创
2. evidence_ids 只能引用输入中已知的证据 ID
3. priority 从 1 开始连续递增（1 = 最优先防御的争点）
4. confidence_score ∈ [0.0, 1.0]，基于证据充分程度和法律依据清晰度评估
5. 优先级排序原则：
   - outcome_impact = high 的争点优先
   - 证据充足的争点优先（evidence_strength_gap > 0）
   - 程序性争点通常低于实体性争点

## 房屋买卖合同纠纷防御要点

- 逾期交付争点：竣工验收备案日期是最有力的客观时间节点证据，优先固化
- 产权过户争点：不动产权属登记查询结果和付款凭证共同证明过户条件已成就
- 面积差异争点：委托具有资质的测绘机构出具实测报告，与合同约定面积形成精确比对
- 违约金过高抗辩：买方应预备违约金合理性的反驳论证（损失实际发生的证明）
- 合同解除权：需明确解除权的法律依据（《民法典》第 563 条）及权利行使时间节点

## 注意事项

- 防御策略应聚焦原告方的举证优势，而非攻击对方
- supporting_argument 应具体引用证据内容和法律条文，不得空泛
- 对证据薄弱的争点，说明补充证据的方向（如申请法院调取不动产登记记录）
"""

SYSTEM_PROMPT = _BASE_SYSTEM_PROMPT + load_few_shot_text("defense_chain")


def build_user_prompt(
    issues: list[Issue],
    evidence_index: EvidenceIndex,
    plaintiff_party_id: str,
) -> str:
    """构建用户提示。"""
    issue_lines = []
    for issue in issues:
        impact = getattr(issue, "outcome_impact", None)
        gap = getattr(issue, "evidence_strength_gap", None)
        issue_lines.append(
            f"- issue_id: {issue.issue_id}\n"
            f"  title: {issue.title}\n"
            f"  issue_type: {issue.issue_type.value}\n"
            f"  outcome_impact: {impact.value if impact else '未评估'}\n"
            f"  evidence_strength_gap: {gap if gap is not None else '未知'}\n"
            f"  evidence_ids: {issue.evidence_ids}"
        )

    evidence_lines = []
    for ev in evidence_index.evidence[:20]:  # 限制 token
        evidence_lines.append(
            f"- {ev.evidence_id}: [{ev.evidence_type.value}] {ev.title} — {ev.summary[:80]}"
        )

    return f"""\
## 案件信息

原告方 party_id: {plaintiff_party_id}

## 争点列表（{len(issues)} 个）

{chr(10).join(issue_lines)}

## 可用证据（{len(evidence_index.evidence)} 条）

{chr(10).join(evidence_lines)}

请为原告方生成完整的防御策略链，按上述格式输出严格 JSON。
"""
