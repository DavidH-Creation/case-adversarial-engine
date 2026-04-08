---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\decision_path_tree\schemas.py"
type: "code"
community: "C: Users"
location: "L65"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# LLMDecisionPathTreeOutput

## Connections
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[DecisionPathTreeGenerator]] - `uses` [INFERRED]
- [[IssueDependencyGraphGenerator — 争点依赖图构建器（P2）。 Issue Dependency Graph Generator]] - `uses` [INFERRED]
- [[LLM 失败时返回空 DecisionPathTree。]] - `uses` [INFERRED]
- [[Normalize alternative field names LLM may use. LLM sometimes returns]] - `uses` [INFERRED]
- [[schemas.py]] - `contains` [EXTRACTED]
- [[从争点标题提取核心中文片段，用于模糊匹配。 去掉常见虚词后，提取所有 ≥4 字的连续中文片段。]] - `uses` [INFERRED]
- [[从已处理的路径列表计算路径排序结果（v3：不再使用 probability）。 Sort criteria (stable, determ]] - `uses` [INFERRED]
- [[从推断出的 issue_ids 通过 canonical linkage 派生 evidence_ids。 优先级： 1]] - `uses` [INFERRED]
- [[从路径文本中推断 trigger_issue_ids。 按标题长度倒序匹配，避免短标题被长标题子串误命中。 支持两层匹配]] - `uses` [INFERRED]
- [[检查是否有任一片段（或其 ≥4 字子串）出现在目标文本中。 先尝试完整片段匹配，再尝试滑窗子串匹配。]] - `uses` [INFERRED]
- [[生成裁判路径树。 Args inp 生成器输入 Returns]] - `uses` [INFERRED]
- [[裁判路径树生成器。 Args llm_client 符合 LLMClient 协议的客户端实例 case]] - `uses` [INFERRED]
- [[规则层处理阻断条件，并自动注入来自 unresolved_conflicts 的 amount_conflict。]] - `uses` [INFERRED]
- [[规范化 LLM 输出 dict，失败时返回 None。_1]] - `uses` [INFERRED]
- [[调用 LLM（结构化输出），失败时返回 None（不抛异常）。_1]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users