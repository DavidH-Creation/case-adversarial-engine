"""
房屋买卖合同纠纷（real_estate）案件类型的争点影响排序 LLM 提示模板。
LLM prompt templates for real estate sale contract dispute case type issue impact ranking.

指导 LLM 对每个争点从十个维度进行结构化评估，输出严格 JSON。
Guides LLM to evaluate each issue on 10 dimensions and output strict JSON.
"""

from __future__ import annotations

from engines.shared.few_shot_examples import load_few_shot_text
from typing import Optional

from engines.shared.models import AmountConsistencyCheck, EvidenceIndex, IssueTree

_BASE_SYSTEM_PROMPT = """\
你是一名专业的中国房屋买卖合同纠纷案件法律分析助手，负责对案件争点进行结构化影响评估。

你的任务是对每个争点从以下十个维度进行评估：

## 分类维度（1-5）
1. outcome_impact：该争点对最终裁判结果的影响程度
   允许值：high / medium / low
2. impact_targets：该争点影响的诉请对象（可多选）
   允许值：specific_performance / refund / liquidated_damages / damages / credibility
   说明：
   - specific_performance 继续履行：要求过户、交付房屋、办理产权登记等履行之诉
   - refund 返还房款：解除合同后返还已付购房款（含定金、首付款、按揭款）
   - liquidated_damages 违约金：合同约定的违约金（法释〔2003〕7号关于审理商品房买卖合同纠纷案件适用法律若干问题的解释）
   - damages 赔偿损失：差价损失、装修损失、迟延履行损失等其他损害赔偿
   - credibility 可信度：争点结果对当事人陈述/证据可信度的冲击
3. proponent_evidence_strength：主张方（举证责任承担方）在该争点的当前证据强度
   允许值：strong / medium / weak
   约束：必须在 proponent_evidence_ids 中引用至少一条具体证据 ID
4. opponent_attack_strength：反对方在该争点的攻击强度
   允许值：strong / medium / weak
   约束：必须在 opponent_attack_evidence_ids 中引用至少一条具体证据 ID
5. recommended_action：系统建议行动
   允许值：supplement_evidence / amend_claim / abandon / explain_in_trial
   约束：recommended_action_basis 必须非空，且在 recommended_action_evidence_ids 中引用至少一条证据 ID

## 评分维度（6-10）—— 必须使用 0-100 量纲，不得使用 0-10
6. importance_score (0-100)：该争点对最终裁判结果的法律关键程度
   - 100 = 该争点是判决的核心法律要件
   - 0 = 对判决无影响
   - 房产纠纷中：交付义务履行、产权过户义务、合同效力争点通常 ≥ 80
   - 违约金金额争点通常 60-75（影响赔偿额但不影响责任认定）
   - 辅助性/背景事实争点通常 ≤ 40
7. swing_score (0-100)：该争点的双方争议烈度
   - 核心定义：衡量双方当事人对该争点存在多大实质性对立
   - 100 = 双方对此争点存在根本性对立，且结论翻转将直接决定判决走向
   - 0 = 双方对此争点基本不争议
8. evidence_strength_gap (-100 to +100)：主张方证据优势度
   - 正值 = 主张方占优；负值 = 反对方攻击占优；0 = 均势
9. dependency_depth (整数 ≥ 0)：争点依赖层级
   - 0 = 根争点；1 = 依赖一个上游争点；2+ = 多层派生争点
   - 硬性规则：有 parent_issue_id 的争点 depth 必须 ≥ 1
10. credibility_impact (0-100)：该争点对整案可信度的冲击
    - 100 = 若此争点对当事人不利，整案可信度崩塌
    - 0 = 不影响整案可信度

重要量纲提示：所有评分必须使用 0-100 量纲。请使用完整区间，不要压缩到 0-10。
房产纠纷核心争点（合同效力、交付义务）应 ≥ 70，辅助争点应 ≤ 40。

硬性约束（违反则输出无效）：
- 分类维度（1-5）必须使用以上枚举值，不得使用自由文本
- 评分维度（6-10）必须为整数且在指定范围内
- 所有 evidence_ids 字段只能引用案件证据清单中已知的 evidence_id
- evaluations 数组与输入争点列表一一对应

## 输出格式（严格遵守，违反则输出无效）

你必须输出且仅输出一个 JSON 对象。每条评估必须是**平铺结构**（所有字段在同一层级）。

```json
{
  "evaluations": [
    {
      "issue_id": "issue-xxx-001",
      "outcome_impact": "high",
      "impact_targets": ["specific_performance", "liquidated_damages"],
      "proponent_evidence_strength": "strong",
      "proponent_evidence_ids": ["evidence-plaintiff-001"],
      "opponent_attack_strength": "medium",
      "opponent_attack_evidence_ids": ["evidence-defendant-001"],
      "recommended_action": "explain_in_trial",
      "recommended_action_basis": "建议庭审中详细说明竣工验收备案日期的法律意义",
      "recommended_action_evidence_ids": ["evidence-plaintiff-001"],
      "importance_score": 85,
      "swing_score": 75,
      "evidence_strength_gap": 30,
      "dependency_depth": 0,
      "credibility_impact": 20
    }
  ]
}
```

禁止：
- 添加 title / dimensions / scores / rationale 等额外字段
- 使用嵌套对象
- 添加任何前言、说明、markdown 标题或注释\
"""

