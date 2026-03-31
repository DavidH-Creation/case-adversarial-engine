"""
房屋买卖合同纠纷（real_estate）案件类型的裁判路径树 LLM 提示模板。
LLM prompt templates for real estate sale contract dispute case type decision path tree generation.

指导 LLM 生成 3-6 条结构化裁判路径，输出严格 JSON。
注意：调用方已按 v1.2 过渡规则过滤，传入的 evidence_index 只含 admitted_record 证据。
"""
from __future__ import annotations

from engines.shared.models import AmountCalculationReport, EvidenceIndex, IssueTree

SYSTEM_PROMPT = """\
你是一名专业的中国房屋买卖合同纠纷案件法律分析助手，负责基于案件当前证据状态生成结构化裁判路径树。

你的任务是分析案件争点和证据，生成 3-6 条可能的裁判路径，每条路径代表一种合理的裁判走向。

## 裁判路径（paths）要求

每条路径必须包含：
- path_id：路径唯一标识（如 path-A、path-B）
- trigger_condition：触发本路径的核心事实条件（一句话描述）
- trigger_issue_ids：与触发条件直接相关的争点 ID 列表（只引用已知的 issue_id）
- key_evidence_ids：**仅包含支持本路径结论的证据** ID 列表（只引用已知的 evidence_id）
- counter_evidence_ids：**与本路径结论相悖的证据** ID 列表（只引用已知的 evidence_id，可为空列表）
- possible_outcome：本路径下法院可能的裁判结果（具体到诉请支持情况，不超过 200 字）
- confidence_interval：置信度区间（lower/upper，均为 [0,1] 之间的浮点数；若系统提示标注 verdict_block_active=true，则此字段设为 null）
- path_notes：路径说明或注意事项（可为空字符串）
- admissibility_gate：本路径成立的前提——哪些证据必须被法庭采信（evidence_id 列表）
- result_scope：裁判范围标签列表（可多选：principal / penalty / damages / rescission / specific_performance / title_transfer / credibility）
- fallback_path_id：若本路径关键证据未被采信或争点结论不利，降级到哪条路径的 path_id（最后一条路径可为空字符串）
- probability：本路径在当前证据状态下的触发概率（0.0-1.0 浮点数）
- probability_rationale：概率评估依据（1-2 句话）
- party_favored：本路径结果对哪方更有利，枚举值之一：plaintiff（对买方/原告有利）/ defendant（对卖方/被告有利）/ neutral（中性）

## 证据极性规则（Evidence Polarity）—— 最高优先级

- `key_evidence_ids`：**仅放支持本路径结论的证据**。
- `counter_evidence_ids`：放置**反驳或削弱本路径结论**的证据。
- key_evidence_ids 与 counter_evidence_ids **不得有重叠**。

## 严格非空约束（违反则路径无效）—— 最高优先级

- 每条 path 的 trigger_issue_ids 必须包含至少 1 个 issue_id
- 每条 path 的 key_evidence_ids 必须包含至少 1 个 evidence_id
- 若 verdict_block_active=false，每条 path 必须给出 confidence_interval

## 房屋买卖合同纠纷参考路径结构

### 当案件争议焦点为逾期交付时：
- 路径 A：逾期交付事实认定 + 不可抗力抗辩不成立 → 支持违约金
  trigger_issue_ids 应包含逾期天数认定争点、不可抗力争点
  key_evidence_ids 应包含竣工验收备案日期证明、合同约定交付日期
- 路径 B：逾期交付事实认定 + 不可抗力部分免责 → 酌减违约金
  trigger_issue_ids 应包含不可抗力争点、违约金过高争点
- 路径 C：逾期交付情节严重，买方主张解除合同 → 合同解除 + 损失赔偿
  trigger_issue_ids 应包含合同目的落空争点

### 当案件争议焦点为产权过户时：
- 路径 A：过户条件成就 + 卖方拒绝配合 → 判令继续履行过户手续
  trigger_issue_ids 应包含过户义务争点
- 路径 B：买方贷款不获批 → 按合同约定处理（解除或重新融资）
  trigger_issue_ids 应包含贷款审批争点

### 当案件争议焦点为面积差异时：
- 路径 A：面积误差超出合同容忍区间 → 价款调整或部分解除
- 路径 B：面积误差在容忍区间内 → 驳回价款调整诉请

## 输出格式（严格 JSON，不得添加前言或注释）

```json
{
  "paths": [
    {
      "path_id": "path-A",
      "trigger_condition": "法院认定开发商逾期交付且不可抗力抗辩不成立",
      "trigger_issue_ids": ["issue-001", "issue-002"],
      "key_evidence_ids": ["ev-001", "ev-003"],
      "counter_evidence_ids": ["ev-defendant-002"],
      "admissibility_gate": ["ev-001"],
      "result_scope": ["penalty", "damages"],
      "fallback_path_id": "path-B",
      "possible_outcome": "认定逾期交付违约，支持按日计算违约金，驳回解除合同诉请",
      "confidence_interval": {"lower": 0.4, "upper": 0.65},
      "path_notes": "依赖竣工验收备案日期与合同约定交付日期的时间差直接证据",
      "probability": 0.50,
      "probability_rationale": "原告持有竣工备案证明（直接证据），但被告主张政府审批延误（制约因素）。",
      "party_favored": "plaintiff"
    }
  ],
  "blocking_conditions": [
    {
      "condition_id": "bc-001",
      "condition_type": "evidence_gap",
      "description": "不可抗力认定标准存在争议，若行政审批延误被认定为不可抗力将显著影响多条路径概率",
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
