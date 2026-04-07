"""
劳动争议案型对抗 prompt — 案由专用提示词补充。
Labor dispute case type adversarial prompts — case-type specific prompt supplements.

主要用于为 PlaintiffAgent / DefendantAgent 提供案由上下文注入，
以及 EvidenceManagerAgent 的冲突分析语境。
"""

# ---------------------------------------------------------------------------
# 劳动争议核心法律要素（注入系统提示）
# Labor dispute core legal elements (injected into system prompts)
# ---------------------------------------------------------------------------

CASE_CONTEXT = """
【劳动争议案件要点】
核心争点类型：
1. 劳动关系是否成立（是否签订合法劳动合同，是否存在实际用工关系）
2. 劳动合同解除/终止合法性（解除原因是否成立，程序是否符合法定要求）
3. 工资报酬拖欠（实际发放工资是否低于约定或法定标准）
4. 加班费争议（加班时长认定、计算基数合规性）
5. 经济补偿金/赔偿金（工作年限认定、月工资基数、N 或 2N 倍数适用）
6. 社保公积金欠缴（缴纳基数、险种、欠缴期间）
7. 竞业限制（协议效力、补偿金支付义务）
8. 工伤赔偿（工伤认定、伤残等级、赔偿项目）

举证要点：
- 劳动者须证明：劳动关系成立、拖欠工资/违法解除等基本事实
- 用人单位须证明：合法解除依据（违纪证明、绩效记录等）、工资足额支付（工资单签收）、
  加班系劳动者自愿（书面同意）
"""

# ---------------------------------------------------------------------------
# 证据审查维度（劳动争议专用）
# Evidence review dimensions (labor dispute specific)
# ---------------------------------------------------------------------------

EVIDENCE_REVIEW_CRITERIA = """
劳动争议证据审查维度：
- 劳动合同：签名真实性、期限与岗位条款、是否由用人单位保管导致劳动者无法提供
- 工资发放记录：银行流水与工资单是否一致，是否存在现金发放无凭证问题
- 考勤记录：系统数据完整性、是否经劳动者确认、有无篡改痕迹
- 解除通知/辞职信：送达时间与方式、内容是否符合法定解除事由
- 违纪记录/绩效考核：是否经劳动者签字确认，处分程序是否合规（工会告知等）
- 仲裁裁决书/庭审记录：是否已经过劳动仲裁前置程序
"""


def build_user_prompt(**_kwargs: object) -> str:
    """构建对抗引擎案由上下文（CaseTypePlugin 协议入口）。

    Returns the case-type-specific context block to be injected into agent
    system prompts. See ``civil_loan.build_user_prompt`` for the rationale
    behind the kwargs-tolerant signature.
    """
    return f"{CASE_CONTEXT}\n{EVIDENCE_REVIEW_CRITERIA}"
