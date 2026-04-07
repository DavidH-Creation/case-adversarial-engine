"""
房屋买卖合同纠纷（Real Estate）案件类型的报告生成 LLM 提示模板。
LLM prompt templates for real estate sale contract dispute case type report generation.

用于指导 LLM 根据争点树和证据索引生成结构化诊断报告。
"""

SYSTEM_PROMPT = """\
你是一位专业的中国房屋买卖合同纠纷案件诊断分析师，擅长房产交易合同效力、交付、产权过户及违约赔偿案件的综合分析。
You are a professional Chinese real estate sale contract dispute case diagnostic analyst.

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
  "title": "报告标题（如：房屋买卖合同纠纷诊断报告 - 案件ID）",
  "summary": "律师可在 5 分钟内读懂的报告摘要，≤500字，覆盖所有核心争点和主要风险点",
  "sections": [
    {{
      "title": "章节标题（对应一个争点，如「合同效力」）",
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

### 房屋买卖合同纠纷诊断要点

- 合同效力：首先确认合同是否合法成立，有无欺诈、重大误解、显失公平等可撤销事由
- 交付与过户：区分「交付」（钥匙/实际占有转移）与「过户」（不动产登记），两者可能分离
- 定金罚则：明确款项性质（定金 vs 订金 vs 首付款），只有「定金」才适用双倍返还罚则
- 违约金调整：违约金过高或过低均可申请调整，以实际损失为主要参考
- 贷款审批：贷款未获批是否属于不可抗力或合同约定的解除条件，影响定金退还义务\
"""


def build_user_prompt(*, case_id: str, issue_tree: dict, evidence_list: list[dict]) -> str:
    """构建报告生成 user prompt（CaseTypePlugin 协议入口）。

    Reuses civil_loan's case-type-agnostic format helpers via one-way import
    (see labor_dispute.py for the same rationale).
    """
    from .civil_loan import format_evidence_block, format_issue_tree_block

    issue_tree_block = format_issue_tree_block(issue_tree)
    evidence_block = format_evidence_block(evidence_list)
    return GENERATION_PROMPT.format(
        case_id=case_id,
        issue_tree_block=issue_tree_block,
        evidence_block=evidence_block,
    )
