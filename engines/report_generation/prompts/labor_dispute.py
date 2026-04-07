"""
劳动争议（Labor Dispute）案件类型的报告生成 LLM 提示模板。
LLM prompt templates for labor dispute case type report generation.

用于指导 LLM 根据争点树和证据索引生成结构化诊断报告。
"""

SYSTEM_PROMPT = """\
你是一位专业的中国劳动争议案件诊断分析师，擅长劳动合同纠纷、工资报酬、经济补偿金及工伤赔偿案件的综合分析。
You are a professional Chinese labor dispute case diagnostic analyst.

你的任务是根据提供的争点树（IssueTree）和证据索引（EvidenceIndex），生成一份结构化的案件诊断报告。

报告要求：
1. 每个顶层争点（parent_issue_id 为 null 或未提供）必须生成一个独立章节
2. 每个章节的关键结论必须引用具体证据 ID（supporting_evidence_ids 不能为空）
3. 每个结论必须标注 statement_class: fact / inference / assumption
4. 报告摘要必须在 500 字以内，律师可在 5 分钟内理解核心结论
5. 所有引用的 evidence_id 必须来自输入的证据索引\
"""

GENERATION_PROMPT = """\
请根据以下案件信息生成诊断报告。

## 案件信息
案件 ID: {case_id}

## 争点树（IssueTree）

{issue_tree_block}

## 证据索引（EvidenceIndex）

{evidence_block}

## 输出要求

请输出符合以下 JSON 结构的报告（**只输出 JSON，不要输出其他内容**）：

```json
{{
  "title": "报告标题（如：劳动争议纠纷诊断报告 - 案件ID）",
  "summary": "律师可在 5 分钟内读懂的报告摘要，≤500字，覆盖所有核心争点和主要风险点",
  "sections": [
    {{
      "title": "章节标题（对应一个争点，如「劳动合同解除合法性」）",
      "body": "章节正文（分析该争点的证据情况、争议焦点和法律适用）",
      "findings": [
        {{
          "statement": "具体结论陈述",
          "statement_class": "fact | inference | assumption",
          "supporting_evidence_ids": ["ev-001", "ev-002"],
          "confidence": "high | medium | low"
        }}
      ]
    }}
  ]
}}
```

### 劳动争议案件诊断要点

- 劳动关系认定：综合考量劳动者工作地点、工作内容、薪酬形式、是否服从管理等要素
- 解除合法性：区分合法解除、违法解除与协商解除，对应不同法律后果（N 倍 vs 2N 倍）
- 工资/加班费：以实际发放工资为基础计算，关注计算基数（应为税前正常工资）
- 经济补偿金：工作年限精确至月，满 6 个月不满 1 年按 1 年计，不满 6 个月按 0.5 年计
- 举证重点：用人单位对工资标准、出勤记录、解除事由负主要举证责任\
"""


def build_user_prompt(*, case_id: str, issue_tree: dict, evidence_list: list[dict]) -> str:
    """构建报告生成 user prompt（CaseTypePlugin 协议入口）。

    Format helpers are case-type-agnostic (they shape dict structures, not
    case-specific text), so labor_dispute reuses civil_loan's helpers via
    a one-way import. A future cleanup may extract them to a shared module.
    """
    from .civil_loan import format_evidence_block, format_issue_tree_block

    issue_tree_block = format_issue_tree_block(issue_tree)
    evidence_block = format_evidence_block(evidence_list)
    return GENERATION_PROMPT.format(
        case_id=case_id,
        issue_tree_block=issue_tree_block,
        evidence_block=evidence_block,
    )
