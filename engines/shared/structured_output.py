"""
结构化输出工具 — 使用 tool_use 强制 LLM 输出符合预定义 JSON schema。
Structured output utilities — uses tool_use to enforce schema-compliant JSON output.

主路径（AnthropicSDKClient）：通过 tool_use API，LLM 被强制返回符合 input_schema 的 JSON，
彻底消除 json_utils 截断恢复、引号修复等不稳定的后处理逻辑。
Primary path (AnthropicSDKClient): tool_use API forces schema-compliant JSON output,
eliminating unstable post-processing (truncation recovery, quote repair) in json_utils.

Fallback 路径（ClaudeCLIClient / MockLLMClient / CodexCLIClient）：
tools 参数通过 **kwargs 透传给 create_message，但被忽略；LLM 返回自由格式文本，
由 json_utils._extract_json_object 解析，保持向后兼容。
Fallback path (others): tools param is ignored, free-form text parsed by _extract_json_object,
maintaining backward compatibility — tests using MockLLMClient continue to pass unchanged.

用法 / Usage::

    from engines.shared.structured_output import call_structured_llm

    data = await call_structured_llm(
        llm_client,
        system="你是律师",
        user="分析这份借条",
        model="claude-sonnet-4-6",
        tool_name="extract_issues",
        tool_description="从诉请和抗辩中提取争点",
        tool_schema=LLMExtractionOutput.model_json_schema(),
        max_tokens=8192,
    )
    output = LLMExtractionOutput.model_validate(data)
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engines.shared.models import LLMClient

from engines.shared.json_utils import _extract_json_object
from engines.shared.llm_utils import call_llm_with_retry
from engines.shared.logging_config import LLMCallRecord, get_token_tracker

logger = logging.getLogger(__name__)


async def call_structured_llm(
    llm: "LLMClient",
    *,
    system: str,
    user: str,
    model: str,
    tool_name: str,
    tool_description: str,
    tool_schema: dict,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    max_retries: int = 3,
) -> dict:
    """
    调用 LLM 并返回符合 tool_schema 的结构化 dict。
    Call LLM and return a structured dict conforming to tool_schema.

    主路径（AnthropicSDKClient）：
      - 传入 tools + tool_choice 给 create_message
      - AnthropicSDKClient 使用 Claude API 的 tool_use 模式
      - 返回 json.dumps(block.input)（保证符合 input_schema）
      - _extract_json_object 解析该 JSON 字符串为 dict

    Primary path (AnthropicSDKClient):
      - Passes tools + tool_choice to create_message
      - AnthropicSDKClient uses Claude API's tool_use mode
      - Returns json.dumps(block.input) — guaranteed to conform to input_schema
      - _extract_json_object parses the JSON string into a dict

    Fallback 路径（ClaudeCLIClient、MockLLMClient 等）：
      - tools/tool_choice 参数通过 **kwargs 传给 create_message，被忽略
      - LLM 返回自由格式文本
      - _extract_json_object 用三阶段提取+修复逻辑解析 JSON

    Fallback path (ClaudeCLIClient, MockLLMClient, etc.):
      - tools/tool_choice forwarded via **kwargs, silently ignored
      - LLM returns free-form text
      - _extract_json_object uses 3-stage extraction + repair to parse JSON

    Args:
        llm:              LLMClient 实例 / LLMClient instance
        system:           系统提示词 / System prompt
        user:             用户消息 / User message
        model:            LLM 模型名称 / Model name
        tool_name:        tool 名称（≤64 字符，仅含 [a-zA-Z0-9_-]）/ Tool name
        tool_description: tool 描述，帮助 LLM 理解输出用途 / Tool description
        tool_schema:      JSON Schema dict（顶层必须为 type:object）/ JSON Schema dict
        temperature:      生成温度（默认 0.0）/ Temperature (default 0.0)
        max_tokens:       最大输出 token 数（默认 4096）/ Max tokens (default 4096)
        max_retries:      失败时最大重试次数（默认 3）/ Max retries (default 3)

    Returns:
        解析后的 dict，对应 LLM 输出的 JSON 对象。
        Parsed dict corresponding to the LLM's JSON output.

    Raises:
        RuntimeError: 所有重试均失败 / All retry attempts failed.
        ValueError:   响应无法解析为 JSON 对象 / Response cannot be parsed as JSON object.
    """
    tools: list[dict[str, Any]] = [
        {
            "name": tool_name,
            "description": tool_description,
            "input_schema": tool_schema,
        }
    ]
    tool_choice: dict[str, Any] = {"type": "tool", "name": tool_name}

    t0 = time.monotonic()
    success = True
    error_msg: str | None = None
    try:
        raw = await call_llm_with_retry(
            llm,
            system=system,
            user=user,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=max_retries,
            tools=tools,
            tool_choice=tool_choice,
        )
    except Exception as exc:
        success = False
        error_msg = f"{type(exc).__name__}: {str(exc)[:200]}"
        raise
    finally:
        latency_ms = (time.monotonic() - t0) * 1000
        usage = getattr(llm, "_last_usage", None)
        rec = LLMCallRecord(
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            module=tool_name,
            model=model,
            input_tokens=usage.get("input_tokens") if usage else None,
            output_tokens=usage.get("output_tokens") if usage else None,
            latency_ms=round(latency_ms, 1),
            success=success,
            error=error_msg,
        )
        get_token_tracker().record(rec)
        logger.info(
            "LLM call: %s model=%s tokens=%s/%s latency=%.0fms success=%s",
            tool_name,
            model,
            rec.input_tokens,
            rec.output_tokens,
            latency_ms,
            success,
            extra={"llm_call": rec},
        )

    return _extract_json_object(raw)
