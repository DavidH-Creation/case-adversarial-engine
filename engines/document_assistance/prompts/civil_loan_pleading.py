"""
民间借贷（civil_loan）起诉状（pleading）LLM 提示模板。
LLM prompt templates for civil loan pleading draft generation.
"""

from __future__ import annotations

from typing import Any, Optional

from engines.shared.models import EvidenceIndex, IssueTree

SYSTEM_PROMPT = """\
你是一名专业的中国民间借贷案件诉讼律师，负责为原告起草起诉状骨架。

你的任务是基于争点树、证据索引和案件背景，填充起诉状的固定骨架字段，生成结构化草稿。

## 民间借贷案件起诉状要点

### 事实陈述（fact_narrative_items）
- 借款合意成立的时间、地点、金额
- 资金交付方式（银行转账/现金）及凭证
- 约定利率/利息条款（如有）
- 还款期限及逾期情况
- 催告还款经过

### 法律依据（legal_claim_items）
- 《民法典》第六百七十五条（借款人返还借款义务）
- 《民法典》第六百八十条（禁止高利贷规定）
- 如涉及担保，引用担保相关条款
- 管辖依据

### 诉讼请求（prayer_for_relief_items）
- 主张返还借款本金（具体金额）
- 主张支付利息（计算方式）
- 主张承担诉讼费用

## 证据引用要求
- evidence_ids_cited 必须包含直接支持事实陈述的证据 ID
- 优先引用借条/合同、银行流水、催款记录等核心证据

## 输出要求
- header：格式为"民间借贷纠纷起诉状 | 案件：{case_id}"
- attack_chain_basis：如有攻击链产物，提炼核心攻击策略依据；否则填 "unavailable"
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
    """构建民间借贷起诉状生成的用户 prompt。"""
    case_id = case_data.get("case_id", "unknown")
    parties = case_data.get("parties", {})
    p_name = parties.get("plaintiff", {}).get("name", "原告")
    d_name = parties.get("defendant", {}).get("name", "被告")

    # 争点块
    issue_lines = []
    for iss in issue_tree.issues:
        issue_lines.append(f"  - {iss.issue_id}: {iss.title} [{iss.issue_type.value}]")
    issues_block = "\n".join(issue_lines) if issue_lines else "（无争点）"

    # 证据块（前 20 条）
    ev_lines = []
    for ev in evidence_index.evidence[:20]:
        ev_lines.append(
            f"  - {ev.evidence_id}: {ev.title} ({ev.evidence_type.value}, {ev.status.value})"
        )
    ev_block = "\n".join(ev_lines) if ev_lines else "（无证据）"
    if len(evidence_index.evidence) > 20:
        ev_block += f"\n  ... 共 {len(evidence_index.evidence)} 条证据"

    # 攻击链摘要（可选）
    attack_block = "（无攻击链产物）"
    if attack_chain is not None:
        try:
            top = getattr(attack_chain, "top_attacks", [])
            if top:
                top_strs = [f"{n.attack_node_id}: {n.attack_description}" for n in top[:3]]
                attack_block = "\n".join(f"  - {s}" for s in top_strs)
        except Exception:  # noqa: BLE001
            pass

    return (
        f"【案件】{case_id}\n"
        f"【原告】{p_name}  【被告】{d_name}\n"
        f"\n【争点列表（共 {len(issue_tree.issues)} 条）】\n{issues_block}\n"
        f"\n【证据摘要（共 {len(evidence_index.evidence)} 条）】\n{ev_block}\n"
        f"\n【攻击链核心节点（供策略参考）】\n{attack_block}\n"
        f"\n请填充起诉状骨架字段，以严格 JSON 格式输出，不要输出任何其他内容。"
    )
