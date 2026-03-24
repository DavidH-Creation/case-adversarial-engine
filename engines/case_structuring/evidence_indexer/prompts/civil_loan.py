"""
民间借贷（Civil Loan）案件类型的 LLM 提示模板。

用于指导 LLM 从原始案件材料中提取并结构化证据信息。
"""

SYSTEM_PROMPT = """\
你是一位专业的中国民事诉讼证据分析专家，擅长民间借贷纠纷案件的证据梳理。
你的任务是从原始案件材料中识别、提取并结构化每条证据。\
"""

EXTRACTION_PROMPT_TEMPLATE = """\
请从以下案件原始材料中提取并结构化每条证据。

## 案件信息
- 案件 ID: {case_id}
- 案件类型: 民间借贷纠纷
- 材料提交方: {owner_party_id}

## 原始材料

{materials_block}

## 输出要汃

对于每条原始材料，请提取以下信息并以 **JSON 数组** 格式输出：

```json
[
  {{
    "title": "证据标题（简短描述，如"借条原件"、"银行转账电子回单"）",
    "summary": "证据内容摘要（概括该证据证明了什么事实）",
    "evidence_type": "证据类型（见下方枚举值）",
    "source_id": "对应的原始材料 source_id",
    "target_facts": ["该证据能够证明的事实命题（用简短的事实 ID 描述）"],
    "target_issues": ["该证据关联的争议焦点（如有）"]
  }}
]
```

### 证据类型枚举值
- `documentary` — 书证（借条、合同、收据等纸质文件）
- `physical` — 物证
- `witness_statement` — 证人证言
- `electronic_data` — 电子数据（银行转账记录、微信聊天记录、电子邮件等）
- `expert_opinion` — 鉴定意见
- `audio_visual` — 视听资料（录音、录像）
- `other` — 其他

### 民间借贷案件关键事实命题参考
- 借贷合意的成立（借条、合同是否存在）
- 借款金额
- 款项实际交付（出借行为是否履行）
- 利率约定
- 还款期限
- 逾期事实
- 借款人身份确认
- 还款事实

### 注意事项
1. 每条原始材料至少提取一条证据
2. `target_facts` 不能为空，每条证据至少绑定一条事实命题
3. 事实命题 ID 使用 `fact-` 前缀加简短英文描述，如 `fact-loan-contract-existence-001`
4. 争议焦点 ID 使用 `issue-` 前缀，如 `issue-loan-contract-validity-001`
5. 请只输出 JSON 数组，不要输出其他内容\
"""


def format_materials_block(materials: list[dict]) -> str:
    """将原始材料列表格式化为 prompt 中的文本块。"""
    blocks = []
    for i, mat in enumerate(materials, 1):
        source_id = mat.get("source_id", f"unknown-{i}")
        text = mat.get("text", "")
        metadata = mat.get("metadata", {})
        doc_type = metadata.get("document_type", "unknown")
        date = metadata.get("date", "unknown")

        block = (
            f"### 材料 {i}\n"
            f"- source_id: `{source_id}`\n"
            f"- 文档类型: {doc_type}\n"
            f"- 日期: {date}\n"
            f"- 内容:\n{text}"
        )
        blocks.append(block)
    return "\n\n".join(blocks)


def build_extraction_prompt(
    case_id: str,
    owner_party_id: str,
    materials: list[dict],
) -> str:
    """构建完整的证据提取 prompt。"""
    materials_block = format_materials_block(materials)
    return EXTRACTION_PROMPT_TEMPLATE.format(
        case_id=case_id,
        owner_party_id=owner_party_id,
        materials_block=materials_block,
    )
