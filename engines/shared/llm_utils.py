"""
LLM 调用工具 — 统一的重试逻辑（指数退避 + jitter）。
LLM call utilities — centralized retry logic with exponential backoff and jitter.

语义约定 / Retry semantics:
  max_retries=3 → 1 次初始调用 + 最多 3 次重试 = 最多 4 次总调用
  max_retries=3 → 1 initial call + up to 3 retries = 4 total calls maximum

退避间隔 / Backoff schedule (before each retry):
  第 1 次重试: 1s + jitter
  第 2 次重试: 2s + jitter
  第 3 次重试: 4s + jitter

用法 / Usage::

    from engines.shared.llm_utils import call_llm_with_retry

    text = await call_llm_with_retry(
        llm_client,
        system="你是律师",
        user="分析这份借条",
        model="claude-sonnet-4-6",
        max_tokens=4096,
        max_retries=3,
    )
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engines.shared.models import LLMClient

logger = logging.getLogger(__name__)

# Module-level sleep callable — replaceable in tests to avoid real delays.
# In tests, monkeypatch: engines.shared.llm_utils._sleep = your_no_op_async
_sleep = asyncio.sleep


async def call_llm_with_retry(
    llm: "LLMClient",
    *,
    system: str,
    user: str,
    model: str,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    max_retries: int = 3,
    tools: "list[dict] | None" = None,
    tool_choice: "dict | None" = None,
    **kwargs: Any,
) -> str:
    """LLM 调用（带指数退避重试）。
    Call LLM with exponential backoff retry.

    仅在 LLM 网络/API 错误时重试；JSON 解析错误或验证错误由调用方处理。
    Retries only on LLM network/API exceptions; parse/validation errors are
    handled by the caller.

    Args:
        llm:         LLMClient 实例 / LLMClient instance.
        system:      系统提示词 / System prompt.
        user:        用户消息 / User message.
        model:       模型名称 / Model name.
        temperature: 生成温度 / Temperature (default 0.0).
        max_tokens:  最大输出 token 数 / Max output tokens (default 4096).
        max_retries: 失败后最大重试次数（默认 3）。max_retries=3 → 最多 4 次总调用。
                     Max retries after initial failure (default 3).
                     max_retries=3 → up to 4 total calls.
        tools:       tool_use 模式的 tool 定义列表（可选）。
                     AnthropicSDKClient 会使用 tool_use API；其他客户端通过 **kwargs
                     透传，由 create_message 自行决定是否处理。
                     Tool definitions for tool_use mode (optional).
                     AnthropicSDKClient uses tool_use API; other clients receive it
                     via **kwargs and may ignore it.
        tool_choice: tool_use 模式的 tool 选择策略（可选，配合 tools 使用）。
                     Tool selection strategy for tool_use mode (optional, used with tools).
        **kwargs:    透传给 create_message 的额外参数 / Extra kwargs forwarded.

    Returns:
        LLM 文本响应 / LLM text response.
        当 tools 被 AnthropicSDKClient 处理时，返回 json.dumps(block.input) 字符串。
        When tools are handled by AnthropicSDKClient, returns json.dumps(block.input).

    Raises:
        RuntimeError: 所有重试均失败 / All attempts failed.
    """
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        # 指数退避（仅重试时）/ Exponential backoff (only on retries)
        if attempt > 0:
            delay = float(2 ** (attempt - 1)) + random.random() * 0.5  # 1~1.5s, 2~2.5s, 4~4.5s
            logger.debug(
                "LLM retry %d/%d after %.2fs backoff",
                attempt, max_retries, delay,
            )
            await _sleep(delay)

        try:
            extra: dict[str, Any] = {}
            if tools is not None:
                extra["tools"] = tools
            if tool_choice is not None:
                extra["tool_choice"] = tool_choice
            return await llm.create_message(
                system=system,
                user=user,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **extra,
                **kwargs,
            )
        except Exception as e:  # noqa: BLE001
            last_error = e
            logger.warning(
                "LLM call failed (attempt %d/%d): %s: %s",
                attempt + 1,
                max_retries + 1,
                type(e).__name__,
                str(e)[:200],
            )

    raise RuntimeError(
        f"LLM 调用失败，已重试 {max_retries} 次。"
        f"最后错误 / Last error: {type(last_error).__name__}"
    )
