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
- key_evidence_ids：**仅包含支持本路径结论的证据** ID 列表（只引用已知的 evidence_id）
- counter_evidence_ids：**与本路径结论相悖的证据** ID 列表——即那些挑战、反驳或削弱本路径结论的证据（只引用已知的 evidence_id，可为空列表）
- possible_outcome：本路径下法院可能的裁判结果（具体到诉请支持情况，不超过 200 字）
- confidence_interval：置信度区间（lower/upper，均为 [0,1] 之间的浮点数；若系统提示标注 verdict_block_active=true，则此字段设为 null）
- path_notes：路径说明或注意事项（可为空字符串）
- admissibility_gate：本路径成立的前提——哪些证据必须被法庭采信（evidence_id 列表）
- result_scope：裁判范围标签列表（可多选：principal / interest / penalty / liability_allocation / credibility / attorney_fee / costs）
- fallback_path_id：若本路径关键证据未被采信或争点结论不利，降级到哪条路径的 path_id（最后一条路径可为空字符串）
- probability：本路径在当前证据状态下的触发概率（0.0-1.0 浮点数）；综合评估以下因素：① 支撑证据数量与质量（直接证据 vs 间接证据）；② 关键阻断条件能否被满足；③ 法律先例与裁判口径的对齐度；④ 争点树中高影响力争点的分布
- probability_rationale：概率评估依据（1-2 句话，说明主要支撑因素和制约因素）
- party_favored：本路径结果对哪方更有利，枚举值之一：plaintiff（对原告有利）/ defendant（对被告有利）/ neutral（中性）

## 证据极性规则（Evidence Polarity）—— 最高优先级

**key_evidence_ids 与 counter_evidence_ids 的区别是本模块最核心的正确性约束，违反将导致错误的裁判分析。**

- `key_evidence_ids`：**仅放支持本路径结论的证据**。若一条证据的内容/结论与本路径的 trigger_condition 或 possible_outcome 相悖，绝对不得列入 key_evidence_ids。
- `counter_evidence_ids`：放置**反驳或削弱本路径结论**的证据。被告方提交的、用于驳斥原告主张的证据，若本路径倾向支持原告，则该类证据通常属于 counter_evidence_ids。
- **党派对齐原则**：若本路径结论有利于原告，则被告证据中主动反驳该结论的证据（如证明"三方未曾会面"的证据）应归入 counter_evidence_ids，而非 key_evidence_ids；反之亦然。例外：对方当事人作出的不利于己的自认（admission against interest）可列入 key_evidence_ids。
- key_evidence_ids 与 counter_evidence_ids **不得有重叠**。

## 严格非空约束（违反则路径无效）—— 最高优先级

**trigger_issue_ids 和 key_evidence_ids 是必填字段，绝对不能为空列表。**

- 每条 path 的 trigger_issue_ids 必须包含至少 1 个 issue_id — 空列表 = 无效路径
- 每条 path 的 key_evidence_ids 必须包含至少 1 个 evidence_id — 空列表 = 无效路径
- 若 verdict_block_active=false，每条 path 必须给出 confidence_interval（lower/upper 均为浮点数）
- 不得返回 trigger_issue_ids: [] 或 key_evidence_ids: [] 的路径

示例（借款人主体争议案，原告有利路径）：
```json
{
  "path_id": "path-A",
  "trigger_condition": "法院认定借贷关系在原告与被告之间成立",
  "trigger_issue_ids": ["issue-001", "issue-002"],
  "key_evidence_ids": ["ev-plaintiff-001", "ev-plaintiff-002"],
  "counter_evidence_ids": ["ev-defendant-003", "ev-defendant-006"],
  "possible_outcome": "支持原告全部诉请，判令被告偿还本金20万元及利息"
}
```
注意：ev-defendant-003 和 ev-defendant-006 是被告方提出的反驳证据，不得列入 key_evidence_ids。

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

请根据争点树的实际争议焦点判断适用哪种路径模板：

### 当案件争议焦点为金额/还款时：
- 路径 A：争议款项认定计入还款 → 较低未还本金 → 利率支持（LPR 4 倍上限）
  trigger_issue_ids 应包含还款认定争点
- 路径 B：争议款项不认定计入还款 → 较高未还本金 → 违约金与利息择一
  trigger_issue_ids 应包含本金基数争点
- 若本金基数存在口径冲突，建议增加路径 C（以某一口径为基准的中间路径）

### 当案件争议焦点为借款人主体认定时：
- 路径 A：收款人为适格借款人（借贷合意成立）→ 全额/部分支持原告
  trigger_issue_ids 应包含借贷合意争点、借款人主体争点
  key_evidence_ids 应包含转账记录、借款合意相关证据
- 路径 B：收款人非借款人（代收代付/指示付款关系）→ 驳回原告
  trigger_issue_ids 应包含款项性质争点、账户控制争点
  key_evidence_ids 应包含代付证据、第三方证言
- 路径 C：三方关系下共同借款/连带责任 → 部分支持
  trigger_issue_ids 应包含三方关系争点
- 路径 D：程序性不利推定 → 因妨碍诉讼行为影响证据采信
  trigger_issue_ids 应包含程序性争点
  admissibility_gate 应包含被质疑的证据 ID

## 输出格式（严格 JSON，不得添加前言或注释）

```json
{
  "paths": [
    {
      "path_id": "path-A",
      "trigger_condition": "法院认定收款人与原告之间存在借贷合意",
      "trigger_issue_ids": ["issue-001", "issue-002"],
      "key_evidence_ids": ["ev-001", "ev-003"],
      "counter_evidence_ids": ["ev-defendant-002", "ev-defendant-006"],
      "admissibility_gate": ["ev-001"],
      "result_scope": ["principal", "interest"],
      "fallback_path_id": "path-C",
      "possible_outcome": "全额支持原告——认定借贷关系成立，判令被告偿还借款本金及利息",
      "confidence_interval": {"lower": 0.3, "upper": 0.6},
      "path_notes": "依赖原告转账凭证与借贷合意的直接证据；counter_evidence_ids 中的被告证据系对本路径结论的反驳",
      "probability": 0.45,
      "probability_rationale": "原告持有直接转账凭证（直接证据），但借贷合意缺少书面合同支撑（制约因素），综合评估概率中等偏下。",
      "party_favored": "plaintiff"
    }
  ],
  "blocking_conditions": [
    {
      "condition_id": "bc-001",
      "condition_type": "evidence_gap",
      "description": "录音证据可采性存疑，若被排除将影响多条路径的触发条件",
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
