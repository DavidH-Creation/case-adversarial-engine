"""
劳动争议（Labor Dispute）案件类型的程序设置 LLM 提示模板。
LLM prompt templates for labor dispute case type procedure setup.

用于指导 LLM 根据案件基本信息和争点树，生成完整的诉讼程序状态序列。
"""

SYSTEM_PROMPT = """\
你是一位专业的中国劳动争议案件程序设置分析师，擅长劳动合同纠纷、工资报酬及经济补偿金案件的庭审程序框架设计。
You are a professional civil litigation procedure setup analyst for Chinese courts, specializing in labor dispute cases.

你的任务是：根据案件当事人信息和争点树概要，为整个诉讼程序生成结构化的程序状态序列（ProcedureState）、程序配置和时间线事件。
Your task: given party information and the issue tree, generate a structured procedure state sequence (ProcedureState[]), procedure config, and timeline events for the complete litigation.

设计原则 / Design principles:
1. 必须严格按顺序覆盖以下全部八个阶段（phase）：
   case_intake → element_mapping → opening → evidence_submission → evidence_challenge → judge_questions → rebuttal → output_branching
2. 每个阶段的访问控制（readable_access_domains）必须遵循权限最小化原则
3. 裁判阶段（judge_questions）不得在 readable_access_domains 中包含 owner_private
4. 证据状态（admissible_evidence_statuses）必须按阶段递进
5. 时间线事件（relative_day）必须合理递增，体现实际庭审节奏
6. entry_conditions 和 exit_conditions 必须是可操作的清单项，不得写空字符串\
"""

SETUP_PROMPT = """\
请根据以下案件信息和争点树，生成完整的诉讼程序设置。

## 案件基本信息
案件 ID: {case_id}
案件类型: {case_type}
当事人概要:
{parties_block}

## 争点树（IssueTree）摘要

{issue_tree_block}

## 输出要求

请输出符合以下 JSON 结构的程序设置（**只输出 JSON，不要输出其他内容**）：

```json
{{
  "procedure_config": {{
    "evidence_submission_deadline_days": 15,
    "evidence_challenge_window_days": 10,
    "max_rounds_per_phase": 3,
    "applicable_laws": ["中华人民共和国劳动合同法", "中华人民共和国劳动争议调解仲裁法", "中华人民共和国民事诉讼法"]
  }},
  "procedure_states": [
    {{
      "phase": "case_intake",
      "allowed_role_codes": ["plaintiff_agent", "judge_agent", "evidence_manager"],
      "readable_access_domains": ["shared_common"],
      "writable_object_types": ["Party", "Claim", "Evidence"],
      "admissible_evidence_statuses": ["private"],
      "entry_conditions": ["仲裁前置程序已完成，仲裁裁决书已送达", "原告起诉状已接收"],
      "exit_conditions": ["被告已收到应诉通知", "双方当事人身份信息核实完毕"]
    }},
    {{
      "phase": "element_mapping",
      "allowed_role_codes": ["plaintiff_agent", "defendant_agent", "judge_agent"],
      "readable_access_domains": ["shared_common"],
      "writable_object_types": ["Issue", "Burden", "Claim", "Defense"],
      "admissible_evidence_statuses": ["private", "submitted"],
      "entry_conditions": ["案件受理完毕"],
      "exit_conditions": ["争点树梳理完成", "举证责任分配明确"]
    }},
    {{
      "phase": "opening",
      "allowed_role_codes": ["plaintiff_agent", "defendant_agent", "judge_agent"],
      "readable_access_domains": ["shared_common"],
      "writable_object_types": ["Claim", "Defense", "AgentOutput"],
      "admissible_evidence_statuses": ["submitted"],
      "entry_conditions": ["争点梳理完成"],
      "exit_conditions": ["原告陈述意见完毕", "被告陈述意见完毕"]
    }},
    {{
      "phase": "evidence_submission",
      "allowed_role_codes": ["plaintiff_agent", "defendant_agent", "evidence_manager"],
      "readable_access_domains": ["shared_common"],
      "writable_object_types": ["Evidence", "AgentOutput"],
      "admissible_evidence_statuses": ["private", "submitted"],
      "entry_conditions": ["举证期限已开始"],
      "exit_conditions": ["举证期限届满", "双方证据均已提交"]
    }},
    {{
      "phase": "evidence_challenge",
      "allowed_role_codes": ["plaintiff_agent", "defendant_agent", "evidence_manager", "judge_agent"],
      "readable_access_domains": ["shared_common", "admitted_record"],
      "writable_object_types": ["Evidence", "AgentOutput"],
      "admissible_evidence_statuses": ["submitted", "challenged"],
      "entry_conditions": ["举证期限届满"],
      "exit_conditions": ["质证程序完毕", "争议证据状态确定"]
    }},
    {{
      "phase": "judge_questions",
      "allowed_role_codes": ["judge_agent"],
      "readable_access_domains": ["shared_common", "admitted_record"],
      "writable_object_types": ["AgentOutput"],
      "admissible_evidence_statuses": ["admitted_for_discussion"],
      "entry_conditions": ["质证程序完毕"],
      "exit_conditions": ["法官问询完毕", "当事人问题已回复"]
    }},
    {{
      "phase": "rebuttal",
      "allowed_role_codes": ["plaintiff_agent", "defendant_agent", "judge_agent"],
      "readable_access_domains": ["shared_common", "admitted_record"],
      "writable_object_types": ["AgentOutput"],
      "admissible_evidence_statuses": ["admitted_for_discussion"],
      "entry_conditions": ["法官问询完毕"],
      "exit_conditions": ["双方辩论意见完毕"]
    }},
    {{
      "phase": "output_branching",
      "allowed_role_codes": ["judge_agent", "review_agent"],
      "readable_access_domains": ["shared_common", "admitted_record"],
      "writable_object_types": ["AgentOutput", "ReportArtifact"],
      "admissible_evidence_statuses": ["admitted_for_discussion"],
      "entry_conditions": ["辩论终结"],
      "exit_conditions": ["结论性意见生成完毕", "争点处理结果输出"]
    }}
  ],
  "timeline_events": [
    {{
      "event_type": "filing_deadline",
      "phase": "case_intake",
      "description": "案件登记与受理截止",
      "relative_day": 0,
      "is_mandatory": true
    }},
    {{
      "event_type": "evidence_submission_deadline",
      "phase": "evidence_submission",
      "description": "举证期限届满，双方完成证据提交",
      "relative_day": 15,
      "is_mandatory": true
    }},
    {{
      "event_type": "evidence_challenge_deadline",
      "phase": "evidence_challenge",
      "description": "质证期限届满",
      "relative_day": 25,
      "is_mandatory": true
    }},
    {{
      "event_type": "hearing_date",
      "phase": "opening",
      "description": "开庭审理日期",
      "relative_day": 30,
      "is_mandatory": true
    }}
  ]
}}
```

### 重要约束 / Critical constraints

1. **procedure_states 必须严格按以下顺序覆盖全部八个阶段**：
   `case_intake` → `element_mapping` → `opening` → `evidence_submission` →
   `evidence_challenge` → `judge_questions` → `rebuttal` → `output_branching`
2. **judge_questions 阶段禁止包含 `owner_private`**（judicial access constraint）
3. **output_branching 必须仅基于 `admitted_for_discussion` 状态的证据**
4. **entry_conditions 和 exit_conditions 必须非空**，且每项描述必须有实质内容
5. **时间线事件的 relative_day 必须合理递增**，体现实际庭审时间安排
6. **applicable_laws 应结合劳动争议案件特点**，至少包含《劳动合同法》和《劳动争议调解仲裁法》

### 劳动争议案件程序要点 / Labor dispute procedure considerations

- 劳动争议须经劳动仲裁前置程序，仲裁裁决是起诉的前提
- 举证期限通常为立案后 15 日，劳动者举证能力有限，法院可适当释明
- 用人单位对解除事由、工资发放、考勤记录等事实负举证责任
- 涉及工伤的案件，工伤认定书和劳动能力鉴定结论是核心证据
- 经济补偿金/赔偿金计算需精确认定工作年限和月平均工资\
"""


