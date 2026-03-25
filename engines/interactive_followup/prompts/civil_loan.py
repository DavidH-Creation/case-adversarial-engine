"""
民间借贷（Civil Loan）案件类型的追问响应 LLM 提示模板。
LLM prompt templates for civil loan (民间借贷) case type interactive followup.

用于指导 LLM 根据已生成报告和历史追问轮次回答用户追问，保持证据引用完整性。
Guides LLM to answer user questions based on the generated report and history,
maintaining complete evidence citation.
"""

SYSTEM_PROMPT = """\
你是一位专业的中国民事诉讼案件分析师，擅长民间借贷纠纷案件的追问解答。
You are a professional Chinese civil litigation case analyst, specializing in civil loan disputes follow-up Q&A.

你的任务是根据已生成的案件诊断报告，回答律师的追问。
Your task is to answer lawyer's follow-up questions based on the generated case diagnostic report.

回答要求：
Answer requirements:
1. 只能引用报告中已出现的证据 ID（evidence_ids 必须是报告已引用证据的子集）
2. 每条回答必须绑定至少一个争点 ID（issue_ids 不能为空）
3. 必须标注 statement_class：fact（已证事实）/ inference（推理结论）/ assumption（假设前提）
4. 事实性断言必须引用具体 evidence_id，不能凭空断言
5. 多轮追问中，前后回答不得矛盾\
"""

RESPONSE_PROMPT = """\
请根据以下案件报告和追问历史，回答用户的追问。

## 案件信息
案件 ID: {case_id}
报告 ID: {report_id}

## 案件诊断报告摘要

{report_context_block}

{history_block}

## 当前追问

{question}

## 输出要求

请输出符合以下 JSON 结构的回答（**只输出 JSON，不要输出其他内容**）：

```json
{{
  "answer": "对追问的详细回答，应结合报告内容和具体证据进行分析",
  "issue_ids": ["issue-xxx-001"],
  "evidence_ids": ["evidence-xxx-001"],
  "statement_class": "inference",
  "citations": [
    {{
      "evidence_id": "evidence-xxx-001",
      "quote": "证据中的关键引用文本（可选）"
    }}
  ]
}}
```

### 重要约束

1. **evidence_ids 只能包含报告中已引用的证据 ID**，不能引用报告外的证据
2. **issue_ids 不能为空**，必须绑定报告中存在的争点 ID
3. **statement_class 必须是以下之一**：`fact`（已证事实）、`inference`（推理结论）、`assumption`（假设前提）
4. **事实性陈述（fact）必须有 evidence_ids 支撑**，不能无引用
5. **回答必须基于报告内容**，不得引入报告外的信息

### 民间借贷案件追问分析重点

- **借贷关系成立**：借条/合同 + 款项交付证据的互相印证
- **还款事实**：还款凭证、转账记录的真实性
- **利息约定**：利率合法性（法定上限 LPR×4）
- **诉讼时效**：起算点、中断事由、三年期限
- **举证责任分配**：争点上的举证责任归属\
"""


def format_report_context(report: dict) -> str:
    """将报告格式化为 prompt 上下文块。
    Format the report into a readable prompt context block.
    """
    lines = []
    lines.append(f"**报告标题**: {report.get('title', '')}")
    lines.append(f"**报告摘要**: {report.get('summary', '')}")
    lines.append("")
    lines.append("**章节概览 / Section overview:**")

    for sec in report.get("sections", []):
        lines.append(f"\n**{sec.get('section_id', '?')}**: {sec.get('title', '')}")
        # 关联争点 / Linked issues
        if sec.get("linked_issue_ids"):
            lines.append(f"  关联争点: {', '.join(sec['linked_issue_ids'])}")
        # 关联证据 / Linked evidence
        if sec.get("linked_evidence_ids"):
            lines.append(f"  引用证据: {', '.join(sec['linked_evidence_ids'])}")
        # 关键结论 / Key conclusions
        for concl in sec.get("key_conclusions", []):
            sc = concl.get("statement_class", "inference")
            text = concl.get("text", "")
            ev_ids = concl.get("supporting_evidence_ids", [])
            ev_str = ", ".join(ev_ids) if ev_ids else "（无）"
            lines.append(f"  - [{sc}] {text} → 证据: {ev_str}")

    return "\n".join(lines)


def format_history_block(turns: list[dict]) -> str:
    """将历史追问轮次格式化为 prompt 上下文块。
    Format previous interaction turns into a readable context block.

    使用 XML 标签隔离每轮追问防止注入。
    Uses XML tags to isolate each turn against prompt injection.
    """
    if not turns:
        return ""

    def _escape(val: str) -> str:
        return (
            val.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    lines = ["## 历史追问记录 / Previous Q&A History"]
    for i, turn in enumerate(turns, start=1):
        turn_id = _escape(turn.get("turn_id", f"turn-{i}"))
        question = _escape(turn.get("question", ""))
        answer = _escape(turn.get("answer", ""))
        issue_ids = turn.get("issue_ids", [])
        evidence_ids = turn.get("evidence_ids", [])
        statement_class = _escape(turn.get("statement_class", "inference"))

        lines.append(
            f'\n<turn id="{turn_id}" round="{i}">\n'
            f"  问题: {question}\n"
            f"  回答: {answer}\n"
            f"  statement_class: {statement_class}\n"
            f"  争点: {', '.join(issue_ids)}\n"
            f"  证据: {', '.join(evidence_ids)}\n"
            f"</turn>"
        )

    return "\n".join(lines)
