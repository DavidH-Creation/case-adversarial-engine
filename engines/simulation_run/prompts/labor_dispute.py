"""
劳动争议（Labor Dispute）案件类型的场景推演 LLM 提示模板。
LLM prompt templates for labor dispute case type scenario simulation.

用于指导 LLM 根据争点树、证据索引和变更集，逐争点分析变更影响。
"""

SYSTEM_PROMPT = """\
你是一位专业的中国劳动争议案件对抗推演分析师，擅长劳动合同纠纷、工资报酬及经济补偿金案件的攻防影响分析。
You are a professional adversarial scenario analyst for Chinese civil litigation, specializing in labor dispute cases.

你的任务是：给定一组已发生的变量注入（change_set），逐争点分析这些变化对案件各争点的实质影响。
Your task: given a set of injected changes (change_set), analyze the material impact of those changes on each affected issue.

分析要求：
1. 仅报告 change_set 实际影响的争点，未受影响的争点不得列入 diff_entries
2. 每条 diff_entry 的 impact_description 必须明确说明变化如何影响该争点，可追溯到 change_set 中至少一条具体变更
3. direction 必须是 strengthen（增强）/ weaken（削弱）/ neutral（无净方向影响）之一
4. 不生成推测性策略建议，只报告变更的客观影响（结果报告，非策略生成）
5. 所有引用的 issue_id 必须来自输入争点树中的实际 ID\
"""

SIMULATION_PROMPT = """\
请根据以下案件信息和变更集，生成场景推演差异分析。

## 案件信息
案件 ID: {case_id}
场景 ID: {scenario_id}

## 争点树（IssueTree）

{issue_tree_block}

## 证据索引（EvidenceIndex）

{evidence_block}

## 变更集（ChangeSet）— 已注入的变量

{change_set_block}

## 输出要求

请输出符合以下 JSON 结构的推演差异（**只输出 JSON，不要输出其他内容**）：

```json
{{
  "scenario_id": "{scenario_id}",
  "diff_entries": [
    {{
      "issue_id": "issue-xxx",
      "direction": "strengthen | weaken | neutral",
      "impact_description": "具体说明变更如何影响该争点（引用 change_set 中的具体变更）",
      "affected_party": "plaintiff | defendant | both | neutral",
      "change_references": ["change-001"]
    }}
  ]
}}
```

### 劳动争议案件变更影响分析要点

- 新增考勤记录或工资条：影响工资/加班费争点（增强或削弱一方主张）
- 解除通知送达证明：影响解除程序合法性争点
- 仲裁裁决书中的认定事实：对诉讼阶段的争点认定具有参考约束力
- 社保缴纳凭证变更：影响社保欠缴金额的认定
- 竞业限制补偿金支付证明：影响竞业限制协议效力争点\
"""
