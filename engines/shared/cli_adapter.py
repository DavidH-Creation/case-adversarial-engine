"""
CLI Adapter — 通过 subprocess 调用 Claude CLI 和 Codex CLI 的 LLMClient 实现。
CLI Adapter — LLMClient implementations that call Claude CLI and Codex CLI via subprocess.

两个类都实现 LLMClient Protocol（engines/shared/models.py），可直接传给所有引擎组件。
Both classes implement the LLMClient Protocol and can be passed to any engine component.

用法 / Usage::

    from engines.shared.cli_adapter import ClaudeCLIClient, CodexCLIClient

    claude = ClaudeCLIClient()
    codex  = CodexCLIClient()

    text = await claude.create_message(system="你是律师", user="分析这份借条")
    text = await codex.create_message(system="你是律师", user="分析这份借条")
"""

from __future__ import annotations

import asyncio
import shutil
from typing import Any


class CLINotFoundError(RuntimeError):
    """目标 CLI 工具不在 PATH 中 / Target CLI binary not found in PATH."""


class CLICallError(RuntimeError):
    """CLI 进程以非零状态退出 / CLI process exited with non-zero status.

    Attributes:
        returncode: 进程退出码
        stderr:     stderr 文本（截断至 1000 字符）
    """

    def __init__(self, tool: str, returncode: int, stderr: str) -> None:
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(
            f"{tool} CLI 调用失败 (exit {returncode}): {stderr[:1000]}"
        )


# ---------------------------------------------------------------------------
# ClaudeCLIClient
# ---------------------------------------------------------------------------


class ClaudeCLIClient:
    """通过 `claude` CLI 实现 LLMClient Protocol。
    LLMClient implementation using the `claude` CLI subprocess.

    CLI 调用格式 / CLI invocation::

        claude --print --bare --system-prompt "{system}" --model "{model}" "{user}"

    `--bare` 跳过 hooks / LSP / auto-memory，适合程序化调用。
    `--bare` skips hooks/LSP/auto-memory — suited for programmatic calls.

    Args:
        timeout:  每次调用的最长等待秒数 / Max seconds to wait per call (default 120)
        cli_bin:  CLI 可执行文件名，默认 "claude" / CLI binary name (default "claude")
    """

    def __init__(self, timeout: float = 120.0, cli_bin: str = "claude") -> None:
        self._timeout = timeout
        self._cli_bin = cli_bin

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
        if not shutil.which(self._cli_bin):
            raise CLINotFoundError(
                f"找不到 `{self._cli_bin}` 命令。请确认 Claude Code CLI 已安装并在 PATH 中。"
                f" / `{self._cli_bin}` not found. Ensure Claude Code CLI is installed and in PATH."
            )

        cmd = [
            self._cli_bin,
            "--print",
            "--bare",
            "--model", model,
        ]
        if system:
            cmd += ["--system-prompt", system]

        # 把 user 作为最后一个位置参数（避免 stdin 编码问题）
        # Pass user as trailing positional arg to avoid stdin encoding edge cases
        cmd.append(user)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise asyncio.TimeoutError(
                f"claude CLI 调用超时（>{self._timeout}s）"
                f" / claude CLI timed out (>{self._timeout}s)"
            )

        if proc.returncode != 0:
            raise CLICallError("claude", proc.returncode, stderr.decode(errors="replace"))

        return stdout.decode(errors="replace").strip()


# ---------------------------------------------------------------------------
# CodexCLIClient
# ---------------------------------------------------------------------------


class CodexCLIClient:
    """通过 `codex exec` CLI 实现 LLMClient Protocol。
    LLMClient implementation using the `codex exec` CLI subprocess.

    Codex CLI 没有 system prompt flag，system 内容被前置到 prompt 中。
    Codex CLI has no system-prompt flag — system content is prepended to the prompt.

    CLI 调用格式 / CLI invocation::

        codex exec "[SYSTEM]\\n{system}\\n[/SYSTEM]\\n\\n{user}"

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
        if not shutil.which(self._cli_bin):
            raise CLINotFoundError(
                f"找不到 `{self._cli_bin}` 命令。请确认 Codex CLI 已安装并在 PATH 中。"
                f" / `{self._cli_bin}` not found. Ensure Codex CLI is installed and in PATH."
            )

        # Codex 不支持独立 system prompt flag，将 system 嵌入 prompt 头部
        # Codex has no separate system-prompt flag; embed system at the top
        effective_model = self._default_model or model
        if system:
            full_prompt = f"[SYSTEM]\n{system}\n[/SYSTEM]\n\n{user}"
        else:
            full_prompt = user

        cmd = [self._cli_bin, "exec"]
        if effective_model:
            cmd += ["-m", effective_model]
        cmd.append(full_prompt)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise asyncio.TimeoutError(
                f"codex CLI 调用超时（>{self._timeout}s）"
                f" / codex CLI timed out (>{self._timeout}s)"
            )

        if proc.returncode != 0:
            raise CLICallError("codex", proc.returncode, stderr.decode(errors="replace"))

        return stdout.decode(errors="replace").strip()
