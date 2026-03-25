"""
交互追问响应器核心模块
Interactive followup responder core module.

接收报告 + 用户问题，生成带 citation 的追问回答，支持多轮对话。
Receives report + user question, generates cited answers, supports multi-turn conversation.

合约保证 / Contract guarantees:
- evidence_ids ⊆ 报告已引用证据 / evidence_ids ⊆ report-cited evidence
- issue_ids 不为空 / issue_ids non-empty
- 100% statement_class 覆盖 / 100% statement_class coverage
- 多轮上下文一致性（history 传入 LLM）/ Multi-turn context consistency
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from engines.shared.json_utils import _extract_json_object

from .schemas import (
    InteractionTurn,
    LLMFollowupOutput,
    ReportArtifact,
    StatementClass,
)


@runtime_checkable
class LLMClient(Protocol):
    """LLM 客户端协议 — 兼容 Anthropic 和 OpenAI SDK。
    LLM client protocol — compatible with Anthropic and OpenAI SDKs.
    """

    async def create_message(
        self,
        *,
        system: str,
        user: str,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.0,
        max_tokens: int = 8192,
        **kwargs: Any,
    ) -> str:
        """发送消息并返回文本响应。Send message and return text response."""
        ...


# ---------------------------------------------------------------------------
# statement_class 解析工具 / statement_class resolution utility
# ---------------------------------------------------------------------------


def _resolve_statement_class(raw: str) -> StatementClass:
    """将 LLM 返回的 statement_class 字符串解析为枚举值。
    Resolve raw statement_class string to enum value.
    Defaults to 'inference' for unknown values.
    """
    _MAP = {
        "fact": StatementClass.fact,
        "事实": StatementClass.fact,
        "inference": StatementClass.inference,
        "推理": StatementClass.inference,
        "assumption": StatementClass.assumption,
        "假设": StatementClass.assumption,
    }
    return _MAP.get(raw.strip().lower(), StatementClass.inference)


# ---------------------------------------------------------------------------
# 主引擎类 / Main engine class
# ---------------------------------------------------------------------------


class FollowupResponder:
    """交互追问响应器
    Interactive Followup Responder.

    输入报告 + 用户问题（+可选历史轮次），输出 InteractionTurn。
    Takes report + user question (+ optional history), outputs InteractionTurn.

    Args:
        llm_client: 符合 LLMClient 协议的客户端 / LLMClient-compatible client
        case_type: 案由类型，默认 "civil_loan" / Case type, default "civil_loan"
        model: LLM 模型名称 / LLM model name
        temperature: LLM 温度参数 / LLM temperature
        max_tokens: LLM 最大输出 token 数 / Max output tokens
        max_retries: LLM 调用失败时的最大重试次数 / Max retries on failure
    """

    def __init__(
        self,
        llm_client: LLMClient,
        case_type: str = "civil_loan",
        *,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        max_retries: int = 3,
    ) -> None:
        self._llm_client = llm_client
        self._case_type = case_type
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_retries = max_retries
        self._prompt_module = self._load_prompt_module(case_type)

    @staticmethod
    def _load_prompt_module(case_type: str):
        """加载案由对应的 prompt 模板模块。
        Load prompt template module for the given case type.
        """
        from .prompts import PROMPT_REGISTRY

        if case_type not in PROMPT_REGISTRY:
            available = ", ".join(PROMPT_REGISTRY.keys()) or "(none)"
            raise ValueError(
                f"不支持的案由类型 / Unsupported case type: '{case_type}'。"
                f"可用类型 / Available: {available}"
            )
        return PROMPT_REGISTRY[case_type]

    def _validate_input(
        self,
        report: ReportArtifact,
        question: str,
    ) -> None:
        """验证输入数据合法性。
        Validate input data validity.

        Raises:
            ValueError: question 为空，或 report 无章节。
        """
        if not question.strip():
            raise ValueError(
                "question 不能为空 / question cannot be empty"
            )
        if not report.sections:
            raise ValueError(
                "report.sections 不能为空 / report.sections cannot be empty"
            )

    def _collect_report_evidence_ids(self, report: ReportArtifact) -> set[str]:
        """收集报告中所有引用过的 evidence_id 集合。
        Collect all evidence IDs referenced in the report.
        """
        ids: set[str] = set()
        for sec in report.sections:
            ids.update(sec.linked_evidence_ids)
            for concl in sec.key_conclusions:
                ids.update(concl.supporting_evidence_ids)
        return ids

    def _collect_report_issue_ids(self, report: ReportArtifact) -> set[str]:
        """收集报告中所有关联的 issue_id 集合。
        Collect all issue IDs referenced in the report.
        """
        ids: set[str] = set()
        for sec in report.sections:
            ids.update(sec.linked_issue_ids)
        return ids

    async def respond(
        self,
        report: ReportArtifact,
        question: str,
        *,
        previous_turns: list[InteractionTurn] | None = None,
        turn_slug: str = "turn",
        run_id: str | None = None,
    ) -> InteractionTurn:
        """执行追问响应。
        Execute followup response.

        Args:
            report: 已生成的报告 / Generated report artifact
            question: 用户追问问题 / User question
            previous_turns: 之前的追问轮次（多轮对话上下文）/ Previous turns for context
            turn_slug: Turn ID 简称 / Turn slug for ID generation
            run_id: 运行 ID（可选，默认使用 report.run_id）/ Run ID (optional override)

        Returns:
            结构化 InteractionTurn / Structured InteractionTurn

        Raises:
            ValueError: 输入无效或 LLM 响应无法解析 / Invalid input or unparseable response
            RuntimeError: LLM 调用失败且超过最大重试次数 / LLM call failed after max retries
        """
        self._validate_input(report, question)

        previous_turns = previous_turns or []
        report_evidence_ids = self._collect_report_evidence_ids(report)
        report_issue_ids = self._collect_report_issue_ids(report)

        # 构建 prompt / Build prompt
        system_prompt = self._prompt_module.SYSTEM_PROMPT
        report_context_block = self._prompt_module.format_report_context(
            report.model_dump()
        )
        history_block = self._prompt_module.format_history_block(
            [t.model_dump() for t in previous_turns]
        )
        user_prompt = self._prompt_module.RESPONSE_PROMPT.format(
            case_id=report.case_id,
            report_id=report.report_id,
            report_context_block=report_context_block,
            history_block=history_block,
            question=question,
        )

        # 调用 LLM（带重试）/ Call LLM with retry
        raw_response = await self._call_llm_with_retry(system_prompt, user_prompt)

        # 解析 LLM 输出 / Parse LLM output
        raw_dict = _extract_json_object(raw_response)
        llm_output = LLMFollowupOutput.model_validate(raw_dict)

        # 构建 InteractionTurn / Build InteractionTurn
        effective_run_id = run_id or report.run_id
        return self._build_turn(
            llm_output,
            report,
            question,
            report_evidence_ids,
            report_issue_ids,
            turn_slug,
            len(previous_turns),
            effective_run_id,
        )

    async def _call_llm_with_retry(self, system: str, user: str) -> str:
        """调用 LLM 并在失败时重试。
        Call LLM with retry on failure.

        Raises:
            RuntimeError: 超过最大重试次数 / Max retries exceeded
        """
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = await self._llm_client.create_message(
                    system=system,
                    user=user,
                    model=self._model,
                    temperature=self._temperature,
                    max_tokens=self._max_tokens,
                )
                return response
            except Exception as e:
                last_error = e
                if attempt < self._max_retries:
                    continue
                break

        raise RuntimeError(
            f"LLM 调用失败，已重试 {self._max_retries} 次。"
            f"最后一次错误 / Last error: {last_error}"
        )

    def _build_turn(
        self,
        llm_output: LLMFollowupOutput,
        report: ReportArtifact,
        question: str,
        report_evidence_ids: set[str],
        report_issue_ids: set[str],
        turn_slug: str,
        turn_index: int,
        run_id: str,
    ) -> InteractionTurn:
        """将 LLM 输出规范化为 InteractionTurn。
        Normalize LLM output into an InteractionTurn.

        强制执行合约不变量 / Enforces contract invariants:
        - evidence_ids ⊆ 报告已引用证据（证据边界）
        - issue_ids 不为空（回退到报告顶层争点）
        - statement_class 有标注
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        # 使用 UUID 确保唯一性 / Use UUID for uniqueness
        unique_suffix = uuid.uuid4().hex[:8]
        one_based = turn_index + 1
        turn_id = f"turn-{turn_slug}-{one_based:02d}-{unique_suffix}"

        # ── 证据边界过滤 / Evidence boundary filtering ───────────────────────
        # 只允许报告已引用的证据 ID / Only allow evidence IDs from the report
        valid_evidence_ids = [
            eid for eid in llm_output.evidence_ids if eid in report_evidence_ids
        ]
        # 合并 citations 中的 evidence_id / Merge citation evidence IDs
        for citation in llm_output.citations:
            if citation.evidence_id in report_evidence_ids:
                if citation.evidence_id not in valid_evidence_ids:
                    valid_evidence_ids.append(citation.evidence_id)

        # ── 争点绑定保证 / Issue binding guarantee ───────────────────────────
        # 过滤只保留报告中存在的 issue_id / Filter to issue IDs present in report
        valid_issue_ids = [
            iid for iid in llm_output.issue_ids if iid in report_issue_ids
        ]
        # 合约保证：至少一个 issue_id / Contract: at least one issue_id
        if not valid_issue_ids:
            # 回退到报告关联的所有争点 / Fallback to all report-linked issues
            valid_issue_ids = sorted(report_issue_ids)[:1]

        # ── statement_class 解析 / Resolve statement_class ───────────────────
        statement_class = _resolve_statement_class(llm_output.statement_class)

        return InteractionTurn(
            turn_id=turn_id,
            case_id=report.case_id,
            report_id=report.report_id,
            run_id=run_id,
            turn_index=one_based,
            question=question,
            answer=llm_output.answer,
            issue_ids=valid_issue_ids,
            evidence_ids=valid_evidence_ids,
            statement_class=statement_class,
            created_at=now,
        )
