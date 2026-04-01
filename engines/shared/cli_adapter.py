"""
CLI Adapter — 通过 subprocess 调用 Claude CLI 和 Codex CLI 的 LLMClient 实现。
CLI Adapter — LLMClient implementations that call Claude CLI and Codex CLI via subprocess.

三个类都实现 LLMClient Protocol（engines/shared/models.py），可直接传给所有引擎组件。
All three classes implement the LLMClient Protocol and can be passed to any engine component.

用法 / Usage::

    from engines.shared.cli_adapter import ClaudeCLIClient, CodexCLIClient, AnthropicSDKClient

    claude = ClaudeCLIClient()        # Claude CLI subprocess（向后兼容）
    codex  = CodexCLIClient()         # Codex CLI subprocess
    sdk    = AnthropicSDKClient()     # Anthropic Python SDK（支持 tool_use 结构化输出）

    text = await claude.create_message(system="你是律师", user="分析这份借条")
    text = await codex.create_message(system="你是律师", user="分析这份借条")
    text = await sdk.create_message(system="你是律师", user="分析这份借条")

    # tool_use 结构化输出 / Structured output via tool_use:
    json_str = await sdk.create_message(
        system="你是律师", user="分析这份借条",
        tools=[{"name": "t", "description": "...", "input_schema": {...}}],
        tool_choice={"type": "tool", "name": "t"},
    )  # 返回 json.dumps(block.input) / returns json.dumps(block.input)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import sys
from typing import Any

_sdk_logger = logging.getLogger(__name__)


class CLINotFoundError(RuntimeError):
    """目标 CLI 工具不在 PATH 中 / Target CLI binary not found in PATH."""


class CLICallError(RuntimeError):
    """CLI 进程以非零状态退出 / CLI process exited with non-zero status.

    Attributes:
        returncode: 进程退出码
        stderr:     清洗后的 stderr 摘要（已移除 token、路径等敏感信息）
    """

    def __init__(self, tool: str, returncode: int, stderr: str) -> None:
        self.returncode = returncode
        self.stderr = stderr
        sanitized = _sanitize_stderr(stderr)
        super().__init__(f"{tool} CLI 调用失败 (exit {returncode}): {sanitized}")


# ---------------------------------------------------------------------------
# stderr 清洗工具 / stderr sanitization utility
# ---------------------------------------------------------------------------

# 触发整行脱敏的关键词（不区分大小写）
_SENSITIVE_KEYWORDS = frozenset(
    {
        "token",
        "key",
        "bearer",
        "authorization",
        "credential",
        "password",
        "secret",
        "apikey",
        "api_key",
        "auth",
    }
)

# 文件系统路径正则（Windows 和 Unix）
_WIN_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s,;\"'<>]+")
_UNIX_PATH_RE = re.compile(r"(?<!\w)/(?:home|usr|var|tmp|etc|opt|root|Users)[^\s,;\"'<>]*")


def _sanitize_stderr(raw: str) -> str:
    """清洗 stderr 文本，移除可能的 token、路径等敏感信息。
    Sanitize stderr text by removing potentially sensitive tokens and paths.

    策略 / Strategy:
    - 包含敏感关键词的行整行替换为 [REDACTED]
    - 绝对路径替换为 [PATH]
    - 截断至 500 字符（清洗后）
    """
    lines = raw.splitlines()
    cleaned: list[str] = []
    for line in lines:
        if any(kw in line.lower() for kw in _SENSITIVE_KEYWORDS):
            cleaned.append("[REDACTED]")
        else:
            line = _WIN_PATH_RE.sub("[PATH]", line)
            line = _UNIX_PATH_RE.sub("[PATH]", line)
            cleaned.append(line)
    return "\n".join(cleaned)[:500]


# ---------------------------------------------------------------------------
# ClaudeCLIClient
# ---------------------------------------------------------------------------


class ClaudeCLIClient:
    """通过 `claude` CLI 实现 LLMClient Protocol。
    LLMClient implementation using the `claude` CLI subprocess.

    CLI 调用格式 / CLI invocation::

        claude --print --output-format text --system-prompt "{system}" --model "{model}" "{user}"

    Args:
        timeout:  每次调用的最长等待秒数 / Max seconds to wait per call (default 120)
        cli_bin:  CLI 可执行文件名，默认 "claude" / CLI binary name (default "claude")
    """

    def __init__(self, timeout: float = 120.0, cli_bin: str = "claude") -> None:
        self._timeout = timeout
        self._cli_bin = cli_bin
        self._last_usage: dict[str, int] | None = None

    async def create_message(
        self,
        *,
        system: str,
        user: str,
        model: str = "claude-sonnet-4-6",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        """调用 claude CLI 并返回文本响应。
        Invoke claude CLI and return the text response.

        Raises:
            CLINotFoundError: claude 不在 PATH 中
            CLICallError:     进程以非零状态退出
            asyncio.TimeoutError: 超过 timeout 秒
        """
        resolved_bin = shutil.which(self._cli_bin)
        if not resolved_bin:
            raise CLINotFoundError(
                f"找不到 `{self._cli_bin}` 命令。请确认 Claude Code CLI 已安装并在 PATH 中。"
                f" / `{self._cli_bin}` not found. Ensure Claude Code CLI is installed and in PATH."
            )

        self._last_usage = None
        stdout, stderr, rc = await self._invoke(resolved_bin, system=system, user=user, model=model)
        if rc == 0:
            return stdout.decode(errors="replace").strip()

        stderr_text = stderr.decode(errors="replace")
        raise CLICallError("claude", rc, stderr_text)

    async def _invoke(
        self,
        resolved_bin: str,
        *,
        system: str,
        user: str,
        model: str,
    ) -> tuple[bytes, bytes, int]:
        """执行一次 claude CLI 调用，返回 (stdout, stderr, returncode)。
        Execute a single claude CLI invocation, returning (stdout, stderr, returncode).
        """
        cmd: list[str] = [resolved_bin, "--print", "--output-format", "text"]
        cmd += ["--model", model]
        if system:
            cmd += ["--system-prompt", system]

        # Windows 上 .cmd/.bat 文件需要通过 cmd /c 执行
        # Windows .cmd/.bat files require cmd /c to execute
        if sys.platform == "win32" and resolved_bin.lower().endswith((".cmd", ".bat")):
            cmd = ["cmd", "/c"] + cmd

        # 通过 stdin 传 user prompt 以避免 Windows cmd.exe 8191 字符行长限制
        # Pass user via stdin to avoid Windows cmd.exe 8191-char command-line limit
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=user.encode("utf-8")), timeout=self._timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise asyncio.TimeoutError(
                f"claude CLI 调用超时（>{self._timeout}s）"
                f" / claude CLI timed out (>{self._timeout}s)"
            )

        return stdout, stderr, proc.returncode or 0


# ---------------------------------------------------------------------------
# CodexCLIClient
# ---------------------------------------------------------------------------


class CodexCLIClient:
    """通过 `codex exec` CLI 实现 LLMClient Protocol。
    LLMClient implementation using the `codex exec` CLI subprocess.

    Codex CLI 没有 system prompt flag，system 内容被前置到 prompt 中。
    Codex CLI has no system-prompt flag — system content is prepended to the prompt.

    CLI 调用格式 / CLI invocation::

        codex exec -m {model}   # prompt via stdin to avoid Windows 8191-char limit
        stdin: "[SYSTEM]\\n{system}\\n[/SYSTEM]\\n\\n{user}"

    Args:
        timeout:  每次调用的最长等待秒数 / Max seconds per call (default 120)
        cli_bin:  CLI 可执行文件名，默认 "codex" / CLI binary name (default "codex")
        model:    传递给 codex 的模型名（via -m flag）/ Model passed via -m flag
    """

    def __init__(
        self,
        timeout: float = 120.0,
        cli_bin: str = "codex",
        model: str | None = None,
    ) -> None:
        self._timeout = timeout
        self._cli_bin = cli_bin
        self._default_model = model
        self._last_usage: dict[str, int] | None = None

    async def create_message(
        self,
        *,
        system: str,
        user: str,
        model: str = "o3",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        """调用 codex exec 并返回文本响应。
        Invoke codex exec and return the text response.

        system 与 user 合并为单一 prompt 传入。
        system and user are merged into a single prompt.

        Raises:
            CLINotFoundError: codex 不在 PATH 中
            CLICallError:     进程以非零状态退出
            asyncio.TimeoutError: 超过 timeout 秒
        """
        self._last_usage = None
        resolved_codex = shutil.which(self._cli_bin)
        if not resolved_codex:
            raise CLINotFoundError(
                f"找不到 `{self._cli_bin}` 命令。请确认 Codex CLI 已安装并在 PATH 中。"
                f" / `{self._cli_bin}` not found. Ensure Codex CLI is installed and in PATH."
            )

        # Codex 不支持独立 system prompt flag，将 system 嵌入 prompt 头部
        # Codex has no separate system-prompt flag; embed system at the top
        # 忽略 Claude 系列模型名——Codex CLI 用 OpenAI provider，不认识 claude-* 模型
        # Ignore Claude model names — Codex CLI uses OpenAI provider, not Anthropic
        _requested = self._default_model or model
        effective_model = None if (_requested and _requested.startswith("claude-")) else _requested
        if system:
            full_prompt = f"[SYSTEM]\n{system}\n[/SYSTEM]\n\n{user}"
        else:
            full_prompt = user

        cmd = [resolved_codex, "exec"]
        if effective_model:
            cmd += ["-m", effective_model]

        # Windows 上 .cmd/.bat 文件需要通过 cmd /c 执行
        if sys.platform == "win32" and resolved_codex.lower().endswith((".cmd", ".bat")):
            cmd = ["cmd", "/c"] + cmd

        # 通过 stdin 传 prompt 以避免 Windows cmd.exe 8191 字符行长限制
        # Pass prompt via stdin to avoid Windows cmd.exe 8191-char command-line limit
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=full_prompt.encode("utf-8")), timeout=self._timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise asyncio.TimeoutError(
                f"codex CLI 调用超时（>{self._timeout}s） / codex CLI timed out (>{self._timeout}s)"
            )

        if proc.returncode != 0:
            raise CLICallError("codex", proc.returncode, stderr.decode(errors="replace"))

        return stdout.decode(errors="replace").strip()


# ---------------------------------------------------------------------------
# AnthropicSDKClient
# ---------------------------------------------------------------------------


class AnthropicSDKClient:
    """通过 Anthropic Python SDK 直接调用 Claude API 的 LLMClient 实现。
    LLMClient implementation using the Anthropic Python SDK directly.

    相比 ClaudeCLIClient，优势在于支持 tool_use（结构化输出）：
    When create_message receives a ``tools`` kwarg, it uses the Claude API's
    tool_use mode and returns ``json.dumps(block.input)`` — a JSON string
    guaranteed to conform to the tool's ``input_schema``.  This is consumed
    by ``_extract_json_object`` in the normal pipeline, requiring zero changes
    to the downstream parsing/validation logic.

    当 ``tools`` 未传入时，行为与 ClaudeCLIClient 等价，返回普通文本响应。
    Without ``tools``, behaviour is equivalent to ClaudeCLIClient — plain text.

    Args:
        api_key:  Anthropic API key（None 则读取 ANTHROPIC_API_KEY 环境变量）
                  None reads from ANTHROPIC_API_KEY env var.
        timeout:  每次调用最长等待秒数 / Max seconds per call (default 120)
    """

    # 标记位：evidence_indexer 等需要数组输出的引擎通过此属性判断是否走 tool_use 路径
    # Marker flag: engines that need array output (e.g. evidence_indexer) use this to
    # decide whether to take the tool_use path or the _extract_json_array fallback path.
    _supports_structured_output: bool = True

    def __init__(self, api_key: str | None = None, timeout: float = 120.0) -> None:
        try:
            from anthropic import AsyncAnthropic  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "anthropic 库未安装。请运行: pip install 'anthropic>=0.39.0'\n"
                "anthropic package not installed. Run: pip install 'anthropic>=0.39.0'"
            ) from exc
        self._client = AsyncAnthropic(api_key=api_key, timeout=timeout)
        self._last_usage: dict[str, int] | None = None

    async def create_message(
        self,
        *,
        system: str,
        user: str,
        model: str = "claude-sonnet-4-6",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        tools: list[dict] | None = None,
        tool_choice: dict | None = None,
        **kwargs: Any,
    ) -> str:
        """调用 Anthropic Claude API 并返回文本响应。
        Call Anthropic Claude API and return a text response.

        tool_use 模式 / tool_use mode:
          当 ``tools`` 非 None 时，传入 tool_use 参数并强制使用指定 tool。
          返回 ``json.dumps(block.input)``（符合 input_schema 的 JSON 字符串）。
          When ``tools`` is not None, passes tool_use params and forces the
          specified tool.  Returns ``json.dumps(block.input)`` — a JSON string
          conforming to ``input_schema``.

        Raises:
            anthropic.APIError: API 调用失败（由 call_llm_with_retry 捕获并重试）
                                 API call failed (caught and retried by call_llm_with_retry).
        """
        params: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": user}],
        }
        if system:
            params["system"] = system
        # Claude API 仅在 temperature>0 时接受该参数；0 则使用默认值
        # Claude API only accepts temperature when > 0; use default otherwise
        if temperature > 0.0:
            params["temperature"] = temperature
        if tools is not None:
            params["tools"] = tools
        if tool_choice is not None:
            params["tool_choice"] = tool_choice

        self._last_usage = None
        response = await self._client.messages.create(**params)

        # 提取 token 用量 / Extract token usage from response
        usage = getattr(response, "usage", None)
        if usage is not None:
            self._last_usage = {
                "input_tokens": getattr(usage, "input_tokens", 0),
                "output_tokens": getattr(usage, "output_tokens", 0),
            }

        # tool_use 模式：提取 tool_use block 并序列化 input 为 JSON 字符串
        # tool_use mode: extract the tool_use block and serialize input as JSON
        if tools is not None:
            for block in response.content:
                if block.type == "tool_use":
                    return json.dumps(block.input, ensure_ascii=False)
            # 理论上不会执行到这里（tool_choice 强制使用了指定 tool）
            # Should not reach here when tool_choice forces a specific tool
            _sdk_logger.warning(
                "AnthropicSDKClient: tools provided (%d) but no tool_use block in response "
                "(stop_reason=%s); falling back to text extraction",
                len(tools),
                getattr(response, "stop_reason", "unknown"),
            )

        # 普通文本模式：返回第一个 text block / Normal text mode: return first text block
        for block in response.content:
            if hasattr(block, "text"):
                return block.text  # type: ignore[return-value]
        return ""
