"""
民间借贷（Civil Loan）案件类型的场景推演 LLM 提示模板。
LLM prompt templates for civil loan (民间借贷) case type scenario simulation.

用于指导 LLM 根据争点树、证据索引和变更集，逐争点分析变更影响。
Guides LLM to analyze per-issue impact of the change_set given IssueTree and EvidenceIndex.
"""

SYSTEM_PROMPT = """\
你是一位专业的中国民事诉讼案件对抗推演分析师，擅长民间借贷纠纷案件的攻防影响分析。
You are a professional adversarial scenario analyst for Chinese civil litigation, specializing in civil loan disputes.

你的任务是：给定一组已发生的变量注入（change_set），逐争点分析这些变化对案件各争点的实质影响。
Your task: given a set of injected changes (change_set), analyze the material impact of those changes on each affected issue.

分析要求：
Analysis requirements:
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

请输出符合以下 JSON 结构的差异分析（**只输出 JSON，不要输出其他内容**）：

```json
{{
  "summary": "整体变更影响的简要概述（1-3句，可为空字符串）",
  "diff_entries": [
    {{
      "issue_id": "issue-xxx-001",
      "impact_description": "说明该变更如何影响此争点，必须可追溯到 change_set 中的具体变更",
      "direction": "weaken"
    }}
  ]
}}
```

### 重要约束

1. **仅列出受 change_set 实际影响的争点**，未受影响的争点不得出现在 diff_entries 中
2. **每条 impact_description 必须非空**，且明确引用或说明是 change_set 中哪项变更导致了该影响
3. **direction 必须是以下之一**：`strengthen`（增强己方立场）、`weaken`（削弱己方立场）、`neutral`（有实质变化但无净方向影响）
4. **只报告客观影响，不生成策略建议**——引擎仅报告变更结果，不建议进一步操作
5. **所有 issue_id 必须来自上方争点树中的实际 ID**

### 民间借贷案件变更分析重点

- **证据降级**（原件→复印件）：直接削弱真实性认定，通常 `weaken` 借贷关系相关争点
- **金额变更**：影响诉讼标的，可能 `strengthen` 或 `weaken` 还款争点
- **时间节点变更**：影响诉讼时效认定，可能 `weaken` 或 `neutral` 时效争点
- **当事人信息变更**：影响主体资格争点，通常需标注 `direction`
- **证据新增/撤回**：视具体情况分析对各争点的支撑度变化\
"""


def format_issue_tree_block(issue_tree: dict) -> str:
    """将争点树格式化为 prompt 输入块。
    Format the IssueTree into a readable prompt block.
    """
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
            for fp in issue.get("fact_propositions", []):
                lines.append(
                    f"  - 事实命题: {fp.get('text', '')} [{fp.get('status', 'unverified')}]"
                )

    if burdens:
        lines.append("\n### 举证责任")
        for b in burdens:
            lines.append(
                f"  {b['burden_id']} → {b['issue_id']}: "
                f"{b.get('description', '')} [{b.get('status', '')}]"
            )

    return "\n".join(lines)


def format_evidence_block(evidence_list: list[dict]) -> str:
    """将证据列表格式化为 prompt 输入块。
    Format the evidence list into a readable prompt block.

    使用 XML 标签隔离每条证据防止注入。
    Uses XML tags to isolate each evidence item against prompt injection.
    """

    def _escape(val: str) -> str:
        return (
            val.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    blocks = []
    for e in evidence_list:
        safe_id = _escape(e.get("evidence_id", ""))
        safe_type = _escape(e.get("evidence_type", ""))
        safe_summary = _escape(e.get("summary", ""))
        blocks.append(
            f'<evidence id="{safe_id}" type="{safe_type}">\n'
            f"  标题: {e.get('title', '')}\n"
            f"  摘要: {safe_summary}\n"
            f"  状态: {e.get('status', 'private')}\n"
            f"</evidence>"
        )
    return "\n\n".join(blocks)


def format_change_set_block(change_set: list[dict]) -> str:
    """将变更集格式化为 prompt 输入块。
    Format the change_set into a readable prompt block.

    使用 XML 标签隔离每条变更项防止注入。
    Uses XML tags to isolate each change item against prompt injection.
    """
    if not change_set:
        return "（无变更项 / No change items）"

    blocks = []
    for idx, c in enumerate(change_set, start=1):
        # 转义旧值/新值中的 XML 特殊字符 / Escape XML special chars in old/new value
        def _safe(val: object) -> str:
            s = str(val) if val is not None else "null"
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        blocks.append(
            f'<change index="{idx}" type="{c.get("target_object_type", "")}">\n'
            f"  目标对象 ID: {c.get('target_object_id', '')}\n"
            f"  字段路径: {c.get('field_path', '')}\n"
            f"  旧值: {_safe(c.get('old_value'))}\n"
            f"  新值: {_safe(c.get('new_value'))}\n"
            f"</change>"
        )
    return "\n\n".join(blocks)
