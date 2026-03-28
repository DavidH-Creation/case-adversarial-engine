"""
民间借贷案件质证 prompt 模板。
Civil loan cross-examination prompt templates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engines.shared.models import Evidence, IssueTree


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

CROSS_EXAM_SYSTEM = """\
你是一位资深民事诉讼代理律师，正在参加庭前会议的质证环节。

你的职责：
1. 对对方提交的每一条证据，从四个维度进行质证：
   - authenticity（真实性）：证据是否真实，来源是否可靠
   - relevance（关联性）：证据与争点是否有关联
   - legality（合法性）：证据取得方式是否合法
   - probative_value（证明力）：证据对待证事实的证明程度
2. 对每个维度给出结论：accepted（认可）、challenged（不认可）、reserved（保留意见）
3. 结论必须附理由

重要约束：
- 只输出 JSON 对象，不输出任何解释文字
- evidence_id 和 issue_ids 必须使用输入中提供的真实 ID，不得编造
- 每条证据应尽量覆盖全部四个维度
"""


# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------


def build_cross_exam_user_prompt(
    evidences: list[Evidence],
    issue_tree: IssueTree,
    examiner_role: str,
) -> str:
    """构建质证 user prompt。

    Args:
        evidences:     待质证的证据列表（对方 submitted 的证据）
        issue_tree:    争点树
        examiner_role: 质证方角色描述（如 "被告代理律师"）
    """
    # 争点摘要
    issue_lines = []
    for iss in issue_tree.issues:
        issue_lines.append(f"- {iss.issue_id}: {iss.title}")
    issue_block = "\n".join(issue_lines) if issue_lines else "（无争点）"

    # 证据清单
    ev_lines = []
    for ev in evidences:
        ev_lines.append(
            f"- evidence_id: {ev.evidence_id}\n"
            f"  title: {ev.title}\n"
            f"  summary: {ev.summary}\n"
            f"  target_issue_ids: {ev.target_issue_ids}"
        )
    ev_block = "\n".join(ev_lines) if ev_lines else "（无证据）"

    return f"""\
你作为{examiner_role}，请对以下对方提交的证据逐一进行质证。

## 争点列表
{issue_block}

## 待质证证据
{ev_block}

## 输出格式
请严格输出如下 JSON（不要输出其他内容）：
```json
{{
  "opinions": [
    {{
      "evidence_id": "证据ID",
      "issue_ids": ["关联争点ID"],
      "dimension": "authenticity|relevance|legality|probative_value",
      "verdict": "accepted|challenged|reserved",
      "reasoning": "质证理由（50字以内）"
    }}
  ]
}}
```

要求：
- 每条证据应覆盖四个维度（authenticity, relevance, legality, probative_value）
- evidence_id 和 issue_ids 必须使用上面列出的真实 ID
- reasoning 应具体，不得空泛
"""
