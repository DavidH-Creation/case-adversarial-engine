---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\adversarial\agents\base_agent.py"
type: "code"
community: "C: Users"
location: "L31"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# BasePartyAgent

## Connections
- [[.__init__()_8]] - `method` [EXTRACTED]
- [[._build_claim_prompt()]] - `method` [EXTRACTED]
- [[._build_rebuttal_prompt()]] - `method` [EXTRACTED]
- [[._build_system_prompt()]] - `method` [EXTRACTED]
- [[._call_and_parse()]] - `method` [EXTRACTED]
- [[._parse_agent_output()]] - `method` [EXTRACTED]
- [[._validate_citations()]] - `method` [EXTRACTED]
- [[.generate_claim()]] - `method` [EXTRACTED]
- [[.generate_rebuttal()]] - `method` [EXTRACTED]
- [[Argument]] - `uses` [INFERRED]
- [[DefendantAgent]] - `uses` [INFERRED]
- [[DefendantAgent — 被告代理人，生成抗辩和反驳。 DefendantAgent — defendant party agent, generat]] - `uses` [INFERRED]
- [[EvidenceManager 返回空 evidence_citations 应触发重试后抛 RuntimeError。]] - `uses` [INFERRED]
- [[MockLLMClient]] - `uses` [INFERRED]
- [[PartyAgent 单元测试 — 使用 mock LLMClient，不调用真实 API。 PartyAgent unit tests — uses moc]] - `uses` [INFERRED]
- [[PlaintiffAgent]] - `uses` [INFERRED]
- [[PlaintiffAgent — 原告代理人，生成主张和反驳。 PlaintiffAgent — plaintiff party agent, generat]] - `uses` [INFERRED]
- [[RoundConfig]] - `uses` [INFERRED]
- [[TestDefendantAgent]] - `uses` [INFERRED]
- [[TestEvidenceManagerAgent]] - `uses` [INFERRED]
- [[TestPlaintiffAgent]] - `uses` [INFERRED]
- [[base_agent.py]] - `contains` [EXTRACTED]
- [[原告代理人。Plaintiff party agent.]] - `uses` [INFERRED]
- [[固定返回 JSON 的 mock LLM 客户端。]] - `uses` [INFERRED]
- [[场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.]] - `uses` [INFERRED]
- [[引用不在可见证据中的 ID 应触发重试，重试耗尽后抛 RuntimeError。]] - `uses` [INFERRED]
- [[当顶层 evidence_citations 为空时，应从 arguments 中聚合。]] - `uses` [INFERRED]
- [[所有当事方代理的基类，封装 LLM 调用和重试逻辑。 Base class for all party agents, encapsulating L]] - `rationale_for` [EXTRACTED]
- [[被告代理人。Defendant party agent.]] - `uses` [INFERRED]
- [[顶层 issue_ids 和 arguments 均为空时应 RuntimeError（禁止 unknown-issue fallback）。]] - `uses` [INFERRED]
- [[首次返回幻觉证据 ID，第二次返回合法 ID → 成功，共调用 2 次 LLM。]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users