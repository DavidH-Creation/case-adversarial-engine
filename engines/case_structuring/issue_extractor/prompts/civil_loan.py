"""
民间借贷（Civil Loan）案件类型的 LLM 提示模板。
LLM prompt templates for civil loan (民间借贷) case type.

用于指导 LLM 从 Claims、Defenses、Evidence 中提取争点、举证责任和映射关系。
Guides LLM to extract issues, burdens, and mappings from Claims, Defenses, Evidence.
"""

SYSTEM_PROMPT = """\
你是一位专业的中国民事诉讼争点分析专家，擅长民间借贷纠纷案件的法律分析与争点梳理。
你的任务是从原告诉请、被告抗辩和已索引证据中识别争议焦点，构建争点树，
并为每个核心争点确定举证责任承担方及其证明命题。\
"""

EXTRACTION_PROMPT = """\
请从以下民间借贷纠纷案件材料中提取争议焦点，输出结构化争点树。

## 案件 ID
{case_id}

## 输入材料

{input_block}

## 输出格式

请输出一个 **JSON 对象**（不含其他文字），包含以下字段：

```json
{{
  "issues": [
    {{
      "tmp_id": "issue-tmp-001",
      "title": "争点标题（简短描述，如\"借贷关系成立\"）",
      "issue_type": "factual | legal | procedural | mixed",
      "parent_tmp_id": null,
      "related_claim_ids": ["claim-xxx"],
      "related_defense_ids": ["defense-xxx"],
      "evidence_ids": ["evidence-xxx"],
      "fact_propositions": [
        {{
          "text": "具体可验证的事实命题",
          "status": "unverified | supported | contradicted | disputed",
          "linked_evidence_ids": ["evidence-xxx"]
        }}
      ]
    }}
  ],
  "burdens": [
    {{
      "issue_tmp_id": "issue-tmp-001",
      "burden_party_id": "party-xxx",
      "description": "该方需证明的具体命题",
      "proof_standard": "高度盖然性",
      "legal_basis": "《民事诉讼法》第XX条"
    }}
  ],
  "claim_issue_mapping": [
    {{
      "claim_id": "claim-xxx",
      "issue_tmp_ids": ["issue-tmp-001", "issue-tmp-002"]
    }}
  ],
  "defense_issue_mapping": [
    {{
      "defense_id": "defense-xxx",
      "issue_tmp_ids": ["issue-tmp-002"]
    }}
  ]
}}
```

## 民间借贷案件典型争点分类

| 争点 | 类型 | 说明 |
|---|---|---|
| 借贷关系成立 | factual | 合意是否存在，借条是否真实 |
| 款项实际交付 | factual | 出借行为是否完成，金额是否正确 |
| 还款事实 | factual | 被告是否已还款及金额 |
| 利率约定 | mixed | 利率条款是否明确，是否超出法定上限 |
| 诉讼时效 | legal | 起诉是否在三年诉讼时效内 |

## 争点分解指引

当同一事实同时涉及事实认定与法律性质认定时，必须拆分为独立争点：
- 事实层争点（factual）：如「是否完成交付行为」「是否实际收到款项」
- 法律/混合层争点（mixed/legal）：如「交付行为的法律性质认定」「款项性质是借款还是指示付款」

拆分原则：同一底层事实如果既需要证据验证，又需要法律定性，则创建平行或父子争点，不得合并为单一争点。

## 注意事项

1. `tmp_id` 格式为 `issue-tmp-001`、`issue-tmp-002` 等，仅用于本次输出内部引用
2. 顶层争点（`parent_tmp_id: null`）必须在 `burdens` 中至少分配一个举证责任
3. 输入中的每个 `claim_id` 和每个 `defense_id` 都必须出现在对应映射中
4. `fact_propositions` 应具体、可验证，避免泛泛而论
5. 子争点（有 parent_tmp_id）描述具体事实；顶层争点描述核心法律问题；当事实认定与法律定性并存时，必须拆分（参见争点分解指引）
6. 只输出 JSON 对象，不要输出任何其他内容
7. **JSON字符串值内禁止使用未转义的双引号**。如需引用原文词语，请使用中文引号「」，如「借条」\
"""


def format_input_block(
    claims: list,
    defenses: list,
    evidence: list,
) -> str:
    """格式化 claims、defenses、evidence 为 prompt 输入块。
    Format claims, defenses, and evidence into a prompt input block.

    使用 XML 标签分隔各部分，防止文本注入。
    Uses XML tags to delimit sections, preventing prompt injection.
    """
    parts: list[str] = []

    # 格式化诉请 / Format claims
    parts.append("### 诉请 (Claims)\n")
    for c in claims:
        cid = _escape_xml(c.get("claim_id", ""))
        title = _escape_xml(c.get("title", ""))
        desc = _escape_xml(c.get("description", ""))
        evids = ", ".join(c.get("related_evidence_ids", []))
        parts.append(
            f'<claim id="{cid}">\n'
            f"  <title>{title}</title>\n"
            f"  <description>{desc}</description>\n"
            f"  <related_evidence>{evids}</related_evidence>\n"
            f"</claim>"
        )

    # 格式化抗辩 / Format defenses
    parts.append("\n### 抗辩 (Defenses)\n")
    for d in defenses:
        did = _escape_xml(d.get("defense_id", ""))
        against = _escape_xml(d.get("against_claim_id", ""))
        title = _escape_xml(d.get("title", ""))
        desc = _escape_xml(d.get("description", ""))
        evids = ", ".join(d.get("related_evidence_ids", []))
        parts.append(
            f'<defense id="{did}" against="{against}">\n'
            f"  <title>{title}</title>\n"
            f"  <description>{desc}</description>\n"
            f"  <related_evidence>{evids}</related_evidence>\n"
            f"</defense>"
        )

    # 格式化证据摘要 / Format evidence summary
    parts.append("\n### 证据 (Evidence)\n")
    for e in evidence:
        eid = _escape_xml(e.get("evidence_id", ""))
        etype = _escape_xml(e.get("evidence_type", ""))
        title = _escape_xml(e.get("title", ""))
        desc = _escape_xml(e.get("description", e.get("summary", "")))
        parts.append(
            f'<evidence id="{eid}" type="{etype}">\n'
            f"  <title>{title}</title>\n"
            f"  <description>{desc}</description>\n"
            f"</evidence>"
        )

    return "\n".join(parts)


def build_user_prompt(*, case_id: str, claims: list, defenses: list, evidence: list) -> str:
    """构建争点抽取器 user prompt（CaseTypePlugin 协议入口）。"""
    input_block = format_input_block(claims, defenses, evidence)
    return EXTRACTION_PROMPT.format(case_id=case_id, input_block=input_block)


def _escape_xml(text: str) -> str:
    """转义 XML 特殊字符，防止提示注入。
    Escape XML special characters to prevent prompt injection.
    """
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
