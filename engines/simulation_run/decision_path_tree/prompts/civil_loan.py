"""
民间借贷（civil_loan）案件类型的裁判路径树 LLM 提示模板。
LLM prompt templates for civil loan case type decision path tree generation.

指导 LLM 生成 3-6 条结构化裁判路径，输出严格 JSON。
注意：调用方已按 v1.2 过渡规则过滤，传入的 evidence_index 只含 admitted_record 证据。
"""
from __future__ import annotations

from engines.shared.models import AmountCalculationReport, EvidenceIndex, IssueTree

SYSTEM_PROMPT = """\
你是一名专业的中国民间借贷案件法律分析助手，负责基于案件当前证据状态生成结构化裁判路径树。

你的任务是分析案件争点和证据，生成 3-6 条可能的裁判路径，每条路径代表一种合理的裁判走向。

## 裁判路径（paths）要求

每条路径必须包含：
- path_id：路径唯一标识（如 path-A、path-B）
- trigger_condition：触发本路径的核心事实条件（一句话描述）
- trigger_issue_ids：与触发条件直接相关的争点 ID 列表（只引用已知的 issue_id）
- key_evidence_ids：本路径成立的关键证据 ID 列表（只引用已知的 evidence_id）
- possible_outcome：本路径下法院可能的裁判结果（具体到诉请支持情况，不超过 200 字）
- confidence_interval：置信度区间（lower/upper，均为 [0,1] 之间的浮点数；若系统提示标注 verdict_block_active=true，则此字段设为 null）
- path_notes：路径说明或注意事项（可为空字符串）

## 阻断条件（blocking_conditions）要求

若存在阻断稳定裁判判断的因素，需在 blocking_conditions 中列出：
- condition_id：条件唯一标识
- condition_type：枚举值之一（amount_conflict / evidence_gap / procedure_unresolved）
- description：阻断原因描述
- linked_issue_ids：关联争点（只引用已知 issue_id）
- linked_evidence_ids：关联证据（只引用已知 evidence_id）

## 硬性约束

- paths 数量必须在 3-6 条之间
- 所有 issue_id 只能引用争点树中已知的 issue_id
- 所有 evidence_id 只能引用已进入庭审的证据（已由系统过滤，直接使用证据索引中的 evidence_id 即可）
- 若 verdict_block_active=true，所有 paths 的 confidence_interval 必须设为 null
- 不得输出超出上述字段之外的自由评论

## 民间借贷案件参考路径结构

路径树至少应覆盖以下分支：
- 路径 A：争议款项认定计入还款 → 较低未还本金 → 利率支持（LPR 4 倍上限）→ 律师费部分支持
- 路径 B：争议款项不认定计入还款 → 较高未还本金 → 违约金与利息择一 → 律师费全额支持
- 若本金基数存在口径冲突，建议增加路径 C（以某一口径为基准的中间路径）

## 输出格式（严格 JSON，不得添加前言或注释）

```json
{
  "paths": [
    {
      "path_id": "path-A",
      "trigger_condition": "争议款项被认定计入已还款项",
      "trigger_issue_ids": ["issue-repayment-001"],
      "key_evidence_ids": ["ev-001", "ev-003"],
      "possible_outcome": "法院认定未还本金为 X 元，支持利率 Y%，律师费部分支持",
      "confidence_interval": {"lower": 0.3, "upper": 0.6},
      "path_notes": "依赖被告提交的还款凭证"
    }
  ],
  "blocking_conditions": [
    {
      "condition_id": "bc-001",
      "condition_type": "amount_conflict",
      "description": "本金基数存在两种口径，无法确定稳定计算基数",
      "linked_issue_ids": ["issue-principal-001"],
      "linked_evidence_ids": ["ev-001", "ev-005"]
    }
  ]
}
```\
"""


def build_user_prompt(
    *,
    issue_tree: IssueTree,
    evidence_index: EvidenceIndex,
    amount_report: AmountCalculationReport,
) -> str:
    """构建 user prompt。
    注意：evidence_index 在调用前已被生成器按 v1.2 过渡规则过滤（只含 admitted_record 证据）。
    """
    check = amount_report.consistency_check_result

    # 金额一致性状态块
    verdict_note = (
        "注意：verdict_block_active=True，所有 paths 的 confidence_interval 必须设为 null。"
        if check.verdict_block_active
        else ""
    )
    amount_block = f"""\
【金额一致性状态】
- verdict_block_active: {check.verdict_block_active}
- principal_base_unique: {check.principal_base_unique}
- all_repayments_attributed: {check.all_repayments_attributed}
- unresolved_conflicts 数量: {len(check.unresolved_conflicts)} 条
{verdict_note}"""

    # 争点树摘要（展示已排序的争点，包含 outcome_impact）
    issues_lines = []
    for issue in issue_tree.issues:
        impact = (
            f"outcome_impact={issue.outcome_impact.value}"
            if issue.outcome_impact
            else "outcome_impact=未评估"
        )
        evidence_ids = ", ".join(issue.evidence_ids[:5]) if issue.evidence_ids else "无"
        issues_lines.append(
            f"  - {issue.issue_id}: {issue.title} [{impact}] (证据: {evidence_ids})"
        )
    issues_block = "【争点树（已按 outcome_impact 排序）】\n" + (
        "\n".join(issues_lines) if issues_lines else "  （无争点）"
    )

    # 证据索引摘要（已过滤为 admitted_record）
    evidence_lines = []
    for ev in evidence_index.evidence[:20]:
        evidence_lines.append(
            f"  - {ev.evidence_id}: {ev.title} ({ev.evidence_type.value})"
        )
    evidence_block = "【已进入庭审的证据（admitted_record）】\n" + (
        "\n".join(evidence_lines) if evidence_lines else "  （无证据）"
    )
    if len(evidence_index.evidence) > 20:
        evidence_block += f"\n  ... 共 {len(evidence_index.evidence)} 条证据"

    return f"""\
{amount_block}

{issues_block}

{evidence_block}

请根据以上信息生成 3-6 条裁判路径树，以严格 JSON 格式输出。"""
