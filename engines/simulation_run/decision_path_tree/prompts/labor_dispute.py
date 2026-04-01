"""
劳动争议（labor_dispute）案件类型的裁判路径树 LLM 提示模板。
LLM prompt templates for labor dispute case type decision path tree generation.

指导 LLM 生成 3-6 条结构化裁判路径，输出严格 JSON。
注意：调用方已按 v1.2 过渡规则过滤，传入的 evidence_index 只含 admitted_record 证据。
"""

from __future__ import annotations

from engines.shared.models import AmountCalculationReport, EvidenceIndex, IssueTree

SYSTEM_PROMPT = """\
你是一名专业的中国劳动争议案件法律分析助手，负责基于案件当前证据状态生成结构化裁判路径树。

你的任务是分析案件争点和证据，生成 3-6 条可能的裁判路径，每条路径代表一种合理的裁判走向。

## 裁判路径（paths）要求

每条路径必须包含：
- path_id：路径唯一标识（如 path-A、path-B）
- trigger_condition：触发本路径的核心事实条件（一句话描述）
- trigger_issue_ids：与触发条件直接相关的争点 ID 列表（只引用已知的 issue_id）
- key_evidence_ids：**仅包含支持本路径结论的证据** ID 列表（只引用已知的 evidence_id）
- counter_evidence_ids：**与本路径结论相悖的证据** ID 列表（只引用已知的 evidence_id，可为空列表）
- possible_outcome：本路径下法院可能的裁判结果（具体到诉请支持情况，不超过 200 字）
- path_notes：路径说明或注意事项（可为空字符串）
- admissibility_gate：本路径成立的前提——哪些证据必须被法庭采信（evidence_id 列表）
- result_scope：裁判范围标签列表（可多选：severance_pay / back_wages / reinstatement / compensation / social_insurance / penalty / credibility）
- fallback_path_id：若本路径关键证据未被采信或争点结论不利，降级到哪条路径的 path_id（最后一条路径可为空字符串）
- party_favored：本路径结果对哪方更有利，枚举值之一：plaintiff（对劳动者有利）/ defendant（对用人单位有利）/ neutral（中性）

## 证据极性规则（Evidence Polarity）—— 最高优先级

- `key_evidence_ids`：**仅放支持本路径结论的证据**。
- `counter_evidence_ids`：放置**反驳或削弱本路径结论**的证据。
- key_evidence_ids 与 counter_evidence_ids **不得有重叠**。

## 严格非空约束（违反则路径无效）—— 最高优先级

- 每条 path 的 trigger_issue_ids 必须包含至少 1 个 issue_id
- 每条 path 的 key_evidence_ids 必须包含至少 1 个 evidence_id

## 劳动争议案件参考路径结构

### 当案件争议焦点为解除行为合法性时：
- 路径 A：违法解除认定 → 支持赔偿金（N×2 倍月工资）
  trigger_issue_ids 应包含解除程序争点、解除事由争点
  key_evidence_ids 应包含解除通知书、程序缺失证明
- 路径 B：合法解除认定 → 仅支持经济补偿金（N 倍月工资）或驳回
  trigger_issue_ids 应包含解除事由争点
  key_evidence_ids 应包含违纪证明、工会通知函
- 路径 C：协商解除认定 → 按协议约定处理
  trigger_issue_ids 应包含解除性质认定争点
- 路径 D：劳动关系不认定 → 驳回全部诉请
  trigger_issue_ids 应包含劳动关系成立争点

### 当案件争议焦点为工资计算时：
- 路径 A：加班事实认定 + 月工资基数采信劳动者主张 → 较高加班费
- 路径 B：加班事实部分认定 + 月工资基数采信用人单位 → 较低加班费
- 路径 C：加班事实不认定 → 驳回加班费诉请

## 输出格式（严格 JSON，不得添加前言或注释）

```json
{
  "paths": [
    {
      "path_id": "path-A",
      "trigger_condition": "法院认定用人单位解除行为违反《劳动合同法》第 43 条（未经工会同意）",
      "trigger_issue_ids": ["issue-001", "issue-002"],
      "key_evidence_ids": ["ev-001", "ev-003"],
      "counter_evidence_ids": ["ev-defendant-002"],
      "admissibility_gate": ["ev-001"],
      "result_scope": ["compensation", "back_wages"],
      "fallback_path_id": "path-B",
      "possible_outcome": "认定违法解除，支持劳动者主张赔偿金（N×2），并支持欠付工资差额",
      "path_notes": "依赖解除通知书缺少工会意见栏盖章这一直接证据",
      "party_favored": "plaintiff"
    }
  ],
  "blocking_conditions": [
    {
      "condition_id": "bc-001",
      "condition_type": "evidence_gap",
      "description": "工会是否存在及其介入程度存疑，若工会不存在则第 43 条要件不成立",
      "linked_issue_ids": ["issue-010"],
      "linked_evidence_ids": ["ev-007"]
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
    amount_block = f"""\
【金额一致性状态】
- verdict_block_active: {check.verdict_block_active}
- principal_base_unique: {check.principal_base_unique}
- all_repayments_attributed: {check.all_repayments_attributed}
- unresolved_conflicts 数量: {len(check.unresolved_conflicts)} 条"""

    # 争点树摘要（展示已排序的争点，包含评分信息）
    issues_lines = []
    for issue in issue_tree.issues:
        impact = (
            f"outcome_impact={issue.outcome_impact.value}"
            if issue.outcome_impact
            else "outcome_impact=未评估"
        )
        score = (
            f"composite_score={issue.composite_score:.1f}"
            if issue.composite_score is not None
            else "composite_score=未计算"
        )
        parent = f" parent={issue.parent_issue_id}" if issue.parent_issue_id else ""
        evidence_ids = ", ".join(issue.evidence_ids[:5]) if issue.evidence_ids else "无"
        issues_lines.append(
            f"  - {issue.issue_id}: {issue.title} [{impact}, {score}]{parent} (证据: {evidence_ids})"
        )
    issues_block = "【争点树（已按 composite_score 排序）】\n" + (
        "\n".join(issues_lines) if issues_lines else "  （无争点）"
    )

    # 证据索引摘要（已过滤为 admitted_record）
    evidence_lines = []
    for ev in evidence_index.evidence[:20]:
        evidence_lines.append(f"  - {ev.evidence_id}: {ev.title} ({ev.evidence_type.value})")
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
