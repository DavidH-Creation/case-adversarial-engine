"""
CLI Adapter 单元测试 — 不需要真实 CLI 调用。
CLI Adapter unit tests — no real CLI calls required.

覆盖：
- ClaudeCLIClient / CodexCLIClient 满足 LLMClient Protocol（isinstance 检查）
- 成功调用路径（mock subprocess）
- 非零退出码 → CLICallError
- CLI 不在 PATH → CLINotFoundError
- 超时 → asyncio.TimeoutError
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from engines.shared.cli_adapter import (
    CLICallError,
    CLINotFoundError,
    ClaudeCLIClient,
    CodexCLIClient,
)
from engines.shared.models import LLMClient


# ---------------------------------------------------------------------------
# 协议合规 / Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    """两个 adapter 都必须满足 LLMClient Protocol（runtime_checkable）。"""

    def test_claude_client_satisfies_llm_client_protocol(self) -> None:
        client = ClaudeCLIClient()
        assert isinstance(client, LLMClient)

    def test_codex_client_satisfies_llm_client_protocol(self) -> None:
        client = CodexCLIClient()
        assert isinstance(client, LLMClient)

    def test_claude_client_has_create_message(self) -> None:
        client = ClaudeCLIClient()
        assert callable(getattr(client, "create_message", None))

    def test_codex_client_has_create_message(self) -> None:
        client = CodexCLIClient()
        assert callable(getattr(client, "create_message", None))


# ---------------------------------------------------------------------------
# ClaudeCLIClient 测试
# ---------------------------------------------------------------------------


class TestClaudeCLIClient:
    """ClaudeCLIClient 单元测试。"""

    @pytest.fixture
    def client(self) -> ClaudeCLIClient:
        return ClaudeCLIClient(timeout=10.0)

    # ── 成功路径 / Success path ─────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_returns_stdout_on_success(self, client: ClaudeCLIClient) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(
            return_value=(b"  JSON response here  \n", b"")
        )

        with patch("shutil.which", return_value="/usr/bin/claude"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await client.create_message(
                system="你是律师",
                user="分析借条",
                model="claude-sonnet-4-6",
            )

        assert result == "JSON response here"

    @pytest.mark.asyncio
    async def test_builds_command_with_system_prompt(self, client: ClaudeCLIClient) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"ok", b""))

        with patch("shutil.which", return_value="/usr/bin/claude"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            await client.create_message(
                system="system text",
                user="user text",
                model="claude-opus-4-6",
            )

        call_args = mock_exec.call_args[0]  # positional args are the command tokens
        cmd = list(call_args)
        assert "claude" in cmd[0]
        assert "--print" in cmd
        assert "--output-format" in cmd
        assert "text" in cmd
        assert "--system-prompt" in cmd
        assert "system text" in cmd
        assert "--model" in cmd
        assert "claude-opus-4-6" in cmd
        # user prompt is sent via stdin, not in the command line
        assert "user text" not in cmd
        mock_proc.communicate.assert_called_once_with(input=b"user text")

    @pytest.mark.asyncio
    async def test_skips_system_prompt_flag_when_empty(self, client: ClaudeCLIClient) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"ok", b""))

        with patch("shutil.which", return_value="/usr/bin/claude"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            await client.create_message(system="", user="hello")

        cmd = list(mock_exec.call_args[0])
        assert "--system-prompt" not in cmd

    # ── 错误路径 / Error paths ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_raises_cli_not_found_when_binary_missing(self, client: ClaudeCLIClient) -> None:
        with patch("shutil.which", return_value=None):
            with pytest.raises(CLINotFoundError):
                await client.create_message(system="s", user="u")

    @pytest.mark.asyncio
    async def test_raises_cli_call_error_on_nonzero_exit(self, client: ClaudeCLIClient) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"fatal error"))

        with patch("shutil.which", return_value="/usr/bin/claude"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(CLICallError) as exc_info:
                await client.create_message(system="s", user="u")

        assert exc_info.value.returncode == 1
        assert "fatal error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_timeout_error_when_process_hangs(self, client: ClaudeCLIClient) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = None
        mock_proc.kill = MagicMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)

        def _wait_for_timeout(coro, *args, **kwargs):
            # Close the coroutine so the GC never sees an unawaited coroutine.
            if hasattr(coro, "close"):
                coro.close()
            raise asyncio.TimeoutError()

        with patch("shutil.which", return_value="/usr/bin/claude"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
             patch("asyncio.wait_for", side_effect=_wait_for_timeout):
            with pytest.raises(asyncio.TimeoutError):
                await client.create_message(system="s", user="u")

    # ── 配置 / Configuration ─────────────────────────────────────────────

    def test_default_timeout_is_120(self) -> None:
        client = ClaudeCLIClient()
        assert client._timeout == 120.0

    def test_custom_timeout(self) -> None:
        client = ClaudeCLIClient(timeout=30.0)
        assert client._timeout == 30.0

    def test_custom_cli_bin(self) -> None:
        client = ClaudeCLIClient(cli_bin="claude-dev")
        assert client._cli_bin == "claude-dev"


# ---------------------------------------------------------------------------
# CodexCLIClient 测试
# ---------------------------------------------------------------------------


class TestCodexCLIClient:
    """CodexCLIClient 单元测试。"""

    @pytest.fixture
    def client(self) -> CodexCLIClient:
        return CodexCLIClient(timeout=10.0)

    # ── 成功路径 / Success path ─────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_returns_stdout_on_success(self, client: CodexCLIClient) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"  codex response  \n", b""))

        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await client.create_message(
                system="法律助手",
                user="分析案件",
                model="o3",
            )

        assert result == "codex response"

    @pytest.mark.asyncio
    async def test_embeds_system_in_prompt(self, client: CodexCLIClient) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"ok", b""))

        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            await client.create_message(
                system="my system",
                user="my user",
                model="o3",
            )

        # prompt is sent via stdin, not in the command line
        stdin_bytes = mock_proc.communicate.call_args.kwargs["input"]
        full_prompt = stdin_bytes.decode("utf-8")
        assert "[SYSTEM]" in full_prompt
        assert "my system" in full_prompt
        assert "[/SYSTEM]" in full_prompt
        assert "my user" in full_prompt

    @pytest.mark.asyncio
    async def test_uses_exec_subcommand(self, client: CodexCLIClient) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"ok", b""))

        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            await client.create_message(system="s", user="u", model="o3")

        cmd = list(mock_exec.call_args[0])
        assert "codex" in cmd[0]
        assert "exec" in cmd

    @pytest.mark.asyncio
    async def test_passes_model_flag(self, client: CodexCLIClient) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"ok", b""))

        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            await client.create_message(system="s", user="u", model="gpt-5")

        cmd = list(mock_exec.call_args[0])
        assert "-m" in cmd
        assert "gpt-5" in cmd

    @pytest.mark.asyncio
    async def test_empty_system_skips_system_wrapper(self, client: CodexCLIClient) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"ok", b""))

        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            await client.create_message(system="", user="hello world")

        # prompt is sent via stdin, not in the command line
        stdin_bytes = mock_proc.communicate.call_args.kwargs["input"]
        full_prompt = stdin_bytes.decode("utf-8")
        assert "[SYSTEM]" not in full_prompt
        assert full_prompt == "hello world"

    # ── 错误路径 / Error paths ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_raises_cli_not_found_when_binary_missing(self, client: CodexCLIClient) -> None:
        with patch("shutil.which", return_value=None):
            with pytest.raises(CLINotFoundError):
                await client.create_message(system="s", user="u")

    @pytest.mark.asyncio
    async def test_raises_cli_call_error_on_nonzero_exit(self, client: CodexCLIClient) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = 2
        mock_proc.communicate = AsyncMock(return_value=(b"", b"codex error msg"))

        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(CLICallError) as exc_info:
                await client.create_message(system="s", user="u")

        assert exc_info.value.returncode == 2
        assert "codex error msg" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_timeout_error_when_process_hangs(self, client: CodexCLIClient) -> None:
        mock_proc = MagicMock()
        mock_proc.kill = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        def _wait_for_timeout(coro, *args, **kwargs):
            # Close the coroutine so the GC never sees an unawaited coroutine.
            if hasattr(coro, "close"):
                coro.close()
            raise asyncio.TimeoutError()

        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
             patch("asyncio.wait_for", side_effect=_wait_for_timeout):
            with pytest.raises(asyncio.TimeoutError):
                await client.create_message(system="s", user="u")

    def test_default_model_override(self) -> None:
        client = CodexCLIClient(model="gpt-5.4")
        assert client._default_model == "gpt-5.4"

    def test_default_model_none_uses_create_message_model(self) -> None:
        client = CodexCLIClient()
        assert client._default_model is None

    def test_custom_cli_bin(self) -> None:
        client = CodexCLIClient(cli_bin="codex-dev")
        assert client._cli_bin == "codex-dev"


# ---------------------------------------------------------------------------
# CLICallError 内容测试
# ---------------------------------------------------------------------------


class TestCLICallError:
    def test_attributes(self) -> None:
        err = CLICallError("claude", 1, "something went wrong")
        assert err.returncode == 1
        assert err.stderr == "something went wrong"
        assert "claude" in str(err)
        assert "exit 1" in str(err)

    def test_stderr_truncated_in_message(self) -> None:
        long_stderr = "x" * 2000
        err = CLICallError("codex", 1, long_stderr)
        assert len(str(err)) < 1500  # message is truncated at 1000 chars of stderr
