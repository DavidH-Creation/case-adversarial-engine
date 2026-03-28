"""
庭前会议追问扩展 — 薄包装层。
Pretrial conference followup — thin wrapper over FollowupResponder.

将质证记录 + 法官追问注入现有 FollowupResponder 的上下文，
不修改 v1 的 responder.py。
"""

from __future__ import annotations

from engines.interactive_followup.responder import FollowupResponder
from engines.shared.models import (
    InteractionTurn,
    IssueTree,
    LLMClient,
    ReportArtifact,
)

from .minutes_generator import MinutesGenerator
from .schemas import PretrialConferenceResult


class PretrialFollowup:
    """庭前会议追问扩展。

    将 PretrialConferenceResult 转换为 ReportArtifact，
    然后委托给 FollowupResponder 处理追问。

    Args:
        llm_client:  LLM 客户端
        model:       LLM 模型
        temperature: LLM 温度
        max_retries: 最大重试次数
    """

    def __init__(
        self,
        llm_client: LLMClient,
        *,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.0,
        max_retries: int = 3,
    ) -> None:
        self._responder = FollowupResponder(
            llm_client,
            model=model,
            temperature=temperature,
            max_retries=max_retries,
        )
        self._minutes_gen = MinutesGenerator()

    async def respond(
        self,
        conference_result: PretrialConferenceResult,
        issue_tree: IssueTree,
        question: str,
        *,
        previous_turns: list[InteractionTurn] | None = None,
    ) -> InteractionTurn:
        """基于庭前会议结果回答追问。

        Args:
            conference_result: 庭前会议结果
            issue_tree:        争点树
            question:          用户追问
            previous_turns:    之前的追问轮次

        Returns:
            InteractionTurn
        """
        report = self._minutes_gen.generate(
            result=conference_result,
            issue_tree=issue_tree,
        )
        return await self._responder.respond(
            report=report,
            question=question,
            previous_turns=previous_turns,
        )
