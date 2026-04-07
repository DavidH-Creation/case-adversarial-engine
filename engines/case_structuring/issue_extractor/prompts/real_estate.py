"""
房屋买卖合同纠纷案件类型的 LLM 提示模板。
LLM prompt templates for real estate sale contract dispute (房屋买卖合同纠纷) case type.

用于指导 LLM 从 Claims、Defenses、Evidence 中提取争点、举证责任和映射关系。
Guides LLM to extract issues, burdens, and mappings from Claims, Defenses, Evidence.
"""

SYSTEM_PROMPT = """\
你是一位专业的中国房屋买卖合同纠纷争点分析专家，擅长房产交易合同效力、交付、过户、违约责任及贷款纠纷案件的法律分析与争点梳理。
你的任务是从原告诉请、被告抗辩和已索引证据中识别争议焦点，构建争点树，
并为每个核心争点确定举证责任承担方及其证明命题。\
"""

EXTRACTION_PROMPT = """\
请从以下房屋买卖合同纠纷案件材料中提取争议焦点，输出结构化争点树。

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
      "title": "争点标题（简短描述，如\"合同效力\"）",
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
      "legal_basis": "《民法典》第XX条"
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

## 房屋买卖合同纠纷典型争点分类

| 争点 | 类型 | 说明 |
|---|---|---|
| 合同效力 | legal | 合同是否成立生效，是否存在无效或可撤销事由（欺诈、胁迫、显失公平） |
| 房屋交付事实 | factual | 出卖方是否按约定时间和条件交付房屋 |
| 产权过户义务 | mixed | 是否已办理不动产登记手续，障碍是否可归责于出卖方 |
| 违约事实认定 | factual | 哪方当事人违约，违约行为的具体内容与时间 |
| 定金/订金性质与效力 | legal | 款项性质认定，定金罚则是否适用 |
| 面积差异与价款调整 | factual | 实测面积与合同约定面积之差，超出约定误差范围的认定 |
| 质量瑕疵 | factual | 房屋是否存在质量问题，瑕疵是否属于出卖方责任范围 |
| 贷款审批不通过 | mixed | 贷款未获批准的原因，是否触发合同解除条件 |
| 违约金/损失赔偿 | mixed | 违约金数额认定，是否过高或过低需调整，损失范围举证 |

## 房屋买卖合同纠纷争点优先级链（P1–P5）

在提取争点时，应按以下优先级顺序识别和排列顶层争点。优先级高的争点（P1）通常是其他争点的前提，
若 P1 争点导致合同无效，则部分低优先级争点将转化为不当得利/返还之诉：

| 优先级 | 争点 | 触发条件 | 对下游争点的影响 |
|---|---|---|---|
| P1 | **合同效力** | 存在欺诈、胁迫、无权处分、违反强制性规定等无效/可撤销事由 | P1 合同无效则 P2–P5 违约责任框架失效，转为返还诉求 |
| P2 | **交付/过户条件是否满足** | 出卖方是否按期、按条件完成房屋交付及产权过户 | P2 交付瑕疵直接触发 P3 违约事实及 P4 违约金计算 |
| P3 | **违约事实认定** | 哪方当事人存在迟延、拒绝履行或不完全履行行为 | P3 影响责任归属，是 P4 计算的前提 |
| P4 | **定金/违约金金额** | 当事人主张定金罚则适用或要求支付/调整违约金 | 依赖 P3 违约事实；定金罚则与违约金通常不可并用 |
| P5 | **面积差异 / 质量瑕疵** | 实测面积与合同约定面积差异超出约定误差，或房屋存在质量问题 | 相对独立，但严重质量瑕疵可上升为 P2 交付条件争议 |

## 争点分解指引

当同一事实同时涉及事实认定与法律性质认定时，必须拆分为独立争点：
- 事实层争点（factual）：如「是否存在延期交房行为」「实测面积差异数值」
- 法律/混合层争点（mixed/legal）：如「延期交房是否构成根本违约」「定金罚则是否适用」

拆分原则：同一底层事实如果既需要证据验证，又需要法律定性，则创建平行或父子争点，不得合并为单一争点。

## 注意事项

1. `tmp_id` 格式为 `issue-tmp-001`、`issue-tmp-002` 等，仅用于本次输出内部引用
2. 顶层争点（`parent_tmp_id: null`）必须在 `burdens` 中至少分配一个举证责任
3. 输入中的每个 `claim_id` 和每个 `defense_id` 都必须出现在对应映射中
4. `fact_propositions` 应具体、可验证，避免泛泛而论
5. 子争点（有 parent_tmp_id）描述具体事实；顶层争点描述核心法律问题；当事实认定与法律定性并存时，必须拆分（参见争点分解指引）
6. 只输出 JSON 对象，不要输出任何其他内容
7. **JSON字符串值内禁止使用未转义的双引号**。如需引用原文词语，请使用中文引号「」，如「买卖合同」\
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
