---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\evidence_indexer\schemas.py"
type: "code"
community: "C: Users"
location: "L54"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# LLMEvidenceItem

## Connections
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[EvidenceIndexer]] - `uses` [INFERRED]
- [[LLM 返回的单条证据提取结果（尚未补全 ID 等字段）。]] - `rationale_for` [EXTRACTED]
- [[schemas.py]] - `contains` [EXTRACTED]
- [[加载案由对应的 prompt 模板模块 Load prompt template module for the given case type]] - `uses` [INFERRED]
- [[将 LLM 提取的原始项转化为 Evidence 对象 Convert LLM-extracted raw items into Eviden]] - `uses` [INFERRED]
- [[将 LLM 返回的证据类型字符串解析为枚举值 Map LLM-returned evidence type string to enum value.]] - `uses` [INFERRED]
- [[执行证据索引 Execute evidence indexing. Args materials 原始案]] - `uses` [INFERRED]
- [[证据索引器 Evidence Indexer. 将原始案件材料通过 LLM 提取为结构化 Evidence 对象。 Extra]] - `uses` [INFERRED]
- [[证据索引器核心模块 Evidence Indexer core module. 将原始案件材料转化为结构化 Evidence 对象。 Transfor]] - `uses` [INFERRED]
- [[调用 LLM 并返回证据条目列表（结构化输出优先，fallback 到 json_utils）。 Call LLM and return li]] - `uses` [INFERRED]
- [[验证输入材料 Validate input materials. Raises ValueError 输]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users