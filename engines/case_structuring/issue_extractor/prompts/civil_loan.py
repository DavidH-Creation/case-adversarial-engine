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
      "bearer_party_id": "party-xxx",
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

## 注意事项

1. `tmp_id` 格式为 `issue-tmp-001`、`issue-tmp-002` 等，仅用于本次输出内部引用
2. 顶层争点（`parent_tmp_id: null`）必须在 `burdens` 中至少分配一个举证责任
3. 输入中的每个 `claim_id` 和每个 `defense_id` 都必须出现在对应映射中
4. `fact_propositions` 应具体、可验证，避免泛泛而论
5. 子争点（有 parent_tmp_id）描述具体事实；顶层争点描述核心法律问题
6. 只输出 JSON 对象，不要输出任何其他内容\
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
        cid = c.get("claim_id", "")
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
        did = d.get("defense_id", "")
        against = d.get("against_claim_id", "")
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
        eid = e.get("evidence_id", "")
        etype = e.get("evidence_type", "")
        title = _escape_xml(e.get("title", ""))
        desc = _escape_xml(e.get("description", e.get("summary", "")))
        parts.append(
            f'<evidence id="{eid}" type="{etype}">\n'
            f"  <title>{title}</title>\n"
            f"  <description>{desc}</description>\n"
            f"</evidence>"
        )

    return "\n".join(parts)


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
