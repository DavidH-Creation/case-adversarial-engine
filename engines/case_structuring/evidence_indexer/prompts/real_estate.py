"""
房屋买卖合同纠纷（Real Estate）案件类型的 LLM 提示模板。

用于指导 LLM 从原始案件材料中提取并结构化证据信息。
"""

SYSTEM_PROMPT = """\
你是一位专业的中国房屋买卖合同纠纷证据分析专家，擅长房产交易合同效力、交付、产权过户、违约及贷款纠纷案件的证据梳理。
你的任务是从原始案件材料中识别、提取并结构化每条证据。\
"""

EXTRACTION_PROMPT = """\
请从以下案件原始材料中提取并结构化每条证据。

## 案件信息
案件 ID: {case_id}
案件类型: 房屋买卖合同纠纷

## 原始材料

{materials}

## 输出要求

对于每条原始材料，请提取以下信息并以 **JSON 数组** 格式输出：

```json
[
  {{
    "title": "证据标题（简短描述，如\"房屋买卖合同原件\"、\"定金收据\"）",
    "summary": "证据内容摘要（概括该证据证明了什么事实）",
    "evidence_type": "证据类型（见下方枚举值）",
    "source_id": "对应的原始材料 source_id",
    "target_facts": ["该证据能够证明的事实命题（用简短的事实 ID 描述）"],
    "target_issues": ["该证据关联的争议焦点（如有）"]
  }}
]
```

### 证据类型枚举值
- `documentary` — 书证（买卖合同、收据、产权证、不动产登记证明等纸质文件）
- `physical` — 物证（房屋实物状态）
- `witness` — 证人证言
- `electronic` — 电子数据（网签合同、银行转账记录、短信/微信沟通记录等）
- `expert_opinion` — 鉴定意见（如房屋质量鉴定、面积测绘报告）
- `inspection` — 勘验笔录（房屋现场勘验）
- `party_statement` — 当事人陈述

### 房屋买卖合同纠纷关键事实命题参考
- 买卖合同成立事实（合同签署、网签情况）
- 购房款支付事实（金额、时间、方式）
- 定金/订金支付事实及金额
- 房屋交付事实（交房时间、钥匙交接）
- 产权过户申请及办理情况
- 房屋面积实测数据（与合同约定对比）
- 房屋质量瑕疵存在事实
- 贷款审批结果及原因
- 违约行为发生事实（逾期交房、逾期付款等）

### 注意事项
1. 每条原始材料至少提取一条证据
2. `target_facts` 不能为空，每条证据至少绑定一条事实命题
3. 事实命题 ID 使用 `fact-` 前缀加简短英文描述，如 `fact-sale-contract-existence-001`
4. 争议焦点 ID 使用 `issue-` 前缀，如 `issue-delivery-delay-001`
5. 请只输出 JSON 数组，不要输出其他内容
6. **JSON字符串值内禁止使用未转义的双引号**。如需引用原文中的词语，请使用中文引号「」或书名号《》，例如：备注为「定金」，而不是 备注为"定金"\
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
