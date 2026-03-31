"""
民间借贷（civil_loan）案件类型的行动建议策略层 LLM 提示模板。
LLM prompt templates for civil loan case type action recommender strategic layer.

指导 LLM 基于案型生成 party-specific 策略建议，输出严格 JSON。
"""

from __future__ import annotations

from engines.shared.models import EvidenceIndex, Issue

SYSTEM_PROMPT = """\
你是一名专业的中国民间借贷案件法律策略分析助手，负责为原告和被告分别生成针对性行动建议。

你的任务是基于争点分析结果和案件争议类别，为双方当事人分别生成 3-5 条策略性建议。

## 案件争议类别特定指引

### borrower_identity（借款人主体争议）
原告策略重点：
- 补充能直接证明借贷合意发生在原被告之间的证据（借条、聊天记录、借款合意表述）
- 解释催款行为中可能暴露的矛盾（如次日催第三方而非被告）
- 考虑是否需要备位主张结构（主位：被告单独借款；备位：被告与第三方共同借款）
- 攻击对方关键证据的可采性（如录音合法性、聊天记录完整性）

被告策略重点：
- 补完整资金流向链——证明款项到账后立即转出或由第三方实际控制使用
- 争取实际借款人出庭作证或提供书面确认
- 建立账户控制的连续性证据（银行流水、第三方指令记录）
- 将程序性攻击建立在证据可采性闸门之后（先确立证据可采，再利用不利推定）

### amount_dispute（金额争议）
原告策略重点：还款流水的精确匹配、本金基数的法定口径确认
被告策略重点：争议还款的证据补强、利率违法性抗辩

### contract_validity（合同效力争议）
原告策略重点：合同成立要件的补证、交付事实的证据链
被告策略重点：合同无效事由的证据支撑

### general（通用/未分类）
按争点 composite_score 从高到低逐条生成攻防建议

## 输出要求

每条建议必须包含：
- recommendation_text：具体可操作的策略建议（一句话，不超过 100 字）
- target_party：plaintiff / defendant
- linked_issue_ids：该建议关联的争点 ID 列表（至少 1 个）
- priority：优先级 1-5（1=最高，应立即执行；5=可选的补充动作）
- rationale：策略依据说明（不超过 50 字）

同时输出：
- strategic_headline：一句话概括案件核心策略方向（不超过 50 字，不要提及具体金额数字）

## 硬性约束
- 原告建议 3-5 条，被告建议 3-5 条
- 所有 linked_issue_ids 只能引用已知的 issue_id
- 不要输出纯金额相关建议（除非案型为 amount_dispute）
- 建议必须具体可操作，不是泛泛的法律原则

## 输出格式（严格 JSON，不得添加前言或注释）

```json
{
  "strategic_headline": "本案核心争议为借款人主体认定，双方应围绕借贷合意直接证据展开攻防",
  "plaintiff_recommendations": [
    {
      "recommendation_text": "补充小陈本人在借款时发出的借款意思表示证据",
      "target_party": "plaintiff",
      "linked_issue_ids": ["issue-002"],
      "priority": 1,
      "rationale": "当前缺乏小陈本人作出借款合意的直接证据"
    }
  ],
  "defendant_recommendations": [
    {
      "recommendation_text": "申请老庄出庭作证，确认实际借款人身份",
      "target_party": "defendant",
      "linked_issue_ids": ["issue-004"],
      "priority": 1,
      "rationale": "老庄出庭可直接证明实际借款人非小陈"
    }
  ]
}
```\
"""


def build_user_prompt(
    *,
    issue_list: list[Issue],
    evidence_index: EvidenceIndex,
    dispute_category: str,
    proponent_party_id: str,
) -> str:
    """构建用于策略建议生成的用户 prompt。

    Args:
        issue_list:          含 P0.1 扩展字段的争点列表（已排序）
        evidence_index:      证据索引
        dispute_category:    案型分类（borrower_identity/amount_dispute/...）
        proponent_party_id:  主张方 party_id
    """
    # 争点块（含评分信息）
    issue_lines: list[str] = []
    for issue in issue_list:
        score = (
            f"composite_score={issue.composite_score:.1f}"
            if issue.composite_score is not None
            else "未评分"
        )
        impact = issue.outcome_impact.value if issue.outcome_impact else "未评估"
        action = issue.recommended_action.value if issue.recommended_action else "无"
        issue_lines.append(
            f"  - {issue.issue_id}: {issue.title} [{impact}, {score}, action={action}]"
        )
    issues_block = "\n".join(issue_lines) if issue_lines else "（无争点）"

    # 证据摘要
    evidence_lines: list[str] = []
    for ev in evidence_index.evidence[:15]:
        evidence_lines.append(
            f"  - {ev.evidence_id}: {ev.title} ({ev.evidence_type.value}, {ev.status.value})"
        )
    evidence_block = "\n".join(evidence_lines) if evidence_lines else "（无证据）"
    if len(evidence_index.evidence) > 15:
        evidence_block += f"\n  ... 共 {len(evidence_index.evidence)} 条证据"

    return (
        f"【案件争议类别】{dispute_category}\n"
        f"【主张方】{proponent_party_id}\n"
        f"\n【争点列表（共 {len(issue_list)} 条，按 composite_score 排序）】\n{issues_block}\n"
        f"\n【证据摘要】\n{evidence_block}\n"
        f"\n请根据以上信息，为原告和被告分别生成策略建议，以严格 JSON 格式输出。"
    )
