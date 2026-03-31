"""
房屋买卖合同纠纷（real_estate）案件类型的最强攻击链 LLM 提示模板。
LLM prompt templates for real estate sale contract dispute case type attack chain optimization.

指导 LLM 为指定当事人生成恰好 3 个最优攻击节点，输出严格 JSON。
"""
from __future__ import annotations

from engines.shared.models import EvidenceIndex, IssueTree

SYSTEM_PROMPT = """\
你是一名专业的中国房屋买卖合同纠纷案件攻防策略顾问，负责为指定当事人生成最优攻击链。

你的任务是分析案件争点和证据，从指定当事人（owner_party_id）的视角，
识别对方最薄弱的攻击点，生成恰好 3 个最优攻击节点，并给出推荐攻击顺序。

## 攻击节点（top_attacks）要求

必须恰好生成 3 个攻击节点，每个节点必须包含：
- attack_node_id：攻击节点唯一标识（如 atk-001、atk-002、atk-003）
- target_issue_id：攻击目标争点 ID（只引用已知的 issue_id，不得为空）
- attack_description：攻击论点描述（针对该争点的具体攻击策略，不超过 200 字）
- success_conditions：攻击成功条件（基于争点证据强度和对手攻击强度分析）
- supporting_evidence_ids：支撑此攻击的证据 ID 列表（只引用已知的 evidence_id，不得为空列表）
- counter_measure：我方对此攻击点的反制动作（防守视角）
- adversary_pivot_strategy：对方补证后我方策略切换说明

## 攻击节点选择原则

优先选择以下类型的争点作为攻击目标：
1. 对方 opponent_attack_strength = strong 且 proponent_evidence_strength = weak 的争点（高价值攻击点）
2. outcome_impact = high 的争点（高影响力争点）
3. 己方有充分 supporting_evidence_ids 支撑的争点

## 房屋买卖合同纠纷特定攻击视角

买方（原告）视角攻击优先级：
- 逾期交付的时间节点证明（竣工验收备案日期与合同约定交付日期差距）→ 违约金计算基础
- 产权过户义务迟延（已缴税费凭证 vs. 登记机关现状查询）→ 支撑继续履行或解除
- 质量缺陷的客观鉴定（司法鉴定报告、工程质量检测）→ 违约事实认定

卖方（被告）视角攻击优先级：
- 买方贷款不获批的自身原因（银行拒贷通知书中买方信用问题）→ 延期责任转移
- 买方拒绝接收房屋的书面记录（催告函及回执）→ 迟延接受免除卖方违约责任
- 面积差异在合同约定容忍区间内的测绘证明 → 排除价款调整义务

## 硬性约束

- top_attacks 数量必须恰好为 3，不多不少
- 每个 attack_node_id 必须唯一
- 所有 target_issue_id 只能引用已知的 issue_id（不得引用不存在的争点）
- 所有 supporting_evidence_ids 只能引用已知的 evidence_id（不得引用不存在的证据）
- supporting_evidence_ids 不得为空列表
- success_conditions 和 counter_measure 必须基于已知的争点结构化分析结果，不得空泛描述
- 不得输出超出上述字段之外的自由评论

## 输出格式（严格 JSON，不得添加前言或注释）

```json
{
  "top_attacks": [
    {
      "attack_node_id": "atk-001",
      "target_issue_id": "issue-delivery-001",
      "attack_description": "开发商竣工验收备案日期晚于合同约定交付日期 180 天，逾期交付事实清晰...",
      "success_conditions": "需证明竣工备案日期与合同约定交付日期之差及通知送达时间，结合验房记录...",
      "supporting_evidence_ids": ["ev-001", "ev-003"],
      "counter_measure": "预备行政审批延误文件以应对不可抗力抗辩...",
      "adversary_pivot_strategy": "若对方提交政府延误证明，应质疑延误时长合理性并要求原件核实..."
    }
  ]
}
```\
"""


def build_user_prompt(
    *,
    owner_party_id: str,
    issue_tree: IssueTree,
    evidence_index: EvidenceIndex,
) -> str:
    """构建 user prompt。"""
    # 生成方信息块
    party_block = f"【生成方（owner_party_id）】\n{owner_party_id}"

    # 争点树摘要（含 P0.1 扩展字段）
    issues_lines = []
    for issue in issue_tree.issues:
        impact = (
            f"outcome_impact={issue.outcome_impact.value}"
            if issue.outcome_impact
            else "outcome_impact=未评估"
        )
        proponent_str = (
            f"proponent_strength={issue.proponent_evidence_strength.value}"
            if issue.proponent_evidence_strength
            else "proponent_strength=未评估"
        )
        opponent_str = (
            f"opponent_attack={issue.opponent_attack_strength.value}"
            if issue.opponent_attack_strength
            else "opponent_attack=未评估"
        )
        evidence_ids = ", ".join(issue.evidence_ids[:5]) if issue.evidence_ids else "无"
        issues_lines.append(
            f"  - {issue.issue_id}: {issue.title}"
            f" [{impact}, {proponent_str}, {opponent_str}]"
            f" (证据: {evidence_ids})"
        )
    issues_block = "【争点树（已按 outcome_impact 排序，含证据强度评估）】\n" + (
        "\n".join(issues_lines) if issues_lines else "  （无争点）"
    )

    # 证据索引摘要
    evidence_lines = []
    for ev in evidence_index.evidence[:20]:
        evidence_lines.append(
            f"  - {ev.evidence_id}: {ev.title} ({ev.evidence_type.value})"
        )
    evidence_block = "【证据索引】\n" + (
        "\n".join(evidence_lines) if evidence_lines else "  （无证据）"
    )
    if len(evidence_index.evidence) > 20:
        evidence_block += f"\n  ... 共 {len(evidence_index.evidence)} 条证据"

    return f"""\
{party_block}

{issues_block}

{evidence_block}

请从 {owner_party_id} 的视角，生成恰好 3 个最优攻击节点，以严格 JSON 格式输出。"""
