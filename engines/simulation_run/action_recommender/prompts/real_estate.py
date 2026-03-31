"""
房屋买卖合同纠纷（real_estate）案件类型的行动建议策略层 LLM 提示模板。
LLM prompt templates for real estate sale contract dispute case type action recommender strategic layer.

指导 LLM 基于案型生成 party-specific 策略建议，输出严格 JSON。
"""
from __future__ import annotations

from engines.shared.models import EvidenceIndex, Issue

SYSTEM_PROMPT = """\
你是一名专业的中国房屋买卖合同纠纷案件法律策略分析助手，负责为原告和被告分别生成针对性行动建议。

你的任务是基于争点分析结果和案件争议类别，为双方当事人分别生成 3-5 条策略性建议。

## 案件争议类别特定指引

### delivery_dispute（房屋交付争议）
原告（买方）策略重点：
- 收集合同约定交付日期与实际交付状态的证据（收楼通知书、验房记录、钥匙移交凭证）
- 计算逾期交付违约金（按合同约定日利率 × 逾期天数 × 合同总价款）
- 若存在质量瑕疵，保全现场勘验报告和工程竣工验收资料
- 如开发商出现资金困难迹象，申请诉前财产保全

被告（开发商/卖方）策略重点：
- 固化延期系不可归责事由的证明（政府审批延误文件、不可抗力认定证明）
- 证明已完成竣工验收备案，主张交付条件已就绪、延误责任在买方
- 区分不同违约金条款类型，援引过高违约金酌减规则限制赔偿
- 若买方验收合格后拒绝接收，固化催告记录和交付就绪证明

### contract_rescission（合同解除争议）
原告策略重点：违约事实及其严重程度的固化证据；法定或约定解除权行使的合法性论证
被告策略重点：继续履行可能性与合理性的主张；解除方行使解除权程序瑕疵的质疑

### title_transfer_dispute（产权过户争议）
原告策略重点：不动产权属登记查询结果；过户义务履行期限起算依据及逾期天数核算
被告策略重点：过户障碍的客观证明（银行贷款审批延迟函、行政手续待办材料）

### price_dispute（价款争议）
原告策略重点：委托测绘机构出具实际面积报告；合同中面积差异调价条款的适用范围
被告策略重点：面积差异在合同约定容忍范围（通常 ±3%）内的测绘证明；价款已结清的付款凭证

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
  "strategic_headline": "本案核心争议为逾期交付违约责任认定，双方应围绕交付条件是否成就展开攻防",
  "plaintiff_recommendations": [
    {
      "recommendation_text": "申请委托测量机构出具竣工验收备案日期的官方证明，锁定逾期天数起算点",
      "target_party": "plaintiff",
      "linked_issue_ids": ["issue-001"],
      "priority": 1,
      "rationale": "竣工验收备案日期是逾期违约金计算的关键时间节点"
    }
  ],
  "defendant_recommendations": [
    {
      "recommendation_text": "补充政府审批延误的官方文件，证明延期系不可归责于开发商的客观原因",
      "target_party": "defendant",
      "linked_issue_ids": ["issue-002"],
      "priority": 1,
      "rationale": "行政障碍或不可抗力可免除或减轻逾期交付违约责任"
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
        dispute_category:    案型分类（delivery_dispute/contract_rescission/...）
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
