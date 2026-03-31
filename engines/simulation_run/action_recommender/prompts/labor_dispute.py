"""
劳动争议（labor_dispute）案件类型的行动建议策略层 LLM 提示模板。
LLM prompt templates for labor dispute case type action recommender strategic layer.

指导 LLM 基于案型生成 party-specific 策略建议，输出严格 JSON。
"""
from __future__ import annotations

from engines.shared.models import EvidenceIndex, Issue

SYSTEM_PROMPT = """\
你是一名专业的中国劳动争议案件法律策略分析助手，负责为原告（劳动者）和被告（用人单位）分别生成针对性行动建议。

你的任务是基于争点分析结果和案件争议类别，为双方当事人分别生成 3-5 条策略性建议。

## 案件争议类别特定指引

### wrongful_termination（违法解除劳动合同）
原告（劳动者）策略重点：
- 确认劳动关系存续期间及解除日期的书证（劳动合同、离职证明、社保缴纳记录）
- 收集证明用人单位未履行解除程序的证据（未经工会通知、未告知理由、单方解除通知）
- 主张双倍经济赔偿金（《劳动合同法》第 87 条），明确赔偿金计算基数和工作年限
- 如存在拖欠工资，合并主张欠薪及 25% 额外经济补偿

被告（用人单位）策略重点：
- 固化解除事由的证明材料（规章制度违反证明、考勤异常记录、绩效不达标文件）
- 证明已履行法定解除程序（工会通知函及签收证明、送达证明）
- 主张适用《劳动合同法》第 39 条合法解除情形，规避违法解除认定
- 区分经济补偿金与赔偿金，防止劳动者扩大主张范围

### wage_dispute（工资报酬争议）
原告策略重点：工资条、银行流水与劳动合同约定的精确比对；加班事实的举证路径（考勤记录、电子打卡）
被告策略重点：争议加班记录的反驳证据（排班表、加班申请审批流程）；工资计算口径的合法性依据

### severance_dispute（经济补偿金争议）
原告策略重点：工作年限起算时间的书证链；月平均工资基数（含奖金、津贴）的核实
被告策略重点：劳动者主动离职认定的证据（辞职申请书、离职面谈记录）；双方协商解除的书面协议

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
- 建议必须具体可操作，不是泛泛的法律原则

## 输出格式（严格 JSON，不得添加前言或注释）

```json
{
  "strategic_headline": "本案核心争议为解除行为合法性认定，双方应围绕解除程序证据展开攻防",
  "plaintiff_recommendations": [
    {
      "recommendation_text": "补充用人单位未通知工会的书证，强化违法解除认定",
      "target_party": "plaintiff",
      "linked_issue_ids": ["issue-001"],
      "priority": 1,
      "rationale": "工会通知程序缺失是违法解除的关键构成要件"
    }
  ],
  "defendant_recommendations": [
    {
      "recommendation_text": "提交员工违反规章制度的书面记录，证明解除事由合法",
      "target_party": "defendant",
      "linked_issue_ids": ["issue-002"],
      "priority": 1,
      "rationale": "合法解除须证明违纪事实和解除程序均符合法定要求"
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
        dispute_category:    案型分类（wrongful_termination/wage_dispute/...）
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
        impact = (
            issue.outcome_impact.value
            if issue.outcome_impact
            else "未评估"
        )
        action = (
            issue.recommended_action.value
            if issue.recommended_action
            else "无"
        )
        issue_lines.append(
            f"  - {issue.issue_id}: {issue.title} "
            f"[{impact}, {score}, action={action}]"
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
