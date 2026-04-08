---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\issue_category_classifier\classifier.py"
type: "rationale"
community: "C: Users"
location: "L175"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 将 LLM 分类结果校验后富化到 Issue 对象。 校验失败规则（任一失败 → 清空 issue_category，记入 unclass

## Connections
- [[._apply_classifications()]] - `rationale_for` [EXTRACTED]
- [[IssueCategoryClassificationResult]] - `uses` [INFERRED]
- [[IssueCategoryClassifierInput]] - `uses` [INFERRED]
- [[LLMIssueCategoryItem]] - `uses` [INFERRED]
- [[LLMIssueCategoryOutput]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users