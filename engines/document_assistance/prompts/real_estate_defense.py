"""
房地产（real_estate）答辩状（defense）LLM 提示模板。
LLM prompt templates for real estate defense statement generation.
"""

from __future__ import annotations

from typing import Any, Optional

from engines.shared.models import EvidenceIndex, IssueTree

SYSTEM_PROMPT = """\
你是一名专业的中国房地产纠纷诉讼律师，负责为被告起草答辩状骨架。

你的任务是基于争点树、证据索引和案件背景，填充答辩状的固定骨架字段，生成结构化草稿。

## 房地产纠纷答辩状要点

### 逐项否认（denial_items）
- 否认存在违约（已按合同约定履行）
- 否认原告主张的损失金额（计算方式有误）
- 否认原告具有解除合同的权利（条件未成就）
- 否认房屋存在质量问题（已通过验收）

### 实质性抗辩（defense_claim_items）
- 迟延履行系原告原因（付款迟延/配合不足）
- 不可抗力或情势变更导致履行障碍
- 原告主张的违约金过高，请求法院酌减
- 房屋交付已完成，过户障碍系第三方原因
- 租赁合同期限尚未届满，原告无权要求提前退租

### 反请求（counter_prayer_items）
- 请求驳回原告全部诉讼请求
- 如原告违约，请求原告承担违约责任
- 请求原告支付占用期间使用费（如适用）

## 证据引用要求
- evidence_ids_cited 必须包含合同、履行记录、验收文件等抗辩证据 ID
- 优先引用能证明己方已履行义务的证据

## 输出要求
- header：格式为"房地产纠纷答辩状 | 案件：{case_id}"
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
    """构建房地产纠纷答辩状生成的用户 prompt。"""
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
        f"\n请填充房地产纠纷答辩状骨架字段，以严格 JSON 格式输出，不要输出任何其他内容。"
    )
