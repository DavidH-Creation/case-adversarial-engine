"""
AdversarialSummarizer — 三轮对抗结束后的 LLM 语义分析总结层。
AdversarialSummarizer — LLM-powered semantic summary layer after three adversarial rounds.

接收 AdversarialResult（含 5 个 AgentOutput），调用 LLM 进行全局分析，
输出结构化 AdversarialSummary（最强论证、未闭合争点原因、缺证分析、整体态势）。

Takes AdversarialResult (5 AgentOutputs), calls LLM for global analysis,
outputs structured AdversarialSummary (strongest arguments, unresolved issue reasons,
missing evidence analysis, overall assessment).
"""

from __future__ import annotations

from engines.shared.json_utils import _extract_json_object
from engines.shared.models import IssueTree, LLMClient

from .schemas import (
    AdversarialResult,
    AdversarialSummary,
    MissingEvidenceSummary,
    RoundConfig,
    StrongestArgument,
    UnresolvedIssueDetail,
)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
你是一名中立的法律分析员，专注于对对抗性辩论进行结构化分析。
You are a neutral legal analyst specializing in structured analysis of adversarial debates.

任务：基于三轮对抗辩论的完整记录，提取最强论证、识别未闭合争点原因、分析缺证情况，并给出整体态势评估。
Task: Based on the complete three-round adversarial debate record, extract the strongest arguments,
identify reasons for unresolved issues, analyze missing evidence, and provide an overall assessment.

输出要求 / Output requirements:
- 严格输出 JSON，不输出任何解释文字或 markdown 代码块
- Strictly output JSON only — no explanatory text or markdown code blocks
- 所有 issue_id 必须来自已知争点列表
- All issue_ids must come from the known issue list
- 所有 evidence_ids 必须非空，引用实际证据 ID
- All evidence_ids must be non-empty, referencing actual evidence IDs

## 证据质量加权 / Evidence Quality Weighting
- 多源佐证（>=2条独立证据印证）的论点权重更高
- 孤证（单方录音、单一记录、仅一方陈述）应降权评估，在分析中注明「孤证」
- 双方引用同一证据但解读相反时，关注证据的原始性和直接性
- 当事方自认的薄弱点（own_weaknesses / own-weakness- 前缀的 risk_flags）应在态势评估中重点考量

