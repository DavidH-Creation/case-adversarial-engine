"""
法官追问 prompt 模板。
Judge questioning prompt templates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engines.shared.models import (
        BlockingCondition,
        Evidence,
        EvidenceGapItem,
        Issue,
    )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

JUDGE_SYSTEM = """\
你是一位经验丰富的民事审判法官，正在主持庭前会议。

你的职责：
1. 基于已采纳的证据和待审争点，提出关键追问
2. 追问类型包括：
   - clarification（澄清）：要求当事人说明含糊或矛盾之处
   - contradiction（矛盾发现）：指出证据之间或证据与陈述之间的矛盾
   - gap（缺证识别）：指出待证事实缺乏充分证据支持
   - legal_basis（法律依据）：要求当事人说明其主张的法律依据
3. 每个问题必须绑定到具体争点和相关证据
4. 问题按重要性排序（priority 1-10，1 最重要）

重要约束：
- 只输出 JSON 对象，不输出任何解释文字
- 只引用已采纳的证据（admitted_for_discussion），不得引用未采纳证据
- issue_id 和 evidence_ids 必须使用输入中提供的真实 ID
- 最多输出 10 个问题
- 优先关注金额计算争点（calculation_issue）和存在阻断条件的争点
- 保持中立司法立场
"""


# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------


def build_judge_user_prompt(
    issues: list[Issue],
    admitted_evidence: list[Evidence],
    *,
    evidence_gaps: list[EvidenceGapItem] | None = None,
    blocking_conditions: list[BlockingCondition] | None = None,
    plaintiff_party_id: str = "",
    defendant_party_id: str = "",
) -> str:
    """构建法官追问 user prompt。"""
    # 争点列表
    issue_lines = []
    for iss in issues:
        cat = f" [{iss.issue_category.value}]" if iss.issue_category else ""
        status_str = iss.status.value if iss.status else "open"
        issue_lines.append(
            f"- {iss.issue_id}: {iss.title}{cat} (status: {status_str})"
        )
    issue_block = "\n".join(issue_lines) if issue_lines else "（无争点）"

    # 已采纳证据
    ev_lines = []
    for ev in admitted_evidence:
        ev_lines.append(
            f"- {ev.evidence_id}: {ev.title} "
            f"(owner: {ev.owner_party_id}, issues: {ev.target_issue_ids})"
        )
    ev_block = "\n".join(ev_lines) if ev_lines else "（无已采纳证据）"

    # 可选增强：证据缺口
    gap_block = ""
    if evidence_gaps:
        gap_lines = []
        for g in evidence_gaps:
            gap_lines.append(
                f"- {g.gap_id}: {g.gap_description} "
                f"(related_issue: {g.related_issue_id})"
            )
        gap_block = f"\n\n## 证据缺口\n" + "\n".join(gap_lines)

    # 可选增强：阻断条件
    bc_block = ""
    if blocking_conditions:
        bc_lines = []
        for bc in blocking_conditions:
            bc_lines.append(
                f"- {bc.condition_id}: {bc.description} "
                f"(type: {bc.condition_type.value}, "
                f"issues: {bc.linked_issue_ids})"
            )
        bc_block = f"\n\n## 阻断条件\n" + "\n".join(bc_lines)

    # 当事人信息
    party_block = ""
    if plaintiff_party_id or defendant_party_id:
        party_block = (
            f"\n\n## 当事人\n"
            f"- 原告: {plaintiff_party_id}\n"
            f"- 被告: {defendant_party_id}"
        )

    return f"""\
请基于以下庭前会议材料，提出关键追问。

## 争点列表
{issue_block}

## 已采纳证据
{ev_block}{gap_block}{bc_block}{party_block}

## 输出格式
请严格输出如下 JSON（不要输出其他内容）：
```json
{{
  "questions": [
    {{
      "question_id": "jq-001",
      "issue_id": "争点ID",
      "evidence_ids": ["相关证据ID"],
      "question_text": "追问内容",
      "target_party_id": "被追问方party_id",
      "question_type": "clarification|contradiction|gap|legal_basis",
      "priority": 1
    }}
  ]
}}
```

要求：
- 最多 10 个问题，按 priority 从高到低排序（1 最重要）
- 优先关注金额计算争点和阻断条件相关争点
- evidence_ids 只能使用上面列出的已采纳证据 ID
- issue_id 只能使用上面列出的争点 ID
- target_party_id 使用实际的 party_id
"""
