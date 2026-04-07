"""
房屋买卖合同纠纷案型对抗 prompt — 案由专用提示词补充。
Real estate sale contract dispute adversarial prompts — case-type specific prompt supplements.

主要用于为 PlaintiffAgent / DefendantAgent 提供案由上下文注入，
以及 EvidenceManagerAgent 的冲突分析语境。
"""

# ---------------------------------------------------------------------------
# 房屋买卖合同纠纷核心法律要素（注入系统提示）
# Real estate core legal elements (injected into system prompts)
# ---------------------------------------------------------------------------

CASE_CONTEXT = """
【房屋买卖合同纠纷案件要点】
核心争点类型：
1. 合同效力（合同是否成立生效，是否存在欺诈/胁迫/显失公平等无效/可撤销事由）
2. 房屋交付（是否按约定时间和条件完成交付，延迟交付的责任归属）
3. 产权过户（不动产登记是否完成，障碍原因及责任归属）
4. 违约责任（哪方违约、违约时间、违约金计算）
5. 定金/订金性质（款项性质认定，定金罚则是否适用）
6. 面积差异（实测面积与合同约定差异是否超出约定误差，价款如何调整）
7. 质量瑕疵（房屋是否存在隐蔽瑕疵，瑕疵修复责任）
8. 贷款审批（贷款未获批是否触发合同解除条款，定金是否退还）

举证要点：
- 买受方须证明：合同成立、付款事实、对方违约（逾期交房/不配合过户）
- 出卖方须证明：交房/过户义务已履行、买受方逾期付款或违约、
  贷款未获批系买受方自身原因
"""

# ---------------------------------------------------------------------------
# 证据审查维度（房屋买卖专用）
# Evidence review dimensions (real estate specific)
# ---------------------------------------------------------------------------

EVIDENCE_REVIEW_CRITERIA = """
房屋买卖合同纠纷证据审查维度：
- 买卖合同：是否有双方签名及日期，是否已网签备案，与口头约定是否存在出入
- 付款凭证：银行转账记录与收据是否对应，定金/首付/尾款性质是否明确
- 交房记录：收房确认书、钥匙交接凭证、房屋验收单的真实性与完整性
- 不动产权证/登记证明：官方核发，权威性强，但需关注是否存在抵押/查封等权利负担
- 贷款审批文件：银行审批结论及原因，是否存在买受方主观原因导致审批失败
- 面积测绘报告：是否由具备资质的测绘机构出具，测量方法是否规范
- 往来函件/微信记录：催告违约行为的送达时效，截图完整性与设备溯源
"""


def build_user_prompt(**_kwargs: object) -> str:
    """构建对抗引擎案由上下文（CaseTypePlugin 协议入口）。

    Returns the case-type-specific context block to be injected into agent
    system prompts. See ``civil_loan.build_user_prompt`` for the rationale
    behind the kwargs-tolerant signature.
    """
    return f"{CASE_CONTEXT}\n{EVIDENCE_REVIEW_CRITERIA}"