JSON schema（严格遵守 / strictly follow）:
{
  "plaintiff_strongest_arguments": [
    {
      "issue_id": "（对应争点 ID）",
      "position": "（原告最强论点，必须引用具体证据 ID，不超过 300 字）",
      "evidence_ids": ["（证据 ID 列表，非空）"],
      "reasoning": "（为什么这是最强论点，不超过 200 字）"
    }
  ],
  "defendant_strongest_defenses": [
    {
      "issue_id": "（对应争点 ID）",
      "position": "（被告最强抗辩，必须引用具体证据 ID，不超过 300 字）",
      "evidence_ids": ["（证据 ID 列表，非空）"],
      "reasoning": "（为什么这是最强抗辩，不超过 200 字）"
    }
  ],
  "unresolved_issues": [
    {
      "issue_id": "（争点 ID）",
      "issue_title": "（争点标题）",
      "why_unresolved": "（未闭合原因，不超过 150 字）"
    }
  ],
  "missing_evidence_report": [
    {
      "issue_id": "（争点 ID）",
      "missing_for_party_id": "（缺证方 party_id）",
      "gap_description": "（缺少什么证据，不超过 150 字）"
    }
  ],
  "overall_assessment": "（整体态势评估，不超过 300 字）"
}
"""

# ---------------------------------------------------------------------------
# Summarizer
# ---------------------------------------------------------------------------


class AdversarialSummarizer:
    """三轮对抗 LLM 语义分析总结器。
    LLM-powered semantic summarizer for three-round adversarial debate.

    Args:
        llm_client: 符合 LLMClient 协议的客户端实例 / LLMClient-compatible client
        config:     轮次配置（复用 RoundConfig 的 model/temperature/max_retries）
    """

    def __init__(self, llm_client: LLMClient, config: RoundConfig) -> None:
        self._llm = llm_client
        self._config = config

    async def summarize(
        self,
        result: AdversarialResult,
        issue_tree: IssueTree,
    ) -> AdversarialSummary:
        """分析三轮对抗结果，输出结构化总结。
        Analyze three-round adversarial result and produce structured summary.

        Args:
            result:     完整对抗结果（含所有轮次输出）
            issue_tree: 案件争点树（用于提供争点标题和上下文）

        Returns:
            AdversarialSummary 结构化总结

        Raises:
            RuntimeError: LLM 调用失败超过最大重试次数
        """
        user_prompt = self._build_user_prompt(result, issue_tree)
        raw = await self._call_llm_with_retry(_SYSTEM_PROMPT, user_prompt)
        data = _extract_json_object(raw)
        return self._parse_summary(data)

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    @staticmethod
    def _build_user_prompt(result: AdversarialResult, issue_tree: IssueTree) -> str:
        """构建用户提示词，包含辩论全貌上下文。
        Build user prompt containing full debate context.
        """
        lines: list[str] = []

        # 案件基本信息
        lines.append(f"【案件 ID】{result.case_id}")
        lines.append("")

        # 争点列表
        lines.append("【争点列表】")
        for issue in issue_tree.issues:
            lines.append(f"  [{issue.issue_id}] {issue.title} ({issue.issue_type.value})")
        lines.append("")

        # 三轮辩论记录
        lines.append("【三轮辩论记录】")
        for round_state in result.rounds:
            lines.append(f"--- 第 {round_state.round_number} 轮 ({round_state.phase.value}) ---")
            for output in round_state.outputs:
                lines.append(
                    f"  [{output.output_id}] {output.agent_role_code} (round {output.round_index}):"
                )
                lines.append(f"  标题: {output.title}")
                lines.append(f"  正文: {output.body[:600]}")
                lines.append(f"  引用证据: {', '.join(output.evidence_citations)}")
                lines.append("")

        # 已检测的证据冲突
        if result.evidence_conflicts:
            lines.append("【已检测证据冲突】")
            for conflict in result.evidence_conflicts:
                lines.append(f"  争点 {conflict.issue_id}: {conflict.conflict_description}")
            lines.append("")

        # 已检测的未决争点（规则层，供参考）
        if result.unresolved_issues:
            lines.append("【已检测未决争点 ID（供参考）】")
            lines.append(f"  {', '.join(result.unresolved_issues)}")
            lines.append("")

        # 已检测的缺证情况（规则层，供参考）
        if result.missing_evidence_report:
            lines.append("【已检测缺证情况（供参考）】")
            for item in result.missing_evidence_report:
                lines.append(
                    f"  争点 {item.issue_id} - {item.missing_for_party_id}: {item.description}"
                )
            lines.append("")

        lines.append("请基于以上信息，严格按照 JSON schema 输出结构化总结。")
        lines.append("Output the structured summary strictly following the JSON schema.")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # LLM call with retry
    # ------------------------------------------------------------------

    async def _call_llm_with_retry(self, system: str, user: str) -> str:
        """调用 LLM，失败时重试最多 max_retries 次。
        Call LLM, retry up to max_retries times on failure.

        Raises:
            RuntimeError: 超过最大重试次数 / Max retries exceeded
        """
        from engines.shared.llm_utils import call_llm_with_retry

        return await call_llm_with_retry(
            self._llm,
            system=system,
            user=user,
            model=self._config.model,
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens_per_output,
            max_retries=self._config.max_retries,
        )

    # ------------------------------------------------------------------
    # Parse LLM output
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_summary(data: dict) -> AdversarialSummary:
        """将 LLM JSON 输出解析为 AdversarialSummary。
        Parse LLM JSON output dict to AdversarialSummary.
        """

        def _to_dict(item: object) -> dict:
            """Normalize LLM output element: if it's a string, wrap it."""
            return item if isinstance(item, dict) else {"issue_id": str(item)}

        plaintiff_args = [
            StrongestArgument(
                issue_id=a.get("issue_id", "unknown"),
                position=a.get("position") or "（未提供）",
                evidence_ids=a.get("evidence_ids") or ["unknown-evidence"],
                reasoning=a.get("reasoning") or "（未提供）",
            )
            for a in [_to_dict(x) for x in data.get("plaintiff_strongest_arguments", [])]
        ]

        defendant_defenses = [
            StrongestArgument(
                issue_id=d.get("issue_id", "unknown"),
                position=d.get("position") or "（未提供）",
                evidence_ids=d.get("evidence_ids") or ["unknown-evidence"],
                reasoning=d.get("reasoning") or "（未提供）",
            )
            for d in [_to_dict(x) for x in data.get("defendant_strongest_defenses", [])]
        ]

        unresolved = [
            UnresolvedIssueDetail(
                issue_id=u.get("issue_id", "unknown"),
                issue_title=u.get("issue_title") or u.get("issue_id", "unknown"),
                why_unresolved=u.get("why_unresolved") or "（原因未说明）",
            )
            for u in [_to_dict(x) for x in data.get("unresolved_issues", [])]
        ]

        missing_ev = [
            MissingEvidenceSummary(
                issue_id=m.get("issue_id", "unknown"),
                missing_for_party_id=m.get("missing_for_party_id", "unknown"),
                gap_description=m.get("gap_description", ""),
            )
            for m in [_to_dict(x) for x in data.get("missing_evidence_report", [])]
        ]

        overall = data.get("overall_assessment", "")
        if isinstance(overall, dict):
            # LLM returned a structured object instead of plain string — flatten it
            parts = []
            for k, v in overall.items():
                parts.append(f"{k}: {v}")
            overall = "；".join(parts)

        return AdversarialSummary(
            plaintiff_strongest_arguments=plaintiff_args,
            defendant_strongest_defenses=defendant_defenses,
            unresolved_issues=unresolved,
            missing_evidence_report=missing_ev,
            overall_assessment=overall if overall else "对抗分析完成，详见各字段。",
        )
