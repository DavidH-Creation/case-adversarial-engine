"""
民间借贷（Civil Loan）案件类型的报告生成 LLM 提示模板。
LLM prompt templates for civil loan (民间借贷) case type report generation.

用于指导 LLM 根据争点树和证据索引生成结构化诊断报告。
Guides LLM to generate a structured diagnostic report from IssueTree and EvidenceIndex.
"""

SYSTEM_PROMPT = """\
你是一位专业的中国民事诉讼案件诊断分析师，擅长民间借贷纠纷案件的综合分析。
You are a professional Chinese civil litigation case diagnostic analyst, specializing in civil loan disputes.

你的任务是根据提供的争点树（IssueTree）和证据索引（EvidenceIndex），生成一份结构化的案件诊断报告。
Your task is to generate a structured diagnostic report based on the provided IssueTree and EvidenceIndex.

报告要求：
Report requirements:
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
  "title": "报告标题（如：民间借贷纠纷诊断报告 - 案件ID）",
  "summary": "律师可在 5 分钟内读懂的报告摘要，≤500字，覆盖所有核心争点和主要风险点",
  "sections": [
    {{
      "title": "章节标题（对应一个争点）",
      "body": "章节正文（分析该争点的证据情况、争议焦点和法律适用）",
      "linked_issue_ids": ["issue-xxx-001"],
      "linked_evidence_ids": ["evidence-xxx-001", "evidence-xxx-002"],
      "key_conclusions": [
        {{
          "text": "关键结论文本",
          "statement_class": "fact",
          "supporting_evidence_ids": ["evidence-xxx-001"]
        }}
      ]
    }}
  ]
}}
```

### 重要约束

1. **每个顶层争点（parent_issue_id 为 null）必须对应一个章节**
2. **每个关键结论的 supporting_evidence_ids 不能为空**，必须引用至少一条具体证据 ID
3. **statement_class 必须是以下之一**：`fact`（已证事实）、`inference`（推理结论）、`assumption`（假设前提）
4. **summary 不超过 500 字**
5. **所有 evidence_id 必须来自上方证据索引中的实际 ID**
6. **章节数量与顶层争点数量一致**，每个顶层争点一个章节，子争点合并进对应父争点章节

### 民间借贷案件分析重点

- **借贷关系成立**：借条/合同 + 款项交付证据
- **还款事实**：还款凭证、转账记录
- **利息约定**：利率合法性（法定上限 LPR×4）、利率约定证明
- **诉讼时效**：起算点、中断事由、三年期限
- **举证责任分配**：原告证明借贷关系、被告证明已还款\
"""


def format_issue_tree_block(issue_tree: dict) -> str:
    """将争点树格式化为 prompt 输入块。
    Format the IssueTree into a readable prompt block.
    """
    import json

    issues = issue_tree.get("issues", [])
    burdens = issue_tree.get("burdens", [])

    lines = []

    # 顶层争点 / Root issues
    root_issues = [i for i in issues if not i.get("parent_issue_id")]
    child_issues = [i for i in issues if i.get("parent_issue_id")]

    lines.append("### 顶层争点（root issues）")
    for issue in root_issues:
        lines.append(f"\n**{issue['issue_id']}**: {issue['title']}")
        lines.append(f"  类型: {issue.get('issue_type', 'factual')}")
        if issue.get("evidence_ids"):
            lines.append(f"  关联证据: {', '.join(issue['evidence_ids'])}")
        for fp in issue.get("fact_propositions", []):
            lines.append(f"  - 事实命题: {fp.get('text', '')} [{fp.get('status', 'unverified')}]")

    if child_issues:
        lines.append("\n### 子争点（sub-issues）")
        for issue in child_issues:
            lines.append(
                f"\n**{issue['issue_id']}** (父: {issue['parent_issue_id']}): {issue['title']}"
            )
            if issue.get("evidence_ids"):
                lines.append(f"  关联证据: {', '.join(issue['evidence_ids'])}")
            for fp in issue.get("fact_propositions", []):
                lines.append(
                    f"  - 事实命题: {fp.get('text', '')} [{fp.get('status', 'unverified')}]"
                )

    if burdens:
        lines.append("\n### 举证责任")
        for b in burdens:
            lines.append(
                f"  {b['burden_id']} → {b['issue_id']}: {b.get('description', '')} [{b.get('status', '')}]"
            )

    return "\n".join(lines)


def format_evidence_block(evidence_list: list[dict]) -> str:
    """将证据列表格式化为 prompt 输入块。
    Format the evidence list into a readable prompt block.

    使用 XML 标签隔离每条证据防止注入。
    Uses XML tags to isolate each evidence item against prompt injection.
    """

    def _escape(val: str) -> str:
        return (
            val.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    blocks = []
    for e in evidence_list:
        safe_id = _escape(e.get("evidence_id", ""))
        safe_type = _escape(e.get("evidence_type", ""))
        safe_summary = _escape(e.get("summary", ""))
        blocks.append(
            f'<evidence id="{safe_id}" type="{safe_type}">\n'
            f"  标题: {e.get('title', '')}\n"
            f"  摘要: {safe_summary}\n"
            f"  状态: {e.get('status', 'private')}\n"
            f"</evidence>"
        )
    return "\n\n".join(blocks)
