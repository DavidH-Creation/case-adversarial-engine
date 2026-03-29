"""
PlaintiffAgent — 原告代理人，生成主张和反驳。
PlaintiffAgent — plaintiff party agent, generates claims and rebuttals.
"""
from __future__ import annotations

from engines.shared.models import AgentOutput, AgentRole, Evidence, IssueTree

from .base_agent import BasePartyAgent


class PlaintiffAgent(BasePartyAgent):
    """原告代理人。Plaintiff party agent."""

    def __init__(self, llm_client, party_id: str, config) -> None:
        super().__init__(llm_client, AgentRole.plaintiff_agent, party_id, config)

    # ------------------------------------------------------------------
    # prompt 实现 / Prompt implementations
    # ------------------------------------------------------------------

    def _build_system_prompt(self) -> str:
        return (
            "你是一位专业民事诉讼代理律师，代表**原告方**进行法庭辩论。\n"
            "你的职责：\n"
            "1. 基于争点树和可见证据，构建有力的主张或反驳。\n"
            "2. 每个论点必须引用具体的证据ID（evidence_id），禁止无证据支撑的论点。\n"
            "3. 输出严格遵循指定的JSON格式，不得输出JSON以外的内容。\n"
            "4. 论点字数控制在600字以内，聚焦核心争点。\n"
            "5. 反驳时必须明确指出对方论点的具体弱点，并用证据反击。\n"
            "6. 客观性校准：必须在 own_weaknesses 字段中诚实列出本方主张的薄弱点"
            "（如孤证、间接推定、证据关联性弱等），至少列出一条。\n"
            "7. 孤证标注：当某论点仅依赖单一证据来源时，在 position 中注明"
            "「（孤证，证明力需质证确认）」。\n"
            "\n重要：你必须只输出JSON对象，不要输出任何解释文字。"
        )

    def _build_claim_prompt(
        self,
        issue_tree: IssueTree,
        visible_evidence: list[Evidence],
        context_outputs: list[AgentOutput],
    ) -> str:
        issue_summary = self._format_issue_tree_summary(issue_tree)
        ev_list = self._format_evidence_list(visible_evidence)
        prior = self._format_prior_outputs(context_outputs)
        schema = self._json_output_schema()

        return f"""## 任务：提交原告首轮主张

### 案件争点
{issue_summary}

### 你（原告）可见证据
{ev_list}

### 历史上下文
{prior}

### 要求
- 针对每个争点提出明确的主张立场
- 每条 argument 的 supporting_evidence_ids 必须非空，且只能引用上方证据列表中的 evidence_id
- 指出被告可能提出的弱点并预先防御
- case_id 字段填写: {issue_tree.case_id}

### 输出格式（严格JSON，不含注释）
{schema}"""

    def _build_rebuttal_prompt(
        self,
        issue_tree: IssueTree,
        visible_evidence: list[Evidence],
        context_outputs: list[AgentOutput],
        opponent_outputs: list[AgentOutput],
    ) -> str:
        issue_summary = self._format_issue_tree_summary(issue_tree)
        ev_list = self._format_evidence_list(visible_evidence)
        prior = self._format_prior_outputs(context_outputs)
        opponent = self._format_prior_outputs(opponent_outputs)
        schema = self._json_output_schema()

        # 收集对方 output_id 列表供 LLM 引用
        opp_ids = ", ".join(o.output_id for o in opponent_outputs) if opponent_outputs else "（无）"

        return f"""## 任务：提交原告针对性反驳

### 案件争点
{issue_summary}

### 你（原告）可见证据
{ev_list}

### 被告方输出（你需要逐一反驳）
{opponent}
可引用的被告 output_id: {opp_ids}

### 历史上下文
{prior}

### 要求
- 必须针对被告每条论点进行具体反驳（在 argument 中设置 rebuttal_target_output_id）
- 每条反驳必须引用具体证据ID（supporting_evidence_ids）
- 指出被告证据的瑕疵或证明力不足之处
- case_id 字段填写: {issue_tree.case_id}

### 输出格式（严格JSON，不含注释）
注意：arguments 中每项可增加 "rebuttal_target_output_id" 字段，填写被告 output_id
{schema}"""
