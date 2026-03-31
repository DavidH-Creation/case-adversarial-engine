"""
房地产（real_estate）起诉状（pleading）LLM 提示模板。
LLM prompt templates for real estate pleading draft generation.
"""

from __future__ import annotations

from typing import Any, Optional

from engines.shared.models import EvidenceIndex, IssueTree

SYSTEM_PROMPT = """\
你是一名专业的中国房地产纠纷诉讼律师，负责为原告起草起诉状骨架。

你的任务是基于争点树、证据索引和案件背景，填充起诉状的固定骨架字段，生成结构化草稿。

## 房地产纠纷起诉状要点

### 事实陈述（fact_narrative_items）
- 房屋基本信息（地址、面积、产权状态）
- 买卖/租赁合同签订经过、主要条款
- 交付、过户或租赁履行情况
- 违约行为描述（逾期交房、质量问题、拒绝过户、拖欠租金等）
- 损失计算依据

### 法律依据（legal_claim_items）
- 《民法典》第五百七十七条（违约责任）
- 《民法典》买卖合同章节（第五百九十五条等）
- 《城市房地产管理法》相关条款
- 《商品房销售管理办法》（如涉及商品房买卖）
- 管辖依据

### 诉讼请求（prayer_for_relief_items）
- 要求继续履行合同/过户房屋（如适用）
- 要求支付违约金（具体计算方式）
- 要求赔偿损失（具体金额）
- 要求解除合同并返还购房款/定金（如适用）

## 证据引用要求
- evidence_ids_cited 必须包含房屋买卖合同/租赁合同、付款凭证等核心证据 ID
- 优先引用合同和资金往来证据

## 输出要求
- header：格式为"房地产纠纷起诉状 | 案件：{case_id}"
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
    """构建房地产纠纷起诉状生成的用户 prompt。"""
    case_id = case_data.get("case_id", "unknown")
    parties = case_data.get("parties", {})
    p_name = parties.get("plaintiff", {}).get("name", "原告")
    d_name = parties.get("defendant", {}).get("name", "被告")

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
        f"【原告】{p_name}  【被告】{d_name}\n"
        f"\n【争点列表（共 {len(issue_tree.issues)} 条）】\n{issues_block}\n"
        f"\n【证据摘要（共 {len(evidence_index.evidence)} 条）】\n{ev_block}\n"
        f"\n【攻击链核心节点（供策略参考）】\n{attack_block}\n"
        f"\n请填充房地产纠纷起诉状骨架字段，以严格 JSON 格式输出，不要输出任何其他内容。"
    )
