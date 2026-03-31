"""
民间借贷（civil_loan）答辩状（defense）LLM 提示模板。
LLM prompt templates for civil loan defense statement generation.
"""

from __future__ import annotations

from typing import Any, Optional

from engines.shared.models import EvidenceIndex, IssueTree

SYSTEM_PROMPT = """\
你是一名专业的中国民间借贷案件诉讼律师，负责为被告起草答辩状骨架。

你的任务是基于争点树、证据索引和案件背景，填充答辩状的固定骨架字段，生成结构化草稿。

## 民间借贷案件答辩状要点

### 逐项否认（denial_items）
- 否认借贷关系成立（如适用）：无书面借条或借条存疑
- 否认借款金额（如存在争议）：实际交付金额与诉称不符
- 否认约定利率（如超出法定利率上限）

### 实质性抗辩（defense_claim_items）
- 实际借款人并非被告（主体争议）
- 款项已全部或部分归还（有流水证明）
- 借款合同因违反法律强制性规定无效
- 诉讼时效已届满
- 原告存在欺诈/胁迫导致合同可撤销

### 反请求（counter_prayer_items）
- 请求驳回原告全部诉讼请求
- 请求确认借款已全部清偿（如有还款证据）
- 如有超额利息，请求返还多付利息

## 证据引用要求
- evidence_ids_cited 必须包含支持抗辩主张的证据 ID
- 优先引用还款记录、资金流向、第三方证明等抗辩证据

## 输出要求
- header：格式为"民间借贷纠纷答辩状 | 案件：{case_id}"
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
    """构建民间借贷答辩状生成的用户 prompt。"""
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

    return (
        f"【案件】{case_id}\n"
        f"【原告】{p_name}  【被告】{d_name}\n"
        f"\n【争点列表（共 {len(issue_tree.issues)} 条）】\n{issues_block}\n"
        f"\n【证据摘要（共 {len(evidence_index.evidence)} 条）】\n{ev_block}\n"
        f"\n请填充答辩状骨架字段，以严格 JSON 格式输出，不要输出任何其他内容。"
    )
