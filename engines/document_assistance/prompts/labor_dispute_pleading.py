"""
劳动争议（labor_dispute）起诉状（pleading）LLM 提示模板。
LLM prompt templates for labor dispute pleading draft generation.
"""

from __future__ import annotations

from typing import Any, Optional

from engines.shared.models import EvidenceIndex, IssueTree

SYSTEM_PROMPT = """\
你是一名专业的中国劳动争议案件诉讼律师，负责为劳动者（申请人/原告）起草起诉状/仲裁申请书骨架。

你的任务是基于争点树、证据索引和案件背景，填充劳动争议文书的固定骨架字段，生成结构化草稿。

## 劳动争议起诉状要点

### 事实陈述（fact_narrative_items）
- 劳动关系建立时间、用人单位名称、岗位及职责
- 工资标准、实际发放情况及欠薪情况（如适用）
- 劳动合同签署、续签、终止/解除经过
- 用人单位违法行为（如违法解除、克扣工资、拒付加班费、工伤认定障碍等）
- 仲裁前置程序完成情况

### 法律依据（legal_claim_items）
- 《劳动合同法》相关条款（解除条件、经济补偿、赔偿金）
- 《劳动法》相关条款（工资、工时、休假）
- 《工伤保险条例》（如涉及工伤）
- 社会保险征缴相关规定（如涉及社保欠缴）

### 诉讼请求（prayer_for_relief_items）
- 要求支付欠付工资（具体金额）
- 要求支付经济补偿金/赔偿金（N/2N 计算）
- 要求补缴社会保险（如适用）
- 要求支付工伤赔偿（如适用）

## 证据引用要求
- evidence_ids_cited 必须包含劳动合同、工资条、工作记录等核心证据 ID
- 优先引用用工关系证明证据

## 输出要求
- header：格式为"劳动争议纠纷起诉状 | 案件：{case_id}"
- attack_chain_basis：如有攻击链产物，提炼核心攻击策略；否则填 "unavailable"
- 所有列表条目使用简明中文，每条不超过 100 字
- 严格 JSON，不得添加前言或注释
"""


def build_user_prompt(
    *,
    issue_tree: IssueTree,
    evidence_index: EvidenceIndex,
    case_data: dict[str, Any],
    attack_chain: Optional[Any] = None,
) -> str:
    """构建劳动争议起诉状生成的用户 prompt。"""
    case_id = case_data.get("case_id", "unknown")
    parties = case_data.get("parties", {})
    p_name = parties.get("plaintiff", {}).get("name", "劳动者")
    d_name = parties.get("defendant", {}).get("name", "用人单位")

    issue_lines = []
    for iss in issue_tree.issues:
        issue_lines.append(f"  - {iss.issue_id}: {iss.title} [{iss.issue_type.value}]")
    issues_block = "\n".join(issue_lines) if issue_lines else "（无争点）"

    ev_lines = []
    for ev in evidence_index.evidence[:20]:
        ev_lines.append(
            f"  - {ev.evidence_id}: {ev.title} ({ev.evidence_type.value}, {ev.status.value})"
        )
    ev_block = "\n".join(ev_lines) if ev_lines else "（无证据）"
    if len(evidence_index.evidence) > 20:
        ev_block += f"\n  ... 共 {len(evidence_index.evidence)} 条证据"

    attack_block = "（无攻击链产物）"
    if attack_chain is not None:
        try:
            top = getattr(attack_chain, "top_attacks", [])
            if top:
                attack_block = "\n".join(
                    f"  - {n.attack_node_id}: {n.attack_description}" for n in top[:3]
                )
        except Exception:  # noqa: BLE001
            pass

    return (
        f"【案件】{case_id}\n"
        f"【劳动者（原告）】{p_name}  【用人单位（被告）】{d_name}\n"
        f"\n【争点列表（共 {len(issue_tree.issues)} 条）】\n{issues_block}\n"
        f"\n【证据摘要（共 {len(evidence_index.evidence)} 条）】\n{ev_block}\n"
        f"\n【攻击链核心节点（供策略参考）】\n{attack_block}\n"
        f"\n请填充劳动争议起诉状骨架字段，以严格 JSON 格式输出，不要输出任何其他内容。"
    )