def format_parties_block(parties: list[dict]) -> str:
    """将当事人列表格式化为 prompt 输入块。"""

    def _escape(val: str) -> str:
        return (
            val.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    blocks = []
    for p in parties:
        safe_id = _escape(p.get("party_id", ""))
        safe_role = _escape(p.get("role_code", ""))
        blocks.append(
            f'<party id="{safe_id}" role="{safe_role}">\n'
            f"  姓名/名称: {p.get('name', '')}\n"
            f"  角色: {safe_role}\n"
            f"  立场: {p.get('side', '')}\n"
            f"</party>"
        )
    return "\n\n".join(blocks)


def format_issue_tree_block(issue_tree: dict) -> str:
    """将争点树格式化为 prompt 输入块。"""
    issues = issue_tree.get("issues", [])
    burdens = issue_tree.get("burdens", [])

    lines = []

    root_issues = [i for i in issues if not i.get("parent_issue_id")]
    child_issues = [i for i in issues if i.get("parent_issue_id")]

    lines.append("### 顶层争点（root issues）")
    for issue in root_issues:
        lines.append(f"\n**{issue['issue_id']}**: {issue['title']}")
        lines.append(f"  类型: {issue.get('issue_type', 'factual')}")
        if issue.get("evidence_ids"):
            lines.append(f"  关联证据: {', '.join(issue['evidence_ids'])}")
        for fp in issue.get("fact_propositions", []):
            lines.append(f"  - 事实命题: {fp.get('text', '')} [{fp.get('status', 'unverified')}]")

    if child_issues:
        lines.append("\n### 子争点（sub-issues）")
        for issue in child_issues:
            lines.append(
                f"\n**{issue['issue_id']}** (父: {issue['parent_issue_id']}): {issue['title']}"
            )
            if issue.get("evidence_ids"):
                lines.append(f"  关联证据: {', '.join(issue['evidence_ids'])}")

    if burdens:
        lines.append("\n### 举证责任")
        for b in burdens:
            lines.append(
                f"  {b['burden_id']} → {b['issue_id']}: "
                f"{b.get('description', '')} [{b.get('status', '')}]"
            )

    return "\n".join(lines)
