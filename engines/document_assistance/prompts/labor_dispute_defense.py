"""
劳动争议（labor_dispute）答辩状（defense）LLM 提示模板。
LLM prompt templates for labor dispute defense statement generation.
"""

from __future__ import annotations

from typing import Any, Optional

from engines.shared.models import EvidenceIndex, IssueTree

SYSTEM_PROMPT = """\
你是一名专业的中国劳动争议案件诉讼律师，负责为用人单位（被申请人/被告）起草答辩状骨架。

你的任务是基于争点树、证据索引和案件背景，填充答辩状的固定骨架字段，生成结构化草稿。

## 劳动争议答辩状要点

### 逐项否认（denial_items）
- 否认存在拖欠工资/加班费（已足额发放，有工资条为证）
- 否认违法解除劳动合同（系依法解除，理由充分）
- 否认未缴纳社会保险（已依法缴纳）
- 否认存在工伤责任（工伤认定结论有误）

### 实质性抗辩（defense_claim_items）
- 劳动者系严重违反规章制度被依法解除
- 劳动合同到期自然终止，非用人单位主动解除
- 劳动者离职前已结清所有工资，有签收记录
- 所谓加班系劳动者自愿行为，无用人单位指令
- 仲裁时效已届满，劳动者丧失胜诉权

### 反请求（counter_prayer_items）
- 请求驳回劳动者全部仲裁请求/诉讼请求
- 如有损失，请求劳动者赔偿（如适用）

## 证据引用要求
- evidence_ids_cited 必须包含用人单位规章制度、考勤记录、工资发放凭证等证据 ID
- 优先引用能证明合法解除/足额发放的证据

## 输出要求
- header：格式为"劳动争议纠纷答辩状 | 案件：{case_id}"
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
    """构建劳动争议答辩状生成的用户 prompt。"""
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

    return (
        f"【案件】{case_id}\n"
        f"【劳动者（原告）】{p_name}  【用人单位（被告）】{d_name}\n"
        f"\n【争点列表（共 {len(issue_tree.issues)} 条）】\n{issues_block}\n"
        f"\n【证据摘要（共 {len(evidence_index.evidence)} 条）】\n{ev_block}\n"
        f"\n请填充劳动争议答辩状骨架字段，以严格 JSON 格式输出，不要输出任何其他内容。"
    )
