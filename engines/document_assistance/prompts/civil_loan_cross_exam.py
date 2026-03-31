"""
民间借贷（civil_loan）质证意见（cross_exam）LLM 提示模板。
LLM prompt templates for civil loan cross-examination opinion generation.
"""

from __future__ import annotations

from typing import Any, Optional

from engines.shared.models import EvidenceIndex, IssueTree

SYSTEM_PROMPT = """\
你是一名专业的中国民间借贷案件诉讼律师，负责针对对方提交的每一份证据出具质证意见。

你的任务是为证据索引中的每一条证据生成恰好一条质证意见条目。

## 民间借贷质证意见要点

对每份证据，从以下维度评估并给出意见：
- **真实性**：证据是否真实，有无伪造/变造风险
- **合法性**：取证方式是否合法（录音、电子数据等）
- **关联性**：证据是否与本案争点直接相关

### 典型质证要点
- 借条/合同：笔迹鉴定、时间是否倒签、是否补写
- 银行流水：资金用途、是否与借贷关系对应
- 聊天记录/录音：截图是否完整、录音是否经对方同意
- 转账记录：是否为借款还是其他性质的资金往来

## 输出格式
- items：每条对应一个证据 ID，opinion_text 简明具体（不超过 80 字）
- evidence_ids_cited：列出所有质证证据的 ID
- 严格 JSON，不得添加前言或注释
"""


def build_user_prompt(
    *,
    issue_tree: IssueTree,
    evidence_index: EvidenceIndex,
    case_data: dict[str, Any],
    attack_chain: Optional[Any] = None,
) -> str:
    """构建民间借贷质证意见生成的用户 prompt。"""
    case_id = case_data.get("case_id", "unknown")

    ev_lines = []
    all_ev_ids = []
    for ev in evidence_index.evidence:
        ev_lines.append(
            f"  - {ev.evidence_id}: {ev.title} ({ev.evidence_type.value}, "
            f"owner={ev.owner_party_id}, status={ev.status.value})"
        )
        all_ev_ids.append(ev.evidence_id)
    ev_block = "\n".join(ev_lines) if ev_lines else "（无证据）"

    return (
        f"【案件】{case_id}\n"
        f"\n【需要质证的证据（共 {len(evidence_index.evidence)} 条，请每条生成恰好 1 条意见）】\n"
        f"{ev_block}\n"
        f"\n证据 ID 列表（按顺序质证）：{all_ev_ids}\n"
        f"\n请为每条证据生成质证意见，以严格 JSON 格式输出，不要输出任何其他内容。"
    )
