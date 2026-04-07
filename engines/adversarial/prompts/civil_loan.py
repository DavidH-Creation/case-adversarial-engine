"""
民间借贷案型对抗 prompt — 案由专用提示词补充。
Civil loan case type adversarial prompts — case-type specific prompt supplements.

主要用于为 PlaintiffAgent / DefendantAgent 提供案由上下文注入，
以及 EvidenceManagerAgent 的冲突分析语境。
"""

# ---------------------------------------------------------------------------
# 民间借贷核心法律要素（注入系统提示）
# Civil loan core legal elements (injected into system prompts)
# ---------------------------------------------------------------------------

CASE_CONTEXT = """
【民间借贷案件要点】
核心争点类型：
1. 借贷关系是否成立（是否有借条/转账记录/证人证词）
2. 借款金额认定（实际交付金额 vs 借条金额）
3. 利率合法性（是否超过法定上限）
4. 还款事实认定（有无还款记录/收条）
5. 诉讼时效（是否超过3年）

举证要点：
- 原告须证明：借贷合意 + 实际交付
- 被告可抗辩：未收到款项 / 已还款 / 利率无效 / 时效届满
"""

# ---------------------------------------------------------------------------
# 证据审查维度（民间借贷专用）
# Evidence review dimensions (civil loan specific)
# ---------------------------------------------------------------------------

EVIDENCE_REVIEW_CRITERIA = """
民间借贷证据审查维度：
- 借条/借款协议：签名真实性、金额一致性、日期合理性
- 转账记录：流向、金额、备注说明
- 微信/短信记录：是否有催款/还款承诺
- 收条：真实性、对应关系
- 证人证词：利害关系、陈述一致性
"""


def build_user_prompt(**_kwargs: object) -> str:
    """构建对抗引擎案由上下文（CaseTypePlugin 协议入口）。

    Returns the case-type-specific context block to be injected into agent
    system prompts (Plaintiff/Defendant/EvidenceManager). Concatenates
    ``CASE_CONTEXT`` and ``EVIDENCE_REVIEW_CRITERIA`` so a single call from
    ``plugin.get_prompt(...)`` returns the complete adversarial context for
    this case type.

    Accepts (and ignores) arbitrary kwargs so callers don't have to know
    which subset of an engine context dict is relevant. The constants are
    static — there are no placeholders to substitute.

    Note: agent code currently builds prompts inline and does not yet
    consume this. Wiring agents to inject ``plugin.get_prompt(...)`` is
    tracked as Unit 14 follow-up Group 2 work.
    """
    return f"{CASE_CONTEXT}\n{EVIDENCE_REVIEW_CRITERIA}"
