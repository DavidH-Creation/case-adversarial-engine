"""
BasePartyAgent — 共享 LLM 调用逻辑的基类。
BasePartyAgent — base class with shared LLM call logic.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from engines.shared.json_utils import _extract_json_object
from engines.shared.models import (
    AgentOutput,
    AgentRole,
    Evidence,
    IssueTree,
    LLMClient,
    ProcedurePhase,
    StatementClass,
)

from ..schemas import Argument, RoundConfig


class BasePartyAgent:
    """所有当事方代理的基类，封装 LLM 调用和重试逻辑。
    Base class for all party agents, encapsulating LLM call and retry logic.

    Args:
        llm_client:  符合 LLMClient 协议的客户端实例
        role:        代理角色（plaintiff_agent / defendant_agent）
        party_id:    本代理所属当事方 ID
        config:      轮次配置
    """

    def __init__(
        self,
        llm_client: LLMClient,
        role: AgentRole,
        party_id: str,
        config: RoundConfig,
    ) -> None:
        self._llm = llm_client
        self._role = role
        self._party_id = party_id
        self._config = config

    # ------------------------------------------------------------------
    # 子类需实现 / Subclasses must implement
    # ------------------------------------------------------------------

    def _build_system_prompt(self) -> str:  # pragma: no cover
        raise NotImplementedError

    def _build_claim_prompt(
        self,
        issue_tree: IssueTree,
        visible_evidence: list[Evidence],
        context_outputs: list[AgentOutput],
    ) -> str:  # pragma: no cover
        raise NotImplementedError

    def _build_rebuttal_prompt(
        self,
        issue_tree: IssueTree,
        visible_evidence: list[Evidence],
        context_outputs: list[AgentOutput],
        opponent_outputs: list[AgentOutput],
    ) -> str:  # pragma: no cover
        raise NotImplementedError

    # ------------------------------------------------------------------
    # 公共接口 / Public interface
    # ------------------------------------------------------------------

    async def generate_claim(
        self,
        issue_tree: IssueTree,
        visible_evidence: list[Evidence],
        context_outputs: list[AgentOutput],
        run_id: str,
        state_id: str,
        round_index: int,
    ) -> AgentOutput:
        """生成首轮主张。Generate round-1 claim."""
        user_prompt = self._build_claim_prompt(issue_tree, visible_evidence, context_outputs)
        return await self._call_and_parse(
            user_prompt=user_prompt,
            run_id=run_id,
            state_id=state_id,
            round_index=round_index,
            phase=ProcedurePhase.opening,
        )

    async def generate_rebuttal(
        self,
        issue_tree: IssueTree,
        visible_evidence: list[Evidence],
        context_outputs: list[AgentOutput],
        opponent_outputs: list[AgentOutput],
        run_id: str,
        state_id: str,
        round_index: int,
    ) -> AgentOutput:
        """生成反驳轮输出。Generate rebuttal round output."""
        user_prompt = self._build_rebuttal_prompt(
            issue_tree, visible_evidence, context_outputs, opponent_outputs
        )
        return await self._call_and_parse(
            user_prompt=user_prompt,
            run_id=run_id,
            state_id=state_id,
            round_index=round_index,
            phase=ProcedurePhase.rebuttal,
        )

    # ------------------------------------------------------------------
    # 内部工具 / Internal utilities
    # ------------------------------------------------------------------

    async def _call_and_parse(
        self,
        user_prompt: str,
        run_id: str,
        state_id: str,
        round_index: int,
        phase: ProcedurePhase,
    ) -> AgentOutput:
        """调用 LLM（带重试）并解析输出为 AgentOutput。
        Call LLM with retry and parse output to AgentOutput.
        """
        raw = await self._call_llm_with_retry(self._build_system_prompt(), user_prompt)
        data = _extract_json_object(raw)
        return self._parse_agent_output(data, run_id, state_id, round_index, phase)

    async def _call_llm_with_retry(self, system: str, user: str) -> str:
        """调用 LLM，失败时重试最多 max_retries 次。
        Call LLM, retry up to max_retries times on failure.
        """
        last_error: Exception | None = None
        for attempt in range(1, self._config.max_retries + 1):
            try:
                return await self._llm.create_message(
                    system=system,
                    user=user,
                    model=self._config.model,
                    temperature=self._config.temperature,
                    max_tokens=self._config.max_tokens_per_output,
                )
            except Exception as e:
                last_error = e
                if attempt < self._config.max_retries:
                    continue
                break
        raise RuntimeError(
            f"LLM 调用失败，已重试 {self._config.max_retries} 次。"
            f"最后错误: {last_error}"
        )

    def _parse_agent_output(
        self,
        data: dict[str, Any],
        run_id: str,
        state_id: str,
        round_index: int,
        phase: ProcedurePhase,
    ) -> AgentOutput:
        """将 LLM JSON 输出解析为 AgentOutput。
        Parse LLM JSON output dict to AgentOutput.

        期望的 JSON 结构：
        {
          "title": "...",
          "body": "...",
          "issue_ids": ["issue-001"],
          "evidence_citations": ["ev-001"],
          "risk_flags": [],
          "arguments": [
            {
              "issue_id": "...",
              "position": "...",
              "supporting_evidence_ids": ["ev-001"],
              "legal_basis": "..."
            }
          ]
        }
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 从 arguments 中聚合 issue_ids 和 evidence_citations
        arguments: list[dict] = data.get("arguments", [])
        issue_ids: list[str] = data.get("issue_ids", [])
        evidence_citations: list[str] = data.get("evidence_citations", [])

        # 若顶层未提供，从 arguments 聚合
        if not issue_ids:
            seen: set[str] = set()
            for arg in arguments:
                for iid in arg.get("issue_id", "").split(","):
                    iid = iid.strip()
                    if iid and iid not in seen:
                        issue_ids.append(iid)
                        seen.add(iid)

        if not evidence_citations:
            seen_ev: set[str] = set()
            for arg in arguments:
                for eid in arg.get("supporting_evidence_ids", []):
                    if eid and eid not in seen_ev:
                        evidence_citations.append(eid)
                        seen_ev.add(eid)

        # 最终保底：避免空列表导致 AgentOutput 校验失败
        if not issue_ids:
            issue_ids = ["unknown-issue"]
        if not evidence_citations:
            evidence_citations = ["unknown-evidence"]

        import uuid
        output_id = f"output-{self._role.value}-r{round_index}-{uuid.uuid4().hex[:8]}"

        return AgentOutput(
            output_id=output_id,
            case_id=data.get("case_id", "unknown"),
            run_id=run_id,
            state_id=state_id,
            phase=phase,
            round_index=round_index,
            agent_role_code=self._role.value,
            owner_party_id=self._party_id,
            issue_ids=issue_ids,
            title=data.get("title", f"{self._role.value} round {round_index}"),
            body=data.get("body", ""),
            evidence_citations=evidence_citations,
            statement_class=StatementClass.fact,
            risk_flags=data.get("risk_flags", []),
            created_at=now,
        )

    # ------------------------------------------------------------------
    # 共用格式化工具 / Shared formatting utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _format_issue_tree_summary(issue_tree: IssueTree) -> str:
        """将 IssueTree 格式化为 prompt 可读摘要。
        Format IssueTree as a prompt-readable summary.
        """
        lines = [f"案件争点列表 (case_id={issue_tree.case_id}):"]
        for issue in issue_tree.issues:
            lines.append(
                f"  - [{issue.issue_id}] {issue.title} ({issue.issue_type.value})"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_evidence_list(evidence: list[Evidence]) -> str:
        """将证据列表格式化为 prompt 可读摘要。
        Format evidence list as prompt-readable summary.
        """
        if not evidence:
            return "  （无可见证据）"
        lines = []
        for ev in evidence:
            lines.append(
                f"  - [{ev.evidence_id}] {ev.title}: {ev.summary}"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_prior_outputs(outputs: list[AgentOutput]) -> str:
        """将历史 AgentOutput 格式化为 prompt 上下文。
        Format prior AgentOutputs as prompt context.
        """
        if not outputs:
            return "  （无历史输出）"
        lines = []
        for out in outputs:
            lines.append(
                f"  [{out.output_id}] ({out.agent_role_code}, 第{out.round_index}轮): "
                f"{out.title}\n    {out.body[:300]}..."
            )
        return "\n".join(lines)

    @staticmethod
    def _json_output_schema() -> str:
        """返回 LLM 输出的 JSON schema 说明（防退化用）。
        Return JSON schema description for LLM output (anti-degeneration).
        """
        return """{
  "title": "（简短标题，不超过30字）",
  "body": "（完整论证文本，必须引用具体证据ID，不超过600字）",
  "issue_ids": ["争点ID列表，不能为空"],
  "evidence_citations": ["证据ID列表，不能为空，必须来自可见证据"],
  "risk_flags": ["可能的法律风险标记，可为空数组"],
  "arguments": [
    {
      "issue_id": "对应争点ID",
      "position": "论点陈述（引用具体证据ID）",
      "supporting_evidence_ids": ["证据ID，必须非空"],
      "legal_basis": "适用法律条款（可选）"
    }
  ]
}"""
