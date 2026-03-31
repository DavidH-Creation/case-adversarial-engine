"""
劳动争议（labor_dispute）质证意见（cross_exam）LLM 提示模板。
LLM prompt templates for labor dispute cross-examination opinion generation.
"""

from __future__ import annotations

from typing import Any, Optional

from engines.shared.models import EvidenceIndex, IssueTree

SYSTEM_PROMPT = """\
你是一名专业的中国劳动争议案件诉讼律师，负责针对对方提交的每一份证据出具质证意见。

你的任务是为证据索引中的每一条证据生成恰好一条质证意见条目。

## 劳动争议质证意见要点

对每份证据，从以下维度评估并给出意见：
- **真实性**：证据是否真实，有无伪造/事后补签风险
- **合法性**：取证方式、证据来源是否合法
- **关联性**：证据是否与劳动争议核心争点相关

### 劳动争议典型质证要点
- 劳动合同：是否经双方签字盖章、时间是否真实、条款是否合法
- 规章制度：是否经民主程序制定、是否向劳动者公示告知
- 考勤记录：系统数据是否可信、有无人工修改痕迹
- 工资条/发放记录：是否经劳动者签收确认
- 解除通知书：送达方式是否合法、理由是否充分

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
    """构建劳动争议质证意见生成的用户 prompt。"""
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
        f"\n证据 ID 列表：{all_ev_ids}\n"
        f"\n请为每条证据生成质证意见，以严格 JSON 格式输出，不要输出任何其他内容。"
    )