# Unit 22 Phase C.5b: load real-estate-specific few-shot examples so the
# example impact_targets stay in lock-step with ALLOWED_IMPACT_TARGETS below.
# The shared "issue_impact_ranker" file was civil_loan-specific and would have
# contradicted this module's vocabulary line — see civil_loan.py for context.
SYSTEM_PROMPT = _BASE_SYSTEM_PROMPT + load_few_shot_text(
    "issue_impact_ranker.real_estate"
)

# Unit 22 Phase C.5b: real-estate (商品房买卖合同纠纷) legal vocabulary for
# Issue.impact_targets. Anchored to 民法典 合同编 + 法释〔2003〕7号 关于审理
# 商品房买卖合同纠纷案件适用法律若干问题的解释, which classifies real-estate
# disputes' relief into 继续履行 / 返还房款 / 违约金 / 赔偿损失. credibility
# is the case-type-neutral pivot. The set MUST stay in lock-step with the
# "允许值" line of the system prompt above and with the example JSON's
# impact_targets.
ALLOWED_IMPACT_TARGETS: frozenset[str] = frozenset(
    {
        "specific_performance",
        "refund",
        "liquidated_damages",
        "damages",
        "credibility",
    }
)


def build_user_prompt(
    *,
    issue_tree: IssueTree,
    evidence_index: EvidenceIndex,
    proponent_party_id: str,
    amount_check: Optional[AmountConsistencyCheck] = None,
) -> str:
    """构建用于争点影响评估的用户 prompt。
    Build user prompt for issue impact evaluation.

    Args:
        issue_tree:          待评估的争点树
        evidence_index:      证据索引（提供已知证据 ID 列表）
        proponent_party_id:  主张方 party_id（告知 LLM 举证责任方）
        amount_check:        P0.2 金额一致性校验结果（案件无金额数据时为 None）
    """
    # 争点块
    issue_lines: list[str] = []
    for issue in issue_tree.issues:
        evidence_ids_str = ", ".join(issue.evidence_ids) if issue.evidence_ids else "（无关联证据）"
        burden_ids_str = ", ".join(issue.burden_ids) if issue.burden_ids else "（无）"
        parent_str = (
            f"\n  parent_issue_id: {issue.parent_issue_id}"
            if issue.parent_issue_id
            else "\n  parent_issue_id: （无，根争点）"
        )
        if issue.fact_propositions:
            total_fp = len(issue.fact_propositions)
            disputed_fp = sum(1 for fp in issue.fact_propositions if fp.status.value == "disputed")
            supported_fp = sum(
                1 for fp in issue.fact_propositions if fp.status.value == "supported"
            )
            dispute_ratio_str = (
                f"{disputed_fp}/{total_fp} 条命题存在争议，"
                f"{supported_fp}/{total_fp} 条已有证据支撑（无争议）"
            )
        else:
            dispute_ratio_str = "无事实命题记录"
        issue_lines.append(
            f"  issue_id: {issue.issue_id}\n"
            f"  title: {issue.title}\n"
            f"  type: {issue.issue_type.value}\n"
            f"  evidence_ids: [{evidence_ids_str}]\n"
            f"  burden_ids: [{burden_ids_str}]\n"
            f"  fact_dispute_ratio: {dispute_ratio_str}"
            f"{parent_str}"
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
    if amount_check is not None:
        amount_block = (
            f"  verdict_block_active: {amount_check.verdict_block_active}\n"
            f"  principal_base_unique: {amount_check.principal_base_unique}\n"
            f"  all_repayments_attributed: {amount_check.all_repayments_attributed}\n"
            f"  unresolved_conflicts 数量: {len(amount_check.unresolved_conflicts)} 条"
        )
        verdict_hint = (
            "\n  ⚠️  注意：verdict_block_active=True，与合同价款、违约金、损失赔偿相关的争点"
            "通常应评估为 outcome_impact=high。"
            if amount_check.verdict_block_active
            else ""
        )
    else:
        amount_block = "  （本案无金额计算数据，跳过金额一致性校验）"
        verdict_hint = ""

    return (
        f"【案件基本信息】\n"
        f"case_id: {issue_tree.case_id}\n"
        f"主张方（举证责任承担方）party_id: {proponent_party_id}\n"
        f"\n【争点列表（共 {len(issue_tree.issues)} 条）】\n{issues_block}\n"
        f"\n【证据清单（共 {len(evidence_index.evidence)} 条）】\n{evidence_block}\n"
        f"\n【金额一致性状态（P0.2 结果）】\n{amount_block}{verdict_hint}\n"
        f"\n请对以上每个争点进行十维度评估，输出严格 JSON（顶层键必须为 evaluations）。"
    )
