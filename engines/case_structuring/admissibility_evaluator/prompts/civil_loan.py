"""
民间借贷（civil_loan）案件类型的证据可采性评估 LLM 提示模板。
LLM prompt templates for civil loan case type admissibility evaluation.

指导 LLM 为每份证据评估可采性评分（admissibility_score）、质疑理由
（admissibility_challenges）及排除影响（exclusion_impact），输出严格 JSON。
"""
from __future__ import annotations

from engines.shared.models import EvidenceIndex, EvidenceType

SYSTEM_PROMPT = """\
你是一名专业的中国民事诉讼证据可采性顾问，负责评估案件中每份证据被法庭采信的概率，
并预测证据被排除时对案件的影响。

## 评估框架

对每份证据输出以下三个字段：

### admissibility_score（可采性评分）：0.0–1.0 之间的浮点数（保留两位小数）
- 1.0：完全可采信，无合理质疑
- 0.8–0.99：基本可采，存在轻微形式瑕疵，可补正
- 0.5–0.79：可采性存疑，对方有实质性质疑空间
- 0.2–0.49：可采性危险，很可能被法庭排除或大幅贬值
- 0.0–0.19：极可能被排除，实质上无法被采信

### admissibility_challenges（质疑理由列表）
列出所有可能影响该证据可采性的具体理由（字符串列表）。若无质疑理由，填空列表 []。

**各类证据重点关注**：

- audio_visual（录音/录屏）：
  - 录制是否合法（《民事诉讼证据规定》第94条：非法录音不得作为证据）
  - 是否经对方同意或在公共场合录制
  - 录音/录像内容是否完整、有无剪辑痕迹
  - 保管链（chain of custody）是否可溯源
  - 是否存在声纹/视频鉴定需求

- documentary（书证）：
  - 是否为原件或经公证的副本（复印件证明力受限）
  - 签章是否完备、有无涂改
  - 传闻规则（hearsay）：若证件内容需证人出庭说明才有意义
  - 关联性：是否与待证事实直接相关

- electronic_data（电子数据）：
  - 公证或可信时间戳是否存在
  - 数据来源和完整性是否可验证

- witness_statement（证人证言）：
  - 证人是否与当事人有利害关系
  - 证人是否愿意出庭接受质证
  - 证言前后是否一致

### exclusion_impact（排除影响描述）
用一段简洁文字（50–200字）描述：**若该证据被法庭排除**，将对案件产生何种实质影响。
重点说明：哪些争点失去支撑、己方举证责任缺口、对最终裁判方向的可能影响。

## 输出格式（严格 JSON，不得添加前言或注释）

```json
{
  "evidence_assessments": [
    {
      "evidence_id": "ev-001",
      "admissibility_score": 0.9,
      "admissibility_challenges": [],
      "exclusion_impact": null
    },
    {
      "evidence_id": "ev-002",
      "admissibility_score": 0.3,
      "admissibility_challenges": [
        "录音系在对方不知情情况下单方录制，可能违反隐私权规定",
        "录音时间与争议时间相差3个月，关联性存疑",
        "录音文件未经公证，对方可申请声纹鉴定"
      ],
      "exclusion_impact": "该录音为证明被告口头承诺还款的唯一证据。若被排除，原告将无法证明被告明确认可了到期日，举证责任落在原告一方，案件胜诉概率将显著下降。"
    }
  ]
}
```

## 严格约束

- evidence_assessments 数量必须与输入证据数量完全一致，不得遗漏或新增条目
- 每个 evidence_id 必须与输入中的 evidence_id 完全匹配
- admissibility_score 必须是 0.0–1.0 之间的浮点数（保留两位小数）
- admissibility_score < 0.5 时，admissibility_challenges 列表不得为空
- 不得在 JSON 之外输出任何文字\
"""


def build_user_prompt(*, evidence_index: EvidenceIndex) -> str:
    """构建 user prompt，列出所有待评估的证据。"""
    lines = []
    for ev in evidence_index.evidence:
        type_label = ev.evidence_type.value
        # 标注录音/录屏证据类型以供 LLM 重点关注
        if ev.evidence_type == EvidenceType.audio_visual:
            type_label += "【重点：录音/录屏证据，关注合法性】"

        line = (
            f"  - evidence_id: {ev.evidence_id}"
            f" | 标题: {ev.title}"
            f" | 类型: {type_label}"
            f" | 状态: {ev.status.value}"
            f" | 摘要: {ev.summary[:200]}"
        )
        if ev.admissibility_notes:
            line += f" | 已有可采性备注: {ev.admissibility_notes}"
        if ev.is_copy_only:
            line += " | ⚠️ 仅有复印件"
        lines.append(line)

    evidence_block = "【待评估证据列表】\n" + (
        "\n".join(lines) if lines else "  （无证据）"
    )

    return f"""\
{evidence_block}

请对上述每份证据进行可采性评估，以严格 JSON 格式输出。
注意：evidence_assessments 数量必须与输入证据数量完全一致（共 {len(evidence_index.evidence)} 条）。
admissibility_score < 0.5 的证据，admissibility_challenges 列表不得为空。
录音/录屏类型证据（audio_visual）请特别关注录制合法性和保管链问题。"""
