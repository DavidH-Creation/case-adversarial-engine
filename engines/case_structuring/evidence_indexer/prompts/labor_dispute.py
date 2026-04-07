"""
劳动争议（Labor Dispute）案件类型的 LLM 提示模板。

用于指导 LLM 从原始案件材料中提取并结构化证据信息。
"""

SYSTEM_PROMPT = """\
你是一位专业的中国劳动争议案件证据分析专家，擅长劳动合同纠纷、工资报酬、经济补偿金及工伤赔偿等案件的证据梳理。
你的任务是从原始案件材料中识别、提取并结构化每条证据。\
"""

EXTRACTION_PROMPT = """\
请从以下案件原始材料中提取并结构化每条证据。

## 案件信息
案件 ID: {case_id}
案件类型: 劳动争议纠纷

## 原始材料

{materials}

## 输出要求

对于每条原始材料，请提取以下信息并以 **JSON 数组** 格式输出：

```json
[
  {{
    "title": "证据标题（简短描述，如\"劳动合同原件\"、\"工资银行流水\"）",
    "summary": "证据内容摘要（概括该证据证明了什么事实）",
    "evidence_type": "证据类型（见下方枚举值）",
    "source_id": "对应的原始材料 source_id",
    "target_facts": ["该证据能够证明的事实命题（用简短的事实 ID 描述）"],
    "target_issues": ["该证据关联的争议焦点（如有）"]
  }}
]
```

### 证据类型枚举值
- `documentary` — 书证（劳动合同、解除通知、工资单等纸质文件）
- `physical` — 物证
- `witness` — 证人证言
- `electronic` — 电子数据（考勤系统记录、银行转账记录、微信工资截图等）
- `expert_opinion` — 鉴定意见（如劳动能力鉴定书）
- `inspection` — 勘验笔录
- `party_statement` — 当事人陈述

### 劳动争议案件关键事实命题参考
- 劳动关系成立事实（是否签订劳动合同）
- 劳动合同期限与岗位约定
- 实际工作年限
- 工资标准及实际发放金额
- 加班事实及加班时长
- 解除/终止劳动合同的原因与程序
- 社保公积金缴纳情况
- 工伤事故发生事实
- 竞业限制协议存在及补偿支付事实

### 注意事项
1. 每条原始材料至少提取一条证据
2. `target_facts` 不能为空，每条证据至少绑定一条事实命题
3. 事实命题 ID 使用 `fact-` 前缀加简短英文描述，如 `fact-labor-contract-existence-001`
4. 争议焦点 ID 使用 `issue-` 前缀，如 `issue-wrongful-termination-001`
5. 请只输出 JSON 数组，不要输出其他内容
6. **JSON字符串值内禁止使用未转义的双引号**。如需引用原文中的词语，请使用中文引号「」或书名号《》，例如：备注为「工资」，而不是 备注为"工资"\
"""


def format_materials_block(materials) -> str:
    """格式化材料列表为 prompt 输入块（带 XML 分隔防注入）"""
    blocks = []
    for m in materials:
        safe_source_id = (
            m.source_id.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        safe_text = m.text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        blocks.append(f'<material source_id="{safe_source_id}">\n{safe_text}\n</material>')
    return "\n\n".join(blocks)


def build_user_prompt(*, case_id: str, materials) -> str:
    """构建证据索引器 user prompt（CaseTypePlugin 协议入口）。"""
    materials_block = format_materials_block(materials)
    return EXTRACTION_PROMPT.format(case_id=case_id, materials=materials_block)
