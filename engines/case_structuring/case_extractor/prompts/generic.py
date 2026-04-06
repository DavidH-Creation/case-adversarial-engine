"""
Generic case extraction prompt — works for all case types.
通用案件提取 prompt — 适用于所有案由类型。

The LLM discovers the case_type from the document content,
then extracts parties, materials, claims, defenses, and financials.
"""

from __future__ import annotations

SYSTEM_PROMPT = """\
你是一位资深中国法律文书分析专家，精通各类民事诉讼案件的文书结构。
You are a senior Chinese legal document analyst, expert in all civil litigation case types.

你的任务是从原始法律文书（起诉状、答辩状、证据清单等）中提取结构化案件信息。
Your task is to extract structured case information from raw legal documents
(complaints, defense statements, evidence lists, etc.).

提取规则 / Extraction rules:
1. 识别案由类型（civil_loan, labor_dispute, real_estate, 或其他）
2. 提取原告和被告信息
3. 将每份文书拆分为独立的材料条目，标注提交方和文书类型
4. 提取所有诉请（原告主张）
5. 提取所有抗辩（被告抗辩）
6. 仅借贷类案件需要提取财务数据（loans, repayments, disputed, claim_entries）
7. 生成案件摘要（关键事实的简要列表）

文书类型参考 / Document type reference:
identity_documents, bank_transfer_records, loan_note, attorney_contract,
objection_statement, communication_records, labor_contract, termination_notice,
salary_records, social_insurance_records, purchase_contract, lease_contract,
deposit_receipt, payment_records, witness_statement, expert_opinion, other

诉请类别参考 / Claim category reference:
返还借款, 利息, 律师费, 违约金, 解除合同, 经济补偿金, 赔偿金,
工资差额, 双倍工资, 定金返还, 物业交付, 修缮费用, 租金, 其他

确保所有 ID 唯一且符合格式要求。
Ensure all IDs are unique and follow the format requirements.
"""

EXTRACTION_PROMPT = """\
请从以下法律文书中提取完整的结构化案件信息。
Please extract complete structured case information from the following legal documents.

<documents>
{documents}
</documents>

请严格按照以下 JSON schema 输出，不要遗漏任何字段：
Output strictly according to the following JSON schema, do not omit any fields:

{{
  "case_type": "civil_loan | labor_dispute | real_estate | other",
  "plaintiff": {{
    "role": "plaintiff",
    "name": "原告姓名",
    "party_id": ""
  }},
  "defendant": {{
    "role": "defendant",
    "name": "被告姓名",
    "party_id": ""
  }},
  "summary": [
    {{"label": "关键事实标签", "description": "简要描述"}}
  ],
  "materials": [
    {{
      "source_id": "src-p-001 或 src-d-001",
      "text": "材料原文内容",
      "submitter": "plaintiff 或 defendant",
      "document_type": "文书类型"
    }}
  ],
  "claims": [
    {{
      "claim_id": "c-001",
      "claim_category": "诉请类别",
      "title": "诉请标题",
      "claim_text": "诉请详细描述"
    }}
  ],
  "defenses": [
    {{
      "defense_id": "d-001",
      "defense_category": "抗辩类别",
      "against_claim_id": "c-001",
      "title": "抗辩标题",
      "defense_text": "抗辩详细描述"
    }}
  ],
  "financials": null
}}

注意 / Notes:
- source_id 格式：原告材料用 src-p-XXX，被告材料用 src-d-XXX
- claim_id 格式：c-001, c-002, ...
- defense_id 格式：d-001, d-002, ...
- financials 仅在 case_type 为 civil_loan 时填写，其余情况设为 null
- 如果文书中信息不完整，尽可能提取已有内容，缺失字段留空字符串
- 如果只有起诉状没有答辩状，defenses 留空列表
"""


def format_documents(texts: list[tuple[str, str]]) -> str:
    """Format document texts into XML blocks for the extraction prompt.

    Args:
        texts: List of (filename, content) tuples.

    Returns:
        XML-escaped document blocks.
    """
    blocks = []
    for filename, content in texts:
        safe_filename = (
            filename.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        safe_content = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        blocks.append(f'<document filename="{safe_filename}">\n{safe_content}\n</document>')
    return "\n\n".join(blocks)
