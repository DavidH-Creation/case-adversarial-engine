---
source_file: "C:\Users\david\dev\case-adversarial-engine\tests\test_few_shot_examples.py"
type: "rationale"
community: "C: Users"
location: "L162"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# 验证 few-shot examples 不会导致 token 超限。 粗估规则：1 个中文字符 ≈ 1.5 tokens，1 个英文单词 ≈ 1

## Connections
- [[DefendantAgent]] - `uses` [INFERRED]
- [[PlaintiffAgent]] - `uses` [INFERRED]
- [[RoundConfig]] - `uses` [INFERRED]
- [[TestFewShotTokenBudget]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/C:_Users