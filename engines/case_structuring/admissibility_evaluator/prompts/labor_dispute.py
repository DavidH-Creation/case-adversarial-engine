"""
劳动争议（labor_dispute）案件类型的证据可采性评估 LLM 提示模板。
LLM prompt templates for labor dispute case type admissibility evaluation.

指导 LLM 为每份证据评估可采性评分（admissibility_score）、质疑理由
（admissibility_challenges）及排除影响（exclusion_impact），输出严格 JSON。
"""

from __future__ import annotations

from engines.shared.models import EvidenceIndex, EvidenceType

SYSTEM_PROMPT = """\
你是一名专业的中国劳动争议案件证据可采性顾问，负责评估案件中每份证据被法庭（劳动仲裁庭
或人民法院）采信的概率，并预测证据被排除时对案件的影响。

## 评估框架

对每份证据输出以下三个字段：

### admissibility_score（可采性评分）：0.0–1.0 之间的浮点数（保留两位小数）
- 1.0：完全可采信，无合理质疑
- 0.8–0.99：基本可采，存在轻微形式瑕疵，可补正
- 0.5–0.79：可采性存疑，对方有实质性质疑空间
- 0.2–0.49：可采性危险，很可能被仲裁庭/法庭排除或大幅贬值
- 0.0–0.19：极可能被排除，实质上无法被采信

### admissibility_challenges（质疑理由列表）
列出所有可能影响该证据可采性的具体理由（字符串列表）。若无质疑理由，填空列表 []。

**各类证据重点关注**：

- audio_visual（录音/录屏）：
  - 录制是否合法（劳动者在工作场所的录音是否侵犯隐私）
  - 是否在劳动仲裁/诉讼前的沟通中自然录制
  - 录音/录像内容是否完整、有无剪辑痕迹
  - 录制环境噪音是否影响内容辨识
  - 是否能确认录音中各方身份

- documentary（书证）：
  - 是否为原件或经公证的副本（复印件证明力受限）
  - 用人单位盖章是否真实有效（是否为公章/合同专用章/人事章）
  - 劳动者签字是否为本人签署（笔迹鉴定风险）
  - 文件日期是否与待证事实时间一致
  - 是否存在涂改、事后补签痕迹

- electronic_data（电子数据）：
  - 钉钉/企业微信/OA 等系统记录是否可由用人单位单方修改
  - 截图是否经过公证或可信时间戳固定
  - 电子考勤记录是否有原始数据库支撑
  - 微信聊天记录能否确认账号归属双方当事人

- witness_statement（证人证言）：
  - 证人是否为在职同事（可能受用人单位影响）
  - 证人是否与劳动者存在利害关系（如已离职的同一批被裁人员）
  - 证人是否愿意出庭接受质证
  - 证言是否与其他书面证据相互印证

### exclusion_impact（排除影响描述）
用一段简洁文字（50–200字）描述：**若该证据被仲裁庭/法庭排除**，将对案件产生何种实质影响。
重点说明：哪些争点失去支撑、举证责任缺口、对裁判方向（支持劳动者/支持用人单位）的影响。

## 劳动争议案件特殊注意事项

### 举证责任倒置
以下情形中，用人单位负有举证责任，劳动者提交的相关证据可采性通常较高：
- 解除/终止劳动合同的合法性（用人单位举证）
- 工资发放记录（用人单位保存义务，两年内）
- 考勤记录（用人单位保存义务）
- 规章制度的民主制定程序和公示告知程序

### 常见证据可采性风险点
- 未签劳动合同：劳动者主张事实劳动关系时，工资流水、社保记录、工作证、考勤等
  间接证据的可采性和证明力需综合评估
- 加班事实证明：考勤记录原件由用人单位掌握而拒不提供时，劳动者的间接证据
  （如加班审批截图）可采性应适当从宽
- 竞业限制：竞业限制协议及补偿金发放记录的真实性和完整性

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
      "admissibility_score": 0.35,
      "admissibility_challenges": [
        "该考勤记录为钉钉系统截图，用人单位可能主张系统数据已更新覆盖",
        "截图未经公证固定，对方可质疑真实性",
        "缺少原始数据库导出记录作为补强"
      ],
      "exclusion_impact": "该考勤记录是证明劳动者连续加班事实的核心证据。若被排除，劳动者将难以证明加班时长，加班工资诉请将面临举证不足的风险，可能导致该项诉请被驳回。"
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
        # 标注电子数据证据类型以供 LLM 重点关注（劳动争议中电子考勤/OA 记录常见）
        if ev.evidence_type == EvidenceType.electronic_data:
            type_label += "【重点：电子数据，关注系统可篡改性】"
        if ev.evidence_type == EvidenceType.audio_visual:
            type_label += "【重点：录音/录屏证据，关注录制合法性】"

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

    evidence_block = "【待评估证据列表】\n" + ("\n".join(lines) if lines else "  （无证据）")

    return f"""\
{evidence_block}

请对上述每份证据进行可采性评估，以严格 JSON 格式输出。
注意：evidence_assessments 数量必须与输入证据数量完全一致（共 {len(evidence_index.evidence)} 条）。
admissibility_score < 0.5 的证据，admissibility_challenges 列表不得为空。
电子数据类型证据（electronic_data）请特别关注系统可篡改性和固定保全措施。
录音/录屏类型证据（audio_visual）请特别关注录制合法性和身份确认问题。"""
