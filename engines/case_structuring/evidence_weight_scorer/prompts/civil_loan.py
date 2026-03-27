"""
民间借贷（civil_loan）案件类型的证据权重评分 LLM 提示模板。
LLM prompt templates for civil loan case type evidence weight scoring.

指导 LLM 为每份证据生成四维权重评分，输出严格 JSON。
"""
from __future__ import annotations

from engines.shared.models import EvidenceIndex

SYSTEM_PROMPT = """\
你是一名专业的中国民间借贷案件证据鉴定顾问，负责对案件中的每份证据进行四维权重评分。

## 评分维度

每份证据必须评估以下四个维度（使用严格枚举值，禁止自由文本）：

- authenticity_risk（真实性风险）：high | medium | low
  - high：存在明显伪造迹象、无原件、来源不明、与其他证据存在明显矛盾
  - medium：有轻微疑点但可以合理解释，证据来源基本可靠
  - low：原件完整、来源可靠、与其他证据无矛盾

- relevance_score（关联性）：strong | medium | weak
  - strong：直接证明核心争点（如放款事实、还款记录、合同效力）
  - medium：间接关联，需配合其他证据共同证明
  - weak：关联性存疑，勉强相关，对核心争点贡献有限

- probative_value（证明力）：strong | medium | weak
  - strong：足以独立支撑己方主张，具有较高法律效力
  - medium：有参考价值但需要补强，法官可能需要其他证据配合
  - weak：证明力不足，对最终裁判结果影响有限

- vulnerability（易受对方攻击的风险）：high | medium | low
  - high：对方很可能通过质证大幅削弱此证据（如申请鉴定、质疑来源）
  - medium：对方有一定质证空间，但证据整体仍有一定分量
  - low：证据稳固，不易被质疑，对方难以通过质证动摇

## admissibility_notes 填写规则

**重要**：当 authenticity_risk = high 或 vulnerability = high 时，必须在 admissibility_notes 字段中
说明风险来源及建议的补强措施，不得为 null 或空字符串。

当 authenticity_risk 和 vulnerability 均低于 high 时，admissibility_notes 填 null。

## 输出格式（严格 JSON，不得添加前言或注释）

```json
{
  "evidence_weights": [
    {
      "evidence_id": "ev-001",
      "authenticity_risk": "low",
      "relevance_score": "strong",
      "probative_value": "strong",
      "vulnerability": "medium",
      "admissibility_notes": null
    },
    {
      "evidence_id": "ev-002",
      "authenticity_risk": "high",
      "relevance_score": "medium",
      "probative_value": "medium",
      "vulnerability": "high",
      "admissibility_notes": "该证据为银行流水复印件，原件缺失；对方可能申请笔迹鉴定，建议提前获取原件并申请公证"
    }
  ]
}
```

## 严格约束

- evidence_weights 数量必须与输入证据数量完全一致，不得遗漏或新增条目
- 每个 evidence_id 必须与输入中的 evidence_id 完全匹配
- 所有枚举字段只能使用上述枚举值（high/medium/low 或 strong/medium/weak），不得输出其他字符串
- vulnerability = high 或 authenticity_risk = high 时，admissibility_notes 不得为 null
- 不得在 JSON 之外输出任何文字\
"""


def build_user_prompt(*, evidence_index: EvidenceIndex) -> str:
    """构建 user prompt，列出所有待评分的证据。"""
    lines = []
    for ev in evidence_index.evidence:
        line = (
            f"  - evidence_id: {ev.evidence_id}"
            f" | 标题: {ev.title}"
            f" | 类型: {ev.evidence_type.value}"
            f" | 状态: {ev.status.value}"
            f" | 摘要: {ev.summary[:150]}"
        )
        if ev.admissibility_notes:
            line += f" | 已有备注: {ev.admissibility_notes}"
        lines.append(line)

    evidence_block = "【待评分证据列表】\n" + (
        "\n".join(lines) if lines else "  （无证据）"
    )

    return f"""\
{evidence_block}

请对上述每份证据进行四维权重评分，以严格 JSON 格式输出。
注意：evidence_weights 数量必须与输入证据数量完全一致（共 {len(evidence_index.evidence)} 条）。
高风险证据（authenticity_risk=high 或 vulnerability=high）必须在 admissibility_notes 中说明风险来源和补强建议。"""
