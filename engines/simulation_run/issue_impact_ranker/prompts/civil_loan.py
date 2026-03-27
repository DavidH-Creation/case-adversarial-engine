"""
民间借贷（civil_loan）案件类型的争点影响排序 LLM 提示模板。
LLM prompt templates for civil loan case type issue impact ranking.

指导 LLM 对每个争点从五个维度进行结构化评估，输出严格 JSON。
Guides LLM to evaluate each issue on 5 dimensions and output strict JSON.
"""
from __future__ import annotations

from engines.shared.models import AmountConsistencyCheck, EvidenceIndex, IssueTree

SYSTEM_PROMPT = """\
你是一名专业的中国民间借贷案件法律分析助手，负责对案件争点进行结构化影响评估。

你的任务是对每个争点从以下五个维度进行评估：
1. outcome_impact：该争点对最终裁判结果的影响程度
   允许值：high / medium / low
2. impact_targets：该争点影响的诉请对象（可多选）
   允许值：principal / interest / penalty / attorney_fee / credibility
3. proponent_evidence_strength：主张方（举证责任承担方）在该争点的当前证据强度
   允许值：strong / medium / weak
   约束：必须在 proponent_evidence_ids 中引用至少一条具体证据 ID
4. opponent_attack_strength：反对方在该争点的攻击强度
   允许值：strong / medium / weak
   约束：必须在 opponent_attack_evidence_ids 中引用至少一条具体证据 ID
5. recommended_action：系统建议行动
   允许值：supplement_evidence / amend_claim / abandon / explain_in_trial
   约束：recommended_action_basis 必须非空，且在 recommended_action_evidence_ids 中引用至少一条证据 ID

硬性约束（违反则输出无效）：
- 所有字段必须使用以上枚举值，不得使用自由文本
- 所有 evidence_ids 字段只能引用案件证据清单中已知的 evidence_id
- evaluations 数组与输入争点列表一一对应

输出格式（严格 JSON，不得添加任何前言或注释）：
```json
{
  "evaluations": [
    {
      "issue_id": "<issue_id>",
      "outcome_impact": "high",
      "impact_targets": ["principal"],
      "proponent_evidence_strength": "weak",
      "proponent_evidence_ids": ["ev-001"],
      "opponent_attack_strength": "strong",
      "opponent_attack_evidence_ids": ["ev-002"],
      "recommended_action": "supplement_evidence",
      "recommended_action_basis": "原告借款凭证仅有转账记录但缺少借条，建议补充书面借贷协议",
      "recommended_action_evidence_ids": ["ev-001"]
    }
  ]
}
```\
"""


def build_user_prompt(
    *,
    issue_tree: IssueTree,
    evidence_index: EvidenceIndex,
    proponent_party_id: str,
    amount_check: AmountConsistencyCheck,
) -> str:
    """构建用于争点影响评估的用户 prompt。
    Build user prompt for issue impact evaluation.

    Args:
        issue_tree:          待评估的争点树
        evidence_index:      证据索引（提供已知证据 ID 列表）
        proponent_party_id:  主张方 party_id（告知 LLM 举证责任方）
        amount_check:        P0.2 金额一致性校验结果（注入阻断条件）
    """
    # 争点块
    issue_lines: list[str] = []
    for issue in issue_tree.issues:
        evidence_ids_str = (
            ", ".join(issue.evidence_ids) if issue.evidence_ids else "（无关联证据）"
        )
        burden_ids_str = (
            ", ".join(issue.burden_ids) if issue.burden_ids else "（无）"
        )
        issue_lines.append(
            f"  issue_id: {issue.issue_id}\n"
            f"  title: {issue.title}\n"
            f"  type: {issue.issue_type.value}\n"
            f"  evidence_ids: [{evidence_ids_str}]\n"
            f"  burden_ids: [{burden_ids_str}]"
        )
    issues_block = "\n\n".join(issue_lines) if issue_lines else "（无争点）"

    # 证据清单块
    evidence_lines: list[str] = []
    for ev in evidence_index.evidence:
        evidence_lines.append(
            f"  evidence_id: {ev.evidence_id} | title: {ev.title} | "
            f"type: {ev.evidence_type.value} | status: {ev.status.value}"
        )
    evidence_block = "\n".join(evidence_lines) if evidence_lines else "（无证据）"

    # 金额一致性状态块
    amount_block = (
        f"  verdict_block_active: {amount_check.verdict_block_active}\n"
        f"  principal_base_unique: {amount_check.principal_base_unique}\n"
        f"  all_repayments_attributed: {amount_check.all_repayments_attributed}\n"
        f"  unresolved_conflicts 数量: {len(amount_check.unresolved_conflicts)} 条"
    )
    verdict_hint = (
        "\n  ⚠️  注意：verdict_block_active=True，与本金、利息、违约金相关的争点"
        "通常应评估为 outcome_impact=high。"
        if amount_check.verdict_block_active
        else ""
    )

    return (
        f"【案件基本信息】\n"
        f"case_id: {issue_tree.case_id}\n"
        f"主张方（举证责任承担方）party_id: {proponent_party_id}\n"
        f"\n【争点列表（共 {len(issue_tree.issues)} 条）】\n{issues_block}\n"
        f"\n【证据清单（共 {len(evidence_index.evidence)} 条）】\n{evidence_block}\n"
        f"\n【金额一致性状态（P0.2 结果）】\n{amount_block}{verdict_hint}\n"
        f"\n请对以上每个争点进行五维度评估，输出 JSON。"
    )
