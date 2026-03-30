"""
免责声明模板
Disclaimer templates for report output.

固定中文文本，用于 Markdown 报告首行和 DOCX 报告首页。
Fixed Chinese text for Markdown report header and DOCX report front page.
"""

from __future__ import annotations

# Markdown 报告免责声明 header（插入报告首行）
DISCLAIMER_MD = (
    "> **免责声明：本报告由 AI 生成，仅供参考，不构成法律意见。"
    "报告内容基于所提供的案件材料和 AI 模型分析，可能存在遗漏或偏差。"
    "如需法律建议，请咨询专业律师。**"
)

# DOCX 报告免责声明（首页插入）
DISCLAIMER_DOCX_TITLE = "免责声明"
DISCLAIMER_DOCX_BODY = (
    "本报告由 AI 生成，仅供参考，不构成法律意见。"
    "报告内容基于所提供的案件材料和 AI 模型分析，可能存在遗漏或偏差。"
    "如需法律建议，请咨询专业律师。\n\n"
    "本报告中的所有分析结论均为 AI 推理结果，不代表任何司法机关的意见或裁判倾向。"
    "使用者应自行判断报告内容的适用性，并承担因使用本报告而产生的一切风险。"
)
