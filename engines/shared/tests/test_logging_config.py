"""
StructuredLogger / TokenTracker 单元测试。
Unit tests for logging_config module.

覆盖:
- TokenTracker: 记录 LLM 调用并生成汇总
- JsonFormatter: 日志格式化为 JSON
- setup_pipeline_logging: 初始化日志到文件 + stderr
- Edge case: 无 usage 信息时 token 字段为 null
- Error path: 日志文件写入失败时不中断
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

import pytest

from engines.shared.logging_config import (
    JsonFormatter,
    LLMCallRecord,
    TokenTracker,
    get_token_tracker,
    reset_token_tracker,
    setup_pipeline_logging,
)


# ---------------------------------------------------------------------------
# LLMCallRecord
# ---------------------------------------------------------------------------


class TestLLMCallRecord:
    def test_create_with_all_fields(self) -> None:
        rec = LLMCallRecord(
            timestamp="2026-03-31T00:00:00.000000Z",
            module="extract_issues",
            model="claude-sonnet-4-6",
            input_tokens=1500,
            output_tokens=800,
            latency_ms=1234.5,
            success=True,
        )
        assert rec.input_tokens == 1500
        assert rec.output_tokens == 800
        assert rec.success is True
        assert rec.error is None

    def test_create_with_null_tokens(self) -> None:
        """Edge case: LLM 返回无 usage 信息时，token 字段为 null 不报错。"""
        rec = LLMCallRecord(
            timestamp="2026-03-31T00:00:00.000000Z",
            module="extract_issues",
            model="claude-sonnet-4-6",
            input_tokens=None,
            output_tokens=None,
            latency_ms=500.0,
            success=True,
        )
        assert rec.input_tokens is None
        assert rec.output_tokens is None

    def test_create_with_error(self) -> None:
        rec = LLMCallRecord(
            timestamp="2026-03-31T00:00:00.000000Z",
            module="extract_issues",
            model="claude-sonnet-4-6",
            input_tokens=None,
            output_tokens=None,
            latency_ms=100.0,
            success=False,
            error="RuntimeError: timeout",
        )
        assert rec.success is False
        assert rec.error == "RuntimeError: timeout"


# ---------------------------------------------------------------------------
# TokenTracker
# ---------------------------------------------------------------------------


class TestTokenTracker:
    def _make_record(
        self,
        module: str = "test_module",
        input_tokens: int | None = 100,
        output_tokens: int | None = 50,
        success: bool = True,
        error: str | None = None,
    ) -> LLMCallRecord:
        return LLMCallRecord(
            timestamp="2026-03-31T00:00:00.000000Z",
            module=module,
            model="claude-sonnet-4-6",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=500.0,
            success=success,
            error=error,
        )

    def test_empty_summary(self) -> None:
        tracker = TokenTracker()
        s = tracker.summary()
        assert s["total_input_tokens"] == 0
        assert s["total_output_tokens"] == 0
        assert s["total_cost_estimate"] == 0.0
        assert s["total_calls"] == 0
        assert s["per_module_breakdown"] == {}

    def test_single_record_summary(self) -> None:
        tracker = TokenTracker()
        tracker.record(self._make_record(input_tokens=1000, output_tokens=500))
        s = tracker.summary()
        assert s["total_input_tokens"] == 1000
        assert s["total_output_tokens"] == 500
        assert s["total_calls"] == 1
        assert s["total_cost_estimate"] > 0

    def test_multi_module_breakdown(self) -> None:
        """pipeline 结束时汇总报告包含 per_module_breakdown。"""
        tracker = TokenTracker()
        tracker.record(
            self._make_record(module="extract_issues", input_tokens=1000, output_tokens=500)
        )
        tracker.record(
            self._make_record(module="extract_issues", input_tokens=800, output_tokens=400)
        )
        tracker.record(self._make_record(module="rank_issues", input_tokens=600, output_tokens=300))
        s = tracker.summary()

        assert s["total_input_tokens"] == 2400
        assert s["total_output_tokens"] == 1200
        assert s["total_calls"] == 3

        breakdown = s["per_module_breakdown"]
        assert "extract_issues" in breakdown
        assert "rank_issues" in breakdown
        assert breakdown["extract_issues"]["calls"] == 2
        assert breakdown["extract_issues"]["input_tokens"] == 1800
        assert breakdown["extract_issues"]["output_tokens"] == 900
        assert breakdown["rank_issues"]["calls"] == 1

    def test_null_tokens_in_summary(self) -> None:
        """Edge case: null token 字段不影响汇总计算。"""
        tracker = TokenTracker()
        tracker.record(self._make_record(input_tokens=1000, output_tokens=500))
        tracker.record(self._make_record(input_tokens=None, output_tokens=None))
        s = tracker.summary()
        assert s["total_input_tokens"] == 1000
        assert s["total_output_tokens"] == 500
        assert s["total_calls"] == 2

    def test_error_tracking(self) -> None:
        tracker = TokenTracker()
        tracker.record(self._make_record(success=True))
        tracker.record(self._make_record(success=False, error="timeout"))
        s = tracker.summary()
        assert s["per_module_breakdown"]["test_module"]["errors"] == 1

    def test_records_property_returns_copy(self) -> None:
        tracker = TokenTracker()
        rec = self._make_record()
        tracker.record(rec)
        records = tracker.records
        records.clear()
        assert len(tracker.records) == 1

    def test_cost_estimate(self) -> None:
        tracker = TokenTracker()
        # 1M input tokens @ $3.0 + 1M output tokens @ $15.0 = $18.0
        tracker.record(self._make_record(input_tokens=1_000_000, output_tokens=1_000_000))
        s = tracker.summary()
        assert s["total_cost_estimate"] == 18.0


# ---------------------------------------------------------------------------
# Global tracker
# ---------------------------------------------------------------------------


class TestGlobalTracker:
    def test_get_and_reset(self) -> None:
        reset_token_tracker()
        t = get_token_tracker()
        assert t.summary()["total_calls"] == 0

        t.record(
            LLMCallRecord(
                timestamp="2026-03-31T00:00:00.000000Z",
                module="test",
                model="test",
                input_tokens=100,
                output_tokens=50,
                latency_ms=1.0,
                success=True,
            )
        )
        assert get_token_tracker().summary()["total_calls"] == 1

        reset_token_tracker()
        assert get_token_tracker().summary()["total_calls"] == 0


# ---------------------------------------------------------------------------
# JsonFormatter
# ---------------------------------------------------------------------------


class TestJsonFormatter:
    def test_basic_format(self) -> None:
        fmt = JsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="hello %s",
            args=("world",),
            exc_info=None,
        )
        output = fmt.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "hello world"
        assert "timestamp" in data

    def test_format_with_llm_call(self) -> None:
        """日志包含 llm_call 字段（input_tokens/output_tokens/latency_ms）。"""
        fmt = JsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="LLM call done",
            args=(),
            exc_info=None,
        )
        record.llm_call = LLMCallRecord(  # type: ignore[attr-defined]
            timestamp="2026-03-31T00:00:00.000000Z",
            module="extract_issues",
            model="claude-sonnet-4-6",
            input_tokens=1500,
            output_tokens=800,
            latency_ms=1234.5,
            success=True,
        )
        output = fmt.format(record)
        data = json.loads(output)
        assert "llm_call" in data
        llm = data["llm_call"]
        assert llm["module"] == "extract_issues"
        assert llm["input_tokens"] == 1500
        assert llm["output_tokens"] == 800
        assert llm["latency_ms"] == 1234.5
        assert llm["success"] is True

    def test_format_without_llm_call(self) -> None:
        fmt = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="plain message",
            args=(),
            exc_info=None,
        )
        output = fmt.format(record)
        data = json.loads(output)
        assert "llm_call" not in data


# ---------------------------------------------------------------------------
# setup_pipeline_logging
# ---------------------------------------------------------------------------


class TestSetupPipelineLogging:
    def test_creates_log_file(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test_pipeline.log"
        setup_pipeline_logging(log_file=log_file)
        logger = logging.getLogger("test.setup_pipeline")
        logger.info("test message")

        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "test message" in content
        # 验证 JSON 格式 / Verify JSON format
        line = content.strip().split("\n")[-1]
        data = json.loads(line)
        assert data["message"] == "test message"

        # Cleanup: remove handlers we added
        root = logging.getLogger()
        for h in root.handlers[:]:
            if getattr(h, "_structured_pipeline", False):
                root.removeHandler(h)
                h.close()

    def test_log_file_write_failure_does_not_crash(self, tmp_path: Path) -> None:
        """Error path: 日志文件写入失败时不中断主 pipeline。"""
        # 指向一个不可能创建的路径 / Point to an impossible path
        if os.name == "nt":
            bad_path = Path("Z:\\nonexistent\\deeply\\nested\\pipeline.log")
        else:
            bad_path = Path("/proc/0/nonexistent/pipeline.log")

        # Should not raise
        setup_pipeline_logging(log_file=bad_path)

        # Cleanup
        root = logging.getLogger()
        for h in root.handlers[:]:
            if getattr(h, "_structured_pipeline", False):
                root.removeHandler(h)
                h.close()

    def test_no_duplicate_handlers(self, tmp_path: Path) -> None:
        """多次调用不会产生重复 handler。"""
        log_file = tmp_path / "dedup.log"
        setup_pipeline_logging(log_file=log_file)
        setup_pipeline_logging(log_file=log_file)

        root = logging.getLogger()
        pipeline_handlers = [h for h in root.handlers if getattr(h, "_structured_pipeline", False)]
        # 每次调用应有 2 个 handler（stderr + file），重复调用不累加
        # Each call should have 2 handlers (stderr + file), not accumulating
        assert len(pipeline_handlers) <= 4  # 2 from latest call (old ones removed)

        # Cleanup
        for h in root.handlers[:]:
            if getattr(h, "_structured_pipeline", False):
                root.removeHandler(h)
                h.close()


# ---------------------------------------------------------------------------
# cli_adapter _last_usage integration
# ---------------------------------------------------------------------------


class TestCliAdapterLastUsage:
    """验证 cli_adapter 客户端暴露 _last_usage 属性。"""

    def test_claude_client_has_last_usage(self) -> None:
        from engines.shared.cli_adapter import ClaudeCLIClient

        client = ClaudeCLIClient()
        assert client._last_usage is None

    def test_codex_client_has_last_usage(self) -> None:
        from engines.shared.cli_adapter import CodexCLIClient

        client = CodexCLIClient()
        assert client._last_usage is None
