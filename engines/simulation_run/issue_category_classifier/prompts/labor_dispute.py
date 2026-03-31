"""
劳动争议（labor_dispute）案件类型的争点类型分类 LLM 提示模板。
LLM prompt templates for labor dispute case type issue category classification.

指导 LLM 对每个争点输出四类分析标签，输出严格 JSON。
Guides LLM to classify each issue into one of four categories and output strict JSON.
"""
from __future__ import annotations

from engines.shared.models import AmountCalculationReport, EvidenceIndex, IssueTree

SYSTEM_PROMPT = """\
你是一名专业的中国劳动争议案件法律分析助手，负责对案件争点进行分析类型分类。

你的任务是对每个争点分配一个 issue_category（争点分析类型标签）：

分类说明：
- fact_issue：事实争点（是否存在某事件或行为，例如：劳动关系是否成立、解除通知是否送达、加班事实是否存在）
- legal_issue：法律适用争点（如何解释或适用法律规则，例如：解除行为是否构成违法解除、工会通知义务的适用范围）
- calculation_issue：计算争点（金额、期限的计算方式，例如：经济补偿金月数计算、加班费计算基数、月平均工资的组成）
- procedure_credibility_issue：程序或可信度争点（证据真实性、程序瑕疵，例如：考勤记录是否真实、仲裁前置程序是否已履行）

重要约束：
- issue_category 与现有 issue_type 并列，独立填写，不要混淆
- 当 issue_category = calculation_issue 时，related_claim_entry_ids 必须引用金额报告中已知的 claim_id（至少一条）
- category_basis 必须非空，简要说明分类依据（1-2 句）
- 所有字段必须使用以上枚举值，不得使用自由文本

## 劳动争议争点分类参考

- 「劳动关系是否成立」→ fact_issue（事实认定）
- 「解除行为是否违法」→ legal_issue（法律适用）
- 「经济补偿金计算基数」→ calculation_issue（金额计算）
- 「考勤记录真实性」→ procedure_credibility_issue（证据可信度）
- 「工会通知程序是否履行」→ fact_issue（程序事实认定）
- 「加班时间认定」→ fact_issue（事实争点，但若涉及费率则升格为 calculation_issue）

输出格式（严格 JSON，不得添加任何前言或注释）：
```json
{
  "classifications": [
    {
      "issue_id": "<issue_id>",
      "issue_category": "fact_issue",
      "related_claim_entry_ids": [],
      "category_basis": "该争点关注劳动关系是否依法成立，属于事实认定问题。"
    }
  ]
}
```\
"""


def build_user_prompt(
    *,
    issue_tree: IssueTree,
    evidence_index: EvidenceIndex,
    amount_calculation_report: AmountCalculationReport,
) -> str:
    """构建用于争点类型分类的用户 prompt。
    Build user prompt for issue category classification.

    Args:
        issue_tree:                待分类的争点树
        evidence_index:            证据索引（提供背景信息）
        amount_calculation_report: P0.2 金额报告（提供 claim_id 参考列表）
    """
    # 争点块
    issue_lines: list[str] = []
    for issue in issue_tree.issues:
        evidence_ids_str = (
            ", ".join(issue.evidence_ids) if issue.evidence_ids else "（无关联证据）"
        )
        claim_ids_str = (
            ", ".join(issue.related_claim_ids) if issue.related_claim_ids else "（无）"
        )
        issue_lines.append(
            f"  issue_id: {issue.issue_id}\n"
            f"  title: {issue.title}\n"
            f"  type: {issue.issue_type.value}\n"
            f"  related_claim_ids: [{claim_ids_str}]\n"
            f"  evidence_ids: [{evidence_ids_str}]"
        )
    issues_block = "\n\n".join(issue_lines) if issue_lines else "（无争点）"

    # 金额报告诉请条目块（供 calculation_issue 关联参考）
    claim_entry_lines: list[str] = []
    for entry in amount_calculation_report.claim_calculation_table:
        claim_entry_lines.append(
            f"  claim_id: {entry.claim_id} | type: {entry.claim_type.value} | "
            f"claimed: {entry.claimed_amount} | calculated: {entry.calculated_amount}"
        )
    claim_entries_block = (
        "\n".join(claim_entry_lines) if claim_entry_lines else "（无金额报告条目）"
    )

    return (
        f"【案件基本信息】\n"
        f"case_id: {issue_tree.case_id}\n"
        f"\n【争点列表（共 {len(issue_tree.issues)} 条）】\n{issues_block}\n"
        f"\n【金额报告诉请条目（共 {len(amount_calculation_report.claim_calculation_table)} 条，供 calculation_issue 关联）】\n"
        f"{claim_entries_block}\n"
        f"\n请对以上每个争点进行类型分类，输出 JSON。"
    )
